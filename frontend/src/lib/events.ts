import { isDomainEvent, type DomainEvent } from "@/src/contracts/events";

export function parseDomainEvent(raw: string): DomainEvent | null {
  try {
    const value: unknown = JSON.parse(raw);
    return isDomainEvent(value) ? value : null;
  } catch {
    return null;
  }
}

export function scopeEventsToWorld(
  events: DomainEvent[],
  input: { ownerId: string; npcId: string; sessionId: string | null },
): DomainEvent[] {
  return events.filter((event) => {
    const payload = event.payload;
    if (event.event_type.startsWith("system.")) return true;
    const hasOwner = typeof payload.owner_id === "string";
    const eventAgents = [payload.npc_id, payload.source_agent_id, payload.target_agent_id].filter(
      (value): value is string => typeof value === "string",
    );
    if (hasOwner && eventAgents.length > 0) {
      return payload.owner_id === input.ownerId && eventAgents.includes(input.npcId);
    }
    return (
      eventAgents.includes(input.npcId) ||
      payload.owner_id === input.ownerId ||
      payload.session_id === input.sessionId ||
      event.session_id === input.sessionId
    );
  });
}
