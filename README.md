# A-Brain

A-Brain is an agent-continuity product: a fresh agent runtime should be able to recover
relevant owner context from a persistent, identity-bound brain and make a better next decision.
Its small 2D world is a visual projection of authoritative backend events, making memory,
session death, recall, and changed behavior visible without replacing the real product flow.

## Current status

This local release boots a Next.js frontend, a FastAPI
runtime, and a versioned domain-event contract shared across the two boundaries. The backend now
uses the verified public `sibyl-memory-client` 0.7.x API against a local SQLite provider. The
adapter writes generic owner-context records and persistent NPC brain identities, verifies both
writes, reopens them after the process boundary, searches owner context, and supports
update/archive/delete with provider-side tenant isolation.

The current proof boundary is local: no hosted Sibyl service, public deployment, or hackathon
submission claim is made by this checkout. The local product slice includes generic memory
promotion and CRUD, durable NPC identity reopen, ephemeral session restart, fresh-session
continuity, explicit agent-side responses, causal replay, and a PixiJS projection driven by
confirmed backend events.

Conversation turns can optionally run through a Gemini structured-output extractor. Set
`ABRAIN_MODEL_PROVIDER=gemini` and provide `ABRAIN_GEMINI_API_KEY` to enable it. The extractor
returns only a bounded candidate schema; server-side provenance is attached before promotion,
and the existing consent policy still decides whether a candidate is promoted, confirmed, or
rejected. If the provider is disabled, turns remain transient and no extraction success is
claimed.

Agent responses run through a provider-neutral `AgentRunner`. The credential-free local runner is
the default; set `ABRAIN_AGENT_PROVIDER=gemini` with the Gemini credential to use the real
structured-output Gemini runner. Both runners receive the current request, NPC role/personality,
current task state, and only the relevant Sibyl retrievals. They return a structured
response, plan, proposed action, used memory IDs, memory effect, missing-context flag, and optional
task update. Provider output is rejected if it references a memory ID that Sibyl did not return.
The local runner is intentionally bounded: it can produce a useful plan or memory-scoped decision,
but it does not claim external research, tool calls, or side effects. Use the Gemini runner for
model-backed task execution and verify its credentials/provider boundary separately.

Tasks are user-created rather than seeded missions. `POST /api/tasks` creates a generic mission and
`POST /api/tasks/{task_id}/run` runs it through the same agent pipeline. The lifecycle is
`queued → thinking → working → blocked/review → completed`; blocked/review tasks can be resumed
after context or review; current task state is written and
verified in Sibyl HOT state under `task:{task_id}`. A completed memory-influenced task may promote
its result as a WARM `decision` with a COLD provenance event. The task response carries the exact
retrieval metadata and memory IDs that influenced the result.

The owner can optionally add at most two specialist NPCs (planner, worker, or reviewer) through
`POST /api/npcs/workers`. A primary task can create a scoped child task with
`POST /api/tasks/{task_id}/handoffs`, selecting the exact WARM memory IDs to share. A-Brain verifies
that each selected record belongs to the source agent and owner, snapshots only those records into
the handoff grant, and runs the child with `source=abrain_scoped_handoff` instead of searching the
target agent's entire brain. This permission layer is A-Brain logic over Sibyl; Sibyl is not being
presented as an ACL or agent-handoff product. Handoff state is verified in Sibyl HOT state under
`handoff:{handoff_id}`, while `handoff.created/accepted/started/completed/blocked` are the runtime
audit events. The same boundary supports a bounded A → B → C review chain without becoming a
civilization simulator.

The product starts with no owner, NPC, conversation, memory, or story fixture. Users choose a
small NPC appearance—palette, body silhouette, and optional accessory—during onboarding. The
world renders identity and role from the persisted NPC record; the Purple Memory is private
fixture material and is not part of production code.

## Prior Work

The A-Brain concept and initial repository scaffold predate the Sibyl hackathon build window. The
repository history preserves that starting point. The current product implementation is a
general-purpose owner-context and session-continuity system; it does not rely on the private Purple
Memory fixture or any seeded personal data.

## Repository layout

```text
abrain/
├── backend/       FastAPI runtime and typed domain modules
├── contracts/     JSON Schema and public event example
├── docs/          Architecture and truthful local demo runbook
└── frontend/      Next.js/TypeScript shell with a PixiJS world viewport
```

The backend owns domain state and emits events. The frontend consumes the same typed event shape:
SSE carries system readiness/heartbeat signals, while owner/NPC-scoped recent-event polling carries
application lifecycle events to the world projection. The canvas never becomes the source of
memory truth.

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for exact memory/event locations and
[docs/DEMO.md](./docs/DEMO.md) for the reproducible local continuity runbook.

## Requirements

- Node.js 22+
- Corepack with pnpm 11+
- Python 3.11+

## Local start

Install frontend dependencies:

```bash
corepack pnpm install
```

Create local configuration:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

In terminal 1, install the backend and start it:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'backend[dev]'
corepack pnpm backend:dev
```

In terminal 2, start the frontend:

```bash
corepack pnpm dev:frontend
```

Open <http://localhost:3000> for development. For the production frontend, use the documented
production command below and open <http://127.0.0.1:3125>. The shell should report the backend health state and receive the
generic `system.ready` event. With `ABRAIN_MEMORY_ENABLED=true`, the runtime uses the local Sibyl
database at `ABRAIN_SIBYL_DB_PATH`. The backend health endpoint is:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

For a production frontend, `NEXT_PUBLIC_API_BASE_URL` is embedded during `next build`, so set it
for the build as well as the server command:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 corepack pnpm build
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 corepack pnpm start:frontend
```

The root `start:frontend` script pins the production server to `127.0.0.1:3125`, matching
`docs/DEMO.md` and the default local acceptance command.

`ABRAIN_CORS_ORIGINS` accepts a comma-separated list of browser origins. The API permits only
the mutation methods it exposes (`GET`, `POST`, `PATCH`, and `DELETE`).

When extraction is enabled, a successful conversation response includes `candidates` and
`extraction_status`. A configured provider failure returns the turn with
`extraction_status: "failed"` and emits `memory.extraction_failed`; it never writes a guessed
memory.

## Verification

With the backend and frontend running, the complete local acceptance gate can be run with:

```bash
corepack pnpm verify:local
```

It checks the local backend health response, frontend HTTP response, tracked-file public
boundary, formatting, lint, typecheck, tests, production build, and whitespace errors. This
command proves only the local `sibyl_local` boundary; it does not claim hosted deployment,
public release, or hackathon submission.

The individual checks remain available:

```bash
corepack pnpm format:check
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
```

The backend checks can also be run directly after the editable install:

```bash
python -m pytest backend/tests
```

## Memory boundary

`backend/src/abrain_api/memory/adapter.py` is the only application boundary that imports
`sibyl_memory_client`. It maps A-Brain records intentionally:

- current brain state → Sibyl HOT state documents;
- current task state → Sibyl HOT state documents keyed by task ID;
- scoped delegation grants → Sibyl HOT state documents keyed by handoff ID;
- durable owner context → Sibyl WARM entities;
- provenance and lifecycle changes → Sibyl COLD journal events;
- archive/delete → provider entity operations.

Normal non-empty recall calls Sibyl's verified `MemoryClient.search(...)` primitive over the WARM
`entity` tier and preserves its provider rank/snippet in the response metadata. A-Brain then applies
the deterministic owner/NPC boundary and returns the matching memory IDs, tier, source, query, and
relevance reason to the decision/UI layer. This is Sibyl provider search/FTS, not semantic or vector
search. Empty-query inspection uses a provider entity listing because there is no meaningful search
term. HOT state and COLD journal entries remain deliberate current-state/provenance writes; they are
not silently promoted into structured owner-context records during recall.

Owner identity is hashed into a stable Sibyl tenant identifier. The record body retains the
original owner, NPC, source session, timestamp, confidence, and evidence reference so recalled
memory remains explainable. Brain identities are stored separately under the `abrain.npc`
provider category, while owner context uses `abrain.memory`; they are never mixed in the user
memory list. `backend/tests/test_sibyl_adapter.py` and `backend/tests/test_npc_reopen_api.py`
destroy and reopen the adapter/application boundary, then prove identity persistence and
cross-owner isolation using the real SQLite provider.

## Event contract

`contracts/domain-events.schema.json` is the wire-level contract. The backend validates events
with Pydantic in `backend/src/abrain_api/contracts.py`; the frontend validates received events in
`frontend/src/lib/events.ts`. The scoped recent-event feed includes backend lifecycle,
conversation, memory, session, continuity, and causal replay events. The SSE endpoint is limited
to system readiness/heartbeat signals. The Pixi world renders confirmed event data; it does not
manufacture provider success or memory objects.

The world is intentionally asset-light and original: Pixi primitives form a compact six-space
agent city (Home/Spawn, Memory Vault, Mission Plaza, Workshop, Review Tower, and Session Gate).
Roads, block footprints, trees, lamps, signs, and reusable building silhouettes establish a tiny
place without bundling third-party art. Confirmed memory objects travel as shards, the agent moves
between city spaces after real lifecycle events, the gate visualizes session death and fresh-body
arrival, and the plaza/workshop/tower expose task and memory-influenced work. This is game-feel
polish around the real event stream, not a pre-recorded animation or a story-specific game scene.

## Product boundary

The verified local continuity path is:

```text
conversation → promoted generic memory → session termination
→ genuinely fresh session → Sibyl recall → changed useful behavior
→ explicit safe degradation with memory disabled
```

After a restart, the first normal conversation turn follows that same recall path automatically;
the Continuity panel is an inspectable diagnostic for the identical decision boundary, not a
separate scripted mode. A fresh turn emits recall and behavior-provenance events before the
response is returned. If no relevant record exists, or memory is disabled, the agent asks for
context rather than inventing prior knowledge.
The owner-scoped `GET /api/sessions?owner_id=...&npc_id=...` endpoint exposes the current
in-process session lineage, and the world renders the terminated predecessor and fresh session
as a compact proof receipt. This is runtime inspection only: session lineage is not persisted as
hosted history across backend restarts.
The optional `POST /api/continuity/compare` diagnostic requires a clean fresh session and runs
the same query through a real Sibyl-enabled lane and a separate memory-disabled lane. The latter
uses the same continuity decision policy with no provider records, asks for missing context, and
is terminated after inspection; it is not a prerecorded or cached judge path.

The same agent pipeline is used when memory is disabled. It receives an empty retrieval set and
must request missing owner context rather than silently falling back to old conversation or
inventing a remembered preference. `behavior.changed_by_memory` is emitted only when the runner's
validated `used_memory_ids` is non-empty.

The browser journey has been run against both the Next production build and the FastAPI runtime:
onboarding → conversation turn → real Sibyl write → restart → fresh recall → causal replay.
Disabling Sibyl returns `continuity_unavailable` with `request_missing_context` and no recalled
memory IDs. The general-purpose Gemini extractor is implemented but optional and
credential-gated. A hosted Sibyl service, user authentication, and cross-machine session
recovery remain future work; this release does not claim them. Session restart and continuity
requests are still owner-scoped: the runtime verifies that the supplied owner owns the NPC before
terminating a session or recalling its brain. Session/transcript reads, conversation writes, and
candidate promotion use the same owner/NPC/source-session checks. Recent event history is filtered
on the server; an unscoped browser receives only system events, while the active owner/NPC receives
its own event history for the world projection.

## License

MIT. See [LICENSE](./LICENSE).

Direct dependency and asset attribution is recorded in
[THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md). No third-party image, audio, or sprite assets
are bundled in this local build.
