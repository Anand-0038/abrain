export const EVENT_TYPES = [
  "system.ready",
  "system.heartbeat",
  "owner.created",
  "npc.created",
  "npc.customized",
  "conversation.turn_recorded",
  "memory.extraction_failed",
  "memory.candidate_detected",
  "memory.candidate_created",
  "memory.candidate_promoted",
  "memory.candidate_rejected",
  "memory.candidate_confirmed",
  "memory.candidate_undone",
  "memory.write_requested",
  "memory.write_succeeded",
  "memory.write_failed",
  "memory.object_materialized",
  "memory.updated",
  "memory.archived",
  "memory.deleted",
  "npc.session_started",
  "npc.session_restarted",
  "npc.session_terminated",
  "memory.recall_requested",
  "memory.recall_succeeded",
  "memory.recall_failed",
  "continuity.memory_disabled",
  "behavior.changed_by_memory",
  "task.created",
  "task.started",
  "task.step_changed",
  "task.blocked",
  "task.completed",
  "handoff.created",
  "handoff.accepted",
  "handoff.started",
  "handoff.completed",
  "handoff.blocked",
  "agent.run_failed",
  "causal.replay_requested",
  "causal.replay_completed",
  "continuity.failed",
  "conversation.completed",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export type DomainEvent = {
  event_id: string;
  event_type: EventType;
  occurred_at: string;
  source: string;
  correlation_id: string;
  agent_id: string | null;
  session_id: string | null;
  proof_ref: string | null;
  payload: Record<string, unknown>;
};

export function isDomainEvent(value: unknown): value is DomainEvent {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.event_id === "string" &&
    typeof candidate.event_type === "string" &&
    EVENT_TYPES.includes(candidate.event_type as EventType) &&
    typeof candidate.occurred_at === "string" &&
    typeof candidate.source === "string" &&
    typeof candidate.correlation_id === "string" &&
    (typeof candidate.agent_id === "string" || candidate.agent_id === null) &&
    (typeof candidate.session_id === "string" || candidate.session_id === null) &&
    (typeof candidate.proof_ref === "string" || candidate.proof_ref === null) &&
    typeof candidate.payload === "object" &&
    candidate.payload !== null &&
    !Array.isArray(candidate.payload)
  );
}
