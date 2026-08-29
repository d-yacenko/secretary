from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Object
from app.services.errors import ValidationError
from app.services.retrieval_constants import (
    ANCHOR_KIND_BOOST,
    ANCHOR_KINDS,
    BODY_FTS_WEIGHT,
    CANDIDATE_BRANCH_LIMIT,
    DEFAULT_FINAL_HITS,
    FTS_DOCUMENT_SQL,
    MAX_CANDIDATE_POOL,
    MAX_FINAL_HITS,
    MIN_BODY_FTS_THRESHOLD,
    MIN_TITLE_QUALIFY_THRESHOLD,
    MIN_TRIGRAM_QUALIFY_THRESHOLD,
    RECENCY_BONUS,
    RECENCY_WINDOW,
    RECENT_HORIZON_DAYS,
    SHORT_EXCERPT_MAX_CHARS,
    STRONG_TITLE_FTS_THRESHOLD,
    STRONG_TRIGRAM_THRESHOLD,
    TIME_SCOPE_ALL,
    TIME_SCOPE_AUTO,
    TIME_SCOPE_RECENT,
    TIME_SENSITIVE_SOURCE_KINDS,
    TITLE_FTS_WEIGHT,
    TRIGRAM_WEIGHT,
    YEAR_HORIZON_DAYS,
)
from app.services.retrieval_models import RetrievalHit, RetrievalResult

_BASE_WHERE = """
    o.user_id = :user_id
    AND (o.status IS NULL OR o.status != 'deleted')
    AND o.state != 'rejected'
"""


def _build_filter_suffix(
    kind: str | None,
    provider: str | None,
    project_id: UUID | None,
    horizon_cutoff: datetime | None,
    date_from: datetime | None,
    date_to: datetime | None,
    apply_horizon: bool,
) -> str:
    filters: list[str] = []
    if kind is not None:
        filters.append("AND o.kind = :kind")
    if provider is not None:
        filters.append("AND o.provider = :provider")
    if project_id is not None:
        filters.append(
            """
            AND o.id IN (
                SELECT e.target_id FROM edges e
                WHERE e.user_id = :user_id AND e.source_id = :project_id
                UNION
                SELECT e.source_id FROM edges e
                WHERE e.user_id = :user_id AND e.target_id = :project_id
            )
            """
        )
    if apply_horizon and horizon_cutoff is not None:
        filters.append(
            """
            AND (
                o.kind NOT IN ('email', 'event', 'chat_message')
                OR (o.occurred_at IS NOT NULL AND o.occurred_at >= :horizon_cutoff)
            )
            """
        )
    if date_from is not None and date_to is not None:
        filters.append(
            """
            AND (
                o.kind NOT IN ('email', 'event', 'chat_message')
                OR (
                    o.occurred_at IS NOT NULL
                    AND o.occurred_at >= :date_from
                    AND o.occurred_at <= :date_to
                )
            )
            """
        )
    elif date_from is not None:
        filters.append(
            """
            AND (
                o.kind NOT IN ('email', 'event', 'chat_message')
                OR (o.occurred_at IS NOT NULL AND o.occurred_at >= :date_from)
            )
            """
        )
    elif date_to is not None:
        filters.append(
            """
            AND (
                o.kind NOT IN ('email', 'event', 'chat_message')
                OR (o.occurred_at IS NOT NULL AND o.occurred_at <= :date_to)
            )
            """
        )
    return "".join(filters)


def _build_fts_candidate_sql(filter_suffix: str) -> str:
    return f"""
    SELECT o.id
    FROM objects o
    WHERE {_BASE_WHERE}
      {filter_suffix}
      AND ({FTS_DOCUMENT_SQL}) @@ plainto_tsquery('simple', :query)
    LIMIT :branch_limit
    """


def _build_trigram_candidate_sql(filter_suffix: str) -> str:
    return f"""
    SELECT o.id
    FROM objects o
    WHERE {_BASE_WHERE}
      {filter_suffix}
      AND o.title % :query
    LIMIT :branch_limit
    """


_RANK_QUERY = text(
    """
    SELECT
        o.id,
        o.title,
        o.kind,
        o.provider,
        o.state,
        o.status,
        o.occurred_at,
        o.body,
        o.created_at,
        ts_rank(
            to_tsvector('simple', coalesce(o.title, '')),
            plainto_tsquery('simple', :query)
        ) AS title_rank,
        ts_rank(
            to_tsvector('simple', coalesce(o.body, '')),
            plainto_tsquery('simple', :query)
        ) AS body_rank,
        similarity(coalesce(o.title, ''), :query) AS title_sim
    FROM objects o
    WHERE o.user_id = :user_id
      AND o.id = ANY(:candidate_ids)
    """
)


class RetrievalService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def retrieve(
        self,
        query: str,
        *,
        kind: str | None = None,
        provider: str | None = None,
        project_id: UUID | None = None,
        time_scope: str = TIME_SCOPE_AUTO,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = DEFAULT_FINAL_HITS,
    ) -> RetrievalResult:
        normalized_query = query.strip()
        if not normalized_query:
            return RetrievalResult(
                hits=[],
                query=normalized_query,
                time_scope_used=time_scope,
                horizon_days=None,
            )

        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValidationError("date_from must be before or equal to date_to")

        final_limit = max(1, min(limit, MAX_FINAL_HITS))
        now = datetime.now(UTC)
        recency_cutoff = now - RECENCY_WINDOW
        explicit_dates = date_from is not None or date_to is not None

        if explicit_dates:
            horizons: list[int | None] = [None]
            effective_scope = TIME_SCOPE_ALL
        elif time_scope == TIME_SCOPE_ALL:
            horizons = [None]
            effective_scope = TIME_SCOPE_ALL
        elif time_scope == TIME_SCOPE_RECENT:
            horizons = [RECENT_HORIZON_DAYS]
            effective_scope = TIME_SCOPE_RECENT
        else:
            horizons = [RECENT_HORIZON_DAYS, YEAR_HORIZON_DAYS, None]
            effective_scope = TIME_SCOPE_AUTO

        last_hits: list[RetrievalHit] = []
        last_horizon: int | None = None

        for horizon_days in horizons:
            horizon_cutoff = None
            if horizon_days is not None:
                horizon_cutoff = now - timedelta(days=horizon_days)

            last_hits = self._score_and_rank(
                query=normalized_query,
                kind=kind,
                provider=provider,
                project_id=project_id,
                horizon_cutoff=horizon_cutoff,
                date_from=date_from,
                date_to=date_to,
                apply_horizon=not explicit_dates,
                recency_cutoff=recency_cutoff,
            )
            last_horizon = horizon_days

            if horizon_days is None:
                break
            if self._should_stop_horizon_expansion(last_hits):
                break

        trimmed = self._trim_to_limit(last_hits, final_limit)
        return RetrievalResult(
            hits=trimmed,
            query=normalized_query,
            time_scope_used=effective_scope,
            horizon_days=last_horizon,
        )

    def _collect_candidate_ids(
        self,
        query: str,
        kind: str | None,
        provider: str | None,
        project_id: UUID | None,
        horizon_cutoff: datetime | None,
        date_from: datetime | None,
        date_to: datetime | None,
        apply_horizon: bool,
    ) -> list[UUID]:
        filter_suffix = _build_filter_suffix(
            kind=kind,
            provider=provider,
            project_id=project_id,
            horizon_cutoff=horizon_cutoff,
            date_from=date_from,
            date_to=date_to,
            apply_horizon=apply_horizon,
        )
        params = {
            "query": query,
            "user_id": self._user_id,
            "kind": kind,
            "provider": provider,
            "project_id": project_id,
            "horizon_cutoff": horizon_cutoff,
            "date_from": date_from,
            "date_to": date_to,
            "branch_limit": CANDIDATE_BRANCH_LIMIT,
        }

        fts_ids = self._session.execute(
            text(_build_fts_candidate_sql(filter_suffix)),
            params,
        ).scalars()
        trigram_ids = self._session.execute(
            text(_build_trigram_candidate_sql(filter_suffix)),
            params,
        ).scalars()

        seen: set[UUID] = set()
        candidate_ids: list[UUID] = []
        for object_id in list(fts_ids) + list(trigram_ids):
            if object_id in seen:
                continue
            seen.add(object_id)
            candidate_ids.append(object_id)
            if len(candidate_ids) >= MAX_CANDIDATE_POOL:
                break
        return candidate_ids

    def _score_and_rank(
        self,
        query: str,
        kind: str | None,
        provider: str | None,
        project_id: UUID | None,
        horizon_cutoff: datetime | None,
        date_from: datetime | None,
        date_to: datetime | None,
        apply_horizon: bool,
        recency_cutoff: datetime,
    ) -> list[RetrievalHit]:
        candidate_ids = self._collect_candidate_ids(
            query=query,
            kind=kind,
            provider=provider,
            project_id=project_id,
            horizon_cutoff=horizon_cutoff,
            date_from=date_from,
            date_to=date_to,
            apply_horizon=apply_horizon,
        )
        if not candidate_ids:
            return []

        rows = self._session.execute(
            _RANK_QUERY,
            {
                "query": query,
                "user_id": self._user_id,
                "candidate_ids": candidate_ids,
            },
        ).mappings()

        hits: list[RetrievalHit] = []
        for row in rows:
            title_rank = float(row["title_rank"] or 0.0)
            body_rank = float(row["body_rank"] or 0.0)
            title_sim = float(row["title_sim"] or 0.0)
            kind_value = str(row["kind"])
            occurred_at = row["occurred_at"]
            created_at = row["created_at"]
            recency_signal = _recency_signal(
                kind_value, occurred_at, created_at, recency_cutoff
            )
            match_quality = (
                TITLE_FTS_WEIGHT * title_rank
                + BODY_FTS_WEIGHT * body_rank
                + TRIGRAM_WEIGHT * title_sim
            )
            ranking_score = match_quality
            if kind_value in ANCHOR_KINDS:
                ranking_score += ANCHOR_KIND_BOOST
            if recency_signal:
                ranking_score += RECENCY_BONUS

            reasons = _build_reasons(
                title_rank=title_rank,
                body_rank=body_rank,
                title_sim=title_sim,
                kind=kind_value,
                recency_signal=recency_signal,
            )

            hits.append(
                RetrievalHit(
                    object_id=row["id"],
                    title=str(row["title"]),
                    kind=kind_value,
                    provider=row["provider"],
                    state=str(row["state"]),
                    status=row["status"],
                    occurred_at=occurred_at,
                    relevance=ranking_score,
                    reasons=reasons,
                    short_excerpt=_short_excerpt(
                        title=str(row["title"]),
                        body=row["body"],
                        max_chars=SHORT_EXCERPT_MAX_CHARS,
                    ),
                )
            )

        hits.sort(key=lambda item: (-item.relevance, str(item.object_id)))
        return hits

    def _should_stop_horizon_expansion(self, hits: list[RetrievalHit]) -> bool:
        qualified = [hit for hit in hits if _hit_is_qualified(hit)]
        if not qualified:
            return False
        return any(_is_strong_textual_hit(hit) for hit in qualified)

    def _trim_to_limit(self, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        qualified = [hit for hit in hits if _hit_is_qualified(hit)]
        return qualified[:limit]


def _recency_signal(
    kind: str,
    occurred_at: datetime | None,
    created_at: datetime | None,
    recency_cutoff: datetime,
) -> bool:
    if kind in TIME_SENSITIVE_SOURCE_KINDS:
        if occurred_at is None:
            return False
        return occurred_at >= recency_cutoff
    reference_time = occurred_at or created_at
    if reference_time is None:
        return False
    return reference_time >= recency_cutoff


def _hit_is_qualified(hit: RetrievalHit) -> bool:
    return any(
        reason in hit.reasons
        for reason in (
            "title_match",
            "title_candidate",
            "body_match",
            "fuzzy_title",
            "fuzzy_title_candidate",
        )
    )


def _is_strong_textual_hit(hit: RetrievalHit) -> bool:
    return "title_match" in hit.reasons or "fuzzy_title" in hit.reasons


def _build_reasons(
    title_rank: float,
    body_rank: float,
    title_sim: float,
    kind: str,
    recency_signal: bool,
) -> list[str]:
    reasons: list[str] = []
    if title_rank >= STRONG_TITLE_FTS_THRESHOLD:
        reasons.append("title_match")
    elif title_rank >= MIN_TITLE_QUALIFY_THRESHOLD:
        reasons.append("title_candidate")
    if body_rank >= MIN_BODY_FTS_THRESHOLD:
        reasons.append("body_match")
    if title_sim >= STRONG_TRIGRAM_THRESHOLD:
        reasons.append("fuzzy_title")
    elif title_sim >= MIN_TRIGRAM_QUALIFY_THRESHOLD:
        reasons.append("fuzzy_title_candidate")
    if kind in ANCHOR_KINDS:
        reasons.append("anchor_kind")
    if recency_signal:
        reasons.append("recent")
    return reasons


def _short_excerpt(title: str, body: str | None, max_chars: int) -> str:
    source = (body or "").strip() or title.strip()
    if len(source) <= max_chars:
        return source
    return source[:max_chars].rstrip() + "…"


def load_objects_ordered(
    session: Session,
    user_id: UUID,
    hits: list[RetrievalHit],
) -> list[Object]:
    if not hits:
        return []
    from sqlalchemy import select

    object_ids = [hit.object_id for hit in hits]
    rows = session.scalars(
        select(Object).where(Object.user_id == user_id, Object.id.in_(object_ids))
    ).all()
    by_id = {obj.id: obj for obj in rows}
    return [by_id[object_id] for object_id in object_ids if object_id in by_id]
