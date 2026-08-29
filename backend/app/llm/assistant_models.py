from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class AssistantHistoryMessage:
    role: str
    content: str


@dataclass
class AssistantProviderResult:
    answer: str
    candidate_object_ids: list[UUID] = field(default_factory=list)
    affected_object_ids: list[UUID] = field(default_factory=list)
    store_false_used: bool = True
    openai_input_tokens: int | None = None
    openai_output_tokens: int | None = None
