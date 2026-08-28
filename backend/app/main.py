from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.graph import router as graph_router
from app.db.engine import engine

app = FastAPI(title="Personal Secretary")
app.include_router(graph_router)


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
