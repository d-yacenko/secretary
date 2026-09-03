"""Canonical Secretary domain tool registry."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.services.domain_tool_service import DomainToolService
from app.tools.assistant_contracts import ASSISTANT_FUNCTION_SCHEMAS
from app.tools.policy import ToolPermission
from app.tools.schemas import (
    CreateTaskInput,
    DeleteTaskInput,
    GetContextInput,
    GetObjectInput,
    LinkObjectsInput,
    ListNeighborsInput,
    ListNotificationsInput,
    QueryObjectsInput,
    RemoveRelationInput,
    RetrieveInput,
    SearchObjectsInput,
    SetTaskStatusInput,
    ToolError,
    UpdateTaskInput,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    permission: ToolPermission
    input_model: type[BaseModel] | None
    service_method: str
    assistant_exposed: bool
    mcp_exposed: bool
    assistant_definition: dict | None = None


def _assistant_definition(name: str) -> dict:
    return ASSISTANT_FUNCTION_SCHEMAS[name]


def _build_tool_registry(specs: tuple[ToolSpec, ...]) -> dict[str, ToolSpec]:
    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        seen: set[str] = set()
        duplicates = [name for name in names if name in seen or seen.add(name)]
        raise ValueError(f"duplicate tool registry names: {duplicates}")
    return {spec.name: spec for spec in specs}


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="retrieve",
        permission=ToolPermission.READ,
        input_model=RetrieveInput,
        service_method="retrieve",
        assistant_exposed=True,
        mcp_exposed=False,
        assistant_definition=_assistant_definition("retrieve"),
    ),
    ToolSpec(
        name="query_objects",
        permission=ToolPermission.READ,
        input_model=QueryObjectsInput,
        service_method="query_objects",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("query_objects"),
    ),
    ToolSpec(
        name="search_objects",
        permission=ToolPermission.READ,
        input_model=SearchObjectsInput,
        service_method="search_objects",
        assistant_exposed=False,
        mcp_exposed=True,
    ),
    ToolSpec(
        name="get_object",
        permission=ToolPermission.READ,
        input_model=GetObjectInput,
        service_method="get_object",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("get_object"),
    ),
    ToolSpec(
        name="get_context",
        permission=ToolPermission.READ,
        input_model=GetContextInput,
        service_method="get_context",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("get_context"),
    ),
    ToolSpec(
        name="list_neighbors",
        permission=ToolPermission.READ,
        input_model=ListNeighborsInput,
        service_method="list_neighbors",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("list_neighbors"),
    ),
    ToolSpec(
        name="list_notifications",
        permission=ToolPermission.READ,
        input_model=ListNotificationsInput,
        service_method="list_notifications",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("list_notifications"),
    ),
    ToolSpec(
        name="create_task",
        permission=ToolPermission.INTERNAL_WRITE,
        input_model=CreateTaskInput,
        service_method="create_task",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("create_task"),
    ),
    ToolSpec(
        name="update_task",
        permission=ToolPermission.INTERNAL_WRITE,
        input_model=UpdateTaskInput,
        service_method="update_task",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("update_task"),
    ),
    ToolSpec(
        name="set_task_status",
        permission=ToolPermission.INTERNAL_WRITE,
        input_model=SetTaskStatusInput,
        service_method="set_task_status",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("set_task_status"),
    ),
    ToolSpec(
        name="delete_task",
        permission=ToolPermission.DESTRUCTIVE_INTERNAL_WRITE,
        input_model=DeleteTaskInput,
        service_method="delete_task",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("delete_task"),
    ),
    ToolSpec(
        name="link_objects",
        permission=ToolPermission.INTERNAL_WRITE,
        input_model=LinkObjectsInput,
        service_method="link_objects",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("link_objects"),
    ),
    ToolSpec(
        name="remove_relation",
        permission=ToolPermission.DESTRUCTIVE_INTERNAL_WRITE,
        input_model=RemoveRelationInput,
        service_method="remove_relation",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("remove_relation"),
    ),
    ToolSpec(
        name="get_today",
        permission=ToolPermission.READ,
        input_model=None,
        service_method="get_today",
        assistant_exposed=True,
        mcp_exposed=True,
        assistant_definition=_assistant_definition("get_today"),
    ),
)

TOOL_REGISTRY: dict[str, ToolSpec] = _build_tool_registry(TOOL_SPECS)

if len(TOOL_SPECS) != len(TOOL_REGISTRY):
    raise RuntimeError("tool registry size mismatch after construction")

ASSISTANT_TOOL_DEFINITIONS: list[dict] = [
    spec.assistant_definition
    for spec in TOOL_SPECS
    if spec.assistant_exposed and spec.assistant_definition is not None
]

MCP_TOOL_NAMES: frozenset[str] = frozenset(
    spec.name for spec in TOOL_SPECS if spec.mcp_exposed
)


def get_tool_spec(tool_name: str) -> ToolSpec | None:
    return TOOL_REGISTRY.get(tool_name)


def registered_tool_names() -> frozenset[str]:
    return frozenset(TOOL_REGISTRY.keys())


def validate_tool_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    if spec.input_model is None:
        return {}
    validated = spec.input_model.model_validate(arguments)
    return validated.model_dump(mode="json", exclude_unset=True)


def execute_registered_tool(
    tools: DomainToolService,
    spec: ToolSpec,
    arguments: dict[str, Any],
) -> BaseModel:
    method: Callable[..., BaseModel] = getattr(tools, spec.service_method)
    if spec.input_model is None:
        return method()
    validated = spec.input_model.model_validate(arguments)
    return method(validated)


def dispatch_registered_tool(
    tools: DomainToolService,
    tool_name: str,
    arguments: dict[str, Any],
) -> BaseModel:
    spec = get_tool_spec(tool_name)
    if spec is None:
        raise ToolError(f"unknown tool: {tool_name}")
    return execute_registered_tool(tools, spec, arguments)
