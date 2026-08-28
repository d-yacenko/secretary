from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx

from app.connectors.yandex.constants import (
    CALENDAR_MULTIGET_BATCH_SIZE,
    DEFAULT_CALDAV_BASE_URL,
)
from app.connectors.yandex.errors import YandexCalDavError, YandexCalDavStaleSyncTokenError

DAV_NS = "DAV:"
CALDAV_NS = "urn:ietf:params:xml:ns:caldav"


def _format_caldav_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _find_children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _find_prop_value(prop: ET.Element, name: str) -> str | None:
    for child in prop:
        if _local_name(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def _status_text(element: ET.Element) -> str | None:
    status = _find_child(element, "status")
    if status is None or not status.text:
        return None
    return status.text.strip()


def _is_status_ok(status: str) -> bool:
    return status.endswith(" 200 OK")


def _is_status_not_found(status: str) -> bool:
    return status.endswith(" 404 Not Found")


def _is_status_insufficient_storage(status: str) -> bool:
    return status.endswith(" 507 Insufficient Storage")


def _ok_propstat(propstat: ET.Element) -> bool:
    status = _status_text(propstat)
    return status is not None and _is_status_ok(status)


def _is_stale_sync_token_response(status_code: int, body: str) -> bool:
    if status_code not in {403, 409}:
        return False
    body_lower = body.lower()
    if "valid-sync-token" in body_lower:
        return True
    if "sync-token" in body_lower and "invalid" in body_lower:
        return True
    return False


def _parse_multistatus_root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise YandexCalDavError("caldav response xml malformed") from exc


def _merge_ok_prop_values(response: ET.Element) -> dict[str, str]:
    merged: dict[str, str] = {}
    for propstat in _find_children(response, "propstat"):
        if not _ok_propstat(propstat):
            continue
        prop = _find_child(propstat, "prop")
        if prop is None:
            continue
        for child in prop:
            name = _local_name(child.tag)
            if name in {"displayname", "getetag", "sync-token", "calendar-data"}:
                value = (child.text or "").strip()
                if value:
                    merged[name] = value
            if name == "resourcetype":
                merged["resourcetype"] = "calendar" if any(
                    _local_name(grandchild.tag) == "calendar" for grandchild in child
                ) else ""
    return merged


@dataclass(frozen=True)
class CalDavCalendar:
    href: str
    display_name: str | None
    sync_token: str | None


@dataclass(frozen=True)
class CalDavEventRef:
    event_href: str
    etag: str | None


@dataclass(frozen=True)
class CalDavEvent:
    event_href: str
    etag: str | None
    calendar_data: str


@dataclass(frozen=True)
class CalDavFetchResult:
    events: list[CalDavEvent]
    sync_token: str | None
    deleted_hrefs: list[str] = field(default_factory=list)
    truncated: bool = False


class CalDavTransport(Protocol):
    def discover_calendars(self, max_results: int) -> list[CalDavCalendar]:
        ...

    def query_events(
        self,
        calendar_href: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> CalDavFetchResult:
        ...

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
        time_min: datetime,
        time_max: datetime,
    ) -> CalDavFetchResult:
        ...


class CalDavHttpTransport:
    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = DEFAULT_CALDAV_BASE_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=30.0)
        self.last_request_depth: str | None = None
        self.last_request_path: str | None = None
        self.last_request_body: str | None = None
        self.last_multiget_body: str | None = None

    def _principal_path(self) -> str:
        return f"/principals/users/{self._email}/"

    def _request(self, method: str, path: str, body: str, depth: str | None = None) -> str:
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": depth or "0",
        }
        self.last_request_depth = headers["Depth"]
        self.last_request_path = path
        self.last_request_body = body
        url = urljoin(self._base_url + "/", path.lstrip("/"))
        response = self._http.request(
            method,
            url,
            content=body.encode("utf-8"),
            headers=headers,
            auth=(self._email, self._password),
        )
        if response.status_code >= 400:
            if "sync-collection" in body and _is_stale_sync_token_response(
                response.status_code, response.text
            ):
                raise YandexCalDavStaleSyncTokenError(f"caldav sync-token invalid for {path}")
            raise YandexCalDavError(f"caldav request failed for {path}")
        return response.text

    def discover_calendars(self, max_results: int) -> list[CalDavCalendar]:
        principal_path = self._principal_path()
        principal_body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            "<d:prop><c:calendar-home-set/></d:prop>"
            "</d:propfind>"
        )
        principal_xml = self._request("PROPFIND", principal_path, principal_body, depth="0")
        calendar_home = self._parse_calendar_home_set(principal_xml)
        if not calendar_home:
            raise YandexCalDavError("caldav calendar-home-set missing")

        home_body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            "<d:prop>"
            "<d:displayname/>"
            "<d:resourcetype/>"
            "<d:sync-token/>"
            "</d:prop>"
            "</d:propfind>"
        )
        home_xml = self._request("PROPFIND", calendar_home, home_body, depth="1")
        calendars = self._parse_calendar_multistatus(home_xml, calendar_home)
        return calendars[:max_results]

    def query_events(
        self,
        calendar_href: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> CalDavFetchResult:
        refs, sync_token, deleted, truncated = self._query_event_refs(
            calendar_href=calendar_href,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
        events = self._multiget_events(
            calendar_href=calendar_href,
            refs=refs,
            time_min=time_min,
            time_max=time_max,
        )
        return CalDavFetchResult(
            events=events,
            sync_token=sync_token,
            deleted_hrefs=deleted,
            truncated=truncated,
        )

    def _query_event_refs(
        self,
        calendar_href: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> tuple[list[CalDavEventRef], str | None, list[str], bool]:
        start = _format_caldav_time(time_min)
        end = _format_caldav_time(time_max)
        # Yandex CalDAV rejects calendar-query with c:expand (400).
        body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<c:calendar-query xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            "<d:prop><d:getetag/></d:prop>"
            f"<c:filter><c:comp-filter name='VCALENDAR'>"
            f"<c:comp-filter name='VEVENT'>"
            f"<c:time-range start='{start}' end='{end}'/>"
            "</c:comp-filter></c:comp-filter></c:filter>"
            "</c:calendar-query>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="1")
        refs, sync_token, deleted, truncated = self._parse_href_multistatus(xml)
        if len(refs) > max_results:
            refs = sorted(refs, key=lambda item: item.event_href)[:max_results]
        return refs, sync_token, deleted, truncated

    def _multiget_events(
        self,
        calendar_href: str,
        refs: list[CalDavEventRef],
        time_min: datetime,
        time_max: datetime,
    ) -> list[CalDavEvent]:
        if not refs:
            return []
        start = _format_caldav_time(time_min)
        end = _format_caldav_time(time_max)
        events: list[CalDavEvent] = []
        batch_size = CALENDAR_MULTIGET_BATCH_SIZE
        for offset in range(0, len(refs), batch_size):
            batch = refs[offset : offset + batch_size]
            href_elements = "".join(f"<d:href>{ref.event_href}</d:href>" for ref in batch)
            body = (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<c:calendar-multiget xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
                "<d:prop>"
                "<d:getetag/>"
                "<c:calendar-data>"
                f"<c:expand start='{start}' end='{end}'/>"
                "</c:calendar-data>"
                "</d:prop>"
                f"{href_elements}"
                "</c:calendar-multiget>"
            )
            self.last_multiget_body = body
            xml = self._request("REPORT", calendar_href, body, depth="1")
            batch_events, _, _, _ = self._parse_event_multistatus(xml)
            events.extend(batch_events)
        return events

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
        time_min: datetime,
        time_max: datetime,
    ) -> CalDavFetchResult:
        start = _format_caldav_time(time_min)
        end = _format_caldav_time(time_max)
        body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<d:sync-collection xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            f"<d:sync-token>{sync_token}</d:sync-token>"
            "<d:sync-level>1</d:sync-level>"
            f"<d:limit><d:nresults>{max_results}</d:nresults></d:limit>"
            "<d:prop>"
            "<d:getetag/>"
            "<c:calendar-data>"
            f"<c:expand start='{start}' end='{end}'/>"
            "</c:calendar-data>"
            "</d:prop>"
            "</d:sync-collection>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="0")
        events, new_token, deleted, truncated = self._parse_event_multistatus(xml)
        if len(events) > max_results and not truncated:
            raise YandexCalDavError("caldav sync-collection exceeded requested result limit")
        return CalDavFetchResult(
            events=events,
            sync_token=new_token,
            deleted_hrefs=deleted,
            truncated=truncated,
        )

    def _parse_calendar_home_set(self, xml_text: str) -> str | None:
        root = _parse_multistatus_root(xml_text)
        for response in root:
            if _local_name(response.tag) != "response":
                continue
            for propstat in _find_children(response, "propstat"):
                if not _ok_propstat(propstat):
                    continue
                prop = _find_child(propstat, "prop")
                if prop is None:
                    continue
                for child in prop:
                    if _local_name(child.tag) == "calendar-home-set":
                        for href_el in child:
                            if _local_name(href_el.tag) == "href" and href_el.text:
                                return href_el.text.strip()
        return None

    def _parse_calendar_multistatus(self, xml_text: str, home_href: str) -> list[CalDavCalendar]:
        root = _parse_multistatus_root(xml_text)
        calendars: list[CalDavCalendar] = []
        for response in root:
            if _local_name(response.tag) != "response":
                continue
            href_el = _find_child(response, "href")
            if href_el is None or not href_el.text:
                continue
            href = href_el.text.strip()
            if href.rstrip("/") == home_href.rstrip("/"):
                continue
            merged = _merge_ok_prop_values(response)
            if merged.get("resourcetype") != "calendar":
                continue
            calendars.append(
                CalDavCalendar(
                    href=href,
                    display_name=merged.get("displayname"),
                    sync_token=merged.get("sync-token"),
                )
            )
        return calendars

    def _parse_href_multistatus(
        self, xml_text: str
    ) -> tuple[list[CalDavEventRef], str | None, list[str], bool]:
        root = _parse_multistatus_root(xml_text)
        refs: list[CalDavEventRef] = []
        deleted: list[str] = []
        sync_token: str | None = None
        truncated = False
        for child in root:
            tag = _local_name(child.tag)
            if tag == "sync-token" and child.text:
                sync_token = child.text.strip()
            if tag != "response":
                continue
            href_el = _find_child(child, "href")
            if href_el is None or not href_el.text:
                continue
            event_href = href_el.text.strip()
            response_status = _status_text(child)
            if response_status is not None and _is_status_not_found(response_status):
                deleted.append(event_href)
                continue
            if response_status is not None and _is_status_insufficient_storage(response_status):
                truncated = True
                continue
            merged = _merge_ok_prop_values(child)
            refs.append(
                CalDavEventRef(
                    event_href=event_href,
                    etag=merged.get("getetag"),
                )
            )
        return refs, sync_token, deleted, truncated

    def _parse_event_multistatus(
        self, xml_text: str
    ) -> tuple[list[CalDavEvent], str | None, list[str], bool]:
        root = _parse_multistatus_root(xml_text)
        events: list[CalDavEvent] = []
        deleted: list[str] = []
        sync_token: str | None = None
        truncated = False
        for child in root:
            tag = _local_name(child.tag)
            if tag == "sync-token" and child.text:
                sync_token = child.text.strip()
            if tag != "response":
                continue
            href_el = _find_child(child, "href")
            if href_el is None or not href_el.text:
                continue
            event_href = href_el.text.strip()
            response_status = _status_text(child)
            if response_status is not None and _is_status_not_found(response_status):
                deleted.append(event_href)
                continue
            if response_status is not None and _is_status_insufficient_storage(response_status):
                truncated = True
                continue
            merged = _merge_ok_prop_values(child)
            calendar_data = merged.get("calendar-data")
            if not calendar_data:
                continue
            events.append(
                CalDavEvent(
                    event_href=event_href,
                    etag=merged.get("getetag"),
                    calendar_data=calendar_data,
                )
            )
        return events, sync_token, deleted, truncated


def _parse_dtstart_from_ical(calendar_data: str) -> datetime | None:
    for line in calendar_data.splitlines():
        if not line.startswith("DTSTART"):
            continue
        value = line.split(":", 1)[1].strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


class FakeCalDavTransport:
    def __init__(
        self,
        calendars: list[CalDavCalendar] | None = None,
        query_events_by_calendar: dict[str, list[CalDavEvent]] | None = None,
        multiget_events_by_calendar: dict[str, dict[str, CalDavEvent]] | None = None,
        sync_batches_by_calendar: dict[str, dict[str, CalDavFetchResult]] | None = None,
        sync_tokens_by_calendar: dict[str, str] | None = None,
        stale_sync_tokens: set[str] | None = None,
        tx_checker: object | None = None,
        calendar_order: list[str] | None = None,
    ) -> None:
        self._calendars = calendars or []
        self._query_events = query_events_by_calendar or {}
        self._multiget_events = multiget_events_by_calendar or {}
        self._sync_batches = sync_batches_by_calendar or {}
        self._sync_tokens = sync_tokens_by_calendar or {}
        self._stale_sync_tokens = stale_sync_tokens or set()
        self._calendar_order = calendar_order
        self.sync_collection_calls: list[tuple[str, str, int]] = []
        self.query_calls: list[str] = []
        self.multiget_calls: list[tuple[str, list[str]]] = []
        self.discover_calls = 0
        self._tx_checker = tx_checker

    def _check_tx(self) -> None:
        if self._tx_checker is not None:
            assert not self._tx_checker()

    def discover_calendars(self, max_results: int) -> list[CalDavCalendar]:
        self._check_tx()
        self.discover_calls += 1
        if self._calendar_order is not None:
            href_map = {calendar.href: calendar for calendar in self._calendars}
            ordered = [href_map[href] for href in self._calendar_order if href in href_map]
            return ordered[:max_results]
        return self._calendars[:max_results]

    def query_events(
        self,
        calendar_href: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> CalDavFetchResult:
        self._check_tx()
        self.query_calls.append(calendar_href)
        source_events = sorted(
            self._query_events.get(calendar_href, []), key=lambda item: item.event_href
        )
        refs = [
            CalDavEventRef(event_href=event.event_href, etag=event.etag)
            for event in source_events
            if self._event_in_time_range(event, time_min, time_max)
        ]
        if len(refs) > max_results:
            refs = refs[:max_results]
        expanded_events = self._multiget_from_refs(calendar_href, refs)
        token = self._sync_tokens.get(calendar_href)
        return CalDavFetchResult(events=expanded_events, sync_token=token)

    def _multiget_from_refs(
        self, calendar_href: str, refs: list[CalDavEventRef]
    ) -> list[CalDavEvent]:
        if not refs:
            return []
        self.multiget_calls.append((calendar_href, [ref.event_href for ref in refs]))
        multiget_map = self._multiget_events.get(calendar_href, {})
        source_map = {
            event.event_href: event for event in self._query_events.get(calendar_href, [])
        }
        events: list[CalDavEvent] = []
        for ref in refs:
            if ref.event_href in multiget_map:
                events.append(multiget_map[ref.event_href])
            elif ref.event_href in source_map:
                events.append(source_map[ref.event_href])
        return events

    def _event_in_time_range(
        self,
        event: CalDavEvent,
        time_min: datetime,
        time_max: datetime,
    ) -> bool:
        start = _parse_dtstart_from_ical(event.calendar_data)
        if start is None:
            return True
        return time_min <= start <= time_max

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
        time_min: datetime,
        time_max: datetime,
    ) -> CalDavFetchResult:
        self._check_tx()
        if sync_token in self._stale_sync_tokens:
            self.sync_collection_calls.append((calendar_href, sync_token, max_results))
            raise YandexCalDavStaleSyncTokenError("caldav sync-token invalid")
        self.sync_collection_calls.append((calendar_href, sync_token, max_results))
        batches = self._sync_batches.get(calendar_href, {})
        if sync_token in batches:
            result = batches[sync_token]
            if len(result.events) > max_results and not result.truncated:
                raise YandexCalDavError("caldav sync-collection exceeded requested result limit")
            return result
        events: list[CalDavEvent] = []
        token = self._sync_tokens.get(calendar_href, sync_token)
        return CalDavFetchResult(events=events, sync_token=token)
