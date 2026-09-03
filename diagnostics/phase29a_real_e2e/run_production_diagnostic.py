"""One-off production diagnostic — run inside api container."""
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text

from app.db.models import Object, Representation
from app.db.session import SessionLocal
from app.services.context_service import ContextService
from app.services.domain_tool_service import DomainToolService
from app.services.retrieval_service import RetrievalService
from app.tools.schemas import QueryObjectsInput
from app.users.bootstrap import BOOTSTRAP_USER_ID

USER = BOOTSTRAP_USER_ID
TARGET_ID = UUID("19940b16-893b-49be-969c-5b430063e6ac")
PHRASES = [
    "Классификация на ручных признаках",
    "Контрольное мероприятие",
    "ручных признаках",
    "Классификация",
]


def main() -> None:
    session = SessionLocal()
    obj = session.get(Object, TARGET_ID)
    meta = dict(obj.metadata_ or {})
    target_object = {
        "object_id": str(obj.id),
        "title": obj.title,
        "provider": obj.provider,
        "kind": obj.kind,
        "state": obj.state,
        "status": obj.status,
        "external_id": obj.external_id,
        "canonical_uri": obj.canonical_uri,
        "created_at": str(obj.created_at),
        "updated_at": str(obj.updated_at),
        "content_extraction_status": meta.get("content_extraction_status"),
        "content_revision": meta.get("content_revision"),
        "content_extraction_version": meta.get("content_extraction_version"),
        "content_truncated": meta.get("content_truncated"),
        "mechanical_representation_count": meta.get("mechanical_representation_count"),
        "semantic_summary_revision": meta.get("semantic_summary_revision"),
        "content_format": meta.get("content_format"),
        "has_embedding": obj.embedding is not None,
    }

    reps = session.scalars(
        select(Representation)
        .where(Representation.object_id == TARGET_ID)
        .order_by(Representation.kind)
    ).all()
    representations = [
        {
            "id": str(r.id),
            "kind": r.kind,
            "part_index": r.part_index,
            "text_length": len(r.text or ""),
            "metadata": dict(r.metadata_ or {}),
            "text_preview": (r.text or "")[:600],
        }
        for r in reps
    ]

    phrase_presence: dict = {}
    for phrase in PHRASES:
        matches = []
        for r in reps:
            txt = r.text or ""
            idx = txt.lower().find(phrase.lower())
            if idx >= 0:
                matches.append(
                    {
                        "kind": r.kind,
                        "part_index": r.part_index,
                        "excerpt": txt[max(0, idx - 30) : idx + len(phrase) + 30],
                    }
                )
        phrase_presence[phrase] = {"present": len(matches) > 0, "matches": matches}

    global_row = session.execute(
        text(
            "SELECT count(*) FROM representations r JOIN objects o ON o.id=r.object_id "
            "WHERE o.user_id=:uid AND r.text ILIKE :pat"
        ),
        {"uid": str(USER), "pat": "%Классификация на ручных%"},
    ).scalar()
    phrase_presence["_global_ilike_Классификация_на_ручных"] = int(global_row)

    svc = RetrievalService(session, USER)
    retrieve_checks = []
    for label, q, kind, scope in [
        (
            "exact_phrase",
            "Контрольное мероприятие №1 Классификация на ручных признаках",
            None,
            "all",
        ),
        ("short_phrase", "Классификация на ручных признаках", None, "all"),
        ("title", "Второе полугодие", None, "all"),
    ]:
        res = svc.retrieve(q, kind=kind, limit=10, time_scope=scope)
        retrieve_checks.append(
            {
                "label": label,
                "query": q,
                "kind": kind,
                "time_scope": scope,
                "hit_count": len(res.hits),
                "target_in_hits": any(h.object_id == TARGET_ID for h in res.hits),
                "hits": [
                    {
                        "object_id": str(h.object_id),
                        "title": h.title,
                        "provider": h.provider,
                    }
                    for h in res.hits[:10]
                ],
            }
        )

    dts = DomainToolService(session, USER)
    qo = dts.query_objects(QueryObjectsInput(kinds=["file"], limit=20))
    qo_files = [
        {
            "object_id": str(i.object_id),
            "title": i.title,
            "provider": i.provider,
            "is_target": str(i.object_id) == str(TARGET_ID),
        }
        for i in qo.objects
    ]
    qo_gd = dts.query_objects(
        QueryObjectsInput(kinds=["file"], providers=["google_drive"], limit=20)
    )
    qo_gdrive = [
        {
            "object_id": str(i.object_id),
            "title": i.title,
            "is_target": str(i.object_id) == str(TARGET_ID),
        }
        for i in qo_gd.objects
    ]

    ctx_res = ContextService(session, USER).build_context(
        object_id=TARGET_ID, max_chars=8000
    )
    ctx_items = [
        {
            "kind": it.kind,
            "why_included": it.why_included,
            "content_length": len(it.content or ""),
            "content_preview": (it.content or "")[:800],
        }
        for it in ctx_res.items
    ]
    joined = "\n".join((it.content or "") for it in ctx_res.items)
    get_context = {
        "total_chars": ctx_res.total_chars,
        "truncated": ctx_res.truncated,
        "target_phrase_present": "Классификация на ручных" in joined,
        "items": ctx_items,
    }

    out = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "application_sha": "fc8e90b7c9e706691aec7afc30caa4b95825cc51",
        "target_object": target_object,
        "representations": representations,
        "phrase_presence": phrase_presence,
        "retrieve_checks": retrieve_checks,
        "query_objects_files": qo_files,
        "query_objects_google_drive": qo_gdrive,
        "get_context": get_context,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    session.close()


if __name__ == "__main__":
    main()
