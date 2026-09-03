"""Bounded mechanical text/dataset/office extractors — no LLM."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from app.content_extraction.constants import (
    MAX_EXTRACTED_TEXT_CHARS,
    MAX_PDF_PAGES,
    MAX_PPTX_SLIDES,
    MAX_XLSX_COLUMNS,
    MAX_XLSX_ROWS_PER_SHEET,
    MAX_XLSX_SHEETS,
)
from app.content_extraction.zip_safety import validate_zip_archive
from app.db.models import Representation
from app.local.bounded_io import (
    bounded_parquet_stats,
    read_bounded_text,
    read_csv_header,
    read_csv_sample_rows,
    read_parquet_sample_rows,
    read_parquet_schema,
    stream_csv_stats,
)
from app.services.bounded_chunks import (
    MAX_INDEXED_TEXT_CHUNKS,
    build_indexing_metadata,
    chunk_text,
    select_bounded_chunks,
)
from app.services.representation_service import (
    KIND_CHUNK,
    KIND_FULL,
    KIND_SAMPLE,
    KIND_SCHEMA,
    KIND_STATISTICS,
    SMALL_TEXT_MAX_CHARS,
    _format_sample_text,
    _format_schema_text,
)

DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PPTX_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _cap_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_EXTRACTED_TEXT_CHARS:
        return text, False
    return text[:MAX_EXTRACTED_TEXT_CHARS], True


def build_text_representations(
    object_id,
    text: str,
    source_meta: dict[str, Any] | None = None,
) -> tuple[list[Representation], bool]:
    extra_meta = dict(source_meta or {})
    capped, truncated = _cap_text(text)
    if len(capped) <= SMALL_TEXT_MAX_CHARS:
        return [
            Representation(
                object_id=object_id,
                kind=KIND_FULL,
                text=capped,
                metadata_={**extra_meta, "truncated": truncated},
            )
        ], truncated

    all_chunks = chunk_text(capped, 800, 100)
    selected_chunks, selected_indices = select_bounded_chunks(
        all_chunks, MAX_INDEXED_TEXT_CHUNKS
    )
    indexing_meta = build_indexing_metadata(
        source_chars=len(capped),
        total_chunks=len(all_chunks),
        indexed_chunks=len(selected_chunks),
    )
    reps: list[Representation] = []
    for part_index, (source_index, chunk) in enumerate(
        zip(selected_indices, selected_chunks, strict=True)
    ):
        reps.append(
            Representation(
                object_id=object_id,
                kind=KIND_CHUNK,
                part_index=part_index,
                text=chunk,
                metadata_={
                    **indexing_meta,
                    **extra_meta,
                    "truncated": truncated,
                    "source_chunk_index": source_index,
                },
            )
        )
    return reps, truncated


def extract_from_path(object_id, path: Path) -> tuple[list[Representation], dict[str, Any]]:
    suffix = path.suffix.lower()
    truncated = False
    source_bytes = path.stat().st_size

    if suffix in {".txt", ".md"}:
        text, source_meta = read_bounded_text(path)
        reps, truncated = build_text_representations(object_id, text, source_meta)
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": suffix,
            "content_truncated": truncated or bool(source_meta.get("truncated")),
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".csv":
        reps = _build_csv_representations(object_id, path)
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".csv",
            "content_truncated": False,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".parquet":
        reps = _build_parquet_representations(object_id, path)
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".parquet",
            "content_truncated": False,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".pdf":
        text, truncated = _extract_pdf_text(path)
        reps, text_truncated = build_text_representations(
            object_id,
            text,
            {"source_bytes": source_bytes},
        )
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".pdf",
            "content_truncated": truncated or text_truncated,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".docx":
        text, truncated = _extract_docx_text(path)
        reps, text_truncated = build_text_representations(
            object_id,
            text,
            {"source_bytes": source_bytes},
        )
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".docx",
            "content_truncated": truncated or text_truncated,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".xlsx":
        reps, truncated = _build_xlsx_representations(object_id, path)
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".xlsx",
            "content_truncated": truncated,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    if suffix == ".pptx":
        reps, truncated = _build_pptx_representations(object_id, path)
        extracted_chars = sum(len(rep.text) for rep in reps)
        return reps, {
            "content_format": ".pptx",
            "content_truncated": truncated,
            "content_source_bytes": source_bytes,
            "content_extracted_chars": extracted_chars,
        }

    raise ValueError(f"unsupported mechanical extraction suffix: {suffix}")


def _extract_pdf_text(path: Path) -> tuple[str, bool]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("encrypted pdf")
    pages = reader.pages[:MAX_PDF_PAGES]
    truncated = len(reader.pages) > MAX_PDF_PAGES
    parts: list[str] = []
    for index, page in enumerate(pages, start=1):
        page_text = page.extract_text() or ""
        parts.append(f"[page {index}]\n{page_text}")
    text = "\n\n".join(parts).strip()
    capped, char_truncated = _cap_text(text)
    return capped, truncated or char_truncated


def _extract_docx_text(path: Path) -> tuple[str, bool]:
    with zipfile.ZipFile(path) as archive:
        validate_zip_archive(archive)
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", DOCX_NS):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", DOCX_NS)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    for table in root.findall(".//w:tbl", DOCX_NS):
        for row in table.findall(".//w:tr", DOCX_NS):
            cells = row.findall(".//w:tc", DOCX_NS)
            cell_texts: list[str] = []
            for cell in cells:
                cell_text = "".join(
                    (node.text or "") for node in cell.findall(".//w:t", DOCX_NS)
                ).strip()
                cell_texts.append(cell_text)
            if any(cell_texts):
                paragraphs.append("| " + " | ".join(cell_texts) + " |")
    text = "\n".join(paragraphs)
    capped, truncated = _cap_text(text)
    return capped, truncated


def _build_csv_representations(object_id, path: Path) -> list[Representation]:
    fieldnames = read_csv_header(path)
    _, sample_rows = read_csv_sample_rows(path, 5)
    stats_meta, stats_lines, column_types = stream_csv_stats(path, fieldnames)
    return [
        Representation(
            object_id=object_id,
            kind=KIND_SCHEMA,
            text=_format_schema_text(fieldnames, column_types),
            metadata_={
                "columns": [{"name": name, "type": column_types[name]} for name in fieldnames]
            },
        ),
        Representation(
            object_id=object_id,
            kind=KIND_SAMPLE,
            text=_format_sample_text(sample_rows, fieldnames),
            metadata_={"row_count_in_sample": len(sample_rows)},
        ),
        Representation(
            object_id=object_id,
            kind=KIND_STATISTICS,
            text="\n".join(stats_lines),
            metadata_=stats_meta,
        ),
    ]


def _build_parquet_representations(object_id, path: Path) -> list[Representation]:
    fieldnames, column_types, row_count = read_parquet_schema(path)
    _, sample_rows = read_parquet_sample_rows(path, 5)
    stats_meta, stats_lines = bounded_parquet_stats(path, fieldnames, column_types, row_count)
    return [
        Representation(
            object_id=object_id,
            kind=KIND_SCHEMA,
            text=_format_schema_text(fieldnames, column_types),
            metadata_={
                "columns": [{"name": name, "type": column_types[name]} for name in fieldnames]
            },
        ),
        Representation(
            object_id=object_id,
            kind=KIND_SAMPLE,
            text=_format_sample_text(sample_rows, fieldnames),
            metadata_={"row_count_in_sample": len(sample_rows)},
        ),
        Representation(
            object_id=object_id,
            kind=KIND_STATISTICS,
            text="\n".join(stats_lines),
            metadata_=stats_meta,
        ),
    ]


def _build_xlsx_representations(object_id, path: Path) -> tuple[list[Representation], bool]:
    with zipfile.ZipFile(path) as archive:
        validate_zip_archive(archive)
        shared_strings = _read_xlsx_shared_strings(archive)
        sheet_names = _read_xlsx_sheet_names(archive)
        truncated = len(sheet_names) > MAX_XLSX_SHEETS
        selected_sheets = sheet_names[:MAX_XLSX_SHEETS]

        schema_lines = ["schema"]
        sample_lines = ["sample"]
        stats_lines = ["statistics"]
        for sheet_name in selected_sheets:
            rows = _read_xlsx_sheet_rows(archive, sheet_name, shared_strings)
            if not rows:
                schema_lines.append(f"{sheet_name}: (empty)")
                continue
            header = rows[0]
            schema_lines.append(f"{sheet_name}: {', '.join(header)}")
            sample_lines.append(f"[{sheet_name}]")
            sample_lines.append(",".join(header))
            for row in rows[1:6]:
                sample_lines.append(",".join(row))
            stats_lines.append(f"{sheet_name}: rows={len(rows) - 1}, columns={len(header)}")

        schema_text, schema_trunc = _cap_text("\n".join(schema_lines))
        sample_text, sample_trunc = _cap_text("\n".join(sample_lines))
        stats_text, stats_trunc = _cap_text("\n".join(stats_lines))
        truncated = truncated or schema_trunc or sample_trunc or stats_trunc

        return [
            Representation(
                object_id=object_id,
                kind=KIND_SCHEMA,
                text=schema_text,
                metadata_={"sheet_count": len(selected_sheets)},
            ),
            Representation(
                object_id=object_id,
                kind=KIND_SAMPLE,
                text=sample_text,
                metadata_={"sheet_count": len(selected_sheets)},
            ),
            Representation(
                object_id=object_id,
                kind=KIND_STATISTICS,
                text=stats_text,
                metadata_={"sheet_count": len(selected_sheets)},
            ),
        ], truncated


def _build_pptx_representations(object_id, path: Path) -> tuple[list[Representation], bool]:
    with zipfile.ZipFile(path) as archive:
        validate_zip_archive(archive)
        slide_paths = sorted(
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        truncated = len(slide_paths) > MAX_PPTX_SLIDES
        selected = slide_paths[:MAX_PPTX_SLIDES]
        lines: list[str] = []
        for index, slide_path in enumerate(selected, start=1):
            xml_bytes = archive.read(slide_path)
            root = ET.fromstring(xml_bytes)
            texts = [
                node.text.strip()
                for node in root.findall(".//a:t", PPTX_NS)
                if node.text and node.text.strip()
            ]
            lines.append(f"[slide {index}]")
            lines.extend(texts)
        text, char_trunc = _cap_text("\n".join(lines))
        reps, text_trunc = build_text_representations(
            object_id,
            text,
            {"slide_count": len(selected)},
        )
        return reps, truncated or char_trunc or text_trunc


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("main:si", XLSX_NS):
        texts = [node.text or "" for node in item.findall(".//main:t", XLSX_NS)]
        strings.append("".join(texts))
    return strings


def _read_xlsx_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    if "xl/workbook.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    names: list[str] = []
    for sheet in root.findall(".//main:sheet", XLSX_NS):
        name = sheet.attrib.get("name")
        if name:
            names.append(name)
    return names


def _read_xlsx_sheet_rows(
    archive: zipfile.ZipFile,
    sheet_name: str,
    shared_strings: list[str],
) -> list[list[str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet_id = None
    for sheet in workbook.findall(".//main:sheet", XLSX_NS):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            sheet_id = rel_id
            break
    if sheet_id is None:
        return []

    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for rel in rels_root:
        if rel.attrib.get("Id") == sheet_id:
            target = rel.attrib.get("Target")
            break
    if not target:
        return []
    sheet_path = target if target.startswith("worksheets/") else f"worksheets/{target}"
    if not sheet_path.startswith("xl/"):
        sheet_path = f"xl/{sheet_path}"
    if sheet_path not in archive.namelist():
        return []

    root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//main:row", XLSX_NS):
        if len(rows) >= MAX_XLSX_ROWS_PER_SHEET:
            break
        values: list[str] = []
        for cell in row.findall("main:c", XLSX_NS):
            if len(values) >= MAX_XLSX_COLUMNS:
                break
            value = _xlsx_cell_value(cell, shared_strings)
            values.append(value)
        if values:
            rows.append(values)
    return rows


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("main:v", XLSX_NS)
    if value_node is None or value_node.text is None:
        inline = cell.find("main:is", XLSX_NS)
        if inline is not None:
            texts = [node.text or "" for node in inline.findall(".//main:t", XLSX_NS)]
            return "".join(texts)
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value_node.text)]
        except (ValueError, IndexError):
            return value_node.text
    return value_node.text
