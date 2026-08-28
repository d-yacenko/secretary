from app.api.schemas import ContextBuildResult
from app.llm.secretary_models import SecretaryAnalysis, SecretaryProposal
from app.services.notification_service import NotificationService


def calculate_notification_priority(
    analysis: SecretaryAnalysis,
    proposal: SecretaryProposal,
) -> str:
    importance = analysis.importance or 0.0
    urgency = analysis.urgency or 0.0
    score = max(importance, urgency) * 0.6 + proposal.confidence * 0.4
    if importance >= 0.9 and urgency >= 0.85:
        return "urgent"
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "normal"
    return "low"


def proposal_to_payload(
    proposal: SecretaryProposal,
    context: ContextBuildResult,
) -> dict:
    evidence = []
    for index in proposal.evidence_item_indices:
        item = context.items[index]
        evidence.append(
            {
                "context_index": index,
                "object_id": str(item.object_id),
                "kind": item.kind,
                "title": item.title,
                "why_included": item.why_included,
                "canonical_uri": item.canonical_uri,
            }
        )
    return {
        "type": proposal.type,
        "title": proposal.title,
        "description": proposal.description,
        "confidence": proposal.confidence,
        "due_at": proposal.due_at.isoformat() if proposal.due_at else None,
        "start_at": proposal.start_at.isoformat() if proposal.start_at else None,
        "relation_type": proposal.relation_type,
        "target_object_id": (
            str(proposal.target_object_id) if proposal.target_object_id else None
        ),
        "evidence": evidence,
    }


def create_notifications_from_analysis(
    service: NotificationService,
    analysis: SecretaryAnalysis,
    context: ContextBuildResult,
) -> list:
    from app.db.models import Notification

    notifications: list[Notification] = []
    for proposal in analysis.proposals:
        source_item = context.items[proposal.evidence_item_indices[0]]
        notification = service.create(
            title=proposal.title,
            body=proposal.description or analysis.summary,
            priority=calculate_notification_priority(analysis, proposal),
            source_object_id=source_item.object_id,
            related_object_id=proposal.target_object_id,
            proposal=proposal_to_payload(proposal, context),
        )
        notifications.append(notification)
    return notifications
