import uuid

import httpx
import pytest
from contextlib import asynccontextmanager
from fastapi import FastAPI
from httpx import ASGITransport
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from app.api.schemas import EdgeCreate, ObjectCreate
from app.mcp.server import MCP_TOOL_NAMES, create_mcp_server
from mcp.server.transport_security import TransportSecuritySettings
from app.services.graph_service import GraphService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE
from app.tools.executor import ToolExecutor
from app.tools.schemas import MAX_CONTEXT_CHARS
from app.users.bootstrap import BOOTSTRAP_USER_ID


FORBIDDEN_MCP_TOOLS = frozenset(
    {
        "create_notification",
        "send_notification",
        "search_calendar",
        "propose_calendar_event",
        "send_email",
        "delete_object",
        "delete_edge",
    }
)


@pytest.fixture
def mcp_server(patched_mcp_tool_session):
    return create_mcp_server()


def _create_task(graph: GraphService, title: str):
    return graph.create_object(ObjectCreate(kind="task", title=title, origin="user"))


@pytest.mark.asyncio
async def test_mcp_lists_only_expected_tools(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.list_tools()
    names = {tool.name for tool in result.tools}
    assert names == MCP_TOOL_NAMES
    assert "list_notifications" in names
    assert not names.intersection(FORBIDDEN_MCP_TOOLS)


@pytest.mark.asyncio
async def test_mcp_search_objects(db_session, mcp_server) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    _create_task(graph, "MCP search unique beta marker")

    async with Client(mcp_server) as client:
        result = await client.call_tool("search_objects", {"query": "beta marker", "limit": 10})

    assert not result.is_error
    objects = result.structured_content["objects"]
    assert any(obj["title"] == "MCP search unique beta marker" for obj in objects)


@pytest.mark.asyncio
async def test_mcp_get_object(db_session, mcp_server) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "MCP get object")

    async with Client(mcp_server) as client:
        result = await client.call_tool("get_object", {"object_id": str(task.id)})

    assert not result.is_error
    obj = result.structured_content["object"]
    assert obj["id"] == str(task.id)
    assert obj["title"] == "MCP get object"


@pytest.mark.asyncio
async def test_mcp_get_context_respects_cap(db_session, mcp_server) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "MCP bounded context task")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_context",
            {"object_id": str(task.id), "max_chars": 200},
        )

    assert not result.is_error
    assert result.structured_content["total_chars"] <= 200


@pytest.mark.asyncio
async def test_mcp_get_context_rejects_above_cap(db_session, mcp_server) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "MCP cap rejection task")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_context",
            {"object_id": str(task.id), "max_chars": MAX_CONTEXT_CHARS + 1},
        )

    assert result.is_error


@pytest.mark.asyncio
async def test_mcp_create_task_agent_proposed(db_session, mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "create_task",
            {"title": "MCP agent task", "confidence": 0.81},
        )

    assert not result.is_error
    obj = result.structured_content["object"]
    assert obj["kind"] == "task"
    assert obj["origin"] == AGENT_ORIGIN
    assert obj["state"] == PROPOSED_STATE
    assert obj["confidence"] == 0.81


@pytest.mark.asyncio
async def test_mcp_list_notifications(db_session, mcp_server) -> None:
    from app.services.notification_service import NotificationService

    NotificationService(db_session, BOOTSTRAP_USER_ID).create(
        title="MCP inbox item",
        body="From MCP test",
        priority="normal",
        proposal={"type": "note", "confidence": 0.5, "evidence": []},
    )

    async with Client(mcp_server) as client:
        result = await client.call_tool("list_notifications", {"limit": 10})

    assert not result.is_error
    notifications = result.structured_content["notifications"]
    assert any(row["title"] == "MCP inbox item" for row in notifications)


@pytest.mark.asyncio
async def test_mcp_invalid_due_at_returns_tool_error(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "create_task",
            {
                "title": "Bad due date task",
                "confidence": 0.5,
                "due_at": "not-a-datetime",
            },
        )

    assert result.is_error
    assert "Traceback" not in result.content[0].text


@pytest.mark.asyncio
async def test_mcp_link_objects_agent_proposed(db_session, mcp_server) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    source = _create_task(graph, "MCP link source")
    target = _create_task(graph, "MCP link target")

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "link_objects",
            {
                "source_id": str(source.id),
                "target_id": str(target.id),
                "relation_type": "related_to",
                "confidence": 0.62,
            },
        )

    assert not result.is_error
    edge = result.structured_content["edge"]
    assert edge["origin"] == AGENT_ORIGIN
    assert edge["state"] == PROPOSED_STATE
    assert edge["confidence"] == 0.62


@pytest.mark.asyncio
async def test_mcp_invalid_object_id_returns_tool_error(mcp_server) -> None:
    missing_id = uuid.uuid4()

    async with Client(mcp_server) as client:
        result = await client.call_tool("get_object", {"object_id": str(missing_id)})

    assert result.is_error
    assert result.content[0].text
    assert "Traceback" not in result.content[0].text
    assert "sqlalchemy" not in result.content[0].text.lower()


@pytest.mark.asyncio
async def test_mcp_get_today_returns_secretary_timezone(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_today", {})

    assert not result.is_error
    payload = result.structured_content
    assert payload["timezone"]
    assert payload["datetime"]


@pytest.mark.asyncio
async def test_multiple_independent_mcp_calls_do_not_exhaust_executor(
    db_session, mcp_server
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "MCP repeat calls")

    async with Client(mcp_server) as client:
        for _ in range(6):
            result = await client.call_tool("get_object", {"object_id": str(task.id)})
            assert not result.is_error


@pytest.mark.asyncio
async def test_mcp_streamable_http_smoke(db_session, patched_mcp_tool_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "Streamable HTTP smoke task")

    mcp = create_mcp_server()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp.session_manager.run():
            yield

    test_app = FastAPI(lifespan=lifespan)
    test_app.mount(
        "/mcp",
        mcp.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
            ),
        ),
    )

    async with test_app.router.lifespan_context(test_app):
        transport = ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as http_client:
            url = "http://127.0.0.1/mcp/"
            client_transport = streamable_http_client(
                url,
                http_client=http_client,
                terminate_on_close=False,
            )
            async with Client(client_transport) as client:
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert names == MCP_TOOL_NAMES

                result = await client.call_tool("get_object", {"object_id": str(task.id)})
                assert not result.is_error
                assert result.structured_content["object"]["id"] == str(task.id)


@pytest.mark.asyncio
async def test_mcp_does_not_use_global_tool_executor(
    db_session, fake_embedding_service, patched_mcp_tool_session
) -> None:
    from app.services.domain_tool_service import DomainToolService

    tools = DomainToolService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = _create_task(graph, "Executor scope task")
    executor = ToolExecutor(tools, max_calls=5)
    for _ in range(5):
        assert executor.execute("get_object", {"object_id": str(task.id)}).success

    mcp = create_mcp_server()
    async with Client(mcp) as client:
        result = await client.call_tool("get_object", {"object_id": str(task.id)})
    assert not result.is_error
