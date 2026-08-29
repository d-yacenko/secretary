from typing import Any
from uuid import UUID


def collect_object_ids_from_bounded_tool(
    tool_name: str,
    bounded: dict[str, Any],
    candidate_ids: list[UUID],
    affected_ids: list[UUID],
) -> None:
    if tool_name == "search_objects":
        for obj in bounded.get("objects", []):
            _append_uuid(candidate_ids, obj.get("id"))
    elif tool_name == "get_object":
        obj = bounded.get("object")
        if obj:
            _append_uuid(candidate_ids, obj.get("id"))
    elif tool_name == "get_context":
        for item in bounded.get("items", []):
            _append_uuid(candidate_ids, item.get("object_id"))
    elif tool_name == "list_neighbors":
        for neighbor in bounded.get("neighbors", []):
            obj = neighbor.get("object")
            if obj:
                _append_uuid(candidate_ids, obj.get("id"))
    elif tool_name in ("create_task", "update_task"):
        obj = bounded.get("object")
        if obj:
            _append_uuid(affected_ids, obj.get("id"))
            _append_uuid(candidate_ids, obj.get("id"))


def dedupe_preserve_order(ids: list[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for object_id in ids:
        if object_id in seen:
            continue
        seen.add(object_id)
        ordered.append(object_id)
    return ordered


def cap_reference_candidate_ids(
    candidate_ids: list[UUID],
    mandatory_ids: list[UUID],
    max_refs: int,
) -> list[UUID]:
    mandatory_unique = dedupe_preserve_order(mandatory_ids)
    rest = [
        object_id
        for object_id in dedupe_preserve_order(candidate_ids)
        if object_id not in mandatory_unique
    ]
    return (mandatory_unique + rest)[:max_refs]


def _append_uuid(target: list[UUID], value: object) -> None:
    if not value:
        return
    try:
        parsed = UUID(str(value))
    except ValueError:
        return
    if parsed not in target:
        target.append(parsed)
