"""Deterministic query-centered evidence snippets for retrieval and context."""

from __future__ import annotations

import re

MARKER_RE = re.compile(r"\[(?:slide|page)\s+\d+\]", re.IGNORECASE)
GENERIC_QUERY_PREFIX_RE = re.compile(
    r"^(?:найди(?:\s+мне)?|найти(?:\s+мне)?|посмотри|find(?:\s+me)?|search(?:\s+for)?)\s+",
    re.IGNORECASE,
)
MIN_NEEDLE_LENGTH = 6

CONTEXT_EVIDENCE_MAX_CHARS = 1200


def normalize_lexical_text(text: str) -> str:
    return " ".join(text.lower().split())


def lexical_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in normalize_lexical_text(text).split():
        cleaned = token.strip(".,;:!?\"'«»()[]{}")
        if len(cleaned) >= 3:
            tokens.add(cleaned)
    return tokens


def lexical_match_score(text: str, query: str) -> tuple[float, float]:
    text_norm = normalize_lexical_text(text)
    query_norm = normalize_lexical_text(query)
    substring = 1.0 if query_norm and query_norm in text_norm else 0.0
    if substring == 0.0:
        stripped = GENERIC_QUERY_PREFIX_RE.sub("", query.strip())
        stripped_norm = normalize_lexical_text(stripped)
        if stripped_norm and stripped_norm in text_norm:
            substring = 1.0
    if substring == 0.0:
        span = find_longest_query_substring(text, query, case_sensitive=True)
        if span is None:
            span = find_longest_query_substring(text, query, case_sensitive=False)
        if span is not None and (span[1] - span[0]) >= MIN_NEEDLE_LENGTH:
            substring = 0.75
    query_tokens = lexical_tokens(query_norm)
    if not query_tokens:
        return substring, 0.0
    text_tokens = lexical_tokens(text_norm)
    coverage = len(query_tokens & text_tokens) / len(query_tokens)
    return substring, coverage


def find_longest_query_substring(
    text: str,
    query: str,
    *,
    case_sensitive: bool,
) -> tuple[int, int] | None:
    needle_source = query.strip()
    if not needle_source or not text:
        return None
    best: tuple[int, int] | None = None
    best_len = 0
    for q_start in range(len(needle_source)):
        for q_end in range(len(needle_source), q_start + MIN_NEEDLE_LENGTH - 1, -1):
            needle = needle_source[q_start:q_end]
            if len(needle) < MIN_NEEDLE_LENGTH:
                break
            if case_sensitive:
                pos = text.find(needle)
            else:
                pos = text.lower().find(needle.lower())
            if pos >= 0 and len(needle) > best_len:
                best_len = len(needle)
                best = (pos, pos + len(needle))
                break
    return best


def find_atom_evidence_span(text: str, atoms: list[str]) -> tuple[int, int] | None:
    if not atoms or not text:
        return None
    text_lower = text.lower()
    best: tuple[int, int, int] | None = None
    for atom in atoms:
        atom_lower = atom.lower()
        if len(atom_lower) < MIN_NEEDLE_LENGTH:
            continue
        start = 0
        while True:
            pos = text_lower.find(atom_lower, start)
            if pos < 0:
                break
            span = (pos, pos + len(atom), len(atom))
            if best is None or span[2] > best[2]:
                best = span
            start = pos + 1
    if best is None:
        return None
    return best[0], best[1]


def find_evidence_anchor(
    text: str,
    query: str,
    atoms: list[str] | None = None,
) -> int | None:
    if not text:
        return None

    span = find_longest_query_substring(text, query, case_sensitive=True)
    if span is not None:
        return (span[0] + span[1]) // 2

    stripped = GENERIC_QUERY_PREFIX_RE.sub("", query.strip()).strip()
    if stripped and stripped != query.strip():
        span = find_longest_query_substring(text, stripped, case_sensitive=True)
        if span is not None:
            return (span[0] + span[1]) // 2

    span = find_longest_query_substring(text, query, case_sensitive=False)
    if span is not None:
        return (span[0] + span[1]) // 2

    if atoms:
        span = find_atom_evidence_span(text, atoms)
        if span is not None:
            return (span[0] + span[1]) // 2

    return None


def _nearest_marker_start(text: str, before_pos: int) -> int | None:
    best: int | None = None
    for match in MARKER_RE.finditer(text):
        if match.start() <= before_pos:
            best = match.start()
    return best


def build_query_centered_snippet(
    text: str,
    query: str,
    max_chars: int,
    atoms: list[str] | None = None,
) -> str:
    source = text.strip()
    if not source or max_chars <= 0:
        return ""
    if len(source) <= max_chars:
        return source

    anchor = find_evidence_anchor(source, query, atoms)
    if anchor is None:
        return source[: max_chars - 1].rstrip() + "…"

    marker_start = _nearest_marker_start(source, anchor)
    start = max(0, anchor - max_chars // 2)
    if marker_start is not None and marker_start < start:
        start = marker_start
    end = min(len(source), start + max_chars)

    prefix_ellipsis = start > 0
    suffix_ellipsis = end < len(source)
    budget = max_chars - int(prefix_ellipsis) - int(suffix_ellipsis)
    if budget <= 0:
        return "…"[:max_chars]

    rel_anchor = anchor - start
    left = min(rel_anchor, budget // 2)
    slice_start = start + rel_anchor - left
    slice_end = slice_start + budget
    if slice_end > len(source):
        slice_end = len(source)
        slice_start = max(0, slice_end - budget)
    snippet = source[slice_start:slice_end]
    prefix_ellipsis = slice_start > 0
    suffix_ellipsis = slice_end < len(source)

    result = snippet
    if prefix_ellipsis:
        result = "…" + result
    if suffix_ellipsis:
        result = result + "…"
    if len(result) > max_chars:
        if prefix_ellipsis and suffix_ellipsis:
            inner = max_chars - 2
            result = "…" + snippet[:inner].rstrip() + "…"
        elif prefix_ellipsis:
            result = "…" + snippet[: max_chars - 1].rstrip()
        elif suffix_ellipsis:
            result = snippet[: max_chars - 1].rstrip() + "…"
        else:
            result = snippet[:max_chars]
    return result


def representation_evidence_score(
    text: str,
    query: str,
    atoms: list[str] | None = None,
) -> tuple[float, float, int]:
    substring, coverage = lexical_match_score(text, query)
    atom_hits = 0
    if atoms:
        text_lower = text.lower()
        for atom in atoms:
            if len(atom) >= MIN_NEEDLE_LENGTH and atom.lower() in text_lower:
                atom_hits += 1
    return substring, coverage, atom_hits
