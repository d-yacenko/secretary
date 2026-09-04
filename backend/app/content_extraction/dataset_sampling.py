"""Bounded adaptive row sampling for CSV/Parquet dataset representations."""

from __future__ import annotations

from typing import Any

from app.content_extraction.constants import (
    MAX_REPRESENTATION_PART_BYTES,
    MAX_REPRESENTATION_TOTAL_BYTES,
)
from app.services.representation_service import _format_sample_text

MAX_SAMPLED_INDEX_LIST = 64


def select_distributed_row_indices(total_rows: int, target_count: int) -> list[int]:
    """Deterministically select row indices spanning the full dataset range."""
    if total_rows <= 0 or target_count <= 0:
        return []
    if target_count >= total_rows:
        return list(range(total_rows))
    if target_count == 1:
        return [total_rows // 2]
    indices: list[int] = []
    for i in range(target_count):
        idx = round(i * (total_rows - 1) / (target_count - 1))
        indices.append(int(idx))
    return sorted(set(indices))


def estimate_row_bytes(fieldnames: list[str], sample_row: dict[str, Any]) -> int:
    if not fieldnames:
        return 1
    line = ",".join(str(sample_row.get(name, "")) for name in fieldnames)
    return max(1, len(line.encode("utf-8")) + 1)


def estimate_rows_for_budget(
    fieldnames: list[str],
    sample_row: dict[str, Any],
    byte_budget: int,
) -> int:
    if not fieldnames or byte_budget <= 0:
        return 0
    header_bytes = len(("sample\n" + ",".join(fieldnames)).encode("utf-8")) + 1
    row_bytes = estimate_row_bytes(fieldnames, sample_row)
    available = byte_budget - header_bytes
    if available <= 0:
        return 0
    return max(1, available // row_bytes)


def plan_dataset_sampling(
    *,
    total_rows: int,
    fieldnames: list[str],
    sample_rows_for_estimate: list[dict[str, Any]],
    structural_bytes: int = 0,
) -> tuple[list[int], str, bool]:
    """Return (selected_indices, sampling_mode, sampling_truncated)."""
    if total_rows <= 0:
        return [], "full", False

    remaining_bytes = max(0, MAX_REPRESENTATION_TOTAL_BYTES - structural_bytes)
    sample_budget = min(MAX_REPRESENTATION_PART_BYTES, remaining_bytes // 2)

    estimate_row = (
        sample_rows_for_estimate[0]
        if sample_rows_for_estimate
        else {name: "" for name in fieldnames}
    )
    max_rows_in_budget = estimate_rows_for_budget(fieldnames, estimate_row, sample_budget)

    if total_rows <= max_rows_in_budget:
        return list(range(total_rows)), "full", False

    target_count = max_rows_in_budget
    indices = select_distributed_row_indices(total_rows, target_count)
    return indices, "distributed", len(indices) < total_rows


def fit_sample_to_part_limit(
    *,
    fieldnames: list[str],
    rows_by_index: dict[int, dict[str, Any]],
    indices: list[int],
    total_rows: int,
) -> tuple[list[dict[str, Any]], list[int], str, str, bool]:
    """Shrink sample rows until formatted sample fits per-part byte limit."""
    current_indices = list(indices)
    while current_indices:
        current_rows = [rows_by_index[i] for i in current_indices if i in rows_by_index]
        sample_text = _format_sample_text(current_rows, fieldnames)
        if len(sample_text.encode("utf-8")) <= MAX_REPRESENTATION_PART_BYTES:
            mode = "full" if len(current_indices) >= total_rows else "distributed"
            truncated = len(current_indices) < total_rows
            return current_rows, current_indices, sample_text, mode, truncated
        if len(current_indices) <= 1:
            encoded = sample_text.encode("utf-8")[:MAX_REPRESENTATION_PART_BYTES]
            clipped = encoded.decode("utf-8", errors="ignore")
            row = current_rows[0] if current_rows else {}
            return [row], current_indices[:1], clipped, "distributed", True
        new_count = max(1, len(current_indices) // 2)
        current_indices = select_distributed_row_indices(total_rows, new_count)
    return [], [], "sample\n(empty)", "distributed", True


def build_dataset_sample_metadata(
    *,
    total_rows: int,
    represented_rows: int,
    sampling_mode: str,
    sampling_truncated: bool,
    sampled_indices: list[int],
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "dataset_row_count": total_rows,
        "dataset_rows_represented": represented_rows,
        "dataset_sampling_mode": sampling_mode,
        "dataset_sampling_truncated": sampling_truncated,
    }
    if (
        sampling_mode == "distributed"
        and sampled_indices
        and len(sampled_indices) <= MAX_SAMPLED_INDEX_LIST
    ):
        meta["sampled_row_indices"] = sampled_indices
    return meta


def format_searchable_dataset_rows(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    indices: list[int],
) -> str:
    lines: list[str] = []
    for row_index, row in zip(indices, rows, strict=False):
        lines.append(f"[row={row_index + 1}]")
        lines.append(_format_sample_text([row], fieldnames).split("\n", 1)[-1])
    return "\n".join(lines)


def estimate_structural_bytes(fieldnames: list[str], stats_lines: list[str]) -> int:
    schema_text = "schema\n" + "\n".join(f"{name}: string" for name in fieldnames)
    stats_text = "\n".join(stats_lines)
    return len(schema_text.encode("utf-8")) + len(stats_text.encode("utf-8"))
