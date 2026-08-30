"""Deterministic tool permission policy for Secretary domain tools."""

from enum import Enum


class ToolPermission(str, Enum):
    READ = "READ"
    INTERNAL_WRITE = "INTERNAL_WRITE"
    EXTERNAL_PROPOSE = "EXTERNAL_PROPOSE"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    COMMUNICATE = "COMMUNICATE"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


def evaluate_policy(permission: ToolPermission) -> PolicyDecision:
    """PHASE 23C baseline: preserve current INTERNAL_WRITE behavior."""
    if permission in (
        ToolPermission.READ,
        ToolPermission.INTERNAL_WRITE,
        ToolPermission.EXTERNAL_PROPOSE,
    ):
        return PolicyDecision.ALLOW
    if permission in (
        ToolPermission.EXTERNAL_WRITE,
        ToolPermission.COMMUNICATE,
    ):
        return PolicyDecision.REQUIRE_APPROVAL
    return PolicyDecision.DENY


def policy_block_message(decision: PolicyDecision) -> str:
    if decision == PolicyDecision.REQUIRE_APPROVAL:
        return "tool execution requires approval"
    return "tool execution denied by policy"
