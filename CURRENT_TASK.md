# Current task — PHASE 13

## Goal

Turn important inferred events into actionable inbox items (notifications).

## Do

1. Create `notifications` table (`title`, `body`, `priority`, `status`, `source_object_id`, `related_object_id`, `proposal` JSONB, `read_at`, timestamps).
2. Priority: `low`, `normal`, `high`, `urgent`.
3. Status: `new`, `read`, `accepted`, `ignored`, `resolved`.
4. Wire notification creation to meaningful Secretary/agent events where infrastructure exists.
5. Defer external delivery (email/push) until connector phases.

## Defer

- `send_notification` job type until notification writes are defined.
- Public MCP exposure.

## Accept

Important inferred events appear as inbox notifications with provenance links to source objects.

## Note

Secrets only in `.env`. Stop after phase for user review.
