import { describe, expect, it } from "vitest";
import { memoryBoundaryPresentation } from "@/src/lib/status";

describe("memory boundary presentation", () => {
  it("reports a ready persistent brain", () => {
    expect(memoryBoundaryPresentation("connected", "sibyl_local")).toEqual({
      state: "connected",
      label: "BRAIN READY",
    });
  });

  it("distinguishes configured-off and unavailable memory", () => {
    expect(memoryBoundaryPresentation("connected", "not_configured").label).toBe(
      "BRAIN UNAVAILABLE",
    );
    expect(memoryBoundaryPresentation("connected", "disabled").label).toBe("MEMORY DISABLED");
    expect(memoryBoundaryPresentation("error", undefined).label).toBe("BRAIN UNAVAILABLE");
  });

  it("keeps the pending state while health is unresolved", () => {
    expect(memoryBoundaryPresentation("checking", undefined)).toEqual({
      state: "checking",
      label: "CHECKING BRAIN",
    });
  });
});
