AGENT_ORIGIN = "agent"
PROPOSED_STATE = "proposed"
SOURCE_ORIGIN = "source"
OBSERVED_STATE = "observed"


def default_object_state(origin: str, state: str | None = None) -> str:
    if state is not None:
        return state
    if origin == SOURCE_ORIGIN:
        return OBSERVED_STATE
    if origin == AGENT_ORIGIN:
        return PROPOSED_STATE
    return "confirmed"


def validate_agent_proposal(
    origin: str,
    state: str,
    confidence: float | None,
    resource: str,
) -> None:
    if origin != AGENT_ORIGIN or state != PROPOSED_STATE:
        return
    if confidence is None:
        raise ValueError(f"{resource}: agent proposed items require confidence")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"{resource}: confidence must be between 0 and 1")
