import type { FormEvent } from "react";
import type { AgentRunResult, MemoryCandidate, MemoryRecord, MemoryRetrieval } from "@/src/lib/api";

type DialogueTurn = {
  id: string;
  speaker: "owner" | "agent";
  text: string;
};

type WorldDialogueProps = {
  npcName: string;
  sessionId: string | null;
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
};

export function WorldDialogue({
  npcName,
  sessionId,
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
}: WorldDialogueProps) {
  const recentTurns = turns.slice(-4);

  return (
    <section className="world-dialogue" aria-labelledby="world-dialogue-title">
      <header className="dialogue-header">
        <div className="dialogue-agent-mark" aria-hidden="true">
          {npcName.slice(0, 1).toUpperCase()}
        </div>
        <div className="dialogue-agent-copy">
          <span className="world-label">home / live dialogue</span>
          <h3 id="world-dialogue-title">{npcName}</h3>
          <span className="dialogue-session mono">
            {busy ? "agent thinking" : `session ${sessionId?.slice(-8) ?? "starting"}`}
          </span>
        </div>
        <span className={`dialogue-state ${busy ? "is-thinking" : ""}`} role="status">
          <span aria-hidden="true">{busy ? "◌" : "●"}</span>
          {busy ? "thinking" : "ready"}
        </span>
      </header>

      <div className="dialogue-transcript" aria-live="polite">
        {recentTurns.length === 0 ? (
          <div className="dialogue-empty">
            <span className="dialogue-prompt-mark" aria-hidden="true">
              ✦
            </span>
            <strong>What should we work on?</strong>
            <p>Tell {npcName} something useful or give it a task.</p>
          </div>
        ) : (
          recentTurns.map((turn) => (
            <div
              className={`dialogue-line ${turn.speaker === "agent" ? "is-agent" : "is-owner"}`}
              key={turn.id}
            >
              <span className="dialogue-speaker">{turn.speaker === "agent" ? npcName : "you"}</span>
              <p>{turn.text}</p>
            </div>
          ))
        )}
        {busy ? (
          <div className="dialogue-thinking" role="status">
            <span className="thinking-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            Checking the brain before responding…
          </div>
        ) : null}
      </div>

      <form className="dialogue-form" onSubmit={onSubmit}>
        <input
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="Say something to your agent…"
          aria-label={`Message ${npcName}`}
        />
        <button
          className="primary-button"
          disabled={busy || !message.trim()}
          type="submit"
          aria-label={`Send message to ${npcName}`}
        >
          Send
        </button>
      </form>

      {extractionNotice || lastPromotedMemory || pendingCandidates.length ? (
        <div className="dialogue-feedback" aria-live="polite">
          {extractionNotice ? <p>{extractionNotice}</p> : null}
          {lastPromotedMemory ? (
            <div className="dialogue-confirmed">
              <span className="memory-kind">brain write confirmed</span>
              <strong>
                {lastPromotedMemory.concept} · {lastPromotedMemory.key}
              </strong>
              <span>{lastPromotedMemory.value}</span>
              <button
                className="text-button"
                type="button"
                onClick={onUndoLastSave}
                disabled={busy}
              >
                Undo save
              </button>
            </div>
          ) : null}
          {pendingCandidates.length ? (
            <div className="dialogue-candidates">
              <strong>Candidate context · decide what should last</strong>
              {pendingCandidates.map((candidate) => (
                <div className="dialogue-candidate" key={candidate.candidate_id}>
                  <div>
                    <span className="memory-kind">{candidate.concept}</span>
                    <strong>{candidate.key}</strong>
                    <small>{candidate.value}</small>
                  </div>
                  <div className="dialogue-candidate-actions">
                    <button
                      className="primary-button"
                      type="button"
                      disabled={busy}
                      onClick={() => onConfirmCandidate(candidate)}
                    >
                      Confirm
                    </button>
                    <button
                      className="text-button"
                      type="button"
                      disabled={busy}
                      onClick={() => onDismissCandidate(candidate.candidate_id)}
                    >
                      Keep transient
                    </button>
                  </div>
                </div>
              ))}
              <small>Unconfirmed or sensitive context stays outside the persistent brain.</small>
            </div>
          ) : null}
        </div>
      ) : null}

      {lastTurnMemoryIds.length ||
      lastTurnRetrievals.length ||
      lastAgentRun?.used_memory_ids.length ? (
        <div className="dialogue-proof">
          <div>
            <span className="memory-kind">memory changed the response</span>
            <span>
              {lastTurnRetrievals.length
                ? `Sibyl returned ${lastTurnRetrievals.length} relevant record${lastTurnRetrievals.length === 1 ? "" : "s"}.`
                : "Persistent context was used by the agent run."}
            </span>
          </div>
          <div className="provenance-row" aria-label="Memory IDs used by this response">
            {(lastTurnMemoryIds.length
              ? lastTurnMemoryIds
              : (lastAgentRun?.used_memory_ids ?? [])
            ).map((memoryId) => (
              <code key={memoryId} title={memoryId}>
                {memoryId.slice(-10)}
              </code>
            ))}
          </div>
          {lastAgentRun?.proposed_action ? (
            <span className="dialogue-action">next action · {lastAgentRun.proposed_action}</span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
