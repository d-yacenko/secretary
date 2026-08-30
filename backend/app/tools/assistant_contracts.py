"""OpenAI Responses API function schemas for Secretary domain tools.

Neutral contract payloads only — exposure policy lives in the tool registry.
"""

ASSISTANT_FUNCTION_SCHEMAS: dict[str, dict] = {
    "retrieve": {
        "type": "function",
        "name": "retrieve",
        "description": (
            "Retrieve up to five qualified local objects ranked by relevance. "
            "Top-K is a maximum, not a target."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": {"type": "string"},
                "time_scope": {
                    "type": "string",
                    "enum": ["auto", "recent", "all"],
                },
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "get_object": {
        "type": "function",
        "name": "get_object",
        "description": "Fetch one object by id for the authenticated user.",
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "get_context": {
        "type": "function",
        "name": "get_context",
        "description": (
            "Build bounded context for one object by id. "
            "Use retrieve(query) first to discover object ids."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "maximum": 8000},
            },
            "required": ["object_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "list_neighbors": {
        "type": "function",
        "name": "list_neighbors",
        "description": "List direct graph neighbors for an object (bounded).",
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "list_notifications": {
        "type": "function",
        "name": "list_notifications",
        "description": "List notifications for the authenticated user.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "additionalProperties": False,
        },
        "strict": False,
    },
    "create_task": {
        "type": "function",
        "name": "create_task",
        "description": (
            "Create a proposed agent-origin task for the authenticated user. "
            "New tasks always start with status=open. "
            "Pass evidence_object_ids from source objects discovered this turn."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "body": {"type": "string"},
                "due_at": {"type": "string"},
                "evidence_object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
            },
            "required": ["title", "confidence"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "update_task": {
        "type": "function",
        "name": "update_task",
        "description": (
            "Update task title, body, due date, or attach evidence references. "
            "Does not change lifecycle status — use set_task_status for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "title": {"type": "string", "minLength": 1},
                "body": {"type": ["string", "null"]},
                "due_at": {"type": ["string", "null"]},
                "evidence_object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
            },
            "required": ["object_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "set_task_status": {
        "type": "function",
        "name": "set_task_status",
        "description": (
            "Change task lifecycle status: open, in_progress, done, cancelled, or archived. "
            "Use for complete, cancel, archive, or reopen — not for field edits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done", "cancelled", "archived"],
                },
            },
            "required": ["object_id", "status"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "delete_task": {
        "type": "function",
        "name": "delete_task",
        "description": (
            "Soft-delete a task (status=deleted). Preserves graph history and evidence. "
            "Requires user approval. Do not use update_task or physical graph deletion."
        ),
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "link_objects": {
        "type": "function",
        "name": "link_objects",
        "description": "Create a proposed relation edge between two objects.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "relation_type": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["source_id", "target_id", "relation_type", "confidence"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "get_today": {
        "type": "function",
        "name": "get_today",
        "description": "Return current Secretary local date/time and timezone.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "strict": False,
    },
}
