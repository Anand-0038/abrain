# A-Brain local demo runbook

This runbook describes the real product flow. It is not a scripted fixture or prerecorded path.

## Start

Run the backend and frontend using the commands in the root README, then open:

<http://127.0.0.1:3125>

The backend health check is:

<http://127.0.0.1:8000/api/health>

## Golden path (the only path to record)

The product is broader than this sequence, but the judge-facing story is deliberately narrow:
show one real user-created NPC carrying useful context across a session boundary. Do not tour
tasks, CRUD, delegation, and every diagnostic in one recording.

1. Enter A-Brain World, create an owner and name an NPC such as `Nova`. The brain starts empty.
2. Give the NPC an arbitrary useful fact or preference through the in-world conversation. Use the
   explicit remember action when consent should be immediate; otherwise review the candidate.
3. Confirm the memory in the Brain Vault. A confirmed memory ID appears in the UI and an event
   reaches the Pixi world.
4. Give the same NPC a related task so the first body uses the stored context.
5. Restart the agent. The previous session is terminated and a new session ID appears with zero
   transient turns.
6. Ask a related question without repeating the old context.
7. Inspect the context-restored response and its recalled memory IDs. The retrieval details identify
   The retrieval details identify the Sibyl query, WARM tier, provider source, rank/snippet when
   available, and why each returned record was relevant. The UI labels this as Sibyl search/FTS,
   not semantic or vector search.
8. Open `Why did this change?` to inspect the memory-causality chain.
9. Open `Why did this change?` to inspect the real memory-causality chain.
10. Run `Compare with memory off` from a clean session. The enabled lane should restore context;
    the disabled lane should safely ask for context and stop.
11. Inspect the structured agent run: its plan and proposed action change when scoped Sibyl records
    are available, while the disabled lane has no used memory IDs and requests context.

The two-line close is: **WHY?** (causal replay), then **COMPARE MEMORY OFF** (same request, safe
continuity break). Stop there. Scoped delegation is an optional product capability, not part of
the primary recording.

## Arbitrary task path

1. In the Activity Zone, enter any objective such as a research request, a plan, a review, a
   recommendation, or unfinished work. Leave the title empty to derive it from the objective.
2. Create and run the task. The event rail and world move through `queued`, `thinking`, and
   `working`; the backend writes each current task snapshot to Sibyl HOT state.
3. Inspect the completed task's result, current step, and relevant memory IDs. A memory-influenced
   completion also creates a WARM decision record with the task ID as its evidence reference and a
   COLD provenance event.
4. Toggle Sibyl off and repeat the same kind of arbitrary task. The same runner executes without
   recalled owner records; it must not invent context, and no durable task-result memory is claimed.

## Optional scoped delegation path

1. In the Activity Zone, add one specialist (Worker) and optionally a second (Reviewer). The UI
   keeps the active roster at one primary plus two specialists.
2. Select the exact confirmed Brain Vault shards that the primary is allowed to share, choose the
   target specialist, and press `Delegate selected context` on a completed primary task.
3. A child task is created and runs in a fresh target-agent session. The returned retrieval metadata
   is marked `abrain_scoped_handoff`; it contains only the selected IDs, not an unrestricted search
   of the target's owner brain.
4. Inspect the handoff receipt. It shows source → target, selected IDs, status, and the worker result.
   For the optional reviewer path, delegate the worker's result memory from the child task to the
   reviewer. `handoff.*` events move the Activity Zone and world through the real lifecycle.

The selection and permission check are A-Brain application logic over Sibyl. The UI does not claim
that Sibyl implements ACL handoff. If the selected record is missing, belongs to another owner, or
belongs to another source NPC, the API rejects the handoff and emits no success animation.

The default local runner is a bounded planner, not an external research worker. It labels that
boundary in its result. A Gemini-backed task run may provide model reasoning, but it is only a
provider claim when `ABRAIN_AGENT_PROVIDER=gemini` is configured and the request is observed.

## What to point out

- The body is ephemeral; the brain is persistent.
- Memory shards and movement are projections of confirmed backend events.
- `behavior.changed_by_memory` is emitted only when recalled context changes the decision.
- The event's memory IDs come from the runner's validated `used_memory_ids`, not from all search
  hits.
- The disabled lane uses the same continuity policy and never invents a remembered fact.

## Evidence boundary

This local runbook proves the local Sibyl SQLite boundary only. A public submission needs a fresh
recording with an on-screen timestamp or commit hash, the public repository URL, and the required
build-page/post artifacts during the official event window.
