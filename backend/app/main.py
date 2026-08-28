from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.graph import router as graph_router
from app.api.routes.notifications import router as notifications_router
from app.core.config import settings
from app.db.engine import engine

_mcp_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _mcp_server is not None:
        async with _mcp_server.session_manager.run():
            yield
    else:
        yield


app = FastAPI(title="Personal Secretary", lifespan=lifespan)
app.include_router(graph_router)
app.include_router(notifications_router)


if settings.mcp_enabled:
    from app.mcp.server import create_mcp_server

    _mcp_server = create_mcp_server()
    app.mount(
        "/mcp",
        _mcp_server.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
