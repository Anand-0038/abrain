import { isDomainEvent, type DomainEvent } from "@/src/contracts/events";

export type HealthResponse = {
  service: string;
  status: "ok";
  environment: string;
  memory_boundary: "not_configured" | "sibyl_local" | "disabled";
  checked_at: string;
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Backend health returned HTTP ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export type Npc = {
  npc_id: string;
  owner_id: string;
  name: string;
  appearance: NpcAppearance;
  role: string;
  personality: string;
  specialization: "primary" | "planner" | "worker" | "reviewer";
};

export type NpcAvatarKey = "node" | "scout" | "orbiter";
export type NpcAccessoryKey = "none" | "antenna" | "satchel";
export type NpcAppearance = {
  palette: string;
  avatar_key: NpcAvatarKey;
  accessory_key: NpcAccessoryKey;
};

export type HandoffStatus = "created" | "accepted" | "working" | "completed" | "blocked";

export type HandoffContext = {
  memory_id: string;
  concept: string;
  key: string;
  value: string;
  source_session_id: string;
  confidence: number | null;
  created_at: string;
  evidence_ref: string | null;
  tier: "entity";
  relevance_reason: string;
};

export type ScopedHandoff = {
  handoff_id: string;
  owner_id: string;
  source_agent_id: string;
  target_agent_id: string;
  parent_task_id: string;
  child_task_id: string;
  objective: string;
  selected_memory_ids: string[];
  selected_context: HandoffContext[];
  status: HandoffStatus;
  created_at: string;
  completed_at: string | null;
  result: string | null;
};

export type Session = {
  session_id: string;
  npc_id: string;
  status: "fresh" | "active" | "terminated";
  started_at: string;
  terminated_at: string | null;
};

export type MemoryCandidate = {
  candidate_id: string;
  owner_id: string;
  npc_id: string;
  source_session_id: string;
  source_turn_id: string;
  concept: string;
  key: string;
  value: string;
  confidence: number;
  explicit_remember?: boolean;
  sensitive?: boolean;
  transient?: boolean;
};

export type MemoryRecord = {
  memory_id: string;
  owner_id: string;
  npc_id: string;
  source_session_id: string;
  concept: string;
  key: string;
  value: string;
  confidence: number | null;
  created_at: string;
  supersedes: string | null;
  evidence_ref: string | null;
};

export type MemoryRetrieval = {
  record: MemoryRecord;
  query: string;
  tier: string;
  source: "sibyl_search" | "sibyl_entity_list" | "abrain_scoped_handoff";
  provider_rank: number | null;
  provider_snippet: string | null;
  relevance_reason: string;
};

export type AgentRunResult = {
  response: string;
  plan: string[];
  proposed_action: string;
  used_memory_ids: string[];
  memory_effect: "none" | "influenced" | "blocked";
  needs_more_context: boolean;
  task_update: Record<string, unknown> | null;
};

export type TaskStatus = "queued" | "thinking" | "working" | "blocked" | "review" | "completed";

export type AgentTask = {
  task_id: string;
  owner_id: string;
  assigned_agent_id: string;
  title: string;
  objective: string;
  status: TaskStatus;
  created_at: string;
  current_step: string;
  result: string | null;
  relevant_memory_ids: string[];
  parent_task_id: string | null;
};

export type TaskRunResult = {
  task: AgentTask;
  agent_run: AgentRunResult;
  retrievals: MemoryRetrieval[];
  persisted_result_memory_id: string | null;
  handoff: ScopedHandoff | null;
};

export type ContinuityResult = {
  request: { owner_id: string; npc_id: string; query: string };
  status: string;
  action: string;
  memory_enabled: boolean;
  influenced_by_memory: boolean;
  recalled_memory_ids: string[];
  recalled_memories: MemoryRecord[];
  retrievals: MemoryRetrieval[];
  agent_run: AgentRunResult;
  explanation: string;
  agent_response: string;
};

export type ContinuityComparisonLane = {
  session_id: string;
  decision: Omit<ContinuityResult, "request">;
};

export type ContinuityComparison = {
  request: { owner_id: string; npc_id: string; query: string };
  memory_lane: ContinuityComparisonLane;
  memory_disabled_lane: ContinuityComparisonLane;
  diverged: boolean;
};

export type CausalReplay = {
  memory: MemoryRecord;
  steps: { step: string; event_id: string | null; event_type: string; detail: string }[];
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed with HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function createNpc(input: { owner_id: string; name: string; appearance: NpcAppearance }) {
  return requestJson<{ npc: Npc }>("/api/npcs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listNpcs(owner_id: string) {
  return requestJson<{ npcs: Npc[] }>(`/api/npcs?owner_id=${encodeURIComponent(owner_id)}`);
}

export function createWorker(input: {
  owner_id: string;
  primary_agent_id: string;
  name: string;
  specialization: "planner" | "worker" | "reviewer";
  appearance?: NpcAppearance;
}) {
  return requestJson<{ npc: Npc }>("/api/npcs/workers", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      appearance: input.appearance ?? {
        palette: "amber",
        avatar_key: "scout",
        accessory_key: "satchel",
      },
    }),
  });
}

export function listMemories(owner_id: string, npc_id?: string) {
  const suffix = npc_id ? `&npc_id=${encodeURIComponent(npc_id)}` : "";
  return requestJson<{ memories: MemoryRecord[] }>(
    `/api/memories?owner_id=${encodeURIComponent(owner_id)}${suffix}`,
  );
}

export function startSession(owner_id: string, npc_id: string) {
  return requestJson<{ session: Session }>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ owner_id, npc_id }),
  });
}

export function listSessions(owner_id: string, npc_id: string) {
  return requestJson<{ sessions: Session[] }>(
    `/api/sessions?owner_id=${encodeURIComponent(owner_id)}&npc_id=${encodeURIComponent(npc_id)}`,
  );
}

export function recordTurn(owner_id: string, session_id: string, text: string) {
  return requestJson<{
    turn: { turn_id: string; session_id: string; text: string };
    agent_response: string;
    memory_influenced: boolean;
    recalled_memory_ids: string[];
    retrievals: MemoryRetrieval[];
    agent_run: AgentRunResult;
    candidates: MemoryCandidate[];
    extraction_status: "disabled" | "completed" | "failed";
  }>("/api/conversations/turns", {
    method: "POST",
    body: JSON.stringify({ owner_id, session_id, text }),
  });
}

export function promoteCandidate(candidate: MemoryCandidate, confirm = false) {
  return requestJson<{ record: MemoryRecord; decision: { disposition: string; reason: string } }>(
    "/api/memory/candidates/promote",
    { method: "POST", body: JSON.stringify({ candidate, confirm }) },
  );
}

export function decideCandidate(candidate: MemoryCandidate) {
  return requestJson<{
    candidate: MemoryCandidate;
    decision: { disposition: "promote" | "confirm" | "reject"; reason: string };
  }>("/api/memory/candidates/decide", {
    method: "POST",
    body: JSON.stringify({ candidate, confirm: false }),
  });
}

export function restartSession(session_id: string, owner_id: string) {
  return requestJson<{ terminated: Session; fresh: Session }>(
    `/api/sessions/${encodeURIComponent(session_id)}/restart?owner_id=${encodeURIComponent(owner_id)}`,
    { method: "POST" },
  );
}

export function restoreContinuity(
  session_id: string,
  input: { owner_id: string; npc_id: string; query: string },
) {
  return requestJson<ContinuityResult>(
    `/api/sessions/${encodeURIComponent(session_id)}/continuity`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function compareContinuity(input: {
  owner_id: string;
  npc_id: string;
  session_id: string;
  query: string;
}) {
  return requestJson<ContinuityComparison>("/api/continuity/compare", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateMemory(
  memory_id: string,
  owner_id: string,
  input: { key: string; value: string; confidence: number | null },
) {
  return requestJson<{ memory_id: string; operation: string; verified: boolean }>(
    `/api/memories/${encodeURIComponent(memory_id)}?owner_id=${encodeURIComponent(owner_id)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
}

export function archiveMemory(memory_id: string, owner_id: string) {
  return requestJson<{ memory_id: string; operation: string; verified: boolean }>(
    `/api/memories/${encodeURIComponent(memory_id)}/archive?owner_id=${encodeURIComponent(owner_id)}`,
    { method: "POST" },
  );
}

export function deleteMemory(memory_id: string, owner_id: string) {
  return requestJson<{ memory_id: string; operation: string; verified: boolean }>(
    `/api/memories/${encodeURIComponent(memory_id)}?owner_id=${encodeURIComponent(owner_id)}`,
    { method: "DELETE" },
  );
}

export function fetchCausalReplay(owner_id: string, memory_id: string) {
  return requestJson<CausalReplay>(
    `/api/continuity/replay?owner_id=${encodeURIComponent(owner_id)}&memory_id=${encodeURIComponent(memory_id)}`,
  );
}

export async function fetchRecentEvents(
  owner_id?: string,
  npc_id?: string,
): Promise<DomainEvent[]> {
  const params = new URLSearchParams();
  if (owner_id) params.set("owner_id", owner_id);
  if (npc_id) params.set("npc_id", npc_id);
  const query = params.toString();
  const result = await requestJson<{ events: unknown[] }>(
    `/api/events/recent${query ? `?${query}` : ""}`,
  );
  return result.events.filter(isDomainEvent);
}

export function createTask(input: {
  owner_id: string;
  assigned_agent_id: string;
  objective: string;
  title?: string;
  parent_task_id?: string;
}) {
  return requestJson<{ task: AgentTask }>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTasks(owner_id: string, assigned_agent_id?: string) {
  const params = new URLSearchParams({ owner_id });
  if (assigned_agent_id) params.set("assigned_agent_id", assigned_agent_id);
  return requestJson<{ tasks: AgentTask[] }>(`/api/tasks?${params.toString()}`);
}

export function runTask(task_id: string, owner_id: string, session_id?: string) {
  return runTaskWithHandoff(task_id, owner_id, { session_id });
}

export function runTaskWithHandoff(
  task_id: string,
  owner_id: string,
  input: { session_id?: string; handoff_id?: string },
) {
  return requestJson<TaskRunResult>(`/api/tasks/${encodeURIComponent(task_id)}/run`, {
    method: "POST",
    body: JSON.stringify({ owner_id, ...input }),
  });
}

export function createHandoff(
  task_id: string,
  input: {
    owner_id: string;
    source_agent_id: string;
    target_agent_id: string;
    objective: string;
    selected_memory_ids: string[];
  },
) {
  return requestJson<{ handoff: ScopedHandoff; task: AgentTask }>(
    `/api/tasks/${encodeURIComponent(task_id)}/handoffs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listHandoffs(owner_id: string) {
  return requestJson<{ handoffs: ScopedHandoff[] }>(
    `/api/handoffs?owner_id=${encodeURIComponent(owner_id)}`,
  );
}
