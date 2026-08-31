"""Validate and persist client-extracted mechanical representations."""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Representation
from app.services.client_intake_constants import (
    CLIENT_REPRESENTATION_KINDS,
    MAX_CLIENT_REPRESENTATION_PART_CHARS,
    MAX_CLIENT_REPRESENTATION_PARTS,
    MAX_CLIENT_REPRESENTATION_TOTAL_CHARS,
)
from app.services.errors import ValidationError
from app.services.representation_service import RepresentationService


class ClientRepresentationValidator:
    def validate_payload(self, representations: list[dict]) -> list[dict]:
        if len(representations) > MAX_CLIENT_REPRESENTATION_PARTS:
            raise ValidationError("client representations exceed max parts")
        seen_indices: set[int] = set()
        total_chars = 0
        normalized: list[dict] = []
        for item in representations:
            kind = str(item.get("kind", "")).strip()
            if kind not in CLIENT_REPRESENTATION_KINDS:
                raise ValidationError(f"client representation kind not allowed: {kind}")
            text = str(item.get("text", ""))
            if len(text) > MAX_CLIENT_REPRESENTATION_PART_CHARS:
                raise ValidationError("client representation part exceeds size limit")
            total_chars += len(text)
            if total_chars > MAX_CLIENT_REPRESENTATION_TOTAL_CHARS:
                raise ValidationError("client representation payload exceeds total size limit")
            part_index = item.get("part_index")
            if part_index is not None:
                index = int(part_index)
                if index in seen_indices:
                    raise ValidationError("duplicate client representation part_index")
                seen_indices.add(index)
            normalized.append(
                {
                    "kind": kind,
                    "text": text,
                    "part_index": part_index,
                    "metadata": dict(item.get("metadata") or {}),
                }
            )
        return normalized


class ClientRepresentationPersistence:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._representations = RepresentationService(session, user_id)
        self._validator = ClientRepresentationValidator()

    def replace_for_object(
        self,
        object_id: UUID,
        representations: list[dict],
    ) -> int:
        validated = self._validator.validate_payload(representations)
        self._representations._get_object(object_id)
        reps: list[Representation] = []
        for item in validated:
            reps.append(
                Representation(
                    object_id=object_id,
                    kind=item["kind"],
                    text=item["text"],
                    part_index=item.get("part_index"),
                    metadata_=item.get("metadata") or {},
                )
            )
        self._session.execute(delete(Representation).where(Representation.object_id == object_id))
        for rep in reps:
            self._session.add(rep)
        self._session.flush()
        return len(reps)
