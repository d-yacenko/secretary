from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.mattermost.constants import (
    DEFAULT_INITIAL_POSTS_PER_CHANNEL,
    DEFAULT_MAX_CHANNELS,
    DEFAULT_MAX_POSTS_PER_RUN,
    DEFAULT_SYNC_DAYS,
    DEFAULT_SYNC_OVERLAP_SECONDS,
    MAX_INITIAL_POSTS_PER_CHANNEL,
    MAX_MAX_CHANNELS,
    MAX_MAX_POSTS_PER_RUN,
    MAX_SYNC_DAYS,
    MAX_SYNC_OVERLAP_SECONDS,
)
from app.connectors.mattermost.credentials import MattermostAccountStore, MattermostSyncSnapshot
from app.connectors.mattermost.errors import (
    MattermostConnectorError,
    MattermostEndpointNotFoundError,
)
from app.connectors.mattermost.normalize import (
    MattermostChannelContext,
    normalize_mattermost_post,
)
from app.connectors.mattermost.transport import MattermostHttpTransport, MattermostTransport
from app.db.models import Object
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _SyncTotals:
    synchronized: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    jobs_enqueued: int = 0


class MattermostSyncService:
    def __init__(
        self,
        session: Session,
        account_store: MattermostAccountStore,
        job_queue: JobQueueService,
        sync_days: int = DEFAULT_SYNC_DAYS,
        max_channels: int = DEFAULT_MAX_CHANNELS,
        initial_posts_per_channel: int = DEFAULT_INITIAL_POSTS_PER_CHANNEL,
        max_posts_per_run: int = DEFAULT_MAX_POSTS_PER_RUN,
        overlap_seconds: int = DEFAULT_SYNC_OVERLAP_SECONDS,
        transport_factory: Callable[[MattermostSyncSnapshot], MattermostTransport] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._job_queue = job_queue
        self._sync_days = min(max(sync_days, 1), MAX_SYNC_DAYS)
        self._max_channels = min(max(max_channels, 1), MAX_MAX_CHANNELS)
        self._initial_posts_per_channel = min(
            max(initial_posts_per_channel, 1),
            MAX_INITIAL_POSTS_PER_CHANNEL,
        )
        self._max_posts_per_run = min(max(max_posts_per_run, 1), MAX_MAX_POSTS_PER_RUN)
        self._overlap_seconds = min(max(overlap_seconds, 0), MAX_SYNC_OVERLAP_SECONDS)
        self._transport_factory = transport_factory
        self._now_factory = now_factory or utcnow

    def sync_account(self, account_id: UUID, user_id: UUID) -> dict[str, Any]:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise MattermostConnectorError("mattermost account not found")

        snapshot = self._account_store.load_sync_snapshot(
            account_id=account_id,
            user_id=user_id,
            normalized_server_url=account.server_url,
        )
        if snapshot is None:
            raise MattermostConnectorError("mattermost account not found")

        self._session.commit()
        transport = self._open_transport(snapshot)
        owns_transport = self._should_close_transport(transport)
        try:
            now = self._now_factory()
            cutoff = now - timedelta(days=self._sync_days)
            cutoff_ms = int(cutoff.timestamp() * 1000)

            channels = self._discover_channels(transport, snapshot.remote_user_id)
            teams_by_id = self._build_teams_index(transport)

            sync_state_root = dict(snapshot.sync_state or {})
            channel_state_root = dict(sync_state_root.get("channels", {}))

            posts_budget = self._max_posts_per_run
            totals = _SyncTotals()

            for channel in channels[: self._max_channels]:
                if posts_budget <= 0:
                    break
                channel_id = str(channel.get("id") or "").strip()
                if not channel_id:
                    continue
                stored = dict(channel_state_root.get(channel_id, {}))
                channel_context = self._build_channel_context(channel, teams_by_id)

                if stored.get("bootstrap_complete"):
                    posts_budget, stored, batch = self._sync_new_posts(
                        transport=transport,
                        snapshot=snapshot,
                        channel_context=channel_context,
                        stored=stored,
                        cutoff_ms=cutoff_ms,
                        posts_budget=posts_budget,
                    )
                else:
                    posts_budget, stored, batch = self._sync_bootstrap(
                        transport=transport,
                        snapshot=snapshot,
                        channel_context=channel_context,
                        stored=stored,
                        cutoff_ms=cutoff_ms,
                        posts_budget=posts_budget,
                    )
                self._merge_totals(totals, batch)

                if posts_budget > 0:
                    posts_budget, stored, batch = self._sync_edit_sweep(
                        transport=transport,
                        snapshot=snapshot,
                        channel_context=channel_context,
                        stored=stored,
                        cutoff_ms=cutoff_ms,
                        posts_budget=posts_budget,
                    )
                    self._merge_totals(totals, batch)

                channel_state_root[channel_id] = stored

            account = self._account_store.get_by_id_for_user(account_id, user_id)
            if account is None:
                raise MattermostConnectorError("mattermost account not found")
            updated_state = dict(sync_state_root)
            updated_state["channels"] = channel_state_root
            self._account_store.update_sync_state(account, updated_state)
            self._session.commit()

            return {
                "account_username": snapshot.username,
                "server_url": snapshot.server_url,
                "synchronized": totals.synchronized,
                "created": totals.created,
                "updated": totals.updated,
                "unchanged": totals.unchanged,
                "jobs_enqueued": totals.jobs_enqueued,
            }
        finally:
            if owns_transport:
                transport.close()

    def _discover_channels(
        self,
        transport: MattermostTransport,
        remote_user_id: str,
    ) -> list[dict[str, Any]]:
        try:
            channels = transport.list_my_channels()
        except MattermostEndpointNotFoundError:
            channels = self._discover_channels_via_teams(transport, remote_user_id)

        deduped: dict[str, dict[str, Any]] = {}
        for channel in channels:
            channel_id = str(channel.get("id") or "").strip()
            if channel_id:
                deduped[channel_id] = channel

        sorted_channels = sorted(
            deduped.values(),
            key=lambda item: int(item.get("last_post_at") or 0),
            reverse=True,
        )
        return sorted_channels

    def _discover_channels_via_teams(
        self,
        transport: MattermostTransport,
        remote_user_id: str,
    ) -> list[dict[str, Any]]:
        teams = transport.list_my_teams()
        discovered: dict[str, dict[str, Any]] = {}
        for team in teams:
            team_id = str(team.get("id") or "").strip()
            if not team_id:
                continue
            team_channels = transport.list_team_channels_for_user(team_id, remote_user_id)
            for channel in team_channels:
                channel_id = str(channel.get("id") or "").strip()
                if channel_id:
                    discovered[channel_id] = channel
        return list(discovered.values())

    def _build_teams_index(self, transport: MattermostTransport) -> dict[str, dict[str, Any]]:
        teams = transport.list_my_teams()
        index: dict[str, dict[str, Any]] = {}
        for team in teams:
            team_id = str(team.get("id") or "").strip()
            if team_id:
                index[team_id] = team
        return index

    def _build_channel_context(
        self,
        channel: dict[str, Any],
        teams_by_id: dict[str, dict[str, Any]],
    ) -> MattermostChannelContext:
        team_id = str(channel.get("team_id") or "").strip() or None
        team = teams_by_id.get(team_id) if team_id else None
        return MattermostChannelContext(
            channel_id=str(channel.get("id") or ""),
            channel_name=str(channel.get("name") or "").strip() or None,
            channel_display_name=str(channel.get("display_name") or "").strip() or None,
            channel_type=str(channel.get("type") or "").strip() or None,
            team_id=team_id,
            team_name=str(team.get("name") or "").strip() if team else None,
            team_display_name=str(team.get("display_name") or "").strip() if team else None,
        )

    def _sync_bootstrap(
        self,
        transport: MattermostTransport,
        snapshot: MattermostSyncSnapshot,
        channel_context: MattermostChannelContext,
        stored: dict[str, Any],
        cutoff_ms: int,
        posts_budget: int,
    ) -> tuple[int, dict[str, Any], _SyncTotals]:
        page = transport.get_posts_page(
            channel_id=channel_context.channel_id,
            page=0,
            per_page=self._initial_posts_per_channel,
        )
        posts = self._ordered_posts(page, cutoff_ms=cutoff_ms)
        totals, posts_budget, last_anchor = self._process_posts(
            transport=transport,
            snapshot=snapshot,
            channel_context=channel_context,
            posts=posts,
            posts_budget=posts_budget,
        )
        if last_anchor is not None:
            stored["last_processed_post_id"] = last_anchor["post_id"]
            stored["last_processed_create_at_ms"] = last_anchor["create_at_ms"]
        stored["bootstrap_complete"] = True
        return posts_budget, stored, totals

    def _sync_new_posts(
        self,
        transport: MattermostTransport,
        snapshot: MattermostSyncSnapshot,
        channel_context: MattermostChannelContext,
        stored: dict[str, Any],
        cutoff_ms: int,
        posts_budget: int,
    ) -> tuple[int, dict[str, Any], _SyncTotals]:
        anchor_id = str(stored.get("last_processed_post_id") or "").strip()
        if not anchor_id:
            return self._sync_bootstrap(
                transport=transport,
                snapshot=snapshot,
                channel_context=channel_context,
                stored=stored,
                cutoff_ms=cutoff_ms,
                posts_budget=posts_budget,
            )

        page = transport.get_posts_after(
            channel_id=channel_context.channel_id,
            after_post_id=anchor_id,
            per_page=min(posts_budget, self._initial_posts_per_channel),
        )
        posts = self._ordered_posts(page, cutoff_ms=cutoff_ms)
        totals, posts_budget, last_anchor = self._process_posts(
            transport=transport,
            snapshot=snapshot,
            channel_context=channel_context,
            posts=posts,
            posts_budget=posts_budget,
        )
        if last_anchor is not None:
            stored["last_processed_post_id"] = last_anchor["post_id"]
            stored["last_processed_create_at_ms"] = last_anchor["create_at_ms"]
        return posts_budget, stored, totals

    def _sync_edit_sweep(
        self,
        transport: MattermostTransport,
        snapshot: MattermostSyncSnapshot,
        channel_context: MattermostChannelContext,
        stored: dict[str, Any],
        cutoff_ms: int,
        posts_budget: int,
    ) -> tuple[int, dict[str, Any], _SyncTotals]:
        watermark_ms = stored.get("edit_sweep_watermark_ms")
        if watermark_ms is None:
            watermark_ms = cutoff_ms
        since_ms = int(watermark_ms) - self._overlap_seconds * 1000

        page = transport.get_posts_since(
            channel_id=channel_context.channel_id,
            since_ms=since_ms,
        )
        posts = self._ordered_posts(page, cutoff_ms=None)
        totals = _SyncTotals()
        if not posts:
            return posts_budget, stored, totals

        processed_all = True
        max_processed_update_ms: int | None = None

        author_map = self._resolve_authors(transport, posts)
        for post in posts:
            if posts_budget <= 0:
                processed_all = False
                break
            change = self._upsert_post(
                snapshot=snapshot,
                channel_context=channel_context,
                post=post,
                author_map=author_map,
            )
            totals.synchronized += 1
            if change == "created":
                totals.created += 1
                totals.jobs_enqueued += 1
                posts_budget -= 1
            elif change == "updated":
                totals.updated += 1
                totals.jobs_enqueued += 1
                posts_budget -= 1
            elif change == "metadata_updated":
                totals.updated += 1
            else:
                totals.unchanged += 1
            update_at_ms = int(post.get("update_at") or post.get("create_at") or 0)
            if max_processed_update_ms is None:
                max_processed_update_ms = update_at_ms
            else:
                max_processed_update_ms = max(max_processed_update_ms, update_at_ms)
            self._session.commit()

        can_advance = (
            processed_all
            and not page.provider_saturated
            and max_processed_update_ms is not None
        )
        if can_advance:
            stored["edit_sweep_watermark_ms"] = max_processed_update_ms

        return posts_budget, stored, totals

    def _process_posts(
        self,
        transport: MattermostTransport,
        snapshot: MattermostSyncSnapshot,
        channel_context: MattermostChannelContext,
        posts: list[dict[str, Any]],
        posts_budget: int,
    ) -> tuple[_SyncTotals, int, dict[str, int] | None]:
        totals = _SyncTotals()
        last_anchor: dict[str, int] | None = None
        author_map = self._resolve_authors(transport, posts)

        for post in posts:
            if posts_budget <= 0:
                break
            change = self._upsert_post(
                snapshot=snapshot,
                channel_context=channel_context,
                post=post,
                author_map=author_map,
            )
            totals.synchronized += 1
            if change == "created":
                totals.created += 1
                totals.jobs_enqueued += 1
                posts_budget -= 1
            elif change == "updated":
                totals.updated += 1
                totals.jobs_enqueued += 1
                posts_budget -= 1
            elif change == "metadata_updated":
                totals.updated += 1
            else:
                totals.unchanged += 1

            post_id = str(post.get("id") or "").strip()
            create_at_ms = int(post.get("create_at") or 0)
            if post_id:
                last_anchor = {"post_id": post_id, "create_at_ms": create_at_ms}
            self._session.commit()

        return totals, posts_budget, last_anchor

    def _ordered_posts(
        self,
        page: Any,
        cutoff_ms: int | None,
    ) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        for post_id in page.order:
            post = page.posts.get(post_id)
            if not isinstance(post, dict):
                continue
            create_at_ms = int(post.get("create_at") or 0)
            if cutoff_ms is not None and create_at_ms < cutoff_ms:
                continue
            posts.append(post)
        posts.sort(key=lambda item: int(item.get("create_at") or 0))
        return posts

    def _resolve_authors(
        self,
        transport: MattermostTransport,
        posts: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        user_ids: list[str] = []
        seen: set[str] = set()
        for post in posts:
            user_id = str(post.get("user_id") or "").strip()
            if user_id and user_id not in seen:
                seen.add(user_id)
                user_ids.append(user_id)
        users = transport.get_users_by_ids(user_ids)
        return {
            str(user.get("id") or ""): user
            for user in users
            if str(user.get("id") or "").strip()
        }

    def _upsert_post(
        self,
        snapshot: MattermostSyncSnapshot,
        channel_context: MattermostChannelContext,
        post: dict[str, Any],
        author_map: dict[str, dict[str, Any]],
    ) -> str:
        author_id = str(post.get("user_id") or "").strip()
        author = author_map.get(author_id)
        normalized = normalize_mattermost_post(
            post=post,
            normalized_server_url=snapshot.normalized_server_url,
            account_id=snapshot.account_id,
            channel=channel_context,
            author=author,
        )
        if normalized is None:
            return "unchanged"

        existing = self._find_existing(snapshot.user_id, normalized["external_id"])
        if existing is None:
            obj = Object(
                user_id=snapshot.user_id,
                kind=normalized["kind"],
                provider=normalized["provider"],
                external_id=normalized["external_id"],
                origin=normalized["origin"],
                state=normalized["state"],
                title=normalized["title"],
                body=normalized.get("body"),
                metadata_=normalized["metadata"],
                occurred_at=normalized.get("occurred_at"),
            )
            self._session.add(obj)
            self._session.flush()
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(obj.id)},
                user_id=snapshot.user_id,
            )
            return "created"

        object_changed = self._object_changed(existing, normalized)
        if not object_changed:
            return "unchanged"

        semantic_changed = self._semantic_content_changed(existing, normalized)
        self._apply_normalized(existing, normalized)
        if semantic_changed:
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(existing.id)},
                user_id=snapshot.user_id,
            )
            return "updated"
        return "metadata_updated"

    def _find_existing(self, user_id: UUID, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == user_id,
                Object.provider == "mattermost",
                Object.kind == "chat_message",
                Object.external_id == external_id,
            )
        )

    def _object_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.title != normalized["title"]:
            return True
        if obj.body != normalized.get("body"):
            return True
        if obj.occurred_at != normalized.get("occurred_at"):
            return True
        return obj.metadata_ != normalized["metadata"]

    def _semantic_content_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.title != normalized["title"]:
            return True
        return obj.body != normalized.get("body")

    def _apply_normalized(self, obj: Object, normalized: dict[str, Any]) -> None:
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.metadata_ = normalized["metadata"]
        obj.occurred_at = normalized.get("occurred_at")

    def _merge_totals(self, totals: _SyncTotals, batch: _SyncTotals) -> None:
        totals.synchronized += batch.synchronized
        totals.created += batch.created
        totals.updated += batch.updated
        totals.unchanged += batch.unchanged
        totals.jobs_enqueued += batch.jobs_enqueued

    def _should_close_transport(self, transport: MattermostTransport) -> bool:
        if self._transport_factory is not None:
            return False
        return isinstance(transport, MattermostHttpTransport)

    def _open_transport(self, snapshot: MattermostSyncSnapshot) -> MattermostTransport:
        if self._transport_factory is not None:
            return self._transport_factory(snapshot)
        return MattermostHttpTransport(
            base_url=snapshot.normalized_server_url,
            access_token=snapshot.access_token,
        )


def build_mattermost_sync_service(
    session: Session,
    credential_key: str,
    sync_days: int,
    max_channels: int,
    initial_posts_per_channel: int,
    max_posts_per_run: int,
    overlap_seconds: int,
    transport_factory: Callable[[MattermostSyncSnapshot], MattermostTransport] | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> MattermostSyncService:
    account_store = MattermostAccountStore(
        session,
        MattermostAccountStore.build_encryption(credential_key),
    )
    job_queue = JobQueueService(session)
    return MattermostSyncService(
        session=session,
        account_store=account_store,
        job_queue=job_queue,
        sync_days=sync_days,
        max_channels=max_channels,
        initial_posts_per_channel=initial_posts_per_channel,
        max_posts_per_run=max_posts_per_run,
        overlap_seconds=overlap_seconds,
        transport_factory=transport_factory,
        now_factory=now_factory,
    )
