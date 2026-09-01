import { describe, expect, it } from "vitest";
import { parseDomainEvent, scopeEventsToWorld } from "@/src/lib/events";

describe("domain event parsing", () => {
  it("accepts the shared system event envelope", () => {
    const event = parseDomainEvent(
      JSON.stringify({
        event_id: "evt_1",
        event_type: "system.ready",
        occurred_at: "2026-08-20T00:00:00Z",
        source: "abrain-runtime",
        correlation_id: "corr_1",
        agent_id: null,
        session_id: null,
        proof_ref: null,
        payload: { boundary: "local" },
      }),
    );

    expect(event?.event_type).toBe("system.ready");
  });

  it("rejects unsupported or malformed events", () => {
    expect(parseDomainEvent("not-json")).toBeNull();
    expect(parseDomainEvent(JSON.stringify({ event_type: "memory.write_succeeded" }))).toBeNull();
    expect(
      parseDomainEvent(
        JSON.stringify({
          event_id: "evt_2",
          event_type: "unknown.event",
          occurred_at: "2026-08-20T00:00:00Z",
          source: "test",
          correlation_id: "corr_2",
          agent_id: null,
          session_id: null,
          proof_ref: null,
          payload: {},
        }),
      ),
    ).toBeNull();
  });

  it("scopes world events to the active NPC and session", () => {
    const base = {
      occurred_at: "2026-08-20T00:00:00Z",
      source: "test",
      agent_id: null,
      proof_ref: null,
    } as const;
    const events = [
      {
        ...base,
        event_id: "system",
        event_type: "system.ready" as const,
        correlation_id: "system",
        session_id: null,
        payload: {},
      },
      {
        ...base,
        event_id: "mine",
        event_type: "memory.object_materialized" as const,
        correlation_id: "mine",
        session_id: null,
        payload: { owner_id: "owner-a", npc_id: "npc-a", memory_id: "m1" },
      },
      {
        ...base,
        event_id: "other",
        event_type: "memory.object_materialized" as const,
        correlation_id: "other",
        session_id: null,
        payload: { owner_id: "owner-b", npc_id: "npc-b", memory_id: "m2" },
      },
      {
        ...base,
        event_id: "same-npc-other-owner",
        event_type: "memory.object_materialized" as const,
        correlation_id: "same-npc-other-owner",
        session_id: null,
        payload: { owner_id: "owner-b", npc_id: "npc-a", memory_id: "m3" },
      },
      {
        ...base,
        event_id: "same-owner-other-npc",
        event_type: "memory.object_materialized" as const,
        correlation_id: "same-owner-other-npc",
        session_id: null,
        payload: { owner_id: "owner-a", npc_id: "npc-b", memory_id: "m4" },
      },
    ];

    expect(
      scopeEventsToWorld(events, { ownerId: "owner-a", npcId: "npc-a", sessionId: "session-a" }),
    ).toHaveLength(2);
  });

  it("keeps a scoped handoff visible to either participating agent", () => {
    const base = {
      occurred_at: "2026-08-20T00:00:00Z",
      source: "test",
      agent_id: null,
      proof_ref: null,
      session_id: null,
      event_type: "handoff.created" as const,
    };
    const event = {
      ...base,
      event_id: "handoff-1",
      correlation_id: "handoff-1",
      payload: {
        owner_id: "owner-a",
        npc_id: "npc-worker",
        source_agent_id: "npc-primary",
        target_agent_id: "npc-worker",
      },
    };

    expect(
      scopeEventsToWorld([event], {
        ownerId: "owner-a",
        npcId: "npc-primary",
        sessionId: null,
      }),
    ).toHaveLength(1);
    expect(
      scopeEventsToWorld([event], {
        ownerId: "owner-a",
        npcId: "npc-other",
        sessionId: null,
      }),
    ).toHaveLength(0);
  });
});
