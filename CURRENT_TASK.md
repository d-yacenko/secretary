# Current task — PHASE 01

## Goal

Run PostgreSQL with pgvector and an empty FastAPI service.

## Do

1. Create Docker Compose with: `db`, `api`, `worker`.
2. Enable pgvector in the database.
3. Add `/health`.
4. Add database connection settings.
5. Add Alembic.
6. Worker may initially only log that it is alive.
7. Add `.env.example`.

## Accept

```text
docker compose up
GET /health -> 200
database connection works
pytest passes
```

Do not add Redis.
