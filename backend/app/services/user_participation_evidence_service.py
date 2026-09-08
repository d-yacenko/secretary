"""Project current-user participation from normalized Object metadata.

Output is factual provider-neutral roles only. No relationship/dependency
inference. No fuzzy name matching. No body keyword scans.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any

from app.db.models import Object
from app.personal_relevance.models import (
    PERSONAL_RELEVANCE_MAX_PARTICIPATION_ROLES,
    USER_PARTICIPATION_ROLES,
)

_EMAIL_PROVIDERS = frozenset({"gmail", "yandex_mail"})
_CALENDAR_PROVIDERS = frozenset({"google_calendar", "yandex_calendar"})
_INTERNAL_AUTHOR_KINDS = frozenset({"task", "note"})


@dataclass(frozen=True)
class ParticipationIdentity:
    emails: frozenset[str]
    mattermost_user_ids: frozenset[str]
    mattermost_usernames: frozenset[str]
    has_google_account: bool
    has_yandex_calendar_account: bool


def extract_email_address(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    _, addr = parseaddr(stripped)
    candidate = (addr or "").strip()
    if not candidate and "@" in stripped and "<" not in stripped:
        candidate = stripped
    candidate = candidate.strip().strip("<>").strip()
    if "@" not in candidate or any(ch.isspace() for ch in candidate):
        return None
    local, _, domain = candidate.partition("@")
    if not local or not domain or "." not in domain:
        return None
    return candidate.casefold()


def current_user_participation_roles(
    obj: Object,
    identity: ParticipationIdentity,
) -> tuple[str, ...]:
    roles: set[str] = set()
    metadata = obj.metadata_ if isinstance(obj.metadata_, dict) else {}
    provider = obj.provider

    if obj.origin == "user" and obj.kind in _INTERNAL_AUTHOR_KINDS:
        roles.add("author")

    if provider in _EMAIL_PROVIDERS:
        sender = extract_email_address(metadata.get("sender"))
        if sender is not None and sender in identity.emails:
            roles.add("sender")
        for recipient in _string_items(metadata.get("recipients")):
            email = extract_email_address(recipient)
            if email is not None and email in identity.emails:
                roles.add("direct_recipient")
                break
        for copied in _string_items(metadata.get("cc")):
            email = extract_email_address(copied)
            if email is not None and email in identity.emails:
                roles.add("copied_recipient")
                break

    if provider in _CALENDAR_PROVIDERS:
        organizer = extract_email_address(metadata.get("organizer"))
        if organizer is not None and organizer in identity.emails:
            roles.add("organizer")
        if _truthy_flag(metadata.get("organizer_self")) and _calendar_self_trusted(
            provider, identity
        ):
            roles.add("organizer")
        for attendee in _attendee_entries(metadata.get("attendees")):
            email = extract_email_address(attendee.get("email"))
            self_flag = _truthy_flag(attendee.get("self"))
            if (email is not None and email in identity.emails) or (
                self_flag and _calendar_self_trusted(provider, identity)
            ):
                roles.add("attendee")
            if self_flag and _truthy_flag(attendee.get("organizer")) and _calendar_self_trusted(
                provider, identity
            ):
                roles.add("organizer")

    if provider == "mattermost":
        author_user_id = _scalar_str(metadata.get("author_user_id"))
        if author_user_id and author_user_id in identity.mattermost_user_ids:
            roles.add("author")
        author_username = _scalar_str(metadata.get("author_username"))
        if author_username and author_username.casefold() in identity.mattermost_usernames:
            roles.add("author")
        for mention in _string_items(metadata.get("mentioned_user_ids")):
            if mention in identity.mattermost_user_ids:
                roles.add("mentioned")
                break
        for mention in _string_items(metadata.get("mentioned_usernames")):
            if mention.casefold() in identity.mattermost_usernames:
                roles.add("mentioned")
                break

    assignee = _first_assignee_email(metadata)
    if assignee is not None and assignee in identity.emails:
        roles.add("assignee")

    ordered = [role for role in USER_PARTICIPATION_ROLES if role in roles]
    return tuple(ordered[:PERSONAL_RELEVANCE_MAX_PARTICIPATION_ROLES])


def _calendar_self_trusted(provider: str | None, identity: ParticipationIdentity) -> bool:
    if provider == "google_calendar":
        return identity.has_google_account
    if provider == "yandex_calendar":
        return identity.has_yandex_calendar_account
    return False


def _first_assignee_email(metadata: dict[str, Any]) -> str | None:
    for key in ("assignee", "assigned_to", "owner_email"):
        email = extract_email_address(metadata.get(key))
        if email is not None:
            return email
    return None


def _string_items(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _attendee_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            entries.append(item)
        elif isinstance(item, str):
            entries.append({"email": item})
    return entries


def _scalar_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _truthy_flag(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes"}
    return False
