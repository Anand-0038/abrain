"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { LandingPreview } from "@/src/components/landing-preview";

const WorldShell = dynamic(
  () => import("@/src/components/world-shell").then((module) => module.WorldShell),
  { ssr: false, loading: () => <div className="world-loading">Opening the world…</div> },
);
import {
  API_BASE_URL,
  archiveMemory,
  compareContinuity,
  createHandoff,
  createTask,
  createNpc,
  createWorker,
  decideCandidate,
  deleteMemory,
  fetchRecentEvents,
  fetchHealth,
  fetchCausalReplay,
  listNpcs,
  listHandoffs,
  listMemories,
  listSessions,
  listTasks,
  promoteCandidate,
  recordTurn,
  restartSession,
  runTask,
  runTaskWithHandoff,
  restoreContinuity,
  startSession,
  updateMemory,
  type ContinuityResult,
  type ContinuityComparison,
  type CausalReplay,
  type HealthResponse,
  type AgentRunResult,
  type AgentTask,
  type ScopedHandoff,
  type MemoryCandidate,
  type MemoryRecord,
  type MemoryRetrieval,
  type Npc,
  type NpcAccessoryKey,
  type NpcAvatarKey,
  type Session,
} from "@/src/lib/api";
import { parseDomainEvent, scopeEventsToWorld } from "@/src/lib/events";
import type { DomainEvent } from "@/src/contracts/events";

type ConnectionState = "checking" | "connected" | "error";
type Stage = "landing" | "onboarding" | "world";
type Theme = "light" | "dark";

function ownerKey(displayName: string) {
  const normalized = displayName.trim();
  if (!normalized) return "";
  return `owner-${crypto.randomUUID()}`;
}

export default function HomePage() {
  const [connection, setConnection] = useState<ConnectionState>("checking");
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    const savedTheme = window.localStorage.getItem("abrain.theme");
    return savedTheme === "dark" ? "dark" : "light";
  });
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [events, setEvents] = useState<DomainEvent[]>([]);
  const [stage, setStage] = useState<Stage>("landing");
  const [ownerName, setOwnerName] = useState("");
  const [npcName, setNpcName] = useState("");
  const [palette, setPalette] = useState("teal");
  const [avatarKey, setAvatarKey] = useState<NpcAvatarKey>("node");
  const [accessoryKey, setAccessoryKey] = useState<NpcAccessoryKey>("none");
  const [memoryConsent, setMemoryConsent] = useState(false);
  const [ownerId, setOwnerId] = useState("");
  const [npc, setNpc] = useState<Npc | null>(null);
  const [agents, setAgents] = useState<Npc[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLineage, setSessionLineage] = useState<Session[]>([]);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [turns, setTurns] = useState<{ id: string; speaker: "owner" | "agent"; text: string }[]>(
    [],
  );
  const [message, setMessage] = useState("");
  const [concept, setConcept] = useState("preference");
  const [memoryKey, setMemoryKey] = useState("");
  const [memoryValue, setMemoryValue] = useState("");
  const [rememberExplicitly, setRememberExplicitly] = useState(true);
  const [pendingCandidates, setPendingCandidates] = useState<MemoryCandidate[]>([]);
  const [extractionNotice, setExtractionNotice] = useState<string | null>(null);
  const [lastTurnMemoryIds, setLastTurnMemoryIds] = useState<string[]>([]);
  const [lastTurnRetrievals, setLastTurnRetrievals] = useState<MemoryRetrieval[]>([]);
  const [lastAgentRun, setLastAgentRun] = useState<AgentRunResult | null>(null);
  const [lastPromotedMemory, setLastPromotedMemory] = useState<MemoryRecord | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [handoffs, setHandoffs] = useState<ScopedHandoff[]>([]);
  const [workerName, setWorkerName] = useState("");
  const [workerSpecialization, setWorkerSpecialization] = useState<
    "planner" | "worker" | "reviewer"
  >("worker");
  const [selectedWorkerId, setSelectedWorkerId] = useState("");
  const [selectedHandoffMemoryIds, setSelectedHandoffMemoryIds] = useState<string[]>([]);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskObjective, setTaskObjective] = useState("");
  const [editingMemory, setEditingMemory] = useState<string | null>(null);
  const [forgettingMemory, setForgettingMemory] = useState<string | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");
  const [continuityQuery, setContinuityQuery] = useState("");
  const [continuity, setContinuity] = useState<ContinuityResult | null>(null);
  const [comparison, setComparison] = useState<ContinuityComparison | null>(null);
  const [replay, setReplay] = useState<CausalReplay | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const restoreInFlight = useRef(false);
  const restoredNpcId = useRef<string | null>(null);
  const restoreGeneration = useRef(0);
  const ownerIdRef = useRef("");
  const npcIdRef = useRef("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("abrain.theme", theme);
  }, [theme]);

  useEffect(() => {
    ownerIdRef.current = ownerId;
    npcIdRef.current = npc?.npc_id ?? "";
  }, [npc?.npc_id, ownerId]);

  useEffect(() => {
    const controller = new AbortController();
    const checkHealth = () =>
      fetchHealth(controller.signal)
        .then((result) => {
          setHealth(result);
          setConnection("connected");
          const savedOwnerId = window.localStorage.getItem("abrain.owner_id");
          const savedNpcId = window.localStorage.getItem("abrain.npc_id");
          if (
            !savedOwnerId ||
            !savedNpcId ||
            result.memory_boundary !== "sibyl_local" ||
            restoreInFlight.current ||
            restoredNpcId.current === savedNpcId
          )
            return;
          restoreInFlight.current = true;
          const generation = restoreGeneration.current;
          void listNpcs(savedOwnerId)
            .then(async ({ npcs }) => {
              if (generation !== restoreGeneration.current) return false;
              const savedNpc = npcs.find((item) => item.npc_id === savedNpcId);
              if (!savedNpc) return false;
              const reopened = await startSession(savedOwnerId, savedNpc.npc_id);
              const stored = await listMemories(savedOwnerId, savedNpc.npc_id);
              const lineage = await listSessions(savedOwnerId, savedNpc.npc_id);
              const storedTasks = await listTasks(savedOwnerId, savedNpc.npc_id);
              const storedHandoffs = await listHandoffs(savedOwnerId);
              if (generation !== restoreGeneration.current) return false;
              setOwnerId(savedOwnerId);
              setNpc(savedNpc);
              setAgents(npcs);
              setSession(reopened.session);
              setSessionLineage(lineage.sessions);
              setMemories(stored.memories);
              setTasks(storedTasks.tasks);
              setHandoffs(storedHandoffs.handoffs);
              setStage("world");
              return true;
            })
            .then((restored) => {
              if (restored) restoredNpcId.current = savedNpcId;
            })
            .catch(() => undefined)
            .finally(() => {
              restoreInFlight.current = false;
            });
        })
        .catch(() => {
          if (!controller.signal.aborted) setConnection("error");
        });
    void checkHealth();

    const stream = new EventSource(`${API_BASE_URL}/api/events/stream`);
    stream.onmessage = (event) => {
      setConnection("connected");
      const parsed = parseDomainEvent(event.data);
      if (parsed) setEvents((current) => [parsed, ...current].slice(0, 12));
    };
    stream.onerror = () =>
      setConnection((current) => (current === "connected" ? current : "error"));
    const poll = window.setInterval(() => {
      void checkHealth();
      void fetchRecentEvents(ownerIdRef.current || undefined, npcIdRef.current || undefined)
        .then((recent) => {
          setConnection("connected");
          setEvents(recent.slice(-12).reverse());
        })
        .catch(() => undefined);
    }, 1500);
    return () => {
      controller.abort();
      stream.close();
      window.clearInterval(poll);
    };
  }, []);

  const worldEvents = useMemo(() => {
    if (!npc) return events;
    return scopeEventsToWorld(events, {
      ownerId,
      npcId: npc.npc_id,
      sessionId: session?.session_id ?? null,
    });
  }, [events, npc, ownerId, session?.session_id]);
  const latestEvent = worldEvents[0]?.event_type ?? "waiting for runtime";
  const currentQuery = continuityQuery || message;
  const worldStatus =
    continuity?.status ?? (session?.status === "active" ? "brain ready" : "empty world");
  const specialists = agents.filter((agent) => agent.specialization !== "primary");
  function beginOnboarding() {
    setError(null);
    setStage("onboarding");
    window.requestAnimationFrame(() => document.getElementById("onboarding-title")?.focus());
  }
  async function enterWorld(event: FormEvent) {
    event.preventDefault();
    if (!memoryConsent) {
      setError("Choose whether this agent may keep useful context before entering the world.");
      return;
    }
    setError(null);
    setBusy(true);
    // A saved brain may still be reopening from the health poll. Invalidate that
    // asynchronous result before creating a new owner/NPC pair.
    restoreGeneration.current += 1;
    restoredNpcId.current = null;
    try {
      const nextOwnerId = ownerKey(ownerName);
      const created = await createNpc({
        owner_id: nextOwnerId,
        name: npcName.trim(),
        appearance: { palette, avatar_key: avatarKey, accessory_key: accessoryKey },
      });
      const started = await startSession(nextOwnerId, created.npc.npc_id);
      setEvents([]);
      setOwnerId(nextOwnerId);
      setNpc(created.npc);
      setAgents([created.npc]);
      setSession(started.session);
      setSessionLineage([started.session]);
      setSessionNotice(null);
      setTasks([]);
      setHandoffs([]);
      setWorkerName("");
      setSelectedWorkerId("");
      setSelectedHandoffMemoryIds([]);
      setTaskTitle("");
      setTaskObjective("");
      setStage("world");
      window.localStorage.setItem("abrain.owner_id", nextOwnerId);
      window.localStorage.setItem("abrain.npc_id", created.npc.npc_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not enter A-Brain World");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !message.trim()) return;
    setBusy(true);
    setError(null);
    setLastPromotedMemory(null);
    setComparison(null);
    try {
      const submittedMessage = message.trim();
      const response = await recordTurn(ownerId, session.session_id, submittedMessage);
      setTurns((current) => [
        ...current,
        { id: response.turn.turn_id, speaker: "owner", text: submittedMessage },
        {
          id: `${response.turn.turn_id}-agent`,
          speaker: "agent",
          text: response.agent_response,
        },
      ]);
      setMessage("");
      setLastTurnMemoryIds(response.recalled_memory_ids);
      setLastTurnRetrievals(response.retrievals);
      setLastAgentRun(response.agent_run);
      setExtractionNotice(
        response.memory_influenced
          ? `Fresh session used ${response.recalled_memory_ids.length} persistent memory record${response.recalled_memory_ids.length === 1 ? "" : "s"} · response provenance attached.`
          : response.extraction_status === "disabled"
            ? "This turn stayed in conversation. Nothing was saved."
            : response.extraction_status === "failed"
              ? "Extraction failed · no guessed memory was written."
              : response.candidates.length === 0
                ? "Turn stayed transient · no durable context was detected."
                : `${response.candidates.length} memory candidate${response.candidates.length === 1 ? "" : "s"} detected · reviewing promotion policy.`,
      );
      for (const candidate of response.candidates) {
        await reviewCandidate(candidate);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Conversation turn failed");
    } finally {
      setBusy(false);
    }
  }

  async function createAndRunTask(event: FormEvent) {
    event.preventDefault();
    if (!session || !npc || !ownerId || !taskObjective.trim()) return;
    setBusy(true);
    setError(null);
    setExtractionNotice(null);
    try {
      const created = await createTask({
        owner_id: ownerId,
        assigned_agent_id: npc.npc_id,
        objective: taskObjective.trim(),
        title: taskTitle.trim() || undefined,
      });
      setTasks((current) => [created.task, ...current]);
      const result = await runTask(created.task.task_id, ownerId, session.session_id);
      setTasks((current) => [
        result.task,
        ...current.filter((item) => item.task_id !== result.task.task_id),
      ]);
      setLastAgentRun(result.agent_run);
      setExtractionNotice(
        result.task.status === "completed"
          ? result.persisted_result_memory_id
            ? `Task completed · result saved as ${result.persisted_result_memory_id.slice(-12)}.`
            : "Task completed · no durable decision memory was needed."
          : `Task ${result.task.status} · ${result.task.current_step}.`,
      );
      setTaskTitle("");
      setTaskObjective("");
      if (result.persisted_result_memory_id) {
        const refreshed = await listMemories(ownerId, npc.npc_id);
        setMemories(refreshed.memories);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Task run failed");
    } finally {
      setBusy(false);
    }
  }

  async function addWorker(event: FormEvent) {
    event.preventDefault();
    if (!npc || !ownerId || !workerName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createWorker({
        owner_id: ownerId,
        primary_agent_id: npc.npc_id,
        name: workerName.trim(),
        specialization: workerSpecialization,
        appearance: {
          palette: workerSpecialization === "reviewer" ? "violet" : "amber",
          avatar_key: workerSpecialization === "reviewer" ? "orbiter" : "scout",
          accessory_key: workerSpecialization === "reviewer" ? "antenna" : "satchel",
        },
      });
      setAgents((current) => [...current, result.npc]);
      setSelectedWorkerId(result.npc.npc_id);
      setWorkerName("");
      setExtractionNotice(
        `${result.npc.name} joined as ${result.npc.specialization}. Delegation remains limited to two specialists.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add specialist");
    } finally {
      setBusy(false);
    }
  }

  function toggleHandoffMemory(memoryId: string) {
    setSelectedHandoffMemoryIds((current) =>
      current.includes(memoryId)
        ? current.filter((item) => item !== memoryId)
        : [...current, memoryId],
    );
  }

  async function delegateTask(task: AgentTask) {
    if (!npc || !ownerId || !selectedWorkerId || selectedHandoffMemoryIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createHandoff(task.task_id, {
        owner_id: ownerId,
        source_agent_id: task.assigned_agent_id,
        target_agent_id: selectedWorkerId,
        objective: task.objective,
        selected_memory_ids: selectedHandoffMemoryIds,
      });
      setTasks((current) => [created.task, ...current]);
      setHandoffs((current) => [created.handoff, ...current]);
      const result = await runTaskWithHandoff(created.task.task_id, ownerId, {
        handoff_id: created.handoff.handoff_id,
      });
      setTasks((current) => [
        result.task,
        ...current.filter((item) => item.task_id !== result.task.task_id),
      ]);
      if (result.handoff) {
        setHandoffs((current) => [
          result.handoff as ScopedHandoff,
          ...current.filter((item) => item.handoff_id !== result.handoff?.handoff_id),
        ]);
      }
      setLastAgentRun(result.agent_run);
      setExtractionNotice(
        result.task.status === "completed"
          ? `Scoped handoff completed · worker used ${result.agent_run.used_memory_ids.length} authorized memory record${result.agent_run.used_memory_ids.length === 1 ? "" : "s"}.`
          : `Scoped handoff ${result.task.status} · ${result.task.current_step}.`,
      );
      setSelectedHandoffMemoryIds([]);
      if (result.persisted_result_memory_id) {
        const refreshed = await listMemories(ownerId);
        setMemories(refreshed.memories);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scoped handoff failed");
    } finally {
      setBusy(false);
    }
  }

  async function resumeTask(task: AgentTask) {
    if (!session || !ownerId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await runTask(task.task_id, ownerId, session.session_id);
      setTasks((current) => [
        result.task,
        ...current.filter((item) => item.task_id !== result.task.task_id),
      ]);
      setLastAgentRun(result.agent_run);
      setExtractionNotice(
        result.task.status === "completed"
          ? "Task resumed and completed."
          : `Task ${result.task.status} · ${result.task.current_step}.`,
      );
      if (result.persisted_result_memory_id) {
        const refreshed = await listMemories(ownerId, task.assigned_agent_id);
        setMemories(refreshed.memories);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Task resume failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveMemory(event: FormEvent, confirm = false) {
    event.preventDefault();
    if (!session || !npc || !ownerId || !memoryKey.trim() || !memoryValue.trim()) return;
    setLastTurnMemoryIds([]);
    setLastTurnRetrievals([]);
    setLastAgentRun(null);
    setContinuity(null);
    setComparison(null);
    setReplay(null);
    const sourceTurn = [...turns].reverse().find((turn) => turn.speaker === "owner");
    const candidate: MemoryCandidate = {
      candidate_id: `memory-${crypto.randomUUID()}`,
      owner_id: ownerId,
      npc_id: npc.npc_id,
      source_session_id: session.session_id,
      source_turn_id: sourceTurn?.id ?? "manual-entry",
      concept,
      key: memoryKey.trim(),
      value: memoryValue.trim(),
      confidence: rememberExplicitly ? 0.98 : 0.72,
      explicit_remember: rememberExplicitly,
      sensitive: false,
      transient: false,
    };
    if (confirm) {
      await promoteMemory(candidate, true);
      return;
    }
    try {
      const result = await decideCandidate(candidate);
      if (result.decision.disposition === "confirm") {
        setPendingCandidates((current) => [...current, candidate]);
        setExtractionNotice("Review the inferred context before it lasts.");
        setMemoryKey("");
        setMemoryValue("");
        return;
      }
      if (result.decision.disposition === "reject") {
        setError(result.decision.reason);
        return;
      }
      await promoteMemory(candidate, false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Memory policy check failed");
    }
  }

  async function reviewCandidate(candidate: MemoryCandidate) {
    try {
      const result = await decideCandidate(candidate);
      if (result.decision.disposition === "promote") {
        const promoted = await promoteCandidate(candidate, false);
        setMemories((current) => [
          promoted.record,
          ...current.filter((item) => item.memory_id !== promoted.record.memory_id),
        ]);
        setLastPromotedMemory(promoted.record);
      } else if (result.decision.disposition === "confirm") {
        setPendingCandidates((current) => [
          ...current.filter((item) => item.candidate_id !== candidate.candidate_id),
          candidate,
        ]);
      } else {
        setExtractionNotice(`Candidate rejected · ${result.decision.reason}.`);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Candidate review failed");
    }
  }

  function dismissCandidate(candidateId: string) {
    setPendingCandidates((current) =>
      current.filter((candidate) => candidate.candidate_id !== candidateId),
    );
    setExtractionNotice("Candidate kept transient · nothing was written to the brain.");
  }

  async function promoteMemory(candidate: MemoryCandidate, confirm: boolean) {
    setBusy(true);
    setError(null);
    try {
      const result = await promoteCandidate(candidate, confirm);
      setMemories((current) => [
        result.record,
        ...current.filter((item) => item.memory_id !== result.record.memory_id),
      ]);
      setLastPromotedMemory(result.record);
      setPendingCandidates((current) =>
        current.filter((item) => item.candidate_id !== candidate.candidate_id),
      );
      setMemoryKey("");
      setMemoryValue("");
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : "Memory promotion failed";
      if (!confirm && text.includes("confirmation")) {
        setPendingCandidates((current) => [
          ...current.filter((item) => item.candidate_id !== candidate.candidate_id),
          candidate,
        ]);
      } else setError(text);
    } finally {
      setBusy(false);
    }
  }

  function clearTransientUi() {
    setTurns([]);
    setMessage("");
    setContinuityQuery("");
    setContinuity(null);
    setComparison(null);
    setReplay(null);
    setPendingCandidates([]);
    setExtractionNotice(null);
    setLastTurnMemoryIds([]);
    setLastTurnRetrievals([]);
    setLastAgentRun(null);
    setLastPromotedMemory(null);
    setEditingMemory(null);
    setForgettingMemory(null);
    setEditKey("");
    setEditValue("");
    setMemoryKey("");
    setMemoryValue("");
  }

  async function restart() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const result = await restartSession(session.session_id, ownerId);
      setSession(result.fresh);
      setSessionLineage((current) => [result.fresh, result.terminated, ...current]);
      clearTransientUi();
      setSessionNotice(
        `Session ${result.terminated.session_id.slice(-10)} terminated. Fresh session ${result.fresh.session_id.slice(-10)} started with zero transient turns.`,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Restart failed");
    } finally {
      setBusy(false);
    }
  }

  function startNewAgent() {
    restoreGeneration.current += 1;
    window.localStorage.removeItem("abrain.owner_id");
    window.localStorage.removeItem("abrain.npc_id");
    restoredNpcId.current = null;
    setOwnerId("");
    setNpc(null);
    setAgents([]);
    setSession(null);
    setSessionLineage([]);
    setSessionNotice(null);
    setEvents([]);
    setMemories([]);
    setTasks([]);
    setHandoffs([]);
    setWorkerName("");
    setSelectedWorkerId("");
    setSelectedHandoffMemoryIds([]);
    setTaskTitle("");
    setTaskObjective("");
    clearTransientUi();
    setOwnerName("");
    setNpcName("");
    setPalette("teal");
    setAvatarKey("node");
    setAccessoryKey("none");
    setMemoryConsent(false);
    setStage("onboarding");
  }

  async function recall() {
    if (!session || !npc || !ownerId || !currentQuery.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await restoreContinuity(session.session_id, {
        owner_id: ownerId,
        npc_id: npc.npc_id,
        query: currentQuery.trim(),
      });
      setContinuity(result);
      setReplay(null);
      setComparison(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Continuity recall failed");
    } finally {
      setBusy(false);
    }
  }

  async function explainMemory(memoryId: string) {
    if (!ownerId) return;
    setBusy(true);
    setError(null);
    try {
      setReplay(await fetchCausalReplay(ownerId, memoryId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Causal replay failed");
    } finally {
      setBusy(false);
    }
  }

  async function explainContinuity() {
    if (!continuity?.recalled_memory_ids[0]) return;
    await explainMemory(continuity.recalled_memory_ids[0]);
  }

  async function runComparison() {
    if (!session || !npc || !ownerId || !continuityQuery.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setComparison(
        await compareContinuity({
          owner_id: ownerId,
          npc_id: npc.npc_id,
          session_id: session.session_id,
          query: continuityQuery.trim(),
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Continuity comparison failed");
    } finally {
      setBusy(false);
    }
  }

  function beginEdit(memory: MemoryRecord) {
    setEditingMemory(memory.memory_id);
    setEditKey(memory.key);
    setEditValue(memory.value);
  }

  async function updateMemoryRecord(memory: MemoryRecord, key: string, value: string) {
    if (!ownerId || !key.trim() || !value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await updateMemory(memory.memory_id, ownerId, {
        key: key.trim(),
        value: value.trim(),
        confidence: memory.confidence,
      });
      setMemories((current) =>
        current.map((item) =>
          item.memory_id === memory.memory_id
            ? { ...item, key: key.trim(), value: value.trim() }
            : item,
        ),
      );
      setContinuity(null);
      setReplay(null);
      setComparison(null);
      setEditingMemory(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Memory update failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(memory: MemoryRecord) {
    if (!editKey.trim() || !editValue.trim()) return;
    await updateMemoryRecord(memory, editKey, editValue);
  }

  async function removeMemory(memory: MemoryRecord, operation: "archive" | "delete") {
    if (!ownerId) return;
    setBusy(true);
    setError(null);
    try {
      if (operation === "archive") await archiveMemory(memory.memory_id, ownerId);
      else await deleteMemory(memory.memory_id, ownerId);
      setMemories((current) => current.filter((item) => item.memory_id !== memory.memory_id));
      setContinuity(null);
      setComparison(null);
      if (lastPromotedMemory?.memory_id === memory.memory_id) {
        setLastPromotedMemory(null);
        setExtractionNotice("Memory removed from the persistent brain.");
      }
      setForgettingMemory(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Memory ${operation} failed`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="wordmark">A—BRAIN</span>
          <span className="eyebrow">
            {stage === "world"
              ? "persistent context / connected"
              : "agent continuity / starts empty"}
          </span>
        </div>
        <button
          className="theme-toggle"
          type="button"
          aria-pressed={theme === "dark"}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
        >
          <span aria-hidden="true">{theme === "light" ? "☾" : "☼"}</span>
          {theme === "light" ? "Dark mode" : "Light mode"}
        </button>
      </header>

      {stage === "landing" ? (
        <>
          <section className="landing-hero" aria-labelledby="landing-title">
            <div className="landing-copy">
              <span className="eyebrow">persistent agent continuity</span>
              <h1 id="landing-title">
                Agents forget when sessions end.
                <em>Their brain shouldn&apos;t.</em>
              </h1>
              <p className="landing-lede">
                A-Brain carries useful context into a fresh runtime through a persistent
                Sibyl-backed brain.
              </p>
              <div className="landing-actions">
                <button
                  className="primary-button landing-primary"
                  type="button"
                  onClick={beginOnboarding}
                >
                  Enter A-Brain World <span aria-hidden="true">↗</span>
                </button>
                <a className="text-link" href="#how-it-works">
                  See how continuity works <span aria-hidden="true">↓</span>
                </a>
              </div>
            </div>
            <LandingPreview onEnter={beginOnboarding} />
          </section>
          <section className="landing-narrative" id="how-it-works" aria-labelledby="how-title">
            <div className="narrative-intro">
              <span className="eyebrow">the continuity loop</span>
              <h2 id="how-title">One brain. Many sessions.</h2>
            </div>
            <ol className="narrative-steps">
              <li>
                <span>01</span>
                <strong>Sessions disappear</strong>
                <p>A runtime can end at any time.</p>
              </li>
              <li>
                <span>02</span>
                <strong>Context survives</strong>
                <p>Sibyl keeps durable facts, decisions, and goals.</p>
              </li>
              <li>
                <span>03</span>
                <strong>Behavior carries forward</strong>
                <p>The next body recalls only what the request needs.</p>
              </li>
              <li>
                <span>04</span>
                <strong>Step into the world</strong>
                <p>Meet your agent with an empty brain and make it yours.</p>
              </li>
            </ol>
          </section>
        </>
      ) : stage === "onboarding" ? (
        <section className="onboarding" aria-labelledby="onboarding-title">
          <div className="onboarding-copy">
            <span className="eyebrow">step 01 · make it yours</span>
            <h1 id="onboarding-title" tabIndex={-1}>
              Create your agent.
            </h1>
            <p className="lede">
              Choose a name and a simple body. You&apos;ll enter a small world with no seeded
              memories, ready to teach your agent what matters.
            </p>
            <ol className="continuity-steps" aria-label="How A-Brain works">
              <li>
                <span className="step-marker">01</span>
                <span>
                  <strong>Name yourself</strong>
                  <small>Your context belongs to you.</small>
                </span>
              </li>
              <li>
                <span className="step-marker">02</span>
                <span>
                  <strong>Choose a body</strong>
                  <small>Make the world feel like yours.</small>
                </span>
              </li>
              <li>
                <span className="step-marker">03</span>
                <span>
                  <strong>Start empty</strong>
                  <small>Teach it what should last.</small>
                </span>
              </li>
            </ol>
          </div>
          <form className="panel onboarding-card" onSubmit={enterWorld}>
            <span className="eyebrow">enter the world</span>
            <h2>Give your agent a body.</h2>
            <label>
              Your name
              <input
                value={ownerName}
                onChange={(event) => setOwnerName(event.target.value)}
                placeholder="Anand"
                required
              />
            </label>
            <label>
              Agent name
              <input
                value={npcName}
                onChange={(event) => setNpcName(event.target.value)}
                placeholder="Nova"
                required
              />
            </label>
            <label>
              Palette
              <select value={palette} onChange={(event) => setPalette(event.target.value)}>
                <option value="teal">Teal signal</option>
                <option value="amber">Amber signal</option>
                <option value="violet">Violet signal</option>
              </select>
            </label>
            <div className="onboarding-choice-grid">
              <label>
                Body
                <select
                  value={avatarKey}
                  onChange={(event) => setAvatarKey(event.target.value as NpcAvatarKey)}
                >
                  <option value="node">Node · grounded</option>
                  <option value="scout">Scout · mobile</option>
                  <option value="orbiter">Orbiter · hovering</option>
                </select>
              </label>
              <label>
                Accessory
                <select
                  value={accessoryKey}
                  onChange={(event) => setAccessoryKey(event.target.value as NpcAccessoryKey)}
                >
                  <option value="none">None</option>
                  <option value="antenna">Signal antenna</option>
                  <option value="satchel">Memory satchel</option>
                </select>
              </label>
            </div>
            <label className="consent-row">
              <input
                type="checkbox"
                checked={memoryConsent}
                onChange={(event) => setMemoryConsent(event.target.checked)}
                required
              />
              <span>
                <strong>Let this agent remember useful context</strong>
                <small>
                  Explicit memories can be edited or forgotten. Uncertain or sensitive context waits
                  for your confirmation.
                </small>
              </span>
            </label>
            <button className="primary-button" disabled={busy || !memoryConsent} type="submit">
              {busy ? "Entering…" : "Spawn into the world"}
            </button>
            {error ? (
              <p className="error-copy" role="alert">
                {error}
              </p>
            ) : null}
          </form>
        </section>
      ) : (
        <section className="world-stage" aria-labelledby="world-stage-title">
          <div className="world-stage-heading">
            <div>
              <span className="eyebrow">continuity lab / {npc?.name}</span>
              <h1 id="world-stage-title">One brain. Many sessions.</h1>
              <p className="lede">
                Every memory below came from a confirmed Sibyl write. The current body can
                disappear; the brain stays inspectable.
              </p>
            </div>
            <div className="status-row stage-actions">
              <span className="live-state" role="status">
                <span className="live-dot" aria-hidden="true" />
                {latestEvent.replaceAll(".", " ")}
              </span>
              <button className="secondary-button" disabled={busy} onClick={restart}>
                Restart agent
              </button>
              <button className="secondary-button" onClick={startNewAgent}>
                New empty agent
              </button>
            </div>
          </div>
          {sessionNotice ? (
            <div className="session-receipt" role="status" aria-live="polite">
              <span className="session-receipt-mark" aria-hidden="true">
                ↻
              </span>
              <span>{sessionNotice}</span>
            </div>
          ) : null}
          <WorldShell
            events={worldEvents}
            ownerId={ownerId}
            npc={npc}
            session={session}
            sessionLineage={sessionLineage}
            memories={memories}
            status={worldStatus}
            turns={turns}
            message={message}
            busy={busy}
            extractionNotice={extractionNotice}
            lastTurnMemoryIds={lastTurnMemoryIds}
            lastTurnRetrievals={lastTurnRetrievals}
            lastAgentRun={lastAgentRun}
            lastPromotedMemory={lastPromotedMemory}
            pendingCandidates={pendingCandidates}
            onMessageChange={setMessage}
            onSubmit={sendMessage}
            onConfirmCandidate={(candidate) => void promoteMemory(candidate, true)}
            onDismissCandidate={dismissCandidate}
            onUndoLastSave={() => {
              if (lastPromotedMemory) void removeMemory(lastPromotedMemory, "delete");
            }}
            replay={replay}
            onExplainMemory={(memoryId) => void explainMemory(memoryId)}
            onCloseReplay={() => setReplay(null)}
            onUpdateMemory={updateMemoryRecord}
            onArchiveMemory={(memory) => void removeMemory(memory, "archive")}
            onDeleteMemory={(memory) => void removeMemory(memory, "delete")}
          />
          <div className="interaction-grid">
            <section className="panel card task-card" aria-labelledby="task-title">
              <span className="eyebrow">activity zone / tasks</span>
              <h2 id="task-title">Give {npc?.name} a real mission.</h2>
              <p className="card-note">
                Research, plan, review, recommend, organize, or continue unfinished work. The
                objective becomes a task; relevant brain context is attached only after Sibyl
                returns it.
              </p>
              <form className="memory-form" onSubmit={createAndRunTask}>
                <input
                  value={taskTitle}
                  onChange={(event) => setTaskTitle(event.target.value)}
                  placeholder="Optional task title"
                  aria-label="Task title"
                />
                <textarea
                  value={taskObjective}
                  onChange={(event) => setTaskObjective(event.target.value)}
                  placeholder="Tell your agent what to accomplish…"
                  aria-label="Task objective"
                  rows={3}
                />
                <button
                  className="primary-button"
                  disabled={busy || !taskObjective.trim()}
                  type="submit"
                >
                  {busy ? "Agent working…" : "Create and run task"}
                </button>
              </form>
              <details className="optional-capability">
                <summary>Optional: scoped specialist handoff</summary>
                <div className="delegation-panel" aria-label="Agent delegation">
                  <div className="delegation-heading">
                    <div>
                      <span className="memory-kind">
                        optional specialists · {agents.length}/3 active
                      </span>
                      <strong>Let the primary agent delegate narrowly.</strong>
                    </div>
                    <span className="mono">A → B → optional C</span>
                  </div>
                  <form className="inline-form" onSubmit={addWorker}>
                    <input
                      value={workerName}
                      onChange={(event) => setWorkerName(event.target.value)}
                      placeholder="Specialist name"
                      aria-label="Specialist name"
                    />
                    <select
                      value={workerSpecialization}
                      onChange={(event) =>
                        setWorkerSpecialization(
                          event.target.value as "planner" | "worker" | "reviewer",
                        )
                      }
                      aria-label="Specialist role"
                    >
                      <option value="planner">Planner</option>
                      <option value="worker">Worker</option>
                      <option value="reviewer">Reviewer</option>
                    </select>
                    <button
                      className="secondary-button"
                      disabled={busy || !workerName.trim() || agents.length >= 3}
                      type="submit"
                    >
                      Add specialist
                    </button>
                  </form>
                  {specialists.length ? (
                    <>
                      <label className="handoff-select-label">
                        Delegate to
                        <select
                          value={selectedWorkerId}
                          onChange={(event) => setSelectedWorkerId(event.target.value)}
                          aria-label="Delegation target"
                        >
                          <option value="">Choose a specialist</option>
                          {specialists.map((agent) => (
                            <option key={agent.npc_id} value={agent.npc_id}>
                              {agent.name} · {agent.specialization}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="handoff-picker">
                        <span className="memory-kind">Select the exact brain shards to share</span>
                        {memories.length ? (
                          memories.slice(0, 8).map((memory) => (
                            <label className="handoff-memory" key={memory.memory_id}>
                              <input
                                type="checkbox"
                                checked={selectedHandoffMemoryIds.includes(memory.memory_id)}
                                onChange={() => toggleHandoffMemory(memory.memory_id)}
                              />
                              <span>
                                <strong>{memory.key}</strong>
                                <small>{memory.value}</small>
                              </span>
                            </label>
                          ))
                        ) : (
                          <span className="muted-row">
                            Write a confirmed memory before delegating.
                          </span>
                        )}
                      </div>
                    </>
                  ) : (
                    <p className="muted-row">
                      Add one specialist to make scoped memory handoff available. A-Brain keeps the
                      active roster intentionally small.
                    </p>
                  )}
                </div>
              </details>
              <div className="task-list" aria-live="polite">
                {tasks.length === 0 ? (
                  <p className="muted-row">
                    No tasks yet. Your first mission will create the activity.
                  </p>
                ) : (
                  tasks.slice(0, 4).map((task) => (
                    <article className={`task-item task-${task.status}`} key={task.task_id}>
                      <div className="task-heading">
                        <span className="memory-kind">{task.status}</span>
                        <strong>{task.title}</strong>
                      </div>
                      <p>{task.current_step}</p>
                      {task.result ? <div className="task-result">{task.result}</div> : null}
                      {task.relevant_memory_ids.length ? (
                        <small className="mono">
                          context ·{" "}
                          {task.relevant_memory_ids.map((id) => id.slice(-10)).join(" · ")}
                        </small>
                      ) : (
                        <small className="mono">context · none required</small>
                      )}
                      {task.status === "blocked" || task.status === "review" ? (
                        <button
                          className="secondary-button task-resume"
                          disabled={busy}
                          onClick={() => void resumeTask(task)}
                          type="button"
                        >
                          Resume task
                        </button>
                      ) : null}
                      {agents.some((agent) => agent.npc_id === task.assigned_agent_id) &&
                      specialists.length > 0 ? (
                        <button
                          className="secondary-button task-delegate"
                          disabled={
                            busy ||
                            !selectedWorkerId ||
                            selectedWorkerId === task.assigned_agent_id ||
                            selectedHandoffMemoryIds.length === 0 ||
                            task.status === "queued" ||
                            task.status === "thinking" ||
                            task.status === "working"
                          }
                          onClick={() => void delegateTask(task)}
                          type="button"
                        >
                          Delegate selected context
                        </button>
                      ) : null}
                    </article>
                  ))
                )}
              </div>
              {handoffs.length ? (
                <div className="handoff-list" aria-live="polite">
                  <span className="memory-kind">handoff receipts</span>
                  {handoffs.slice(0, 3).map((handoff) => (
                    <article
                      className={`handoff-item handoff-${handoff.status}`}
                      key={handoff.handoff_id}
                    >
                      <div className="task-heading">
                        <span className="memory-kind">{handoff.status}</span>
                        <strong>
                          {agents.find((agent) => agent.npc_id === handoff.source_agent_id)?.name ??
                            "Agent"}
                          <span aria-hidden="true"> → </span>
                          {agents.find((agent) => agent.npc_id === handoff.target_agent_id)?.name ??
                            "Worker"}
                        </strong>
                      </div>
                      <small className="mono">
                        authorized ·{" "}
                        {handoff.selected_memory_ids.map((id) => id.slice(-10)).join(" · ")}
                      </small>
                      <p>
                        {handoff.result ??
                          "Only the selected memory records are available to the target."}
                      </p>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
            <section className="panel card" aria-labelledby="memory-title">
              <span className="eyebrow">brain vault / Sibyl</span>
              <h2 id="memory-title">Choose what should last.</h2>
              <form className="memory-form" onSubmit={saveMemory}>
                <div className="form-row">
                  <select
                    value={concept}
                    onChange={(event) => setConcept(event.target.value)}
                    aria-label="Memory concept"
                  >
                    {[
                      "preference",
                      "person",
                      "relationship",
                      "habit",
                      "decision",
                      "constraint",
                      "value",
                      "goal",
                      "project",
                      "event",
                    ].map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                  <input
                    value={memoryKey}
                    onChange={(event) => setMemoryKey(event.target.value)}
                    placeholder="key"
                    aria-label="Memory key"
                  />
                </div>
                <input
                  value={memoryValue}
                  onChange={(event) => setMemoryValue(event.target.value)}
                  placeholder="value worth carrying forward"
                  aria-label="Memory value"
                />
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={rememberExplicitly}
                    onChange={(event) => setRememberExplicitly(event.target.checked)}
                  />{" "}
                  I explicitly want {npc?.name} to remember this
                </label>
                <button
                  className="secondary-button"
                  disabled={busy || !memoryKey.trim() || !memoryValue.trim()}
                  type="submit"
                >
                  Write to brain
                </button>
              </form>
              <div className="memory-list">
                {memories.length === 0 ? (
                  <p className="muted-row">The vault is empty. Start with one useful fact.</p>
                ) : (
                  memories.map((memory) => (
                    <article className="memory-card" key={memory.memory_id}>
                      <span className="memory-kind">{memory.concept}</span>
                      {editingMemory === memory.memory_id ? (
                        <>
                          <input
                            value={editKey}
                            onChange={(event) => setEditKey(event.target.value)}
                            aria-label="Edit memory key"
                          />
                          <input
                            value={editValue}
                            onChange={(event) => setEditValue(event.target.value)}
                            aria-label="Edit memory value"
                          />
                          <div className="memory-actions">
                            <button
                              className="primary-button"
                              disabled={busy}
                              onClick={() => void saveEdit(memory)}
                            >
                              Save edit
                            </button>
                            <button
                              className="secondary-button"
                              onClick={() => setEditingMemory(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <strong>{memory.key}</strong>
                          <p>{memory.value}</p>
                          <small>
                            source {memory.source_session_id} · evidence{" "}
                            {memory.evidence_ref ?? "none"}
                          </small>
                          <div className="memory-actions">
                            <button
                              className="secondary-button"
                              disabled={busy}
                              onClick={() => beginEdit(memory)}
                            >
                              Edit
                            </button>
                            <button
                              className="secondary-button"
                              disabled={busy}
                              onClick={() => void removeMemory(memory, "archive")}
                            >
                              Archive
                            </button>
                            {forgettingMemory === memory.memory_id ? (
                              <>
                                <button
                                  className="danger-button"
                                  disabled={busy}
                                  onClick={() => void removeMemory(memory, "delete")}
                                >
                                  Confirm forget
                                </button>
                                <button
                                  className="secondary-button"
                                  disabled={busy}
                                  onClick={() => setForgettingMemory(null)}
                                >
                                  Keep
                                </button>
                              </>
                            ) : (
                              <button
                                className="danger-button"
                                disabled={busy}
                                onClick={() => setForgettingMemory(memory.memory_id)}
                              >
                                Forget
                              </button>
                            )}
                          </div>
                        </>
                      )}
                    </article>
                  ))
                )}
              </div>
            </section>
            <section className="panel card continuity-card" aria-labelledby="continuity-title">
              <span className="eyebrow">session portal / fresh runtime</span>
              <h2 id="continuity-title">Ask the new body what it remembers.</h2>
              <p className="card-note">
                Restart first, then ask without repeating the old context. Recall is scoped to the
                owner, NPC, and current query.
              </p>
              <form
                className="inline-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void recall();
                }}
              >
                <input
                  value={continuityQuery}
                  onChange={(event) => setContinuityQuery(event.target.value)}
                  placeholder="What should it use from before?"
                  aria-label="Continuity query"
                />
                <button
                  className="primary-button"
                  disabled={busy || !continuityQuery.trim()}
                  type="submit"
                >
                  Recall
                </button>
              </form>
              <button
                className="comparison-button"
                type="button"
                disabled={busy || !continuityQuery.trim()}
                onClick={() => void runComparison()}
              >
                {busy ? "Running continuity arena…" : "Compare continuity"}
              </button>
              <small className="comparison-note">
                Runs the same clean request through two real backend lanes. Restart first; the
                disabled lane must ask for context instead of guessing.
              </small>
              {continuity ? (
                <div
                  className={`continuity-result ${continuity.influenced_by_memory ? "is-restored" : "is-blocked"}`}
                >
                  <strong>{continuity.status.replaceAll("_", " ")}</strong>
                  <p className="agent-response">{continuity.agent_response}</p>
                  <span>{continuity.explanation}</span>
                  <small>
                    {continuity.recalled_memory_ids.length
                      ? `influenced by ${continuity.recalled_memory_ids.join(", ")}`
                      : "no memory IDs returned"}
                  </small>
                  {continuity.retrievals.length ? (
                    <ul className="retrieval-list" aria-label="Memory retrieval details">
                      {continuity.retrievals.map((retrieval) => (
                        <li key={retrieval.record.memory_id}>
                          <span className="memory-kind">{retrieval.tier}</span>
                          <span>{retrieval.relevance_reason}</span>
                          {retrieval.provider_snippet ? (
                            <small>{retrieval.provider_snippet}</small>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <div className="agent-run-summary" aria-label="Structured agent run">
                    <span className="memory-kind">{continuity.agent_run.memory_effect}</span>
                    <strong>{continuity.agent_run.proposed_action}</strong>
                    {continuity.agent_run.plan.length ? (
                      <ol>
                        {continuity.agent_run.plan.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                    ) : null}
                  </div>
                  {continuity.influenced_by_memory ? (
                    <button
                      className="secondary-button"
                      disabled={busy}
                      onClick={() => void explainContinuity()}
                    >
                      Why did this change?
                    </button>
                  ) : null}
                  {replay ? (
                    <ol className="causal-steps">
                      {replay.steps.map((step) => (
                        <li key={`${step.step}-${step.event_id ?? "source"}`}>
                          <span className="memory-kind">{step.step}</span>
                          <strong>{step.detail}</strong>
                          <small>{step.event_type}</small>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>
              ) : null}
              {comparison ? (
                <div className="comparison-result continuity-arena" aria-live="polite">
                  <div className="arena-heading">
                    <div>
                      <span className="memory-kind">continuity arena / live experiment</span>
                      <strong>
                        {comparison.diverged ? "the worlds diverged" : "the worlds matched"}
                      </strong>
                    </div>
                    <span className="arena-query mono">{comparison.request.query}</span>
                  </div>
                  <div className="arena-lanes">
                    <article className="arena-lane is-restored">
                      <header>
                        <span className="arena-lane-mark" aria-hidden="true">
                          ✦
                        </span>
                        <div>
                          <strong>SIBYL ON</strong>
                          <span>brain reconnects</span>
                        </div>
                        <span className="arena-status">continues</span>
                      </header>
                      <div className="arena-track" aria-label="Sibyl on path">
                        <span className="is-done">brain reconnects</span>
                        <span className="is-done">
                          {comparison.memory_lane.decision.recalled_memory_ids.length} shards arrive
                        </span>
                        <span className="is-done">useful action</span>
                      </div>
                      <p>{comparison.memory_lane.decision.agent_response}</p>
                      <div className="arena-proof">
                        <span className="mono">
                          lane session · {comparison.memory_lane.session_id.slice(-10)}
                        </span>
                        <span className="mono">
                          recalled · {comparison.memory_lane.decision.recalled_memory_ids.length}
                        </span>
                      </div>
                      {comparison.memory_lane.decision.recalled_memory_ids.length ? (
                        <div className="arena-memory-ids" aria-label="Sibyl memory IDs">
                          {comparison.memory_lane.decision.recalled_memory_ids.map((memoryId) => (
                            <code key={memoryId} title={memoryId}>
                              {memoryId.slice(-10)}
                            </code>
                          ))}
                        </div>
                      ) : null}
                      <span className="arena-action">
                        action · {comparison.memory_lane.decision.action}
                      </span>
                    </article>
                    <article className="arena-lane is-blocked">
                      <header>
                        <span className="arena-lane-mark" aria-hidden="true">
                          ×
                        </span>
                        <div>
                          <strong>MEMORY OFF</strong>
                          <span>brain unavailable</span>
                        </div>
                        <span className="arena-status">safe stop</span>
                      </header>
                      <div className="arena-track" aria-label="Memory off path">
                        <span className="is-done">fresh body wakes</span>
                        <span className="is-blocked-step">no shards</span>
                        <span className="is-blocked-step">asks / blocks</span>
                      </div>
                      <p>{comparison.memory_disabled_lane.decision.agent_response}</p>
                      <div className="arena-proof">
                        <span className="mono">
                          lane session · {comparison.memory_disabled_lane.session_id.slice(-10)}
                        </span>
                        <span className="mono">recalled · 0</span>
                      </div>
                      <span className="arena-action">
                        action · {comparison.memory_disabled_lane.decision.action}
                      </span>
                    </article>
                  </div>
                  <div className={`arena-verdict ${comparison.diverged ? "is-diverged" : ""}`}>
                    <span aria-hidden="true">{comparison.diverged ? "↯" : "="}</span>
                    <strong>SAME AGENT · SAME REQUEST · ONE DIFFERENCE: MEMORY</strong>
                    <small>
                      {comparison.diverged
                        ? "The returned actions diverged because the memory lane had real recalled context."
                        : "The returned actions did not diverge; inspect the memory query and stored context."}
                    </small>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
          {error ? (
            <p className="error-copy page-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
      )}
      <footer className="footer-row">
        <span>
          {connection === "checking"
            ? "Connecting…"
            : connection === "error"
              ? "Connection unavailable"
              : "A-Brain connected"}
        </span>
        <span className="mono">{latestEvent}</span>
        <span>
          {stage === "world" ? "Persistent brain · ready" : "Empty brain · waiting for you"}
        </span>
      </footer>
    </main>
  );
}
