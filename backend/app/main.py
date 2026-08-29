from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.google import router as google_router
from app.api.local import router as local_router
from app.api.yandex import router as yandex_router
from app.api.routes.resources import router as resources_router
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


@app.exception_handler(StarletteHTTPException)
async def register_multipart_size_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if (
        exc.status_code == 400
        and request.url.path.endswith("/resources/register")
        and "Part exceeded maximum size" in str(exc.detail)
    ):
        return JSONResponse(
            status_code=413,
            content={"detail": "register payload exceeds size limit"},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(graph_router)
app.include_router(resources_router)
app.include_router(local_router)
app.include_router(notifications_router)
app.include_router(google_router)
app.include_router(yandex_router)


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
