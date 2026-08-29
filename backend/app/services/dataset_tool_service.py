import csv
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Object, Representation
from app.local.constants import MAX_DATASET_QUERY_ROWS, PROVIDER_LOCAL_DEVICE
from app.local.errors import LocalFileError
from app.local.paths import LocalPathResolver
from app.services.errors import NotFoundError, ValidationError
from app.services.representation_service import (
    KIND_SAMPLE,
    KIND_SCHEMA,
    KIND_STATISTICS,
)


class DatasetToolService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        path_resolver: LocalPathResolver,
        upload_root: Path | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._path_resolver = path_resolver
        self._upload_root = upload_root

    def get_schema(self, object_id: UUID) -> dict:
        obj = self._get_dataset_object(object_id)
        rep = self._find_representation(obj.id, KIND_SCHEMA)
        if rep is not None and rep.text:
            return {
                "object_id": str(object_id),
                "schema_text": rep.text,
                "columns": (rep.metadata_ or {}).get("columns", []),
            }
        path = self._resolve_dataset_path(obj)
        return self._read_schema_from_path(path, object_id)

    def get_sample(self, object_id: UUID, limit: int = 5) -> dict:
        if limit < 1 or limit > MAX_DATASET_QUERY_ROWS:
            raise ValidationError("sample limit out of bounds")
        obj = self._get_dataset_object(object_id)
        rep = self._find_representation(obj.id, KIND_SAMPLE)
        if rep is not None and rep.text:
            return {
                "object_id": str(object_id),
                "sample_text": rep.text,
                "row_count_in_sample": (rep.metadata_ or {}).get("row_count_in_sample", 0),
            }
        path = self._resolve_dataset_path(obj)
        return self._read_sample_from_path(path, object_id, limit)

    def get_basic_stats(self, object_id: UUID) -> dict:
        obj = self._get_dataset_object(object_id)
        rep = self._find_representation(obj.id, KIND_STATISTICS)
        if rep is not None and rep.text:
            return {
                "object_id": str(object_id),
                "statistics_text": rep.text,
                "statistics": rep.metadata_ or {},
            }
        path = self._resolve_dataset_path(obj)
        return self._read_stats_from_path(path, object_id)

    def query_columns(
        self,
        object_id: UUID,
        columns: list[str],
        limit: int = 20,
    ) -> dict:
        if not columns:
            raise ValidationError("columns must not be empty")
        if limit < 1 or limit > MAX_DATASET_QUERY_ROWS:
            raise ValidationError("query limit out of bounds")
        obj = self._get_dataset_object(object_id)
        path = self._resolve_dataset_path(obj)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows = _query_csv_columns(path, columns, limit)
        elif suffix == ".parquet":
            rows = _query_parquet_columns(path, columns, limit)
        else:
            raise ValidationError(f"unsupported dataset format: {suffix}")
        return {
            "object_id": str(object_id),
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    def _get_dataset_object(self, object_id: UUID) -> Object:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", object_id)
        if obj.kind != "dataset":
            raise ValidationError("dataset tools require kind=dataset")
        return obj

    def _find_representation(self, object_id: UUID, kind: str) -> Representation | None:
        return self._session.scalar(
            select(Representation).where(
                Representation.object_id == object_id,
                Representation.kind == kind,
            )
        )

    def _resolve_dataset_path(self, obj: Object) -> Path:
        metadata = obj.metadata_ or {}
        upload_path = metadata.get("upload_path")
        if upload_path and Path(upload_path).is_file():
            return Path(upload_path)
        if obj.provider == PROVIDER_LOCAL_DEVICE:
            return self._resolve_local_object_path(obj)
        canonical = obj.canonical_uri
        if canonical and Path(canonical).is_file():
            return Path(canonical)
        raise LocalFileError("dataset source file is not available")

    def _resolve_local_object_path(self, obj: Object) -> Path:
        metadata = obj.metadata_ or {}
        device_key = metadata.get("device_key")
        root_path = metadata.get("local_root_path")
        relative_path = metadata.get("local_relative_path")
        if not device_key or not root_path or not relative_path:
            raise LocalFileError("object is missing local path metadata")
        return self._path_resolver.resolve_file_path(
            self._user_id,
            str(device_key),
            str(root_path),
            str(relative_path),
        )

    def _read_schema_from_path(self, path: Path, object_id: UUID) -> dict:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
            columns = [{"name": name, "type": "string"} for name in fieldnames]
            schema_text = "schema\n" + "\n".join(f"{name}: string" for name in fieldnames)
        elif suffix == ".parquet":
            schema = pq.ParquetFile(path).schema_arrow
            fieldnames = schema.names
            columns = [
                {"name": name, "type": str(schema.field(name).type)} for name in fieldnames
            ]
            schema_text = "schema\n" + "\n".join(
                f"{name}: {column['type']}" for name, column in zip(fieldnames, columns, strict=True)
            )
        else:
            raise ValidationError(f"unsupported dataset format: {suffix}")
        return {
            "object_id": str(object_id),
            "schema_text": schema_text,
            "columns": columns,
        }

    def _read_sample_from_path(self, path: Path, object_id: UUID, limit: int) -> dict:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = []
                for index, row in enumerate(reader):
                    if index >= limit:
                        break
                    rows.append(row)
        elif suffix == ".parquet":
            table = pq.read_table(path)
            slice_table = table.slice(0, min(limit, table.num_rows))
            rows = []
            for index in range(slice_table.num_rows):
                row = {}
                for name in slice_table.column_names:
                    row[name] = slice_table.column(name)[index].as_py()
                rows.append(row)
            fieldnames = table.column_names
        else:
            raise ValidationError(f"unsupported dataset format: {suffix}")

        lines = ["sample"]
        if suffix == ".csv":
            lines.append(",".join(fieldnames))
            for row in rows:
                lines.append(",".join(str(row.get(name, "")) for name in fieldnames))
        else:
            lines.append(",".join(fieldnames))
            for row in rows:
                lines.append(",".join(str(row.get(name, "")) for name in fieldnames))
        return {
            "object_id": str(object_id),
            "sample_text": "\n".join(lines),
            "row_count_in_sample": len(rows),
        }

    def _read_stats_from_path(self, path: Path, object_id: UUID) -> dict:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)
            row_count = len(rows)
            column_count = len(fieldnames)
            stats_meta: dict = {
                "row_count": row_count,
                "column_count": column_count,
                "columns": {},
            }
            lines = [f"rows: {row_count}", f"columns: {column_count}"]
            for name in fieldnames:
                numbers = []
                for row in rows:
                    value = row.get(name)
                    if value is None or value == "":
                        continue
                    try:
                        numbers.append(float(value))
                    except ValueError:
                        continue
                if not numbers:
                    continue
                col_stats = {
                    "min": min(numbers),
                    "max": max(numbers),
                    "mean": sum(numbers) / len(numbers),
                }
                stats_meta["columns"][name] = col_stats
                lines.append(
                    f"{name}: min={col_stats['min']}, max={col_stats['max']}, mean={col_stats['mean']}"
                )
        elif suffix == ".parquet":
            table = pq.read_table(path)
            row_count = table.num_rows
            fieldnames = table.column_names
            stats_meta = {
                "row_count": row_count,
                "column_count": len(fieldnames),
                "columns": {},
            }
            lines = [f"rows: {row_count}", f"columns: {len(fieldnames)}"]
            for name in fieldnames:
                column = table.column(name)
                if not pa.types.is_integer(column.type) and not pa.types.is_floating(column.type):
                    continue
                numeric = pc.cast(column, pa.float64(), safe=False).drop_null()
                if numeric.length() == 0:
                    continue
                values = [float(value) for value in numeric.to_pylist()]
                col_stats = {
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }
                stats_meta["columns"][name] = col_stats
                lines.append(
                    f"{name}: min={col_stats['min']}, max={col_stats['max']}, mean={col_stats['mean']}"
                )
        else:
            raise ValidationError(f"unsupported dataset format: {suffix}")
        return {
            "object_id": str(object_id),
            "statistics_text": "\n".join(lines),
            "statistics": stats_meta,
        }


def _query_csv_columns(path: Path, columns: list[str], limit: int) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        available = set(reader.fieldnames or [])
        for name in columns:
            if name not in available:
                raise ValidationError(f"column not found: {name}")
        rows: list[dict] = []
        for index, row in enumerate(reader):
            if index >= limit:
                break
            rows.append({name: row.get(name, "") for name in columns})
        return rows


def _query_parquet_columns(path: Path, columns: list[str], limit: int) -> list[dict]:
    table = pq.read_table(path, columns=columns)
    rows: list[dict] = []
    for index in range(min(limit, table.num_rows)):
        row = {}
        for name in columns:
            row[name] = table.column(name)[index].as_py()
        rows.append(row)
    return rows
