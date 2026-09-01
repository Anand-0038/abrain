import { describe, expect, it } from "vitest";
import { agentSignalColor } from "./world-style";

describe("agentSignalColor", () => {
  it.each([
    ["teal", "teal"],
    ["amber", "gold"],
    ["violet", "violet"],
    ["unknown", "teal"],
  ])("maps %s palette to %s", (palette, expected) => {
    expect(agentSignalColor(palette, "idle")).toBe(expected);
  });

  it("keeps failure and action states semantically distinct from the palette", () => {
    expect(agentSignalColor("amber", "offline")).toBe("muted");
    expect(agentSignalColor("violet", "acting")).toBe("success");
  });
});
