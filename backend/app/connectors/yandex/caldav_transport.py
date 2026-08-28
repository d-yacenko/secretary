from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx

from app.connectors.yandex.constants import DEFAULT_CALDAV_BASE_URL
from app.connectors.yandex.errors import YandexCalDavError

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


def _ok_propstat(propstat: ET.Element) -> bool:
    status = _status_text(propstat)
    return status is not None and _is_status_ok(status)


def _parse_multistatus_root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise YandexCalDavError("caldav response xml malformed") from exc


@dataclass(frozen=True)
class CalDavCalendar:
    href: str
    display_name: str | None
    sync_token: str | None


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

    def _principal_path(self) -> str:
        return f"/principals/users/{self._email}/"

    def _request(self, method: str, path: str, body: str, depth: str | None = None) -> str:
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": depth or "0",
        }
        self.last_request_depth = headers["Depth"]
        self.last_request_path = path
        url = urljoin(self._base_url + "/", path.lstrip("/"))
        response = self._http.request(
            method,
            url,
            content=body.encode("utf-8"),
            headers=headers,
            auth=(self._email, self._password),
        )
        if response.status_code >= 400:
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
        start = _format_caldav_time(time_min)
        end = _format_caldav_time(time_max)
        body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<c:calendar-query xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            "<d:prop>"
            "<d:getetag/>"
            "<c:calendar-data>"
            f"<c:expand start='{start}' end='{end}'/>"
            "</c:calendar-data>"
            "</d:prop>"
            f"<c:filter><c:comp-filter name='VCALENDAR'>"
            f"<c:comp-filter name='VEVENT'>"
            f"<c:time-range start='{start}' end='{end}'/>"
            "</c:comp-filter></c:comp-filter>"
            "</c:calendar-query>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="1")
        events, sync_token, deleted = self._parse_event_multistatus(xml)
        if len(events) > max_results:
            raise YandexCalDavError("caldav query exceeded requested result limit")
        return CalDavFetchResult(events=events, sync_token=sync_token, deleted_hrefs=deleted)

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
    ) -> CalDavFetchResult:
        body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<d:sync-collection xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            f"<d:sync-token>{sync_token}</d:sync-token>"
            "<d:sync-level>1</d:sync-level>"
            f"<d:nresults>{max_results}</d:nresults>"
            "<d:prop>"
            "<d:getetag/>"
            "<c:calendar-data/>"
            "</d:prop>"
            "</d:sync-collection>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="0")
        events, new_token, deleted = self._parse_event_multistatus(xml)
        if len(events) > max_results:
            raise YandexCalDavError("caldav sync-collection exceeded requested result limit")
        return CalDavFetchResult(events=events, sync_token=new_token, deleted_hrefs=deleted)

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
            ok_propstat = None
            for propstat in _find_children(response, "propstat"):
                if _ok_propstat(propstat):
                    ok_propstat = propstat
                    break
            if ok_propstat is None:
                continue
            prop = _find_child(ok_propstat, "prop")
            if prop is None:
                continue
            resource_type = _find_child(prop, "resourcetype")
            if resource_type is None:
                continue
            is_calendar = any(_local_name(child.tag) == "calendar" for child in resource_type)
            if not is_calendar:
                continue
            display_name = _find_prop_value(prop, "displayname")
            sync_token = _find_prop_value(prop, "sync-token")
            calendars.append(
                CalDavCalendar(
                    href=href,
                    display_name=display_name,
                    sync_token=sync_token,
                )
            )
        return calendars

    def _parse_event_multistatus(self, xml_text: str) -> tuple[list[CalDavEvent], str | None, list[str]]:
        root = _parse_multistatus_root(xml_text)
        events: list[CalDavEvent] = []
        deleted: list[str] = []
        sync_token: str | None = None
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
            ok_propstat = None
            for propstat in _find_children(child, "propstat"):
                if _ok_propstat(propstat):
                    ok_propstat = propstat
                    break
            if ok_propstat is None:
                continue
            etag = None
            calendar_data = None
            prop = _find_child(ok_propstat, "prop")
            if prop is not None:
                etag = _find_prop_value(prop, "getetag")
                calendar_data = _find_prop_value(prop, "calendar-data")
            if not calendar_data:
                continue
            events.append(
                CalDavEvent(
                    event_href=event_href,
                    etag=etag,
                    calendar_data=calendar_data,
                )
            )
        return events, sync_token, deleted


class FakeCalDavTransport:
    def __init__(
        self,
        calendars: list[CalDavCalendar] | None = None,
        query_events_by_calendar: dict[str, list[CalDavEvent]] | None = None,
        sync_batches_by_calendar: dict[str, dict[str, CalDavFetchResult]] | None = None,
        sync_tokens_by_calendar: dict[str, str] | None = None,
        tx_checker: object | None = None,
    ) -> None:
        self._calendars = calendars or []
        self._query_events = query_events_by_calendar or {}
        self._sync_batches = sync_batches_by_calendar or {}
        self._sync_tokens = sync_tokens_by_calendar or {}
        self.sync_collection_calls: list[tuple[str, str, int]] = []
        self.query_calls: list[str] = []
        self.discover_calls = 0
        self._tx_checker = tx_checker

    def _check_tx(self) -> None:
        if self._tx_checker is not None:
            assert not self._tx_checker()

    def discover_calendars(self, max_results: int) -> list[CalDavCalendar]:
        self._check_tx()
        self.discover_calls += 1
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
        events = self._query_events.get(calendar_href, [])
        if len(events) > max_results:
            raise YandexCalDavError("caldav query exceeded requested result limit")
        token = self._sync_tokens.get(calendar_href)
        return CalDavFetchResult(events=events, sync_token=token)

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
    ) -> CalDavFetchResult:
        self._check_tx()
        self.sync_collection_calls.append((calendar_href, sync_token, max_results))
        batches = self._sync_batches.get(calendar_href, {})
        if sync_token in batches:
            result = batches[sync_token]
            if len(result.events) > max_results:
                raise YandexCalDavError("caldav sync-collection exceeded requested result limit")
            return result
        events = []
        token = self._sync_tokens.get(calendar_href, sync_token)
        return CalDavFetchResult(events=events, sync_token=token)
