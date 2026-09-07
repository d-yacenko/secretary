"""OpenAI Responses API function schemas for Secretary domain tools.

Neutral contract payloads only — exposure policy lives in the tool registry.
"""

ASSISTANT_FUNCTION_SCHEMAS: dict[str, dict] = {
    "retrieve": {
        "type": "function",
        "name": "retrieve",
        "description": (
            "Retrieve up to five qualified local objects ranked by relevance. "
            "Top-K is a maximum, not a target. "
            "Omit kind to search across all object kinds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": {
                    "type": "string",
                    "description": (
                        "Optional exact Object.kind filter (e.g. file, email, event, task, scheduled_activity). "
                        "Omit to search across all object kinds. "
                        '"all" is not an Object.kind.'
                    ),
                },
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
    "query_objects": {
        "type": "function",
        "name": "query_objects",
        "description": (
            "Structured filter and deterministic ordering over the user's objects. "
            "Use for open tasks, due dates, scheduled activities, date ranges, and sorted lists. "
            "Do not use for semantic topic discovery — use retrieve instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kinds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
                "providers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
                "statuses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
                "states": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 4,
                },
                "due_from": {"type": "string"},
                "due_to": {"type": "string"},
                "start_from": {"type": "string"},
                "start_to": {"type": "string"},
                "occurred_from": {"type": "string"},
                "occurred_to": {"type": "string"},
                "label_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
                "label_match": {
                    "type": "string",
                    "enum": ["all", "any"],
                },
                "sort_by": {
                    "type": "string",
                    "enum": [
                        "due_at",
                        "start_at",
                        "occurred_at",
                        "created_at",
                        "updated_at",
                        "title",
                    ],
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
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
            "Use retrieve(query) first to discover object ids. "
            "When opening a content-backed retrieve hit, pass the relevant search "
            "question or phrase as query so relevant chunks can be selected."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "query": {"type": "string"},
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
        "description": (
            "List direct graph neighbors for an object (bounded). "
            "Each neighbor includes edge.id — required before remove_relation."
        ),
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
            "evidence_object_ids is ADDITIVE only: attach these evidence objects if not "
            "already attached. Omitting an existing evidence object never removes it. "
            "To remove a relation, use remove_relation(edge_id) after list_neighbors. "
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
    "remove_relation": {
        "type": "function",
        "name": "remove_relation",
        "description": (
            "Deactivate a semantic/user/agent graph relation by exact edge_id. "
            "Requires user approval. Call list_neighbors first to obtain edge.id; "
            "never invent edge IDs. Sets edge state to rejected without physical deletion. "
            "Do not use update_task(evidence_object_ids) to remove evidence — that field is "
            "additive only."
        ),
        "parameters": {
            "type": "object",
            "properties": {"edge_id": {"type": "string"}},
            "required": ["edge_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "list_labels": {
        "type": "function",
        "name": "list_labels",
        "description": "List the user's active organizational labels.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
            "additionalProperties": False,
        },
        "strict": False,
    },
    "create_label": {
        "type": "function",
        "name": "create_label",
        "description": (
            "Create an organizational label by display name. Names are normalized; "
            "creating an existing name returns the existing label. Requires approval."
        ),
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "rename_label": {
        "type": "function",
        "name": "rename_label",
        "description": "Rename an existing label by id. Requires approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "label_id": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["label_id", "name"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "assign_label": {
        "type": "function",
        "name": "assign_label",
        "description": (
            "Assign an active label to an object (labeled_with). Requires approval. "
            "Do not use link_objects for labels."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "label_id": {"type": "string"},
            },
            "required": ["object_id", "label_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "remove_label": {
        "type": "function",
        "name": "remove_label",
        "description": (
            "Remove an active labeled_with assignment. Requires approval. "
            "Does not delete the object or the label."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "object_id": {"type": "string"},
                "label_id": {"type": "string"},
            },
            "required": ["object_id", "label_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "delete_label": {
        "type": "function",
        "name": "delete_label",
        "description": (
            "Tombstone a label. Does not delete labeled source objects. Requires approval."
        ),
        "parameters": {
            "type": "object",
            "properties": {"label_id": {"type": "string"}},
            "required": ["label_id"],
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
    "create_scheduled_activity": {
        "type": "function",
        "name": "create_scheduled_activity",
        "description": (
            "Schedule a one-shot internal reminder/activity. "
            "Creates a scheduled_activity object and later emits exactly one internal "
            "notification at run_at. Does not send email, change calendars, or run LLM. "
            "Requires user approval. run_at must be in the future."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": ["string", "null"]},
                "run_at": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                },
            },
            "required": ["title", "run_at"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "create_recurring_scheduled_activity": {
        "type": "function",
        "name": "create_recurring_scheduled_activity",
        "description": (
            "Schedule a daily or weekly internal reminder. "
            "Uses local wall-clock time in an IANA timezone. "
            "Creates a scheduled_activity that stays scheduled until cancelled and "
            "emits one internal notification per occurrence. "
            "Does not send email, change calendars, or run LLM. Requires user approval. "
            "For weekly schedules pass unique weekdays (mon-sun). "
            "Omit timezone to use the trusted client timezone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": ["string", "null"]},
                "schedule_kind": {"type": "string", "enum": ["daily", "weekly"]},
                "local_time": {
                    "type": "string",
                    "description": "Local wall-clock time as 24-hour HH:MM.",
                },
                "timezone": {
                    "type": ["string", "null"],
                    "description": "IANA timezone such as Europe/Moscow. Not a UTC offset.",
                },
                "weekdays": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                        "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    },
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                },
            },
            "required": ["title", "schedule_kind", "local_time"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "cancel_scheduled_activity": {
        "type": "function",
        "name": "cancel_scheduled_activity",
        "description": (
            "Cancel a scheduled_activity (one-shot or recurring) that is still scheduled. "
            "Requires user approval. Does not undo an already delivered notification."
        ),
        "parameters": {
            "type": "object",
            "properties": {"activity_id": {"type": "string"}},
            "required": ["activity_id"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "create_calendar_event": {
        "type": "function",
        "name": "create_calendar_event",
        "description": (
            "Create an event on the user's own Google Calendar primary calendar or "
            "own/default Yandex calendar. "
            "Requires explicit user approval before the provider is written. "
            "Pass exact start_at and end_at instants (ISO 8601). "
            "If the user names Google or Yandex, pass provider. "
            "If multiple accounts are connected, pass provider and account_email. "
            "Do not include attendees, recurrence, conference data, or calendar paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_at": {"type": "string"},
                "end_at": {"type": "string"},
                "description": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "account_email": {"type": ["string", "null"]},
                "provider": {"type": ["string", "null"], "enum": ["google", "yandex"]},
            },
            "required": ["summary", "start_at", "end_at"],
            "additionalProperties": False,
        },
        "strict": False,
    },
    "send_email": {
        "type": "function",
        "name": "send_email",
        "description": (
            "Send a plain-text email from the user's connected Google or Yandex mail account. "
            "Requires explicit user approval before the provider sends. "
            "Compose the final exact To recipients, subject, and body first. "
            "Call this only when the user asked to send. Do not call it for a draft. "
            "If the user names Google or Yandex, pass provider. "
            "If multiple accounts are connected, pass provider and account_email. "
            "Do not include From, CC, BCC, attachments, or HTML."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "account_email": {"type": ["string", "null"]},
                "provider": {"type": ["string", "null"], "enum": ["google", "yandex"]},
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
        "strict": False,
    },
}
