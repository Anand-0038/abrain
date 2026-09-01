import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { DomainEvent } from "@/src/contracts/events";
import type {
  AgentRunResult,
  MemoryCandidate,
  MemoryRecord,
  MemoryRetrieval,
  Npc,
  Session,
} from "@/src/lib/api";
import { PixiWorld } from "@/src/components/pixi-world";
import { WorldDialogue } from "@/src/components/world-dialogue";

type DialogueTurn = {
  id: string;
  speaker: "owner" | "agent";
  text: string;
};

type WorldShellProps = {
  events: DomainEvent[];
  ownerId: string;
  npc: Npc | null;
  session: Session | null;
  sessionLineage: Session[];
  memories: MemoryRecord[];
  status: string;
  turns: DialogueTurn[];
  message: string;
  busy: boolean;
  extractionNotice: string | null;
  lastTurnMemoryIds: string[];
  lastTurnRetrievals: MemoryRetrieval[];
  lastAgentRun: AgentRunResult | null;
  lastPromotedMemory: MemoryRecord | null;
  pendingCandidates: MemoryCandidate[];
  onMessageChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onConfirmCandidate: (candidate: MemoryCandidate) => void;
  onDismissCandidate: (candidateId: string) => void;
  onUndoLastSave: () => void;
  replay: {
    memory: MemoryRecord;
    steps: { step: string; event_id: string | null; event_type: string; detail: string }[];
  } | null;
  onExplainMemory: (memoryId: string) => void;
  onCloseReplay: () => void;
  onUpdateMemory: (memory: MemoryRecord, key: string, value: string) => Promise<void>;
  onArchiveMemory: (memory: MemoryRecord) => void;
  onDeleteMemory: (memory: MemoryRecord) => void;
};

export function WorldShell({
  events,
  ownerId,
  npc,
  session,
  sessionLineage,
  memories,
  status,
  turns,
  message,
  busy,
  extractionNotice,
  lastTurnMemoryIds,
  lastTurnRetrievals,
  lastAgentRun,
  lastPromotedMemory,
  pendingCandidates,
  onMessageChange,
  onSubmit,
  onConfirmCandidate,
  onDismissCandidate,
  onUndoLastSave,
  replay,
  onExplainMemory,
  onCloseReplay,
  onUpdateMemory,
  onArchiveMemory,
  onDeleteMemory,
}: WorldShellProps) {
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const [agentSelected, setAgentSelected] = useState(false);
  const [activitySelected, setActivitySelected] = useState(false);
  const [editingMemory, setEditingMemory] = useState(false);
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");
  const [forgetArmed, setForgetArmed] = useState(false);
  const selectedMemory = memories.find((memory) => memory.memory_id === selectedMemoryId) ?? null;
  const lastTerminated = [...events]
    .reverse()
    .find((event) => event.event_type === "npc.session_terminated");
  const lastRestarted = [...events]
    .reverse()
    .find((event) => event.event_type === "npc.session_restarted");
  const lastRecall = [...events]
    .reverse()
    .find(
      (event) =>
        event.event_type === "memory.recall_succeeded" &&
        (event.session_id === session?.session_id ||
          event.payload.session_id === session?.session_id),
    );
  const oldSessionId =
    (lastRestarted?.payload.terminated_session_id as string | undefined) ??
    (lastTerminated?.payload.session_id as string | undefined) ??
    null;
  const newSessionId =
    (lastRestarted?.payload.fresh_session_id as string | undefined) ??
    (lastRestarted?.session_id as string | undefined) ??
    null;
  const recalledMemoryCount = Array.isArray(lastRecall?.payload.memory_ids)
    ? lastRecall.payload.memory_ids.filter((value) => typeof value === "string").length
    : 0;

  function selectAgent() {
    setAgentSelected(true);
    setSelectedMemoryId(null);
    setActivitySelected(false);
  }

  function selectMemory(memoryId: string) {
    setSelectedMemoryId(memoryId);
    setAgentSelected(false);
    setActivitySelected(false);
    setEditingMemory(false);
    setForgetArmed(false);
  }

  useEffect(() => {
    if (selectedMemoryId && !selectedMemory) setSelectedMemoryId(null);
  }, [selectedMemory, selectedMemoryId]);

  function beginEdit() {
    if (!selectedMemory) return;
    setEditKey(selectedMemory.key);
    setEditValue(selectedMemory.value);
    setEditingMemory(true);
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMemory || !editKey.trim() || !editValue.trim()) return;
    await onUpdateMemory(selectedMemory, editKey.trim(), editValue.trim());
    setEditingMemory(false);
  }

  return (
    <section className="panel world-panel" aria-labelledby="world-title">
      <div className="world-header">
        <div>
          <h2 className="world-title" id="world-title">
            A-Brain World
          </h2>
          <span className="world-label">the world responds to you</span>
        </div>
        <span className={`world-state ${status.includes("restored") ? "is-restored" : ""}`}>
          {status.replaceAll("_", " ")}
        </span>
      </div>
      {lastRestarted ? (
        <div className="continuity-proof-strip" aria-label="Session continuity proof">
          <span className="continuity-proof-step is-complete">
            OLD SESSION <code>{oldSessionId?.slice(-8) ?? "—"}</code>
          </span>
          <span className="continuity-proof-arrow" aria-hidden="true">
            →
          </span>
          <span className="continuity-proof-step is-complete">TERMINATED</span>
          <span className="continuity-proof-divider" aria-hidden="true">
            |
          </span>
          <span className="continuity-proof-step is-complete">
            NEW SESSION{" "}
            <code>{newSessionId?.slice(-8) ?? session?.session_id.slice(-8) ?? "—"}</code>
          </span>
          <span className="continuity-proof-arrow" aria-hidden="true">
            →
          </span>
          <span className="continuity-proof-step is-complete">FRESH</span>
          <span className="continuity-proof-divider" aria-hidden="true">
            |
          </span>
          <span className={`continuity-proof-step ${lastRecall ? "is-complete" : "is-pending"}`}>
            SIBYL → {recalledMemoryCount} RECALLED
          </span>
        </div>
      ) : null}
      <div className="world-viewport">
        <PixiWorld
          events={events}
          memories={memories}
          ownerId={ownerId}
          npcId={npc?.npc_id ?? ""}
          sessionId={session?.session_id ?? null}
          palette={npc?.appearance.palette ?? "teal"}
          avatarKey={npc?.appearance.avatar_key ?? "node"}
          accessoryKey={npc?.appearance.accessory_key ?? "none"}
          npcName={npc?.name ?? "Agent"}
          specialization={npc?.specialization ?? "primary"}
          status={status}
          onAgentSelect={selectAgent}
          onMemorySelect={selectMemory}
          onActivitySelect={() => {
            setActivitySelected(true);
            setSelectedMemoryId(null);
            setAgentSelected(false);
          }}
        />
        {replay ? (
          <div
            className="causal-replay-overlay"
            role="dialog"
            aria-labelledby="causal-replay-title"
          >
            <div className="causal-replay-heading">
              <div>
                <span className="world-label">causal replay · real event chain</span>
                <h3 id="causal-replay-title">Why did the agent do that?</h3>
                <p>
                  {replay.memory.concept} · {replay.memory.key} → {replay.memory.value}
                </p>
              </div>
              <button className="text-button" type="button" onClick={onCloseReplay}>
                Return to city
              </button>
            </div>
            <ol className="causal-replay-chain">
              {replay.steps.map((step, index) => {
                const labels: Record<string, string> = {
                  source: "OWNER SAID / EVENT",
                  persist: "SIBYL MEMORY WRITE",
                  recall: "FRESH SESSION RECALLS",
                  decision: "AGENT DECISION",
                  handoff: "SCOPED HANDOFF",
                  worker: "WORKER ACTION",
                  review: "REVIEWER",
                  result: "TASK RESULT",
                };
                return (
                  <li key={`${step.event_id ?? step.step}-${index}`}>
                    <span className="causal-node-index">{String(index + 1).padStart(2, "0")}</span>
                    <div className="causal-node-copy">
                      <strong>{labels[step.step] ?? step.step.replaceAll("_", " ")}</strong>
                      <span>{step.detail}</span>
                      <small className="mono">
                        event {step.event_id?.slice(-10) ?? "not recorded"} · memory{" "}
                        {replay.memory.memory_id.slice(-10)}
                      </small>
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="causal-replay-proof">
              <span className="memory-kind">source session</span>
              <code>{replay.memory.source_session_id.slice(-12)}</code>
              <span className="memory-kind">persisted</span>
              <span>Sibyl / entity</span>
            </div>
          </div>
        ) : null}
        <WorldDialogue
          npcName={npc?.name ?? "Agent"}
          sessionId={session?.session_id ?? null}
          turns={turns}
          message={message}
          busy={busy}
          extractionNotice={extractionNotice}
          lastTurnMemoryIds={lastTurnMemoryIds}
          lastTurnRetrievals={lastTurnRetrievals}
          lastAgentRun={lastAgentRun}
          lastPromotedMemory={lastPromotedMemory}
          pendingCandidates={pendingCandidates}
          onMessageChange={onMessageChange}
          onSubmit={onSubmit}
          onConfirmCandidate={onConfirmCandidate}
          onDismissCandidate={onDismissCandidate}
          onUndoLastSave={onUndoLastSave}
        />
      </div>
      <div className="world-object-rail" aria-label="Inspectable world objects">
        <span className="world-label">inspect</span>
        <button
          className="object-chip"
          type="button"
          aria-pressed={agentSelected}
          onClick={selectAgent}
        >
          body · {npc?.name ?? "agent"}
        </button>
        {memories.length ? (
          memories.map((memory) => (
            <button
              className="object-chip"
              type="button"
              aria-pressed={selectedMemoryId === memory.memory_id}
              key={memory.memory_id}
              onClick={() => selectMemory(memory.memory_id)}
            >
              memory · {memory.key}
            </button>
          ))
        ) : (
          <span className="world-label">no confirmed memories yet</span>
        )}
      </div>
      {selectedMemory ? (
        <div className="world-inspector memory-inspector" role="status">
          {editingMemory ? (
            <form className="memory-inspector-edit" onSubmit={saveEdit}>
              <span className="world-label">edit persistent memory</span>
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
                <button className="primary-button" type="submit" disabled={busy}>
                  Save edit
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setEditingMemory(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <>
              <div className="memory-inspector-title">
                <span className="world-label">memory</span>
                <strong>{selectedMemory.concept}</strong>
                <span className="memory-inspector-arrow">
                  {selectedMemory.key} → {selectedMemory.value}
                </span>
              </div>
              <div className="memory-inspector-meta">
                <span>
                  source session: <code>{selectedMemory.source_session_id.slice(-10)}</code>
                </span>
                <span>
                  confidence:{" "}
                  {selectedMemory.confidence === null ? "—" : selectedMemory.confidence.toFixed(2)}
                </span>
                <span>persisted: Sibyl / WARM</span>
                <span>evidence: {selectedMemory.evidence_ref ?? "manual entry"}</span>
              </div>
              <div className="memory-inspector-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => onExplainMemory(selectedMemory.memory_id)}
                  disabled={busy}
                >
                  Why?
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={beginEdit}
                  disabled={busy}
                >
                  Edit
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => onArchiveMemory(selectedMemory)}
                  disabled={busy}
                >
                  Archive
                </button>
                <button
                  className="danger-button"
                  type="button"
                  onClick={() => {
                    if (forgetArmed) onDeleteMemory(selectedMemory);
                    else setForgetArmed(true);
                  }}
                  disabled={busy}
                >
                  {forgetArmed ? "Confirm forget" : "Forget"}
                </button>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => setSelectedMemoryId(null)}
                >
                  Close
                </button>
              </div>
              {replay?.memory.memory_id === selectedMemory.memory_id ? (
                <ol className="world-causal-replay" aria-label="Memory causal replay">
                  {replay.steps.map((step) => (
                    <li key={`${step.step}-${step.event_id ?? "source"}`}>
                      <span className="memory-kind">{step.step}</span>
                      <strong>{step.detail}</strong>
                    </li>
                  ))}
                </ol>
              ) : null}
            </>
          )}
        </div>
      ) : agentSelected ? (
        <div className="world-inspector" role="status">
          <div>
            <span className="world-label">selected body</span>
            <strong>{npc?.name ?? "Agent body"}</strong>
          </div>
          <p>The body is ephemeral; this brain survives its session.</p>
          <small>session {session?.session_id.slice(-10) ?? "not started"}</small>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setAgentSelected(false)}
          >
            Close
          </button>
        </div>
      ) : activitySelected ? (
        <div className="world-inspector" role="status">
          <div>
            <span className="world-label">selected activity</span>
            <strong>Memory changes action</strong>
          </div>
          <p>This is where the fresh agent turns recalled context into a useful next step.</p>
          <small>click Why? below a memory-influenced response to inspect the causal chain</small>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setActivitySelected(false)}
          >
            Close
          </button>
        </div>
      ) : null}
      <div className="world-metrics" aria-label="World state">
        <div>
          <span className="world-label">agent</span>
          <strong>{npc?.name ?? "—"}</strong>
        </div>
        <div>
          <span className="world-label">session</span>
          <strong className="mono">{session?.session_id.slice(-10) ?? "—"}</strong>
        </div>
        <div>
          <span className="world-label">brain shards</span>
          <strong>{memories.length.toString().padStart(2, "0")}</strong>
        </div>
        <div>
          <span className="world-label">events</span>
          <strong>{events.length.toString().padStart(2, "0")}</strong>
        </div>
      </div>
      <details className="session-lineage">
        <summary>
          Session lineage <span>{sessionLineage.length.toString().padStart(2, "0")}</span>
        </summary>
        <ol>
          {sessionLineage.map((item) => (
            <li key={item.session_id} data-state={item.status}>
              <span className="mono">{item.session_id.slice(-10)}</span>
              <strong>{item.status}</strong>
            </li>
          ))}
        </ol>
      </details>
      <div className="world-header world-footer">
        <span className="world-label">spaces</span>
        <span className="mono world-label">HOME · VAULT · PLAZA · WORKSHOP · TOWER · GATE</span>
        <span className="mono world-proof">BRAIN · EVENT STREAM ACTIVE</span>
      </div>
    </section>
  );
}
