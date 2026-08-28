from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote, urljoin
from xml.etree import ElementTree as ET

import httpx

from app.connectors.yandex.constants import DEFAULT_CALDAV_BASE_URL
from app.connectors.yandex.errors import YandexCalDavError

DAV_NS = "DAV:"
CALDAV_NS = "urn:ietf:params:xml:ns:caldav"
NS = {"d": DAV_NS, "c": CALDAV_NS}


def _format_caldav_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(element: ET.Element, namespace: str, name: str) -> ET.Element | None:
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _find_prop_value(propstat: ET.Element, namespace: str, name: str) -> str | None:
    prop = _find_child(propstat, DAV_NS, "prop")
    if prop is None:
        return None
    for child in prop:
        if _local_name(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def _response_status_ok(propstat: ET.Element) -> bool:
    status = _find_child(propstat, DAV_NS, "status")
    if status is None or not status.text:
        return False
    return status.text.endswith(" 200 OK")


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
        self._calendar_home = f"/calendars/{quote(self._email, safe='')}/"

    def _request(self, method: str, path: str, body: str, depth: str | None = None) -> str:
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": depth or "0",
        }
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
        body = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
            "<d:prop>"
            "<d:displayname/>"
            "<d:resourcetype/>"
            "<d:sync-token/>"
            "</d:prop>"
            "</d:propfind>"
        )
        xml = self._request("PROPFIND", self._calendar_home, body, depth="1")
        calendars = self._parse_calendar_multistatus(xml, self._calendar_home)
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
            "<c:calendar-data/>"
            "</d:prop>"
            f"<c:filter><c:comp-filter name='VCALENDAR'>"
            f"<c:comp-filter name='VEVENT'>"
            f"<c:time-range start='{start}' end='{end}'/>"
            "</c:comp-filter></c:comp-filter>"
            "</c:calendar-query>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="1")
        events, sync_token = self._parse_event_multistatus(xml)
        return CalDavFetchResult(events=events[:max_results], sync_token=sync_token)

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
            "<d:prop>"
            "<d:getetag/>"
            "<c:calendar-data/>"
            "</d:prop>"
            "</d:sync-collection>"
        )
        xml = self._request("REPORT", calendar_href, body, depth="1")
        events, new_token = self._parse_event_multistatus(xml)
        return CalDavFetchResult(events=events[:max_results], sync_token=new_token)

    def _parse_calendar_multistatus(self, xml_text: str, home_href: str) -> list[CalDavCalendar]:
        root = ET.fromstring(xml_text)
        calendars: list[CalDavCalendar] = []
        for response in root:
            if _local_name(response.tag) != "response":
                continue
            href_el = _find_child(response, DAV_NS, "href")
            if href_el is None or not href_el.text:
                continue
            href = href_el.text.strip()
            if href.rstrip("/") == home_href.rstrip("/"):
                continue
            propstat = None
            for child in response:
                if _local_name(child.tag) == "propstat":
                    propstat = child
                    break
            if propstat is None or not _response_status_ok(propstat):
                continue
            prop = _find_child(propstat, DAV_NS, "prop")
            if prop is None:
                continue
            resource_type = _find_child(prop, DAV_NS, "resourcetype")
            if resource_type is None:
                continue
            is_calendar = any(_local_name(child.tag) == "calendar" for child in resource_type)
            if not is_calendar:
                continue
            display_name = _find_prop_value(propstat, DAV_NS, "displayname")
            sync_token = _find_prop_value(propstat, DAV_NS, "sync-token")
            calendars.append(
                CalDavCalendar(
                    href=href,
                    display_name=display_name,
                    sync_token=sync_token,
                )
            )
        return calendars

    def _parse_event_multistatus(self, xml_text: str) -> tuple[list[CalDavEvent], str | None]:
        root = ET.fromstring(xml_text)
        events: list[CalDavEvent] = []
        sync_token: str | None = None
        for child in root:
            tag = _local_name(child.tag)
            if tag == "sync-token" and child.text:
                sync_token = child.text.strip()
            if tag != "response":
                continue
            href_el = _find_child(child, DAV_NS, "href")
            if href_el is None or not href_el.text:
                continue
            event_href = href_el.text.strip()
            propstat = None
            for sub in child:
                if _local_name(sub.tag) == "propstat":
                    propstat = sub
                    break
            if propstat is None or not _response_status_ok(propstat):
                continue
            etag = _find_prop_value(propstat, DAV_NS, "getetag")
            calendar_data = _find_prop_value(propstat, CALDAV_NS, "calendar-data")
            if not calendar_data:
                continue
            events.append(
                CalDavEvent(
                    event_href=event_href,
                    etag=etag,
                    calendar_data=calendar_data,
                )
            )
        return events, sync_token


class FakeCalDavTransport:
    def __init__(
        self,
        calendars: list[CalDavCalendar] | None = None,
        query_events_by_calendar: dict[str, list[CalDavEvent]] | None = None,
        sync_events_by_calendar: dict[str, list[CalDavEvent]] | None = None,
        sync_tokens_by_calendar: dict[str, str] | None = None,
        tx_checker: object | None = None,
    ) -> None:
        self._calendars = calendars or []
        self._query_events = query_events_by_calendar or {}
        self._sync_events = sync_events_by_calendar or {}
        self._sync_tokens = sync_tokens_by_calendar or {}
        self.sync_collection_calls: list[tuple[str, str]] = []
        self.query_calls: list[str] = []
        self._tx_checker = tx_checker

    def _check_tx(self) -> None:
        if self._tx_checker is not None:
            assert not self._tx_checker()

    def discover_calendars(self, max_results: int) -> list[CalDavCalendar]:
        self._check_tx()
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
        token = self._sync_tokens.get(calendar_href)
        return CalDavFetchResult(events=events[:max_results], sync_token=token)

    def sync_collection(
        self,
        calendar_href: str,
        sync_token: str,
        max_results: int,
    ) -> CalDavFetchResult:
        self._check_tx()
        self.sync_collection_calls.append((calendar_href, sync_token))
        events = self._sync_events.get(calendar_href, [])
        new_token = self._sync_tokens.get(calendar_href, sync_token)
        return CalDavFetchResult(events=events[:max_results], sync_token=new_token)
