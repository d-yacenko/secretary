import csv
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Object, Representation
from app.llm.embedding_service import EmbeddingService
from app.llm.summarizer import FakeSummarizer, Summarizer
from app.services.chunking import chunk_text
from app.services.errors import NotFoundError
from app.services.representation_embedding import refresh_representation_embedding

SMALL_TEXT_MAX_CHARS = 500
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_SAMPLE_ROWS = 5

KIND_FULL = "full"
KIND_SUMMARY = "summary"
KIND_CHUNK = "chunk"
KIND_SAMPLE = "sample"
KIND_SCHEMA = "schema"
KIND_STATISTICS = "statistics"


class RepresentationService:
    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
        summarizer: Summarizer | None = None,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service
        self._summarizer = summarizer or FakeSummarizer()

    def list_for_object(self, object_id: UUID) -> list[Representation]:
        return list(
            self._session.scalars(
                select(Representation)
                .where(Representation.object_id == object_id)
                .order_by(Representation.kind, Representation.part_index)
            ).all()
        )

    def ingest_text_content(self, object_id: UUID, text: str) -> list[Representation]:
        obj = self._get_object(object_id)
        return self._persist(self._build_text_representations(obj, text))

    def ingest_file(self, object_id: UUID, path: Path) -> list[Representation]:
        obj = self._get_object(object_id)
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8")
            return self._persist(self._build_text_representations(obj, text))
        if suffix == ".csv":
            return self._persist(self._build_csv_representations(obj, path))
        if suffix == ".parquet":
            return self._persist(self._build_parquet_representations(obj, path))
        raise ValueError(f"unsupported file format: {suffix}")

    def _get_object(self, object_id: UUID) -> Object:
        obj = self._session.get(Object, object_id)
        if obj is None:
            raise NotFoundError("object", object_id)
        return obj

    def _persist(self, reps: list[Representation]) -> list[Representation]:
        for rep in reps:
            self._session.add(rep)
        self._session.flush()
        return reps

    def _build_text_representations(self, obj: Object, text: str) -> list[Representation]:
        if len(text) <= SMALL_TEXT_MAX_CHARS:
            return [
                Representation(
                    object_id=obj.id,
                    kind=KIND_FULL,
                    text=text,
                )
            ]

        reps: list[Representation] = [
            Representation(
                object_id=obj.id,
                kind=KIND_SUMMARY,
                text=self._summarizer.summarize(text),
            )
        ]
        for index, chunk in enumerate(chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
            rep = Representation(
                object_id=obj.id,
                kind=KIND_CHUNK,
                part_index=index,
                text=chunk,
            )
            if self._embedding_service is not None:
                refresh_representation_embedding(rep, self._embedding_service, chunk)
            reps.append(rep)
        return reps

    def _build_csv_representations(self, obj: Object, path: Path) -> list[Representation]:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        column_types = _infer_column_types(fieldnames, rows)
        schema_text = _format_schema_text(fieldnames, column_types)
        schema_rep = Representation(
            object_id=obj.id,
            kind=KIND_SCHEMA,
            text=schema_text,
            metadata_={
                "columns": [
                    {"name": name, "type": column_types[name]} for name in fieldnames
                ]
            },
        )

        sample_rows = rows[:MAX_SAMPLE_ROWS]
        sample_rep = Representation(
            object_id=obj.id,
            kind=KIND_SAMPLE,
            text=_format_sample_text(sample_rows, fieldnames),
            metadata_={"row_count_in_sample": len(sample_rows)},
        )

        stats_text, stats_meta = _build_tabular_statistics(fieldnames, rows, column_types)
        stats_rep = Representation(
            object_id=obj.id,
            kind=KIND_STATISTICS,
            text=stats_text,
            metadata_=stats_meta,
        )
        return [schema_rep, sample_rep, stats_rep]

    def _build_parquet_representations(self, obj: Object, path: Path) -> list[Representation]:
        parquet_file = pq.ParquetFile(path)
        schema = parquet_file.schema_arrow
        fieldnames = schema.names
        column_types = {name: str(schema.field(name).type) for name in fieldnames}
        row_count = parquet_file.metadata.num_rows if parquet_file.metadata else 0

        table = pq.read_table(path)
        if row_count > MAX_SAMPLE_ROWS:
            sample_table = table.slice(0, MAX_SAMPLE_ROWS)
        else:
            sample_table = table

        sample_rows = _table_rows_as_dicts(sample_table)
        stats_text, stats_meta = _build_arrow_statistics(table, fieldnames, column_types, row_count)

        schema_rep = Representation(
            object_id=obj.id,
            kind=KIND_SCHEMA,
            text=_format_schema_text(fieldnames, column_types),
            metadata_={
                "columns": [
                    {"name": name, "type": column_types[name]} for name in fieldnames
                ]
            },
        )
        sample_rep = Representation(
            object_id=obj.id,
            kind=KIND_SAMPLE,
            text=_format_sample_text(sample_rows, fieldnames),
            metadata_={"row_count_in_sample": len(sample_rows)},
        )
        stats_rep = Representation(
            object_id=obj.id,
            kind=KIND_STATISTICS,
            text=stats_text,
            metadata_=stats_meta,
        )
        return [schema_rep, sample_rep, stats_rep]


def _infer_column_types(fieldnames: list[str], rows: list[dict[str, str]]) -> dict[str, str]:
    types: dict[str, str] = {}
    for name in fieldnames:
        values = [row.get(name, "") for row in rows if row.get(name)]
        if not values:
            types[name] = "string"
            continue
        if all(_looks_int(value) for value in values):
            types[name] = "integer"
        elif all(_looks_float(value) for value in values):
            types[name] = "float"
        else:
            types[name] = "string"
    return types


def _looks_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _looks_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _format_schema_text(fieldnames: list[str], column_types: dict[str, str]) -> str:
    lines = [f"{name}: {column_types.get(name, 'string')}" for name in fieldnames]
    return "schema\n" + "\n".join(lines)


def _format_sample_text(rows: list[dict[str, object]], fieldnames: list[str]) -> str:
    if not fieldnames:
        return "sample\n(empty)"
    lines = ["sample", ",".join(fieldnames)]
    for row in rows:
        lines.append(",".join(str(row.get(name, "")) for name in fieldnames))
    return "\n".join(lines)


def _build_tabular_statistics(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    column_types: dict[str, str],
) -> tuple[str, dict]:
    row_count = len(rows)
    column_count = len(fieldnames)
    lines = [f"rows: {row_count}", f"columns: {column_count}"]
    metadata: dict = {"row_count": row_count, "column_count": column_count, "columns": {}}

    for name in fieldnames:
        col_type = column_types.get(name, "string")
        if col_type not in {"integer", "float"}:
            continue
        numbers = [float(row[name]) for row in rows if row.get(name)]
        if not numbers:
            continue
        col_stats = {
            "min": min(numbers),
            "max": max(numbers),
            "mean": sum(numbers) / len(numbers),
        }
        metadata["columns"][name] = col_stats
        lines.append(
            f"{name}: min={col_stats['min']}, max={col_stats['max']}, mean={col_stats['mean']}"
        )

    return "\n".join(lines), metadata


def _table_rows_as_dicts(table: pa.Table) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(table.num_rows):
        row: dict[str, object] = {}
        for name in table.column_names:
            value = table.column(name)[index]
            if isinstance(value, pa.Scalar):
                row[name] = value.as_py()
            else:
                row[name] = value
        rows.append(row)
    return rows


def _build_arrow_statistics(
    table: pa.Table,
    fieldnames: list[str],
    column_types: dict[str, str],
    row_count: int,
) -> tuple[str, dict]:
    lines = [f"rows: {row_count}", f"columns: {len(fieldnames)}"]
    metadata: dict = {
        "row_count": row_count,
        "column_count": len(fieldnames),
        "columns": {},
    }

    for name in fieldnames:
        column = table.column(name)
        if not pa.types.is_integer(column.type) and not pa.types.is_floating(column.type):
            continue
        numeric = pc.cast(column, pa.float64(), safe=False)
        valid = numeric.drop_null()
        if valid.length() == 0:
            continue
        values = [float(value) for value in valid.to_pylist()]
        col_stats = {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
        metadata["columns"][name] = col_stats
        lines.append(
            f"{name}: min={col_stats['min']}, max={col_stats['max']}, mean={col_stats['mean']}"
        )

    return "\n".join(lines), metadata
