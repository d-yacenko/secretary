"""OpenAI Responses API tool definitions for Secretary domain tools."""

TOOL_DEFINITIONS: list[dict] = [
    {
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
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "name": "create_task",
        "description": (
            "Create a proposed agent-origin task for the authenticated user. "
            "Pass evidence_object_ids from source objects discovered this turn."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "body": {"type": "string"},
                "due_at": {"type": "string"},
                "status": {"type": "string"},
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
    {
        "type": "function",
        "name": "update_task",
        "description": (
            "Update an existing task object or attach evidence references to it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "status": {"type": "string"},
                "due_at": {"type": "string"},
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
    {
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
    {
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
]
