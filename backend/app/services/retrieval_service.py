from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Object
from app.services.retrieval_constants import (
    ANCHOR_KIND_BOOST,
    ANCHOR_KINDS,
    BODY_FTS_WEIGHT,
    DEFAULT_FINAL_HITS,
    MAX_CANDIDATE_POOL,
    MAX_FINAL_HITS,
    MIN_BODY_FTS_THRESHOLD,
    MIN_HIT_SCORE,
    RECENCY_BONUS,
    RECENCY_WINDOW,
    RECENT_HORIZON_DAYS,
    SHORT_EXCERPT_MAX_CHARS,
    STRONG_TITLE_FTS_THRESHOLD,
    STRONG_TRIGRAM_THRESHOLD,
    TIME_SCOPE_ALL,
    TIME_SCOPE_AUTO,
    TIME_SCOPE_RECENT,
    TITLE_FTS_WEIGHT,
    TRIGRAM_WEIGHT,
    YEAR_HORIZON_DAYS,
)
from app.services.retrieval_models import RetrievalHit, RetrievalResult

_ANCHOR_KIND_SQL = ", ".join(f"'{kind}'" for kind in sorted(ANCHOR_KINDS))

_SCORE_QUERY_BASE = """
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
      AND (o.status IS NULL OR o.status != 'deleted')
      AND o.state != 'rejected'
      AND (
        to_tsvector('simple', coalesce(o.title, '')) @@ plainto_tsquery('simple', :query)
        OR to_tsvector('simple', coalesce(o.body, '')) @@ plainto_tsquery('simple', :query)
        OR similarity(coalesce(o.title, ''), :query) > 0.15
      )
"""


def _build_score_query(
    kind: str | None,
    provider: str | None,
    project_id: UUID | None,
    horizon_cutoff: datetime | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> text:
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
    if horizon_cutoff is not None:
        filters.append(
            """
            AND (
                o.kind NOT IN ('email', 'event', 'chat_message')
                OR (o.occurred_at IS NOT NULL AND o.occurred_at >= :horizon_cutoff)
            )
            """
        )
    if date_from is not None:
        if date_to is not None:
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
        else:
            filters.append(
                """
                AND (
                    o.kind NOT IN ('email', 'event', 'chat_message')
                    OR (o.occurred_at IS NOT NULL AND o.occurred_at >= :date_from)
                )
                """
            )

    sql = (
        _SCORE_QUERY_BASE
        + "".join(filters)
        + f"""
    ORDER BY (
        :title_weight * ts_rank(
            to_tsvector('simple', coalesce(o.title, '')),
            plainto_tsquery('simple', :query)
        )
        + :body_weight * ts_rank(
            to_tsvector('simple', coalesce(o.body, '')),
            plainto_tsquery('simple', :query)
        )
        + :trigram_weight * similarity(coalesce(o.title, ''), :query)
        + CASE WHEN o.kind IN ({_ANCHOR_KIND_SQL}) THEN :anchor_boost ELSE 0 END
        + CASE
            WHEN COALESCE(o.occurred_at, o.created_at) >= :recency_cutoff
            THEN :recency_bonus
            ELSE 0
          END
    ) DESC
    LIMIT :candidate_limit
    """
    )
    return text(sql)


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

        final_limit = max(1, min(limit, MAX_FINAL_HITS))
        now = datetime.now(UTC)
        recency_cutoff = now - RECENCY_WINDOW

        if date_from is not None or date_to is not None:
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

    def _score_and_rank(
        self,
        query: str,
        kind: str | None,
        provider: str | None,
        project_id: UUID | None,
        horizon_cutoff: datetime | None,
        date_from: datetime | None,
        date_to: datetime | None,
        recency_cutoff: datetime,
    ) -> list[RetrievalHit]:
        rows = self._session.execute(
            _build_score_query(
                kind=kind,
                provider=provider,
                project_id=project_id,
                horizon_cutoff=horizon_cutoff,
                date_from=date_from,
                date_to=date_to,
            ),
            {
                "query": query,
                "user_id": self._user_id,
                "kind": kind,
                "provider": provider,
                "project_id": project_id,
                "horizon_cutoff": horizon_cutoff,
                "date_from": date_from,
                "date_to": date_to,
                "title_weight": TITLE_FTS_WEIGHT,
                "body_weight": BODY_FTS_WEIGHT,
                "trigram_weight": TRIGRAM_WEIGHT,
                "anchor_boost": ANCHOR_KIND_BOOST,
                "recency_cutoff": recency_cutoff,
                "recency_bonus": RECENCY_BONUS,
                "candidate_limit": MAX_CANDIDATE_POOL,
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
            reference_time = occurred_at or created_at
            recency_signal = (
                reference_time is not None and reference_time >= recency_cutoff
            )

            relevance = (
                TITLE_FTS_WEIGHT * title_rank
                + BODY_FTS_WEIGHT * body_rank
                + TRIGRAM_WEIGHT * title_sim
                + (ANCHOR_KIND_BOOST if kind_value in ANCHOR_KINDS else 0.0)
                + (RECENCY_BONUS if recency_signal else 0.0)
            )

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
                    relevance=relevance,
                    reasons=reasons,
                    short_excerpt=_short_excerpt(
                        title=str(row["title"]),
                        body=row["body"],
                        max_chars=SHORT_EXCERPT_MAX_CHARS,
                    ),
                )
            )

        hits.sort(key=lambda item: item.relevance, reverse=True)
        return hits

    def _should_stop_horizon_expansion(self, hits: list[RetrievalHit]) -> bool:
        qualified = [hit for hit in hits if hit.relevance >= MIN_HIT_SCORE]
        if not qualified:
            return False
        return any(_is_strong_hit(hit) for hit in qualified)

    def _trim_to_limit(self, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        qualified = [hit for hit in hits if hit.relevance >= MIN_HIT_SCORE]
        return qualified[:limit]


def _is_strong_hit(hit: RetrievalHit) -> bool:
    if "title_match" in hit.reasons or "fuzzy_title" in hit.reasons:
        return True
    return "anchor_kind" in hit.reasons and hit.relevance >= MIN_HIT_SCORE


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
    if body_rank >= MIN_BODY_FTS_THRESHOLD:
        reasons.append("body_match")
    if title_sim >= STRONG_TRIGRAM_THRESHOLD:
        reasons.append("fuzzy_title")
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