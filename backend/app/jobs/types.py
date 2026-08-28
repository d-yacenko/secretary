from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.llm.embedding_service import EmbeddingService

JobHandler = Callable[[Session, EmbeddingService, dict[str, Any]], None]
