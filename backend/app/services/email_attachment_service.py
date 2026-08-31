"""Email attachment object materialization."""

import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate
from app.db.models import Object
from app.services.client_intake_constants import (
    ATTACHMENT_TEXT_SUFFIXES,
    MAX_EMAIL_ATTACHMENT_BYTES,
    MAX_EMAIL_ATTACHMENT_BYTES_PER_MESSAGE,
    MAX_EMAIL_ATTACHMENTS_PER_MESSAGE,
)
from app.services.correlation_constants import EDGE_TYPE_CONTAINS
from app.services.edge_dedup import has_equivalent_relation
from app.services.graph_service import GraphService
from app.services.pipeline_enqueue import enqueue_embed_object, enqueue_summarize_resource
from app.services.provenance import OBSERVED_STATE, SOURCE_ORIGIN
from app.services.representation_service import RepresentationService


def build_gmail_attachment_external_id(parent_external_id: str, attachment_id: str) -> str:
    return f"gmail:{parent_external_id}:att:{attachment_id}"


def build_yandex_attachment_external_id(parent_external_id: str, part_key: str) -> str:
    return f"yandex_mail:{parent_external_id}:att:{part_key}"


class EmailAttachmentService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id)

    def materialize_gmail_attachments(
        self,
        parent: Object,
        descriptors: list[dict[str, Any]],
        fetch_bytes: Callable[[dict[str, Any]], bytes | None],
    ) -> int:
        return self._materialize(
            parent=parent,
            provider="gmail",
            descriptors=descriptors[:MAX_EMAIL_ATTACHMENTS_PER_MESSAGE],
            fetch_bytes=fetch_bytes,
            external_id_builder=lambda desc: build_gmail_attachment_external_id(
                parent.external_id or "",
                str(desc["attachment_id"]),
            ),
        )

    def materialize_yandex_attachments(
        self,
        parent: Object,
        descriptors: list[dict[str, Any]],
        raw_parts: dict[str, bytes],
    ) -> int:
        def fetch_bytes(desc: dict[str, Any]) -> bytes | None:
            return raw_parts.get(str(desc["part_key"]))

        return self._materialize(
            parent=parent,
            provider="yandex_mail",
            descriptors=descriptors[:MAX_EMAIL_ATTACHMENTS_PER_MESSAGE],
            fetch_bytes=fetch_bytes,
            external_id_builder=lambda desc: build_yandex_attachment_external_id(
                parent.external_id or "",
                str(desc["part_key"]),
            ),
        )

    def _materialize(
        self,
        parent: Object,
        provider: str,
        descriptors: list[dict[str, Any]],
        fetch_bytes: Callable[[dict[str, Any]], bytes | None],
        external_id_builder: Callable[[dict[str, Any]], str],
    ) -> int:
        created = 0
        fetched_total = 0
        for desc in descriptors:
            external_id = external_id_builder(desc)
            filename = str(desc.get("filename") or "attachment")
            mime_type = desc.get("mime_type")
            size = desc.get("size")
            metadata: dict[str, Any] = {
                "parent_email_id": str(parent.id),
                "filename": filename,
                "mime_type": mime_type,
                "size": size,
                "provider_attachment_id": desc.get("attachment_id") or desc.get("part_key"),
                "content_id": desc.get("content_id"),
            }
            existing = self._session.scalar(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.provider == provider,
                    Object.external_id == external_id,
                )
            )
            if existing is None:
                obj = Object(
                    user_id=self._user_id,
                    kind="file",
                    title=filename,
                    origin="source",
                    state="observed",
                    provider=provider,
                    external_id=external_id,
                    metadata_=metadata,
                    occurred_at=parent.occurred_at,
                )
                self._session.add(obj)
                self._session.flush()
                created += 1
            else:
                obj = existing
                merged = dict(existing.metadata_ or {})
                merged.update(metadata)
                existing.metadata_ = merged

            self._link_contains(parent.id, obj.id)

            suffix = Path(filename).suffix.lower()
            if suffix not in ATTACHMENT_TEXT_SUFFIXES:
                enqueue_embed_object(self._session, obj.id, self._user_id)
                continue

            if fetched_total >= MAX_EMAIL_ATTACHMENT_BYTES_PER_MESSAGE:
                enqueue_embed_object(self._session, obj.id, self._user_id)
                continue

            data = fetch_bytes(desc)
            if data is None:
                enqueue_embed_object(self._session, obj.id, self._user_id)
                continue
            if len(data) > MAX_EMAIL_ATTACHMENT_BYTES:
                enqueue_embed_object(self._session, obj.id, self._user_id)
                continue
            fetched_total += len(data)

            revision = hashlib.sha256(data).hexdigest()
            metadata = dict(obj.metadata_ or {})
            metadata["content_revision"] = revision
            metadata["content_hash"] = revision
            obj.metadata_ = metadata

            reps = RepresentationService(self._session, self._user_id)
            if suffix == ".csv":
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".csv", delete=True
                ) as tmp:
                    tmp.write(data)
                    tmp.flush()
                    count = len(reps.ingest_file(obj.id, Path(tmp.name)))
            else:
                text = data.decode("utf-8", errors="replace")
                count = len(reps.ingest_text_content(obj.id, text))
            if count:
                enqueue_summarize_resource(self._session, obj.id, self._user_id, revision)
            else:
                enqueue_embed_object(self._session, obj.id, self._user_id)

        return created

    def _link_contains(self, email_id: UUID, attachment_id: UUID) -> None:
        if has_equivalent_relation(
            self._session, self._user_id, email_id, attachment_id, EDGE_TYPE_CONTAINS
        ):
            return
        self._graph.create_edge(
            EdgeCreate(
                source_id=email_id,
                target_id=attachment_id,
                type=EDGE_TYPE_CONTAINS,
                origin=SOURCE_ORIGIN,
                state=OBSERVED_STATE,
                metadata={"source_fact": "email_attachment"},
            )
        )
