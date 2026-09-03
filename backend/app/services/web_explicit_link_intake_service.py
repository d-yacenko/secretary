"""Generic public web URL explicit intake via POST /intake/link."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content_extraction.constants import MAX_REPRESENTATION_PARTS
from app.content_extraction.mechanical_extractors import build_bounded_text_representations
from app.content_extraction.mechanical_persistence import MechanicalRepresentationPersistence
from app.content_extraction.metadata_keys import (
    CONTENT_EXTRACTION_STATUS,
    CONTENT_FORMAT,
    MECHANICAL_REPRESENTATION_COUNT,
    STATUS_METADATA_ONLY,
    STATUS_READY,
)
from app.db.models import Object
from app.resources.constants import PROVIDER_WEB
from app.resources.web_fetch import WebFetchError, WebFetchResult, fetch_web_page
from app.services.explicit_link_intake_errors import ExplicitLinkIntakeError
from app.services.explicit_link_intake_service import EXPLICIT_INTAKE_MODE, IntakeLinkResult
from app.services.pipeline_enqueue import enqueue_embed_object, enqueue_summarize_resource
from app.services.web_url_normalize import normalize_explicit_web_url

WEB_CONTENT_REVISION_PREFIX = "web:sha256:"


@dataclass(frozen=True)
class WebExplicitLinkIntakeService:
    session: Session
    user_id: UUID

    def intake_link(self, url: str, account_id: UUID | None = None) -> IntakeLinkResult:
        _ = account_id
        requested_url = url.strip()
        try:
            normalized_identity = normalize_explicit_web_url(requested_url)
        except ValueError as exc:
            raise ExplicitLinkIntakeError("invalid link url") from exc

        existing = self._find_existing(normalized_identity)

        if self.session.in_transaction():
            self.session.commit()

        try:
            fetched = fetch_web_page(requested_url)
        except WebFetchError as exc:
            raise ExplicitLinkIntakeError(exc.message) from exc

        try:
            final_identity = normalize_explicit_web_url(fetched.final_url)
        except ValueError:
            final_identity = normalized_identity

        content_hash = fetched.content_hash or hashlib.sha256(
            fetched.text.encode("utf-8")
        ).hexdigest()
        revision = f"{WEB_CONTENT_REVISION_PREFIX}{content_hash}"

        metadata: dict[str, Any] = {
            "intake_mode": EXPLICIT_INTAKE_MODE,
            "requested_url": requested_url,
            "fetched_at": datetime.now(UTC).isoformat(),
            "content_revision": revision,
            "content_hash": content_hash,
        }
        if fetched.content_type:
            metadata[CONTENT_FORMAT] = fetched.content_type

        if existing is not None and existing.external_id != final_identity:
            # Redirect changed canonical host/path — migrate identity on same object.
            existing.external_id = final_identity
            existing.canonical_uri = fetched.final_url

        obj = existing or self._create_object(
            title=_resolve_title(fetched, final_identity),
            external_id=final_identity,
            canonical_uri=fetched.final_url,
            metadata=metadata,
        )

        prior_meta = dict(obj.metadata_ or {})
        prior_revision = prior_meta.get("content_revision")
        same_revision = prior_revision == revision

        if existing is not None:
            obj.canonical_uri = fetched.final_url
            merged = dict(prior_meta)
            merged.update(metadata)
            obj.metadata_ = merged
            if fetched.title and (obj.title == prior_meta.get("requested_url") or not obj.title):
                obj.title = _resolve_title(fetched, final_identity)

        if same_revision and existing is not None:
            return IntakeLinkResult(
                object_id=obj.id,
                provider=PROVIDER_WEB,
                kind=obj.kind,
                status="unchanged",
                content_status=(obj.metadata_ or {}).get(CONTENT_EXTRACTION_STATUS, STATUS_READY),
                content_jobs_enqueued=0,
            )

        jobs = 0
        if fetched.is_binary:
            obj.body = None
            meta = dict(obj.metadata_ or {})
            meta[CONTENT_EXTRACTION_STATUS] = STATUS_METADATA_ONLY
            meta[MECHANICAL_REPRESENTATION_COUNT] = 0
            obj.metadata_ = meta
            MechanicalRepresentationPersistence(self.session).clear_mechanical_for_object(obj.id)
            enqueue_embed_object(self.session, obj.id, self.user_id)
            jobs = 1
            status = "updated" if existing else "created"
        else:
            preview = fetched.text[:500] if fetched.text else None
            obj.body = preview
            reps, truncated = build_bounded_text_representations(
                obj.id,
                fetched.text,
                MAX_REPRESENTATION_PARTS,
                source_meta={"content_truncated": False},
            )
            count = MechanicalRepresentationPersistence(self.session).replace_mechanical_for_object(
                obj.id, reps
            )
            meta = dict(obj.metadata_ or {})
            meta[CONTENT_EXTRACTION_STATUS] = STATUS_READY
            meta[MECHANICAL_REPRESENTATION_COUNT] = count
            meta["content_truncated"] = truncated
            obj.metadata_ = meta
            enqueue_summarize_resource(self.session, obj.id, self.user_id, revision)
            enqueue_embed_object(self.session, obj.id, self.user_id)
            jobs = 2
            status = "updated" if existing else "created"

        self.session.flush()
        content_status = (obj.metadata_ or {}).get(CONTENT_EXTRACTION_STATUS, STATUS_READY)
        return IntakeLinkResult(
            object_id=obj.id,
            provider=PROVIDER_WEB,
            kind=obj.kind,
            status=status,
            content_status=content_status,
            content_jobs_enqueued=jobs,
        )

    def close(self) -> None:
        return None

    def _find_existing(self, external_id: str) -> Object | None:
        return self.session.scalar(
            select(Object).where(
                Object.user_id == self.user_id,
                Object.provider == PROVIDER_WEB,
                Object.external_id == external_id,
            )
        )

    def _create_object(
        self,
        title: str,
        external_id: str,
        canonical_uri: str,
        metadata: dict[str, Any],
    ) -> Object:
        obj = Object(
            user_id=self.user_id,
            kind="web_page",
            title=title,
            origin="explicit",
            state="observed",
            provider=PROVIDER_WEB,
            external_id=external_id,
            canonical_uri=canonical_uri,
            metadata_=dict(metadata),
        )
        self.session.add(obj)
        self.session.flush()
        return obj


def _resolve_title(fetched: WebFetchResult, fallback: str) -> str:
    if fetched.title and fetched.title.strip():
        return fetched.title.strip()[:200]
    return fallback[:200]
