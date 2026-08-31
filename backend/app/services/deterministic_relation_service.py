"""Deterministic source-normalized email/thread relations."""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate
from app.db.models import Edge, Object
from app.services.correlation_constants import (
    CORRELATION_VERSION,
    EDGE_TYPE_REFERENCES,
    EDGE_TYPE_RELATED_TO,
)
from app.services.edge_dedup import has_equivalent_relation
from app.services.graph_service import GraphService
from app.services.provenance import OBSERVED_STATE, SOURCE_ORIGIN


def _parse_message_ids(value: str | None) -> list[str]:
    if not value:
        return []
    tokens = re.findall(r"<[^>]+>", value)
    if tokens:
        return [token.strip("<>") for token in tokens]
    return [part.strip() for part in value.split() if part.strip()]


class DeterministicRelationService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id)

    def apply_source_relations(self, trigger_object_id: UUID) -> int:
        trigger = self._session.scalar(
            select(Object).where(
                Object.id == trigger_object_id,
                Object.user_id == self._user_id,
            )
        )
        if trigger is None or trigger.kind != "email":
            return 0

        created = 0
        metadata = trigger.metadata_ or {}
        provider = trigger.provider or ""

        if provider == "gmail":
            thread_id = metadata.get("thread_id")
            if thread_id:
                created += self._link_same_thread(trigger, "gmail", str(thread_id))

        message_id = metadata.get("message_id") or (metadata.get("headers") or {}).get(
            "message-id"
        )
        headers = metadata.get("headers") or {}
        reply_refs = _parse_message_ids(headers.get("in-reply-to"))
        reply_refs.extend(_parse_message_ids(headers.get("references")))
        if message_id:
            reply_refs.extend(_parse_message_ids(str(message_id)))

        for ref_id in reply_refs:
            normalized = ref_id.strip("<>")
            if not normalized:
                continue
            target = self._find_email_by_message_id(trigger, normalized)
            if target is None or target.id == trigger.id:
                continue
            if self._create_source_edge(
                trigger.id,
                target.id,
                EDGE_TYPE_REFERENCES,
                {"source_fact": "mail_reference", "referenced_message_id": normalized},
            ):
                created += 1

        return created

    def _link_same_thread(self, trigger: Object, provider: str, thread_id: str) -> int:
        peers = self._session.scalars(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.kind == "email",
                Object.provider == provider,
                Object.id != trigger.id,
                Object.state != "rejected",
            )
        ).all()
        created = 0
        for peer in peers:
            peer_meta = peer.metadata_ or {}
            if str(peer_meta.get("thread_id")) != thread_id:
                continue
            if self._create_source_edge(
                trigger.id,
                peer.id,
                EDGE_TYPE_RELATED_TO,
                {"source_fact": "same_thread", "thread_id": thread_id},
            ):
                created += 1
        return created

    def _find_email_by_message_id(self, trigger: Object, message_id: str) -> Object | None:
        candidates = self._session.scalars(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.kind == "email",
                Object.provider == trigger.provider,
                Object.id != trigger.id,
                Object.state != "rejected",
            )
        ).all()
        needle = message_id.lower()
        for obj in candidates:
            meta = obj.metadata_ or {}
            mid = meta.get("message_id") or (meta.get("headers") or {}).get("message-id")
            if mid and str(mid).strip("<>").lower() == needle:
                return obj
        return None

    def _create_source_edge(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: str,
        fact_meta: dict,
    ) -> bool:
        if has_equivalent_relation(
            self._session, self._user_id, source_id, target_id, relation_type
        ):
            return False
        meta = {
            "correlation_version": CORRELATION_VERSION,
            **fact_meta,
        }
        self._graph.create_edge(
            EdgeCreate(
                source_id=source_id,
                target_id=target_id,
                type=relation_type,
                origin=SOURCE_ORIGIN,
                state=OBSERVED_STATE,
                metadata=meta,
            )
        )
        return True
