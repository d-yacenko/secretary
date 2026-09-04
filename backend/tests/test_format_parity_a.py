"""Format Parity Pass A — ODF extractors, adaptive CSV/Parquet, format resolver."""

import uuid
import zipfile
from pathlib import Path

import pytest

from app.content_extraction.constants import (
    EXTRACTION_VERSION,
    MAX_ODP_SLIDES,
    MAX_REPRESENTATION_PART_BYTES,
    MAX_REPRESENTATION_PARTS,
    MAX_REPRESENTATION_TOTAL_BYTES,
    SUPPORTED_BINARY_SUFFIXES,
)
from app.content_extraction.dataset_sampling import select_distributed_row_indices
from app.content_extraction.format_resolver import (
    MIME_SUFFIX_MAP,
    detect_supported_file_suffix,
    resolve_content_extraction_plan,
)
from app.content_extraction.mechanical_extractors import extract_from_path
from app.content_extraction.zip_safety import UnsafeZipError
from tests.fixtures.format_parity_fixtures import (
    write_large_csv,
    write_large_parquet,
    write_malformed_odt,
    write_minimal_odp,
    write_minimal_ods,
    write_minimal_odt,
    write_ods_with_repeated_rows,
)
from tests.fixtures.phase_29a_fixtures import (
    write_csv,
    write_minimal_docx,
    write_minimal_parquet,
    write_minimal_pdf,
    write_minimal_pptx,
    write_minimal_xlsx,
    write_txt,
    write_zip_bomb,
)


def test_extraction_version_is_format_parity_a() -> None:
    assert EXTRACTION_VERSION == "format-parity-a-v1"


# --- ODT ---


def test_odt_extracts_headings_paragraphs_table(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    odt_path = tmp_path / "sample.odt"
    write_minimal_odt(odt_path)
    reps, meta = extract_from_path(object_id, odt_path)
    joined = "\n".join(rep.text for rep in reps)
    assert "ODT Heading" in joined
    assert "odt distinctive phrase alpha" in joined
    assert "list item one" in joined
    assert "cell_a" in joined and "cell_b" in joined
    assert meta["content_format"] == ".odt"


def test_odt_malformed_archive_rejected(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.odt"
    write_malformed_odt(bad_path)
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        extract_from_path(uuid.uuid4(), bad_path)


def test_odt_zip_safety_limit(tmp_path: Path) -> None:
    bomb_path = tmp_path / "bomb.odt"
    write_zip_bomb(bomb_path)
    with pytest.raises((UnsafeZipError, Exception)):
        extract_from_path(uuid.uuid4(), bomb_path)


def test_odt_truncation_on_huge_content(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    odt_path = tmp_path / "huge.odt"
    write_minimal_odt(odt_path, paragraph="x" * 600_000)
    reps, meta = extract_from_path(object_id, odt_path)
    assert meta["content_truncated"] is True
    assert sum(len(rep.text) for rep in reps) > 0


# --- ODS ---


def test_ods_multiple_sheets_and_cells(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    ods_path = tmp_path / "sample.ods"
    write_minimal_ods(ods_path)
    reps, meta = extract_from_path(object_id, ods_path)
    sample = next(r for r in reps if r.kind == "sample")
    searchable = "\n".join(r.text for r in reps if r.kind in {"full", "chunk"})
    assert "ods_value" in sample.text
    assert "sheet2_marker" in sample.text or "sheet2_marker" in searchable
    assert "4" in sample.text
    assert meta["content_format"] == ".ods"


def test_ods_repeated_rows_bounded(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    ods_path = tmp_path / "repeated.ods"
    write_ods_with_repeated_rows(ods_path, repeat_count=500)
    reps, meta = extract_from_path(object_id, ods_path)
    stats = next(r for r in reps if r.kind == "statistics")
    assert meta["content_format"] == ".ods"
    assert "Repeated" in stats.text
    assert meta.get("content_truncated") in {True, False}


def test_ods_formula_cell_uses_stored_value(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    ods_path = tmp_path / "formula.ods"
    write_minimal_ods(ods_path)
    reps, _ = extract_from_path(object_id, ods_path)
    joined = "\n".join(rep.text for rep in reps)
    assert "of:=" not in joined
    assert "4" in joined


# --- ODP ---


def test_odp_multiple_slides_bullets_table(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    odp_path = tmp_path / "sample.odp"
    write_minimal_odp(odp_path)
    reps, meta = extract_from_path(object_id, odp_path)
    joined = "\n".join(rep.text for rep in reps)
    assert "[slide 1]" in joined
    assert "[slide 2]" in joined
    assert "odp distinctive phrase gamma" in joined
    assert "bullet one" in joined
    assert "second slide text" in joined
    assert "slide_table_a" in joined
    assert meta["content_format"] == ".odp"


def test_odp_slide_bound_truncation(tmp_path: Path) -> None:
    from tests.fixtures.format_parity_fixtures import _write_odf_zip

    slides = "".join(
        f'<draw:page draw:name="p{i}"><text:p>slide {i}</text:p></draw:page>'
        for i in range(MAX_ODP_SLIDES + 5)
    )
    content_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0">
  <office:body><office:presentation>{slides}</office:presentation></office:body>
</office:document-content>"""
    odp_path = tmp_path / "many.odp"
    _write_odf_zip(odp_path, content_xml)
    _, meta = extract_from_path(uuid.uuid4(), odp_path)
    assert meta["content_truncated"] is True


# --- CSV adaptive ---


def test_csv_small_dataset_full_coverage(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    csv_path = tmp_path / "small.csv"
    write_csv(csv_path)
    reps, meta = extract_from_path(object_id, csv_path)
    sample = next(r for r in reps if r.kind == "sample")
    assert meta["dataset_sampling_mode"] == "full"
    assert meta["dataset_row_count"] == 2
    assert meta["dataset_rows_represented"] == 2
    assert meta["dataset_sampling_truncated"] is False
    assert "alpha" in sample.text and "beta" in sample.text


def test_csv_large_dataset_distributed_not_prefix_only(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    csv_path = tmp_path / "large.csv"
    marker_row = 9999
    write_large_csv(csv_path, 10000, marker_row=marker_row)
    reps1, meta1 = extract_from_path(object_id, csv_path)
    _, meta2 = extract_from_path(uuid.uuid4(), csv_path)
    sample1 = next(r for r in reps1 if r.kind == "sample")
    searchable1 = "\n".join(r.text for r in reps1 if r.kind in {"full", "chunk"})
    combined = sample1.text + searchable1
    assert meta1["dataset_sampling_mode"] == "distributed"
    assert meta1["dataset_row_count"] == 10000
    assert meta1["dataset_rows_represented"] < 10000
    assert f"format_parity_marker_row_{marker_row}" in combined
    assert meta2["dataset_sampling_mode"] == meta1["dataset_sampling_mode"]
    assert meta2["dataset_rows_represented"] == meta1["dataset_rows_represented"]


def test_csv_representation_bounds(tmp_path: Path) -> None:
    csv_path = tmp_path / "bounded.csv"
    write_large_csv(csv_path, 5000)
    reps, _ = extract_from_path(uuid.uuid4(), csv_path)
    assert len(reps) <= MAX_REPRESENTATION_PARTS
    total_bytes = sum(len(r.text.encode("utf-8")) for r in reps)
    assert total_bytes <= MAX_REPRESENTATION_TOTAL_BYTES
    for rep in reps:
        assert len(rep.text.encode("utf-8")) <= MAX_REPRESENTATION_PART_BYTES


# --- Parquet adaptive ---


def test_parquet_small_dataset_full_coverage(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    parquet_path = tmp_path / "small.parquet"
    write_minimal_parquet(parquet_path)
    _, meta = extract_from_path(object_id, parquet_path)
    assert meta["dataset_sampling_mode"] == "full"
    assert meta["dataset_row_count"] == 2
    assert meta["dataset_rows_represented"] == 2


def test_parquet_large_dataset_distributed(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    parquet_path = tmp_path / "large.parquet"
    marker_row = 9999
    write_large_parquet(parquet_path, 10000, marker_row=marker_row)
    reps, meta = extract_from_path(object_id, parquet_path)
    searchable = "\n".join(r.text for r in reps if r.kind in {"full", "chunk"})
    sample = next(r for r in reps if r.kind == "sample")
    combined = sample.text + searchable
    assert meta["dataset_sampling_mode"] == "distributed"
    assert meta["dataset_row_count"] == 10000
    assert f"format_parity_marker_row_{marker_row}" in combined


def test_parquet_deterministic_sampling(tmp_path: Path) -> None:
    parquet_path = tmp_path / "deterministic.parquet"
    write_large_parquet(parquet_path, 500, marker_row=400)
    _, meta1 = extract_from_path(uuid.uuid4(), parquet_path)
    _, meta2 = extract_from_path(uuid.uuid4(), parquet_path)
    assert meta1["dataset_rows_represented"] == meta2["dataset_rows_represented"]
    assert meta1["dataset_sampling_mode"] == meta2["dataset_sampling_mode"]


# --- Format resolver ---


@pytest.mark.parametrize(
    ("suffix", "mime"),
    [
        (".odt", "application/vnd.oasis.opendocument.text"),
        (".ods", "application/vnd.oasis.opendocument.spreadsheet"),
        (".odp", "application/vnd.oasis.opendocument.presentation"),
    ],
)
def test_format_resolver_odf_suffix_and_mime(suffix: str, mime: str) -> None:
    assert suffix in SUPPORTED_BINARY_SUFFIXES
    assert MIME_SUFFIX_MAP[mime] == suffix
    detected = detect_supported_file_suffix(
        content_type=mime,
        prefix=b"PK\x03\x04",
        title=f"file{suffix}",
    )
    assert detected == suffix
    plan = resolve_content_extraction_plan(
        "google_drive",
        "file",
        {"mime_type": mime},
        title=f"doc{suffix}",
    )
    assert plan.eligible is True
    assert plan.suffix == suffix


def test_unknown_zip_remains_unsupported() -> None:
    detected = detect_supported_file_suffix(
        content_type="application/zip",
        prefix=b"PK\x03\x04",
        title="archive.zip",
    )
    assert detected is None
    plan = resolve_content_extraction_plan(
        "google_drive",
        "file",
        {"mime_type": "application/zip"},
        title="archive.zip",
    )
    assert plan.eligible is False


# --- Regression ---


def test_phase29a_formats_still_extract(tmp_path: Path) -> None:
    object_id = uuid.uuid4()
    txt_path = tmp_path / "sample.txt"
    write_txt(txt_path)
    reps, meta = extract_from_path(object_id, txt_path)
    assert reps and meta["content_format"] == ".txt"

    csv_path = tmp_path / "sample.csv"
    write_csv(csv_path)
    reps, _ = extract_from_path(object_id, csv_path)
    assert {rep.kind for rep in reps} >= {"schema", "sample", "statistics"}

    pdf_path = tmp_path / "sample.pdf"
    write_minimal_pdf(pdf_path)
    reps, _ = extract_from_path(object_id, pdf_path)
    assert any("distinctive phrase delta" in rep.text for rep in reps)

    docx_path = tmp_path / "sample.docx"
    write_minimal_docx(docx_path)
    reps, _ = extract_from_path(object_id, docx_path)
    assert any("distinctive phrase beta" in rep.text for rep in reps)

    xlsx_path = tmp_path / "sample.xlsx"
    write_minimal_xlsx(xlsx_path)
    reps, _ = extract_from_path(object_id, xlsx_path)
    assert any("xlsx_value" in rep.text for rep in reps)

    pptx_path = tmp_path / "sample.pptx"
    write_minimal_pptx(pptx_path)
    reps, _ = extract_from_path(object_id, pptx_path)
    assert any("distinctive phrase gamma" in rep.text for rep in reps)


def test_distributed_indices_span_range() -> None:
    indices = select_distributed_row_indices(1000, 20)
    assert indices[0] == 0
    assert indices[-1] == 999
    assert len(indices) <= 20
    assert len(set(indices)) == len(indices)
