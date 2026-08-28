import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ContextBuildResult, ContextItem
from app.db.models import Object, Representation
from app.llm.embedding_service import EmbeddingService
from app.services.graph_service import GraphService
from app.services.representation_service import (
    KIND_CHUNK,
    KIND_FULL,
    KIND_SAMPLE,
    KIND_SCHEMA,
    KIND_STATISTICS,
    KIND_SUMMARY,
    RepresentationService,
)
from app.services.search_service import SearchService

DEFAULT_MAX_CHARS = 8000
MAX_NEIGHBORS = 10
MAX_SEMANTIC_CANDIDATES = 10
MAX_CHUNKS = 8

STRUCTURAL_EDGE_TYPES = frozenset(
    {
        "parent_of",
        "child_of",
        "blocked_by",
        "blocks",
        "depends_on",
        "dependency_of",
        "part_of",
    }
)

EDGE_TYPE_PRIORITY = {
    "parent_of": 0,
    "child_of": 1,
    "blocked_by": 2,
    "blocks": 3,
    "depends_on": 4,
    "dependency_of": 5,
    "part_of": 6,
}

# Higher trim_order values are removed first when trimming the budget.
_TRIM_SEMANTIC = 400
_TRIM_NEIGHBOR = 300
_TRIM_CHUNK = 200
_TRIM_REPR_DETAIL = 100


@dataclass
class _Slot:
    item: ContextItem
    sort_key: tuple
    trim_order: int = 0
    protected: bool = False


class ContextService:
    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service
        self._graph = GraphService(session, embedding_service)
        self._search = SearchService(session, embedding_service)
        self._representations = RepresentationService(session, embedding_service)

    def build_context(
        self,
        object_id: UUID | None = None,
        query: str | None = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> ContextBuildResult:
        max_chars = max(1, max_chars)
        if object_id is None and query is None:
            return ContextBuildResult(items=[], total_chars=0, truncated=False)

        slots: list[_Slot] = []
        included_object_ids: set[UUID] = set()
        representation_object_ids: set[UUID] = set()

        if object_id is not None:
            target = self._graph.get_object(object_id)
            included_object_ids.add(target.id)
            slots.append(
                _Slot(
                    sort_key=(0, str(target.id), "", -1),
                    trim_order=0,
                    protected=True,
                    item=self._object_item(
                        target,
                        content=self._object_content(target),
                        why_included="target object",
                    ),
                )
            )

            neighbor_rows = self._graph.get_neighbors(object_id)
            neighbor_rows = sorted(
                neighbor_rows,
                key=lambda row: (
                    EDGE_TYPE_PRIORITY.get(row[1].type, 50),
                    row[1].type,
                    str(row[0].id),
                ),
            )[:MAX_NEIGHBORS]

            for neighbor, edge, _direction in neighbor_rows:
                included_object_ids.add(neighbor.id)
                representation_object_ids.add(neighbor.id)
                is_structural = edge.type in STRUCTURAL_EDGE_TYPES
                protected = is_structural or edge.origin == "source"
                trim_order = _TRIM_NEIGHBOR if not is_structural else 0
                slots.append(
                    _Slot(
                        sort_key=(1 if is_structural else 5, edge.type, str(neighbor.id), -1),
                        trim_order=trim_order,
                        protected=protected,
                        item=self._object_item(
                            neighbor,
                            content=self._neighbor_reference_content(neighbor),
                            relation_type=edge.type,
                            why_included=(
                                f"structural graph relation ({edge.type})"
                                if is_structural
                                else f"direct graph neighbor ({edge.type})"
                            ),
                        ),
                    )
                )

        semantic_objects: list[Object] = []
        if query:
            semantic_results = self._search.search(query=query, limit=MAX_SEMANTIC_CANDIDATES)
            for result in semantic_results:
                if result.id in included_object_ids:
                    continue
                obj = self._session.get(Object, result.id)
                if obj is None:
                    continue
                semantic_objects.append(obj)
                included_object_ids.add(obj.id)
                representation_object_ids.add(obj.id)
                slots.append(
                    _Slot(
                        sort_key=(6, str(obj.id), "", -1),
                        trim_order=_TRIM_SEMANTIC,
                        item=self._object_item(
                            obj,
                            content=self._neighbor_reference_content(obj),
                            why_included="semantic object match",
                        ),
                    )
                )

        for obj_id in sorted(representation_object_ids, key=str):
            reps = self._representations.list_for_object(obj_id)
            if not reps:
                continue
            obj = self._session.get(Object, obj_id)
            if obj is None:
                continue
            slots.extend(
                self._representation_slots(
                    obj=obj,
                    representations=reps,
                    query=query,
                )
            )

        slots.sort(key=lambda slot: slot.sort_key)
        trimmed_slots, truncated = self._trim_to_budget(slots, max_chars)
        trimmed_slots.sort(key=lambda slot: slot.sort_key)
        items = [slot.item for slot in trimmed_slots]
        total_chars = sum(_item_chars(item) for item in items)
        return ContextBuildResult(items=items, total_chars=total_chars, truncated=truncated)

    def _trim_to_budget(self, slots: list[_Slot], max_chars: int) -> tuple[list[_Slot], bool]:
        working = list(slots)
        truncated = False

        while _slots_chars(working) > max_chars:
            removable = [
                index
                for index, slot in enumerate(working)
                if not slot.protected and slot.trim_order > 0
            ]
            if not removable:
                break
            remove_index = max(
                removable,
                key=lambda index: (working[index].trim_order, index),
            )
            working.pop(remove_index)
            truncated = True

        return working, truncated

    def _representation_slots(
        self,
        obj: Object,
        representations: list[Representation],
        query: str | None,
    ) -> list[_Slot]:
        slots: list[_Slot] = []

        summary_rep = next((rep for rep in representations if rep.kind == KIND_SUMMARY), None)
        full_rep = next((rep for rep in representations if rep.kind == KIND_FULL), None)
        chunk_reps = [rep for rep in representations if rep.kind == KIND_CHUNK]

        if summary_rep is not None:
            slots.append(
                _Slot(
                    sort_key=(2, str(obj.id), KIND_SUMMARY, summary_rep.part_index or 0),
                    trim_order=_TRIM_REPR_DETAIL,
                    item=self._representation_item(
                        obj,
                        summary_rep,
                        why_included="document summary",
                    ),
                )
            )
        elif full_rep is not None and not chunk_reps:
            slots.append(
                _Slot(
                    sort_key=(2, str(obj.id), KIND_FULL, 0),
                    trim_order=_TRIM_REPR_DETAIL,
                    item=self._representation_item(
                        obj,
                        full_rep,
                        why_included="small resource full text",
                    ),
                )
            )

        for rep in representations:
            if rep.kind == KIND_SCHEMA:
                slots.append(
                    _Slot(
                        sort_key=(3, str(obj.id), KIND_SCHEMA, 0),
                        trim_order=_TRIM_REPR_DETAIL,
                        item=self._representation_item(
                            obj,
                            rep,
                            why_included="dataset schema",
                        ),
                    )
                )
            elif rep.kind == KIND_STATISTICS:
                slots.append(
                    _Slot(
                        sort_key=(4, str(obj.id), KIND_STATISTICS, 0),
                        trim_order=_TRIM_REPR_DETAIL,
                        item=self._representation_item(
                            obj,
                            rep,
                            why_included="dataset statistics",
                        ),
                    )
                )
            elif rep.kind == KIND_SAMPLE:
                slots.append(
                    _Slot(
                        sort_key=(5, str(obj.id), KIND_SAMPLE, 0),
                        trim_order=_TRIM_REPR_DETAIL,
                        item=self._representation_item(
                            obj,
                            rep,
                            why_included="dataset sample",
                        ),
                    )
                )

        if chunk_reps and query:
            ranked_chunks = self._rank_chunks(chunk_reps, query)
            for rank, chunk_rep in enumerate(ranked_chunks[:MAX_CHUNKS]):
                slots.append(
                    _Slot(
                        sort_key=(7, str(obj.id), KIND_CHUNK, rank),
                        trim_order=_TRIM_CHUNK,
                        item=self._representation_item(
                            obj,
                            chunk_rep,
                            why_included="relevant document chunk",
                        ),
                    )
                )

        return slots

    def _rank_chunks(self, chunk_reps: list[Representation], query: str) -> list[Representation]:
        embedded = [rep for rep in chunk_reps if rep.embedding is not None]
        if not embedded:
            return sorted(chunk_reps, key=lambda rep: (rep.part_index or 0, str(rep.id)))

        query_vector = self._embedding_service.embed(query)
        return sorted(
            embedded,
            key=lambda rep: (
                _cosine_distance(list(rep.embedding), query_vector),
                rep.part_index or 0,
                str(rep.id),
            ),
        )

    def _object_item(
        self,
        obj: Object,
        content: str,
        why_included: str,
        relation_type: str | None = None,
    ) -> ContextItem:
        return ContextItem(
            object_id=obj.id,
            kind=obj.kind,
            title=obj.title,
            content=content,
            relation_type=relation_type,
            why_included=why_included,
            canonical_uri=obj.canonical_uri,
        )

    def _representation_item(
        self,
        obj: Object,
        rep: Representation,
        why_included: str,
    ) -> ContextItem:
        return ContextItem(
            object_id=obj.id,
            kind=obj.kind,
            title=obj.title,
            content=rep.text or "",
            representation_kind=rep.kind,
            why_included=why_included,
            canonical_uri=obj.canonical_uri,
        )

    def _object_content(self, obj: Object) -> str:
        reps = self._representations.list_for_object(obj.id)
        if any(rep.kind == KIND_CHUNK for rep in reps):
            parts = [obj.title]
            if obj.status:
                parts.append(f"status: {obj.status}")
            return "\n".join(parts)
        if obj.body:
            return f"{obj.title}\n{obj.body}"
        return obj.title

    def _neighbor_reference_content(self, obj: Object) -> str:
        if obj.canonical_uri:
            return f"reference: {obj.canonical_uri}"
        reps = self._representations.list_for_object(obj.id)
        if any(rep.kind in {KIND_CHUNK, KIND_SCHEMA} for rep in reps):
            return f"{obj.title} (resource with representations)"
        if obj.body and len(obj.body) <= 500:
            return f"{obj.title}\n{obj.body}"
        return obj.title


def _item_chars(item: ContextItem) -> int:
    return len(item.content) + len(item.title) + len(item.why_included)


def _slots_chars(slots: list[_Slot]) -> int:
    return sum(_item_chars(slot.item) for slot in slots)


def _cosine_distance(left: list[float], right: list[float]) -> float:
    dot = sum(l * r for l, r in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 1.0
    return 1.0 - dot / (left_norm * right_norm)
