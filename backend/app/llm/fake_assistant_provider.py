import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.llm.assistant_models import AssistantHistoryMessage, AssistantProviderResult
from app.tools.executor import ToolExecutionResult

_OBJECT_ID_PATTERN = re.compile(r"object_id=([0-9a-fA-F-]{36})")


class FakeAssistantProvider:
  """Deterministic assistant for tests without OpenAI."""

  def __init__(self, store_false: bool = True) -> None:
      self._store_false = store_false
      self._calls: list[tuple[str, dict]] = []

  @property
  def calls(self) -> list[tuple[str, dict]]:
      return list(self._calls)

  def run(
      self,
      message: str,
      history: list[AssistantHistoryMessage],
      ui_context: str,
      reference_datetime: datetime,
      timezone: str,
      tool_runner: Callable[[str, dict], ToolExecutionResult],
  ) -> AssistantProviderResult:
      lowered = message.lower()
      candidate_ids: list[UUID] = []
      affected_ids: list[UUID] = []

      if "project alpha" in lowered:
          result = tool_runner(
              "search_objects",
              {"query": "Project Alpha", "limit": 5},
          )
          self._calls.append(("search_objects", {"query": "Project Alpha", "limit": 5}))
          if result.success and result.output:
              for obj in result.output.get("objects", []):
                  _append_uuid(candidate_ids, obj.get("id"))
          if candidate_ids:
              ctx = tool_runner(
                  "get_context",
                  {"object_id": str(candidate_ids[0]), "max_chars": 2000},
              )
              self._calls.append(
                  ("get_context", {"object_id": str(candidate_ids[0]), "max_chars": 2000})
              )
              if ctx.success and ctx.output:
                  for item in ctx.output.get("items", []):
                      _append_uuid(candidate_ids, item.get("object_id"))
          answer = "Pending items for Project Alpha are listed in the referenced objects."
      elif ui_context and ("what is this" in lowered or "related to" in lowered):
          object_id = _extract_object_id(ui_context)
          args: dict = {"max_chars": 2000}
          if object_id is not None:
              args["object_id"] = object_id
          result = tool_runner("get_context", args)
          self._calls.append(("get_context", args))
          if result.success and result.output:
              for item in result.output.get("items", []):
                  _append_uuid(candidate_ids, item.get("object_id"))
          answer = "Here is what I found about the attached context."
      elif "create a task" in lowered or "prepare the course outline" in lowered:
          result = tool_runner(
              "create_task",
              {
                  "title": "Prepare course outline",
                  "confidence": 0.8,
                  "body": "Outline draft",
              },
          )
          self._calls.append(
              (
                  "create_task",
                  {
                      "title": "Prepare course outline",
                      "confidence": 0.8,
                      "body": "Outline draft",
                  },
              )
          )
          if result.success and result.output:
              obj = result.output.get("object")
              if obj:
                  _append_uuid(affected_ids, obj.get("id"))
                  _append_uuid(candidate_ids, obj.get("id"))
          answer = "I created a proposed task to prepare the course outline."
      else:
          answer = "I can help search your Secretary objects and tasks."

      return AssistantProviderResult(
          answer=answer,
          candidate_object_ids=candidate_ids,
          affected_object_ids=affected_ids,
          store_false_used=self._store_false,
      )


def _append_uuid(target: list[UUID], value: object) -> None:
    if not value:
        return
    try:
        parsed = UUID(str(value))
    except ValueError:
        return
    if parsed not in target:
        target.append(parsed)


def _extract_object_id(ui_context: str) -> str | None:
    match = _OBJECT_ID_PATTERN.search(ui_context)
    if match is None:
        return None
    return match.group(1)
