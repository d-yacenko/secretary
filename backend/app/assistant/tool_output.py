import json
from typing import Any

from app.assistant.canonical_uri import sanitize_canonical_uri_for_assistant
from app.assistant.constants import (
    MAX_ASSISTANT_BODY_EXCERPT,
    MAX_ASSISTANT_CONTEXT_CHARS,
    MAX_ASSISTANT_LIST_RESULTS,
    MAX_ASSISTANT_NEIGHBOR_RESULTS,
    MAX_ASSISTANT_RETRIEVE_EXCERPT,
    MAX_ASSISTANT_RETRIEVE_RESULTS,
    MAX_ASSISTANT_SEARCH_RESULTS,
    MAX_ASSISTANT_TOOL_OUTPUT_CHARS,
)


def bounded_body_excerpt(body: str | None) -> str | None:
    if body is None:
        return None
    normalized = body.replace("\n", " ").strip()
    if len(normalized) <= MAX_ASSISTANT_BODY_EXCERPT:
        return normalized
    return normalized[:MAX_ASSISTANT_BODY_EXCERPT] + "… [truncated]"


def _bounded_object(obj: dict[str, Any]) -> dict[str, Any]:
    safe_uri = sanitize_canonical_uri_for_assistant(obj.get("canonical_uri"))
    payload: dict[str, Any] = {
        "id": obj.get("id"),
        "kind": obj.get("kind"),
        "title": obj.get("title"),
        "body": bounded_body_excerpt(obj.get("body")),
        "provider": obj.get("provider"),
        "status": obj.get("status"),
        "origin": obj.get("origin"),
        "state": obj.get("state"),
    }
    if safe_uri is not None:
        payload["canonical_uri"] = safe_uri
    return payload


def _bounded_retrieve_excerpt(excerpt: str | None) -> str:
    if not excerpt:
        return ""
    normalized = excerpt.replace("\n", " ").strip()
    if len(normalized) <= MAX_ASSISTANT_RETRIEVE_EXCERPT:
        return normalized
    return normalized[:MAX_ASSISTANT_RETRIEVE_EXCERPT] + "… [truncated]"


def serialize_tool_output_for_model(tool_name: str, raw_output: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "retrieve":
        hits = raw_output.get("hits", [])[:MAX_ASSISTANT_RETRIEVE_RESULTS]
        truncated = len(raw_output.get("hits", [])) > len(hits)
        payload: dict[str, Any] = {
            "hits": [
                {
                    "object_id": hit.get("object_id"),
                    "title": hit.get("title"),
                    "kind": hit.get("kind"),
                    "provider": hit.get("provider"),
                    "occurred_at": hit.get("occurred_at"),
                    "relevance": hit.get("relevance"),
                    "reasons": hit.get("reasons", []),
                    "excerpt": _bounded_retrieve_excerpt(hit.get("excerpt")),
                }
                for hit in hits
            ],
            "time_scope_used": raw_output.get("time_scope_used"),
            "horizon_days": raw_output.get("horizon_days"),
            "candidate_count": raw_output.get("candidate_count"),
        }
        if truncated:
            payload["truncated"] = True
        return payload

    if tool_name == "search_objects":
        objects = raw_output.get("objects", [])[:MAX_ASSISTANT_SEARCH_RESULTS]
        truncated = len(raw_output.get("objects", [])) > len(objects)
        payload: dict[str, Any] = {
            "objects": [_bounded_object(obj) for obj in objects],
        }
        if truncated:
            payload["truncated"] = True
            payload["total_before_truncation"] = len(raw_output.get("objects", []))
        return payload

    if tool_name == "get_object":
        obj = raw_output.get("object")
        return {"object": _bounded_object(obj) if obj else None}

    if tool_name == "get_context":
        items = raw_output.get("items", [])
        bounded_items: list[dict[str, Any]] = []
        total_chars = 0
        truncated = False
        for item in items:
            content = item.get("content", "")
            if total_chars + len(content) > MAX_ASSISTANT_CONTEXT_CHARS:
                remaining = MAX_ASSISTANT_CONTEXT_CHARS - total_chars
                if remaining > 0:
                    content = content[:remaining] + "… [truncated]"
                else:
                    truncated = True
                    break
            item_payload: dict[str, Any] = {
                "object_id": item.get("object_id"),
                "kind": item.get("kind"),
                "title": item.get("title"),
                "content": content,
                "origin": item.get("origin"),
                "state": item.get("state"),
                "why_included": item.get("why_included"),
            }
            safe_uri = sanitize_canonical_uri_for_assistant(item.get("canonical_uri"))
            if safe_uri is not None:
                item_payload["canonical_uri"] = safe_uri
            bounded_items.append(item_payload)
            total_chars += len(content)
            if total_chars >= MAX_ASSISTANT_CONTEXT_CHARS:
                truncated = True
                break
        if len(bounded_items) < len(items):
            truncated = True
        result: dict[str, Any] = {
            "items": bounded_items,
            "total_chars": total_chars,
            "truncated": truncated or raw_output.get("truncated", False),
        }
        return result

    if tool_name == "list_neighbors":
        neighbors = raw_output.get("neighbors", [])[:MAX_ASSISTANT_NEIGHBOR_RESULTS]
        truncated = len(raw_output.get("neighbors", [])) > len(neighbors)
        payload = {
            "object_id": raw_output.get("object_id"),
            "neighbors": [
                {
                    "object": _bounded_object(neighbor.get("object", {})),
                    "edge": {
                        "id": neighbor.get("edge", {}).get("id"),
                        "type": neighbor.get("edge", {}).get("type"),
                        "origin": neighbor.get("edge", {}).get("origin"),
                        "state": neighbor.get("edge", {}).get("state"),
                    },
                    "direction": neighbor.get("direction"),
                }
                for neighbor in neighbors
                if neighbor.get("object")
            ],
        }
        if truncated:
            payload["truncated"] = True
        return payload

    if tool_name == "list_notifications":
        notifications = raw_output.get("notifications", [])[:MAX_ASSISTANT_LIST_RESULTS]
        truncated = len(raw_output.get("notifications", [])) > len(notifications)
        payload = {
            "notifications": [
                {
                    "id": row.get("id"),
                    "title": row.get("title"),
                    "body": bounded_body_excerpt(row.get("body")),
                    "priority": row.get("priority"),
                    "status": row.get("status"),
                    "source_object_id": row.get("source_object_id"),
                    "related_object_id": row.get("related_object_id"),
                    "proposal": row.get("proposal"),
                }
                for row in notifications
            ],
        }
        if truncated:
            payload["truncated"] = True
        return payload

    if tool_name in ("create_task", "update_task"):
        obj = raw_output.get("object")
        return {"object": _bounded_object(obj) if obj else None}

    if tool_name == "link_objects":
        edge = raw_output.get("edge")
        return {
            "edge": {
                "id": edge.get("id"),
                "source_id": edge.get("source_id"),
                "target_id": edge.get("target_id"),
                "type": edge.get("type"),
                "origin": edge.get("origin"),
                "state": edge.get("state"),
            }
            if edge
            else None
        }

    if tool_name == "get_today":
        return raw_output

    return raw_output


def serialize_tool_output_json(tool_name: str, raw_output: dict[str, Any]) -> str:
    bounded = serialize_tool_output_for_model(tool_name, raw_output)
    if tool_name == "search_objects":
        objects = list(bounded.get("objects", []))
        while objects:
            candidate = dict(bounded)
            candidate["objects"] = objects
            if len(json.dumps(candidate, ensure_ascii=False)) <= MAX_ASSISTANT_TOOL_OUTPUT_CHARS:
                return json.dumps(candidate, ensure_ascii=False)
            objects.pop()
        return json.dumps({"objects": [], "truncated": True}, ensure_ascii=False)

    text = json.dumps(bounded, ensure_ascii=False)
    if len(text) <= MAX_ASSISTANT_TOOL_OUTPUT_CHARS:
        return text
    return json.dumps({"truncated": True, "preview_chars": len(text)}, ensure_ascii=False)
