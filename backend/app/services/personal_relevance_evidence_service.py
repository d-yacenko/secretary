"""Read-only personal relevance evidence snapshot builder (Pass E-B).

Zero LLM calls. Zero writes, jobs, or notifications. Reusable later by Proactive E-C.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Edge,
    GoogleAccount,
    MattermostAccount,
    Object,
    YandexCalendarAccount,
    YandexMailAccount,
)
from app.domain.labels import EDGE_TYPE_LABELED_WITH, KIND_LABEL
from app.domain.object_visibility import object_is_active
from app.personal_relevance.models import (
    PERSONAL_RELEVANCE_EVIDENCE_VERSION,
    PERSONAL_RELEVANCE_MAX_LABELS_PER_OBJECT,
    PERSONAL_RELEVANCE_MAX_OBJECTS,
    PERSONAL_RELEVANCE_MAX_SEMANTIC_CONTEXT_CHARS,
    PERSONAL_RELEVANCE_MAX_TITLE_CHARS,
    AssignedLabelEvidence,
    ObjectPersonalRelevanceEvidence,
    PersonalRelevanceEvidenceSnapshot,
    PersonalRelevanceUserContext,
)
from app.services.label_service import label_description
from app.services.personal_semantic_context_service import load_personal_semantic_context
from app.services.provenance import REJECTED_STATE
from app.services.user_identity_constants import MAX_CONNECTED_ACCOUNT_IDENTIFIERS
from app.services.user_identity_context_service import (
    UserIdentityContextService,
    UserIdentityRuntimeFacts,
    bound_runtime_identity_facts,
)
from app.services.user_participation_evidence_service import (
    ParticipationIdentity,
    current_user_participation_roles,
    extract_email_address,
)


class PersonalRelevanceEvidenceService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._identity = UserIdentityContextService.build(session)

    @classmethod
    def build(cls, session: Session) -> PersonalRelevanceEvidenceService:
        return cls(session)

    def build_snapshot(
        self,
        user_id: UUID,
        object_ids: Sequence[UUID],
    ) -> PersonalRelevanceEvidenceSnapshot:
        user_context, identity = self._load_user_context(user_id)
        user_context_signature = _sha256_canonical(user_context.to_payload())

        requested = _dedupe_ids(object_ids)
        truncated_objects = len(requested) > PERSONAL_RELEVANCE_MAX_OBJECTS
        bounded_ids = requested[:PERSONAL_RELEVANCE_MAX_OBJECTS]
        owned = self._load_owned_objects(user_id, bounded_ids)
        labels_by_object = self._load_assigned_labels(user_id, [obj.id for obj in owned])

        object_records: list[ObjectPersonalRelevanceEvidence] = []
        signatures: dict[str, str] = {}
        for obj in owned:
            labels, labels_truncated = labels_by_object.get(obj.id, ((), False))
            record = ObjectPersonalRelevanceEvidence(
                object_id=obj.id,
                kind=obj.kind,
                provider=obj.provider,
                origin=obj.origin,
                state=obj.state,
                status=obj.status,
                title=(obj.title or "")[:PERSONAL_RELEVANCE_MAX_TITLE_CHARS],
                updated_at=obj.updated_at,
                due_at=obj.due_at,
                start_at=obj.start_at,
                occurred_at=obj.occurred_at,
                user_participation_roles=current_user_participation_roles(obj, identity),
                assigned_labels=labels,
                labels_truncated=labels_truncated,
            )
            object_records.append(record)
            signatures[str(obj.id)] = object_evidence_signature(
                record, user_context_signature
            )

        return PersonalRelevanceEvidenceSnapshot(
            version=PERSONAL_RELEVANCE_EVIDENCE_VERSION,
            user_context=user_context,
            objects=tuple(object_records),
            user_context_signature=user_context_signature,
            truncated_objects=truncated_objects,
            object_evidence_signatures=signatures,
        )


    def _load_user_context(
        self, user_id: UUID
    ) -> tuple[PersonalRelevanceUserContext, ParticipationIdentity]:
        raw_facts = self._identity.get_runtime_facts(user_id)
        bounded = bound_runtime_identity_facts(raw_facts)
        semantic = load_personal_semantic_context(self._session, user_id, lock_rows=False)
        semantic_text = semantic.context_text or ""
        semantic_truncated = len(semantic_text) > PERSONAL_RELEVANCE_MAX_SEMANTIC_CONTEXT_CHARS
        semantic_text = semantic_text[:PERSONAL_RELEVANCE_MAX_SEMANTIC_CONTEXT_CHARS]
        identity_truncated = _identity_was_truncated(raw_facts, bounded)
        truncated = identity_truncated or semantic_truncated

        google_emails, yandex_mail_emails, yandex_calendar_emails, mm_ids, mm_usernames = (
            self._connected_match_tokens(user_id)
        )
        emails = frozenset(
            email
            for email in (
                *(extract_email_address(item) for item in bounded.emails),
                *google_emails,
                *yandex_mail_emails,
                *yandex_calendar_emails,
            )
            if email
        )
        identity = ParticipationIdentity(
            emails=emails,
            mattermost_user_ids=mm_ids,
            mattermost_usernames=mm_usernames,
            has_google_account=bool(google_emails),
            has_yandex_calendar_account=bool(yandex_calendar_emails),
        )
        connected = list(bounded.connected_account_identifiers)
        seen_connected = {item.casefold() for item in connected}
        for remote_id in sorted(mm_ids):
            token = f"mattermost:user_id:{remote_id}"
            key = token.casefold()
            if key in seen_connected:
                continue
            if len(connected) >= MAX_CONNECTED_ACCOUNT_IDENTIFIERS:
                truncated = True
                break
            connected.append(token)
            seen_connected.add(key)

        user_context = PersonalRelevanceUserContext(
            full_name=bounded.full_name,
            preferred_name=bounded.preferred_name,
            aliases=tuple(bounded.aliases),
            roles=tuple(bounded.roles),
            organizations=tuple(bounded.organizations),
            emails=tuple(bounded.emails),
            phones=tuple(bounded.phones),
            telegram=tuple(bounded.telegram),
            other_identifiers=tuple(bounded.other_identifiers),
            connected_account_identifiers=tuple(connected),
            semantic_context=semantic_text,
            truncated=truncated,
        )
        return user_context, identity

    def _connected_match_tokens(
        self, user_id: UUID
    ) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
        google_emails = _emails_from_query(
            self._session.scalars(select(GoogleAccount.email).where(GoogleAccount.user_id == user_id))
        )
        yandex_mail_emails = _emails_from_query(
            self._session.scalars(
                select(YandexMailAccount.email).where(YandexMailAccount.user_id == user_id)
            )
        )
        yandex_calendar_emails = _emails_from_query(
            self._session.scalars(
                select(YandexCalendarAccount.email).where(YandexCalendarAccount.user_id == user_id)
            )
        )
        mm_ids: set[str] = set()
        mm_usernames: set[str] = set()
        for account in self._session.scalars(
            select(MattermostAccount).where(MattermostAccount.user_id == user_id)
        ):
            if account.remote_user_id:
                mm_ids.add(account.remote_user_id)
            if account.username:
                mm_usernames.add(account.username.casefold())
        return (
            google_emails,
            yandex_mail_emails,
            yandex_calendar_emails,
            frozenset(mm_ids),
            frozenset(mm_usernames),
        )

    def _load_owned_objects(self, user_id: UUID, object_ids: list[UUID]) -> list[Object]:
        if not object_ids:
            return []
        rows = list(
            self._session.scalars(
                select(Object).where(
                    Object.user_id == user_id,
                    Object.id.in_(object_ids),
                    Object.state != REJECTED_STATE,
                    object_is_active(),
                )
            )
        )
        by_id = {item.id: item for item in rows}
        return [by_id[item_id] for item_id in object_ids if item_id in by_id]

    def _load_assigned_labels(
        self,
        user_id: UUID,
        object_ids: list[UUID],
    ) -> dict[UUID, tuple[tuple[AssignedLabelEvidence, ...], bool]]:
        if not object_ids:
            return {}
        rows = self._session.execute(
            select(Edge, Object)
            .join(Object, Edge.target_id == Object.id)
            .where(
                Edge.user_id == user_id,
                Edge.source_id.in_(object_ids),
                Edge.type == EDGE_TYPE_LABELED_WITH,
                Edge.state != REJECTED_STATE,
                Object.user_id == user_id,
                Object.kind == KIND_LABEL,
                Object.state != REJECTED_STATE,
                object_is_active(Object),
            )
        ).all()
        grouped: dict[UUID, list[AssignedLabelEvidence]] = {object_id: [] for object_id in object_ids}
        for edge, label in rows:
            grouped.setdefault(edge.source_id, []).append(
                AssignedLabelEvidence(
                    label_id=label.id,
                    title=label.title,
                    description=label_description(label),
                    assignment_origin=edge.origin,
                    assignment_confidence=edge.confidence,
                )
            )
        result: dict[UUID, tuple[tuple[AssignedLabelEvidence, ...], bool]] = {}
        for object_id, labels in grouped.items():
            labels.sort(key=lambda item: (item.title.casefold(), item.label_id.bytes))
            truncated = len(labels) > PERSONAL_RELEVANCE_MAX_LABELS_PER_OBJECT
            result[object_id] = (
                tuple(labels[:PERSONAL_RELEVANCE_MAX_LABELS_PER_OBJECT]),
                truncated,
            )
        return result


def object_evidence_signature(
    record: ObjectPersonalRelevanceEvidence,
    user_context_signature: str,
) -> str:
    payload = {
        "version": PERSONAL_RELEVANCE_EVIDENCE_VERSION,
        "object_id": str(record.object_id),
        "kind": record.kind,
        "provider": record.provider,
        "origin": record.origin,
        "state": record.state,
        "status": record.status,
        "title": record.title,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "due_at": record.due_at.isoformat() if record.due_at else None,
        "start_at": record.start_at.isoformat() if record.start_at else None,
        "occurred_at": record.occurred_at.isoformat() if record.occurred_at else None,
        "user_participation_roles": list(record.user_participation_roles),
        "assigned_labels": [item.to_payload() for item in record.assigned_labels],
        "user_context_signature": user_context_signature,
    }
    return _sha256_canonical(payload)


def _dedupe_ids(object_ids: Sequence[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for item in sorted(object_ids, key=lambda value: value.bytes):
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _identity_was_truncated(
    raw: UserIdentityRuntimeFacts,
    bounded: UserIdentityRuntimeFacts,
) -> bool:
    pairs = (
        (raw.aliases, bounded.aliases),
        (raw.roles, bounded.roles),
        (raw.organizations, bounded.organizations),
        (raw.emails, bounded.emails),
        (raw.phones, bounded.phones),
        (raw.telegram, bounded.telegram),
        (raw.other_identifiers, bounded.other_identifiers),
        (raw.connected_account_identifiers, bounded.connected_account_identifiers),
    )
    if any(len(left) > len(right) for left, right in pairs):
        return True
    full_truncated = bool(
        raw.full_name
        and (bounded.full_name is None or len(raw.full_name) > len(bounded.full_name))
    )
    preferred_truncated = bool(
        raw.preferred_name
        and (
            bounded.preferred_name is None
            or len(raw.preferred_name) > len(bounded.preferred_name)
        )
    )
    return full_truncated or preferred_truncated


def _emails_from_query(values) -> frozenset[str]:
    emails: set[str] = set()
    for value in values:
        email = extract_email_address(value)
        if email:
            emails.add(email)
    return frozenset(emails)


def _sha256_canonical(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
