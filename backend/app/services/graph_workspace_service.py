"""Bounded read-only graph workspace for Flutter Graph UI."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.api.schemas import EdgeOut, ObjectOut
from app.db.models import Edge, Object
from app.domain.task_lifecycle import (
    TASK_STATUS_DELETED,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_OPEN,
)
from app.services.errors import NotFoundError
from app.services.graph_service import GraphService
from app.services.provenance import REJECTED_STATE

DEFAULT_SEED_LIMIT = 12
MAX_SEED_LIMIT = 24
DEFAULT_NEIGHBOR_LIMIT = 12
MAX_NEIGHBOR_LIMIT = 24
DEFAULT_NODE_LIMIT = 80
MAX_NODE_LIMIT = 120

ACTIVE_WORK_TASK_STATUSES = frozenset({None, TASK_STATUS_OPEN, TASK_STATUS_IN_PROGRESS})


@dataclass(frozen=True)
class GraphWorkspaceResult:
    root_id: UUID | None
    seed_ids: list[UUID]
    nodes: list[Object]
    edges: list[Edge]
    truncated: bool


class GraphWorkspaceService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id)

    def get_workspace(
        self,
        root_id: UUID | None = None,
        seed_limit: int = DEFAULT_SEED_LIMIT,
        neighbor_limit: int = DEFAULT_NEIGHBOR_LIMIT,
        node_limit: int = DEFAULT_NODE_LIMIT,
    ) -> GraphWorkspaceResult:
        seed_limit = min(max(1, seed_limit), MAX_SEED_LIMIT)
        neighbor_limit = min(max(1, neighbor_limit), MAX_NEIGHBOR_LIMIT)
        node_limit = min(max(1, node_limit), MAX_NODE_LIMIT)

        if root_id is not None:
            return self._rooted_workspace(root_id, neighbor_limit, node_limit)
        return self._overview_workspace(seed_limit, neighbor_limit, node_limit)

    def _rooted_workspace(
        self,
        root_id: UUID,
        neighbor_limit: int,
        node_limit: int,
    ) -> GraphWorkspaceResult:
        root = self._graph.get_object(root_id)
        truncated = False
        node_map: dict[UUID, Object] = {root.id: root}
        edge_map: dict[UUID, Edge] = {}

        neighbors, neighbor_truncated = self._bounded_neighbors(
            [root_id],
            neighbor_limit=neighbor_limit,
            node_limit=node_limit - 1,
            exclude_deleted_neighbors=True,
        )
        truncated = truncated or neighbor_truncated
        for neighbor, edge in neighbors:
            node_map[neighbor.id] = neighbor
            edge_map[edge.id] = edge

        if len(node_map) > node_limit:
            truncated = True
            keep_ids = {root_id}
            for neighbor, _ in neighbors:
                if len(keep_ids) >= node_limit:
                    break
                keep_ids.add(neighbor.id)
            node_map = {oid: node_map[oid] for oid in keep_ids if oid in node_map}
            edge_map = {
                eid: edge
                for eid, edge in edge_map.items()
                if edge.source_id in node_map and edge.target_id in node_map
            }

        return GraphWorkspaceResult(
            root_id=root_id,
            seed_ids=[],
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
            truncated=truncated,
        )

    def _overview_workspace(
        self,
        seed_limit: int,
        neighbor_limit: int,
        node_limit: int,
    ) -> GraphWorkspaceResult:
        truncated = False
        total_seeds = self._count_active_seed_tasks()
        seeds = self._fetch_active_seed_tasks(seed_limit)
        if total_seeds > len(seeds):
            truncated = True

        node_map: dict[UUID, Object] = {seed.id: seed for seed in seeds}
        edge_map: dict[UUID, Edge] = {}
        seed_ids = [seed.id for seed in seeds]

        if seeds and len(node_map) < node_limit:
            remaining = node_limit - len(node_map)
            neighbors, neighbor_truncated = self._bounded_neighbors(
                seed_ids,
                neighbor_limit=neighbor_limit,
                node_limit=remaining,
                exclude_deleted_neighbors=True,
            )
            truncated = truncated or neighbor_truncated
            for neighbor, edge in neighbors:
                if neighbor.id not in node_map and len(node_map) >= node_limit:
                    truncated = True
                    break
                node_map[neighbor.id] = neighbor
                edge_map[edge.id] = edge

        edge_map = {
            eid: edge
            for eid, edge in edge_map.items()
            if edge.source_id in node_map and edge.target_id in node_map
        }

        return GraphWorkspaceResult(
            root_id=None,
            seed_ids=seed_ids,
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
            truncated=truncated,
        )

    def _count_active_seed_tasks(self) -> int:
        return self._session.scalar(
            select(func.count())
            .select_from(Object)
            .where(*self._active_seed_task_filters())
        ) or 0

    def _fetch_active_seed_tasks(self, limit: int) -> list[Object]:
        stmt = (
            select(Object)
            .where(*self._active_seed_task_filters())
            .order_by(
                Object.due_at.asc().nulls_last(),
                Object.updated_at.desc(),
                Object.id.asc(),
            )
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def _active_seed_task_filters(self) -> list:
        return [
            Object.user_id == self._user_id,
            Object.kind == "task",
            Object.state == "confirmed",
            or_(
                Object.status.is_(None),
                Object.status.in_([TASK_STATUS_OPEN, TASK_STATUS_IN_PROGRESS]),
            ),
        ]

    def _bounded_neighbors(
        self,
        center_ids: list[UUID],
        neighbor_limit: int,
        node_limit: int,
        exclude_deleted_neighbors: bool,
    ) -> tuple[list[tuple[Object, Edge]], bool]:
        if not center_ids or node_limit <= 0:
            return [], False

        truncated = False
        results: list[tuple[Object, Edge]] = []
        seen_neighbor_ids: set[UUID] = set(center_ids)
        seen_edge_ids: set[UUID] = set()

        for center_id in center_ids:
            if len(results) >= node_limit:
                truncated = True
                break

            per_center_limit = min(neighbor_limit, node_limit - len(results))
            neighbor_rows, center_truncated = self._neighbors_for_center(
                center_id,
                limit=per_center_limit,
                exclude_deleted_neighbors=exclude_deleted_neighbors,
            )
            truncated = truncated or center_truncated
            for neighbor, edge in neighbor_rows:
                if edge.id in seen_edge_ids:
                    continue
                if neighbor.id in seen_neighbor_ids:
                    seen_edge_ids.add(edge.id)
                    results.append((neighbor, edge))
                    continue
                if len(results) >= node_limit:
                    truncated = True
                    break
                seen_neighbor_ids.add(neighbor.id)
                seen_edge_ids.add(edge.id)
                results.append((neighbor, edge))

        return results, truncated

    def _neighbors_for_center(
        self,
        center_id: UUID,
        limit: int,
        exclude_deleted_neighbors: bool,
    ) -> tuple[list[tuple[Object, Edge]], bool]:
        outgoing_filters = [
            Edge.user_id == self._user_id,
            Edge.source_id == center_id,
            Object.user_id == self._user_id,
            Edge.state != REJECTED_STATE,
            Object.state != REJECTED_STATE,
        ]
        incoming_filters = [
            Edge.user_id == self._user_id,
            Edge.target_id == center_id,
            Object.user_id == self._user_id,
            Edge.state != REJECTED_STATE,
            Object.state != REJECTED_STATE,
        ]
        if exclude_deleted_neighbors:
            outgoing_filters.append(
                or_(Object.status.is_(None), Object.status != TASK_STATUS_DELETED)
            )
            incoming_filters.append(
                or_(Object.status.is_(None), Object.status != TASK_STATUS_DELETED)
            )

        outgoing = (
            select(Edge.id, literal("outgoing").label("direction"))
            .select_from(Edge)
            .join(Object, Edge.target_id == Object.id)
            .where(*outgoing_filters)
        )
        incoming = (
            select(Edge.id, literal("incoming").label("direction"))
            .select_from(Edge)
            .join(Object, Edge.source_id == Object.id)
            .where(*incoming_filters)
        )

        total_available = self._session.scalar(
            select(func.count()).select_from(
                union_all(outgoing, incoming).subquery("neighbor_count")
            )
        ) or 0

        neighbor_edges = union_all(outgoing, incoming).subquery("neighbor_edges")
        edge_rows = self._session.execute(
            select(neighbor_edges.c.id)
            .order_by(neighbor_edges.c.id)
            .limit(limit)
        ).all()

        truncated = total_available > len(edge_rows)
        results: list[tuple[Object, Edge]] = []
        for (edge_id,) in edge_rows:
            edge = self._session.get(Edge, edge_id)
            if edge is None:
                continue
            if edge.state == REJECTED_STATE:
                continue
            if edge.source_id == center_id:
                neighbor = self._session.scalar(
                    select(Object).where(
                        Object.id == edge.target_id,
                        Object.user_id == self._user_id,
                    )
                )
            else:
                neighbor = self._session.scalar(
                    select(Object).where(
                        Object.id == edge.source_id,
                        Object.user_id == self._user_id,
                    )
                )
            if neighbor is None:
                continue
            if neighbor.state == REJECTED_STATE:
                continue
            if exclude_deleted_neighbors and neighbor.status == TASK_STATUS_DELETED:
                continue
            results.append((neighbor, edge))
        return results, truncated

    def to_response(self, result: GraphWorkspaceResult) -> dict:
        return {
            "root_id": str(result.root_id) if result.root_id is not None else None,
            "seed_ids": [str(seed_id) for seed_id in result.seed_ids],
            "nodes": [ObjectOut.from_model(node).model_dump(mode="json") for node in result.nodes],
            "edges": [EdgeOut.from_model(edge).model_dump(mode="json") for edge in result.edges],
            "truncated": result.truncated,
        }
