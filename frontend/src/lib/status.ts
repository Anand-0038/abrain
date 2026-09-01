export type RuntimeConnection = "checking" | "connected" | "error";
export type MemoryBoundary = "not_configured" | "sibyl_local" | "disabled";

export type BoundaryPresentation = {
  state: "checking" | "connected" | "error";
  label: string;
};

export function memoryBoundaryPresentation(
  connection: RuntimeConnection,
  boundary: MemoryBoundary | undefined,
): BoundaryPresentation {
  if (boundary === "sibyl_local") {
    return { state: "connected", label: "BRAIN READY" };
  }
  if (boundary === "disabled") {
    return { state: "error", label: "MEMORY DISABLED" };
  }
  if (boundary === "not_configured") {
    return { state: "error", label: "BRAIN UNAVAILABLE" };
  }
  if (connection === "error") {
    return { state: "error", label: "BRAIN UNAVAILABLE" };
  }
  return { state: "checking", label: "CHECKING BRAIN" };
}
