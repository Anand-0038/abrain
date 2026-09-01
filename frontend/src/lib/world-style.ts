export type AgentRenderMode = "idle" | "writing" | "recalling" | "acting" | "offline" | "restored";

export type AgentSignalColor = "teal" | "gold" | "violet" | "success" | "muted";

export function agentSignalColor(palette: string, mode: AgentRenderMode): AgentSignalColor {
  if (mode === "offline") return "muted";
  if (mode === "acting") return "success";
  if (palette === "amber") return "gold";
  if (palette === "violet") return "violet";
  return "teal";
}
