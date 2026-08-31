"""Validate and persist client-extracted mechanical representations."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Representation
from app.services.client_intake_constants import (
    CLIENT_REP_METADATA_ALLOWLIST,
    CLIENT_REPRESENTATION_KINDS,
    DATASET_FILE_SUFFIXES,
    DATASET_REPRESENTATION_KINDS,
    MAX_CLIENT_REPRESENTATION_PART_BYTES,
    MAX_CLIENT_REPRESENTATION_PARTS,
    MAX_CLIENT_REPRESENTATION_TOTAL_BYTES,
    TEXT_FILE_SUFFIXES,
    TEXT_REPRESENTATION_KINDS,
    UNSUPPORTED_INDEX_SUFFIXES,
)
from app.services.errors import ValidationError
from app.services.representation_service import RepresentationService


def _utf8_byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _normalize_rep_metadata(metadata: dict) -> dict:
    if not metadata:
        return {}
    normalized: dict = {}
    for key, value in metadata.items():
        if key not in CLIENT_REP_METADATA_ALLOWLIST:
            raise ValidationError(f"client representation metadata not allowed: {key}")
        if key == "source_chunk_index":
            normalized[key] = int(value)
        else:
            normalized[key] = value
    return normalized


class ClientRepresentationValidator:
    def validate_payload(
        self,
        filename: str,
        representations: list[dict],
        metadata_only: bool,
    ) -> list[dict]:
        suffix = Path(filename).suffix.lower()
        if metadata_only:
            if representations:
                raise ValidationError("metadata_only intake cannot include representations")
            return []

        if suffix in UNSUPPORTED_INDEX_SUFFIXES or (
            suffix not in TEXT_FILE_SUFFIXES and suffix not in DATASET_FILE_SUFFIXES
        ):
            raise ValidationError("unsupported file format requires metadata_only intake")

        if len(representations) > MAX_CLIENT_REPRESENTATION_PARTS:
            raise ValidationError("client representations exceed max parts")

        allowed_kinds = (
            TEXT_REPRESENTATION_KINDS
            if suffix in TEXT_FILE_SUFFIXES
            else DATASET_REPRESENTATION_KINDS
        )

        seen_indices: set[int] = set()
        seen_dataset_kinds: set[str] = set()
        total_bytes = 0
        normalized: list[dict] = []
        full_count = 0

        for item in representations:
            kind = str(item.get("kind", "")).strip()
            if kind not in CLIENT_REPRESENTATION_KINDS:
                raise ValidationError(f"client representation kind not allowed: {kind}")
            if kind not in allowed_kinds:
                raise ValidationError(
                    f"client representation kind {kind} not allowed for {suffix}"
                )
            if kind == "full":
                full_count += 1
                if full_count > 1:
                    raise ValidationError("only one full representation allowed")
            if suffix in DATASET_FILE_SUFFIXES and kind in seen_dataset_kinds:
                raise ValidationError(f"duplicate dataset representation kind: {kind}")
            if suffix in DATASET_FILE_SUFFIXES:
                seen_dataset_kinds.add(kind)

            text = str(item.get("text", ""))
            part_bytes = _utf8_byte_len(text)
            if part_bytes > MAX_CLIENT_REPRESENTATION_PART_BYTES:
                raise ValidationError("client representation part exceeds size limit")
            total_bytes += part_bytes
            if total_bytes > MAX_CLIENT_REPRESENTATION_TOTAL_BYTES:
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
                    "metadata": _normalize_rep_metadata(dict(item.get("metadata") or {})),
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
        filename: str,
        representations: list[dict],
        metadata_only: bool,
    ) -> int:
        validated = self._validator.validate_payload(filename, representations, metadata_only)
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

    def delete_all_for_object(self, object_id: UUID) -> None:
        self._session.execute(delete(Representation).where(Representation.object_id == object_id))
        self._session.flush()
