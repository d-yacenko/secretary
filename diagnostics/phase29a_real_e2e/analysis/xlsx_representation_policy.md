# XLSX representation policy (deployed SHA fc8e90b)

Source: `backend/app/content_extraction/mechanical_extractors.py`  
Constants: `backend/app/content_extraction/constants.py`

## Mechanical read bounds

| Constant | Value | Effect |
|----------|-------|--------|
| MAX_XLSX_SHEETS | 16 | Max sheets processed |
| MAX_XLSX_ROWS_PER_SHEET | 200 | Max rows read per sheet via `_read_xlsx_sheet_rows` |
| MAX_XLSX_COLUMNS | 64 | Max columns per row |

`_read_xlsx_sheet_rows()` reads up to **200 rows** from the workbook XML.

## What becomes Representation.text

`_build_xlsx_representations()` creates exactly **3 mechanical** representations:

1. **schema** — sheet name + header column names
2. **sample** — header row + **`rows[1:6]`** (first 5 data rows only)
3. **statistics** — `rows=N, columns=M` count per sheet

Plus separate **summary** representation (title only) from intake pipeline.

**No chunk/full representations** are created for XLSX — unlike plain text files which use `build_text_representations()` with chunked `KIND_FULL`/`chunk` reps.

## Code excerpt (sample row selection)

```python
for row in rows[1:6]:
    sample_lines.append(",".join(row))
```

Python slice `rows[1:6]` = indices 1,2,3,4,5 = **5 data rows** after header.

## Production target object evidence

| Field | Value |
|-------|-------|
| statistics | `rows=46` — full sheet row count known |
| sample text_length | 337 chars — ends at row 2.0 seminar topic |
| content_truncated | **false** |
| mechanical_representation_count | 3 |

## Can row ~15 enter searchable text?

**NO** under current policy.

- Rows 6–46 are read into memory for counting but **never appended** to `sample_lines`.
- No alternative Representation kind stores them.
- FTS/trigram indexes only persisted Representation.text.

## content_truncated semantics

`content_truncated=false` is **technically accurate** for parser bounds (46 < 200 rows, no _cap_text hit) but does **NOT** signal the intentional 5-row sample policy.

The distinction between «read mechanically» vs «persisted searchable» is not reflected in `content_truncated`.

## Conclusion

Target row ~15 was likely **read** (46 rows counted) but **never persisted** into any searchable Representation. This is the demonstrated root cause for retrieval failure on the target phrase.
