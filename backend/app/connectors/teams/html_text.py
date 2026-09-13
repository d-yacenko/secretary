from app.connectors.email_html_text import html_email_to_plain_text, normalize_plain_email_text


def teams_body_to_plain_text(*, content_type: str | None, content: str | None) -> str:
    raw = content or ""
    lowered = (content_type or "text").strip().lower()
    if lowered in {"html", "text/html"}:
        return html_email_to_plain_text(raw)
    return normalize_plain_email_text(raw)
