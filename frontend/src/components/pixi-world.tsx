"use client";

import { useEffect, useRef, useState } from "react";
import { Application, Container, Graphics, Rectangle, Text } from "pixi.js";
import type { DomainEvent } from "@/src/contracts/events";
import type { MemoryRecord } from "@/src/lib/api";
import { agentSignalColor, type AgentRenderMode } from "@/src/lib/world-style";

type PixiWorldProps = {
  events: DomainEvent[];
  memories: MemoryRecord[];
  ownerId: string;
  npcId: string;
  sessionId: string | null;
  palette: string;
  avatarKey: string;
  accessoryKey: string;
  npcName: string;
  specialization: string;
  status: string;
  onAgentSelect: () => void;
  onMemorySelect: (memoryId: string) => void;
  onActivitySelect: () => void;
};

type MotionShard = {
  node: Container;
  halo: Graphics;
  progress: number;
  fromX: number;
  toX: number;
  fromY: number;
  toY: number;
  memoryId: string;
  toZone: ZoneId;
};

type AgentMode = AgentRenderMode;
type ZoneId = "home" | "vault" | "plaza" | "workshop" | "review" | "gate";
type ZoneKind = "home" | "vault" | "plaza" | "workshop" | "review" | "gate";
type Point = { x: number; y: number };
type MemoryVisualCategory = "entity" | "decision" | "constraint" | "goal" | "history";

const HEIGHT = 760;
const COLORS = {
  ink: 0x070a0f,
  night: 0x09111a,
  ground: 0x101b22,
  block: 0x14222b,
  road: 0x0b141c,
  roadEdge: 0x243641,
  line: 0x2b414c,
  muted: 0x8993a4,
  text: 0xf4f1e8,
  teal: 0x56e0d2,
  gold: 0xf6c453,
  blue: 0x4ea1ff,
  violet: 0x9c83ff,
  success: 0x6ee7a2,
  danger: 0xff6b6b,
  leaf: 0x376c69,
  lamp: 0xf4d78a,
};

function memoryVisualCategory(concept: string): MemoryVisualCategory {
  if (concept === "decision") return "decision";
  if (concept === "constraint") return "constraint";
  if (concept === "goal" || concept === "project") return "goal";
  if (concept === "event") return "history";
  return "entity";
}

function memoryVisualColor(category: MemoryVisualCategory) {
  if (category === "decision") return COLORS.violet;
  if (category === "constraint") return COLORS.danger;
  if (category === "goal") return COLORS.gold;
  if (category === "history") return COLORS.blue;
  return COLORS.teal;
}

function memoryVisualLabel(category: MemoryVisualCategory) {
  if (category === "decision") return "DEC";
  if (category === "constraint") return "RULE";
  if (category === "goal") return "GOAL";
  if (category === "history") return "HIST";
  return "FACT";
}

function fallbackAgentZone(events: DomainEvent[]): ZoneId {
  const latest = [...events].sort((left, right) =>
    right.occurred_at.localeCompare(left.occurred_at),
  )[0];
  if (!latest) return "home";
  if (
    latest.event_type === "npc.session_restarted" ||
    latest.event_type === "npc.session_terminated"
  ) {
    return "gate";
  }
  if (
    latest.event_type.startsWith("memory.recall") ||
    latest.event_type.startsWith("memory.write")
  ) {
    return "vault";
  }
  if (latest.event_type.startsWith("handoff.")) return "plaza";
  if (
    latest.event_type === "behavior.changed_by_memory" ||
    latest.event_type === "task.completed"
  ) {
    return "review";
  }
  if (latest.event_type.startsWith("task.")) return "workshop";
  return "home";
}

function FallbackCity({
  events,
  memories,
  npcName,
  sessionId,
  palette,
  specialization,
  status,
  onAgentSelect,
  onMemorySelect,
  onActivitySelect,
}: Pick<
  PixiWorldProps,
  | "events"
  | "memories"
  | "npcName"
  | "sessionId"
  | "palette"
  | "specialization"
  | "status"
  | "onAgentSelect"
  | "onMemorySelect"
  | "onActivitySelect"
>) {
  const zone = fallbackAgentZone(events);
  const latestEvent = [...events].sort((left, right) =>
    right.occurred_at.localeCompare(left.occurred_at),
  )[0];
  const signal = agentSignalColor(palette, status.includes("unavailable") ? "offline" : "idle");

  return (
    <div className="fallback-city" data-agent-zone={zone}>
      <div className="fallback-city-sky" aria-hidden="true" />
      <div className="fallback-road fallback-road-horizontal" aria-hidden="true" />
      <div className="fallback-road fallback-road-vertical" aria-hidden="true" />
      <div className="fallback-zone fallback-home">
        <span>HOME</span>
        <strong>Spawn house</strong>
      </div>
      <div className="fallback-zone fallback-vault">
        <span>MEMORY VAULT</span>
        <strong>Persistent brain</strong>
        <div className="fallback-shards" aria-label={`${memories.length} confirmed memories`}>
          {memories.slice(0, 8).map((memory) => {
            const category = memoryVisualCategory(memory.concept);
            return (
              <button
                className={`fallback-shard fallback-shard-${category}`}
                key={memory.memory_id}
                onClick={() => onMemorySelect(memory.memory_id)}
                title={`${memory.key}: ${memory.value}`}
                type="button"
              >
                {memoryVisualLabel(category)}
              </button>
            );
          })}
        </div>
      </div>
      <button className="fallback-zone fallback-plaza" onClick={onActivitySelect} type="button">
        <span>MISSION PLAZA</span>
        <strong>Assign work</strong>
      </button>
      <button className="fallback-zone fallback-workshop" onClick={onActivitySelect} type="button">
        <span>WORKSHOP</span>
        <strong>Agent working</strong>
      </button>
      <button className="fallback-zone fallback-review" onClick={onActivitySelect} type="button">
        <span>REVIEW TOWER</span>
        <strong>Verify result</strong>
      </button>
      <div className="fallback-zone fallback-gate">
        <span>SESSION GATE</span>
        <strong>Fresh body</strong>
      </div>
      <button
        className={`fallback-agent fallback-agent-${signal}`}
        onClick={onAgentSelect}
        type="button"
      >
        <span className="fallback-agent-body" aria-hidden="true">
          <i />
        </span>
        <strong>{npcName}</strong>
        <small>{specialization}</small>
      </button>
      <div className="fallback-city-status" role="status">
        <span>{status.replaceAll("_", " ")}</span>
        <strong>{latestEvent?.event_type.replaceAll(".", " ") ?? "brain ready"}</strong>
        <code>{sessionId?.slice(-8) ?? "no session"}</code>
      </div>
      <p className="fallback-renderer-note">Interactive city · compatibility renderer</p>
    </div>
  );
}

export function PixiWorld({
  events,
  memories,
  ownerId,
  npcId,
  sessionId,
  palette,
  avatarKey,
  accessoryKey,
  npcName,
  specialization,
  status,
  onAgentSelect,
  onMemorySelect,
  onActivitySelect,
}: PixiWorldProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [rendererState, setRendererState] = useState<"loading" | "pixi" | "fallback">("loading");
  const eventsRef = useRef(events);
  const memoriesRef = useRef(memories);
  const ownerIdRef = useRef(ownerId);
  const npcIdRef = useRef(npcId);
  const sessionIdRef = useRef(sessionId);
  const paletteRef = useRef(palette);
  const avatarKeyRef = useRef(avatarKey);
  const accessoryKeyRef = useRef(accessoryKey);
  const npcNameRef = useRef(npcName);
  const specializationRef = useRef(specialization);
  const statusRef = useRef(status);
  const onAgentSelectRef = useRef(onAgentSelect);
  const onMemorySelectRef = useRef(onMemorySelect);
  const onActivitySelectRef = useRef(onActivitySelect);

  useEffect(() => {
    eventsRef.current = events;
    memoriesRef.current = memories;
    ownerIdRef.current = ownerId;
    npcIdRef.current = npcId;
    sessionIdRef.current = sessionId;
    paletteRef.current = palette;
    avatarKeyRef.current = avatarKey;
    accessoryKeyRef.current = accessoryKey;
    npcNameRef.current = npcName;
    specializationRef.current = specialization;
    statusRef.current = status;
    onAgentSelectRef.current = onAgentSelect;
    onMemorySelectRef.current = onMemorySelect;
    onActivitySelectRef.current = onActivitySelect;
  }, [
    events,
    memories,
    onActivitySelect,
    onAgentSelect,
    onMemorySelect,
    ownerId,
    npcId,
    sessionId,
    palette,
    avatarKey,
    accessoryKey,
    npcName,
    specialization,
    status,
  ]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const element = host;
    const app = new Application();
    let disposed = false;
    let initialized = false;
    let resizeObserver: ResizeObserver | undefined;

    async function mount() {
      try {
        await app.init({
          antialias: true,
          background: `#${COLORS.ink.toString(16).padStart(6, "0")}`,
          width: Math.max(1, element.clientWidth),
          height: HEIGHT,
          resolution: Math.min(window.devicePixelRatio, 2),
          autoDensity: true,
        });
      } catch {
        if (!disposed) setRendererState("fallback");
        return;
      }
      initialized = true;
      if (disposed) {
        app.destroy(true);
        return;
      }

      element.appendChild(app.canvas);
      setRendererState("pixi");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const width = () => Math.max(1, element.clientWidth);
      const cityPoint = (zone: ZoneId): Point => {
        const currentWidth = width();
        const left = Math.max(86, currentWidth * 0.25);
        const right = Math.min(currentWidth - 86, currentWidth * 0.75);
        const points: Record<ZoneId, Point> = {
          home: { x: left, y: 190 },
          vault: { x: right, y: 190 },
          plaza: { x: left, y: 386 },
          workshop: { x: right, y: 386 },
          review: { x: left, y: 582 },
          gate: { x: right, y: 582 },
        };
        return points[zone];
      };
      const cityCenter = () => width() / 2;
      const stage = app.stage;
      const scene = new Graphics();
      const zoneLayer = new Container();
      const effectLayer = new Container();
      const objectLayer = new Container();
      stage.addChild(scene, zoneLayer, effectLayer, objectLayer);

      const zones: {
        id: ZoneId;
        kind: ZoneKind;
        label: string;
        sublabel: string;
        color: number;
      }[] = [
        {
          id: "home",
          kind: "home",
          label: "HOME / SPAWN",
          sublabel: "owner context",
          color: COLORS.teal,
        },
        {
          id: "vault",
          kind: "vault",
          label: "MEMORY VAULT",
          sublabel: "persistent brain",
          color: COLORS.gold,
        },
        {
          id: "plaza",
          kind: "plaza",
          label: "MISSION PLAZA",
          sublabel: "tasks arrive here",
          color: COLORS.violet,
        },
        {
          id: "workshop",
          kind: "workshop",
          label: "WORKSHOP",
          sublabel: "agents do the work",
          color: COLORS.teal,
        },
        {
          id: "review",
          kind: "review",
          label: "REVIEW TOWER",
          sublabel: "decisions get clear",
          color: COLORS.success,
        },
        {
          id: "gate",
          kind: "gate",
          label: "SESSION GATE",
          sublabel: "new body enters",
          color: COLORS.blue,
        },
      ];

      function drawTree(x: number, y: number, scale = 1) {
        scene
          .ellipse(x, y + 12 * scale, 12 * scale, 4 * scale)
          .fill({ color: 0x05090c, alpha: 0.45 });
        scene
          .rect(x - 2 * scale, y + scale, 4 * scale, 12 * scale)
          .fill({ color: 0x745338, alpha: 0.9 });
        scene
          .circle(x - 5 * scale, y - 3 * scale, 7 * scale)
          .fill({ color: COLORS.leaf, alpha: 0.92 });
        scene.circle(x + 4 * scale, y - 5 * scale, 8 * scale).fill({ color: 0x4d8b71, alpha: 0.9 });
        scene.circle(x, y - 11 * scale, 7 * scale).fill({ color: 0x63a384, alpha: 0.8 });
      }

      function drawLamp(x: number, y: number) {
        scene.ellipse(x, y + 9, 10, 3).fill({ color: 0x05090c, alpha: 0.52 });
        scene
          .moveTo(x, y + 8)
          .lineTo(x, y - 18)
          .stroke({ color: COLORS.roadEdge, width: 2 });
        scene
          .moveTo(x, y - 17)
          .lineTo(x + 6, y - 20)
          .stroke({ color: COLORS.roadEdge, width: 2 });
        scene.circle(x + 6, y - 20, 3).fill({ color: COLORS.lamp, alpha: 0.85 });
        scene.circle(x + 6, y - 20, 8).fill({ color: COLORS.lamp, alpha: 0.06 });
      }

      function drawRoad(y: number) {
        const currentWidth = width();
        scene
          .roundRect(24, y - 20, currentWidth - 48, 40, 12)
          .fill({ color: COLORS.road, alpha: 0.95 });
        scene
          .roundRect(24, y - 20, currentWidth - 48, 40, 12)
          .stroke({ color: COLORS.roadEdge, width: 1 });
        for (let x = 42; x < currentWidth - 32; x += 38) {
          scene
            .moveTo(x, y)
            .lineTo(x + 18, y)
            .stroke({ color: COLORS.gold, width: 1, alpha: 0.22 });
        }
      }

      function drawScene() {
        const currentWidth = width();
        const center = cityCenter();
        scene.clear();
        scene.rect(0, 0, currentWidth, HEIGHT).fill({ color: COLORS.ink });
        scene.rect(0, 0, currentWidth, 92).fill({ color: COLORS.night });
        scene.rect(0, 92, currentWidth, HEIGHT - 92).fill({ color: COLORS.ground });
        scene.moveTo(0, 92).lineTo(currentWidth, 92).stroke({ color: COLORS.line, width: 1 });
        scene
          .roundRect(14, 108, currentWidth - 28, HEIGHT - 126, 20)
          .fill({ color: COLORS.ground });
        scene
          .roundRect(14, 108, currentWidth - 28, HEIGHT - 126, 20)
          .stroke({ color: COLORS.line, alpha: 0.8, width: 1 });
        for (let y = 118; y < HEIGHT - 22; y += 28) {
          scene
            .moveTo(22, y)
            .lineTo(currentWidth - 22, y)
            .stroke({ color: COLORS.line, alpha: 0.08, width: 1 });
        }
        for (let x = 30; x < currentWidth; x += 32) {
          scene
            .moveTo(x, 112)
            .lineTo(x, HEIGHT - 22)
            .stroke({ color: COLORS.line, alpha: 0.055, width: 1 });
        }
        drawRoad(172);
        drawRoad(316);
        drawRoad(460);
        scene
          .roundRect(center - 18, 118, 36, HEIGHT - 142, 12)
          .fill({ color: COLORS.road, alpha: 0.96 });
        scene
          .roundRect(center - 18, 118, 36, HEIGHT - 142, 12)
          .stroke({ color: COLORS.roadEdge, width: 1 });
        for (let y = 132; y < HEIGHT - 38; y += 34) {
          scene
            .moveTo(center, y)
            .lineTo(center, y + 15)
            .stroke({ color: COLORS.gold, width: 1, alpha: 0.22 });
        }
        for (const block of [
          { x: 28, y: 122, w: Math.max(44, currentWidth * 0.36), h: 96 },
          { x: center + 34, y: 122, w: Math.max(44, currentWidth * 0.36 - 18), h: 96 },
          { x: 28, y: 266, w: Math.max(44, currentWidth * 0.36), h: 96 },
          { x: center + 34, y: 266, w: Math.max(44, currentWidth * 0.36 - 18), h: 96 },
          { x: 28, y: 410, w: Math.max(44, currentWidth * 0.36), h: 96 },
          { x: center + 34, y: 410, w: Math.max(44, currentWidth * 0.36 - 18), h: 96 },
        ]) {
          scene
            .roundRect(block.x, block.y, block.w, block.h, 12)
            .fill({ color: COLORS.block, alpha: 0.46 });
          scene
            .roundRect(block.x, block.y, block.w, block.h, 12)
            .stroke({ color: COLORS.line, alpha: 0.26, width: 1 });
        }
        drawTree(48, 133, 0.75);
        drawTree(currentWidth - 48, 133, 0.72);
        drawTree(48, 367, 0.68);
        drawTree(currentWidth - 48, 367, 0.76);
        drawTree(46, 505, 0.6);
        drawTree(currentWidth - 46, 505, 0.62);
        drawLamp(center - 28, 247);
        drawLamp(center + 28, 386);
        drawLamp(center - 28, 524);
        scene.circle(center, 244, 4).fill({ color: COLORS.gold, alpha: 0.72 });
        scene.circle(center, 244, 13).stroke({ color: COLORS.gold, alpha: 0.24, width: 1 });
        scene.circle(center, 388, 4).fill({ color: COLORS.teal, alpha: 0.72 });
        scene.circle(center, 388, 13).stroke({ color: COLORS.teal, alpha: 0.24, width: 1 });
      }

      const zoneHalos: Graphics[] = [];
      const zoneIcons: Graphics[] = [];
      const zonePlatforms: Graphics[] = [];
      const zoneLabels: { node: Text; zone: ZoneId; offset: number }[] = [];
      let activeZone = -1;
      const resize = () => {
        if (!app.renderer || disposed) return;
        app.renderer.resize(width(), HEIGHT);
        drawScene();
        redrawZones();
      };

      function drawBuilding(icon: Graphics, zone: (typeof zones)[number], active: boolean) {
        const accent = zone.color;
        const fillAlpha = active ? 0.4 : 0.22;
        icon.clear();
        if (zone.kind === "home") {
          icon.roundRect(-31, -14, 62, 31, 7).fill({ color: accent, alpha: fillAlpha });
          icon
            .roundRect(-31, -14, 62, 31, 7)
            .stroke({ color: accent, alpha: active ? 0.96 : 0.72, width: 2 });
          icon.moveTo(-36, -8).lineTo(0, -35).lineTo(36, -8).stroke({ color: accent, width: 3 });
          icon.roundRect(-7, 3, 14, 14, 2).fill({ color: accent, alpha: 0.78 });
          icon.roundRect(-21, -8, 11, 9, 2).fill({ color: COLORS.text, alpha: 0.7 });
          icon.roundRect(10, -8, 11, 9, 2).fill({ color: COLORS.text, alpha: 0.7 });
        } else if (zone.kind === "vault") {
          icon.roundRect(-29, -17, 58, 34, 7).fill({ color: accent, alpha: fillAlpha });
          icon
            .roundRect(-29, -17, 58, 34, 7)
            .stroke({ color: accent, alpha: active ? 0.96 : 0.72, width: 2 });
          icon
            .moveTo(-18, 14)
            .lineTo(-18, -3)
            .lineTo(0, -35)
            .lineTo(18, -3)
            .lineTo(18, 14)
            .stroke({ color: accent, width: 2 });
          icon
            .moveTo(-7, 14)
            .lineTo(-7, -4)
            .lineTo(0, -16)
            .lineTo(7, -4)
            .lineTo(7, 14)
            .stroke({ color: accent, width: 2 });
          icon.circle(0, -4, active ? 8 : 5).fill({ color: accent, alpha: active ? 0.98 : 0.56 });
        } else if (zone.kind === "plaza") {
          icon.roundRect(-31, -14, 62, 28, 6).fill({ color: accent, alpha: fillAlpha });
          icon
            .roundRect(-31, -14, 62, 28, 6)
            .stroke({ color: accent, alpha: active ? 0.96 : 0.72, width: 2 });
          icon.roundRect(-23, -7, 46, 14, 3).fill({ color: COLORS.ink, alpha: 0.84 });
          icon
            .moveTo(-14, -11)
            .lineTo(-14, -29)
            .lineTo(-4, -24)
            .lineTo(-4, -11)
            .stroke({ color: accent, width: 2 });
          icon
            .moveTo(14, -11)
            .lineTo(14, -29)
            .lineTo(4, -24)
            .lineTo(4, -11)
            .stroke({ color: accent, width: 2 });
          icon
            .circle(0, 20, active ? 7 : 4)
            .fill({ color: active ? COLORS.success : accent, alpha: 0.92 });
        } else if (zone.kind === "workshop") {
          icon.roundRect(-31, -19, 62, 38, 6).fill({ color: accent, alpha: fillAlpha });
          icon
            .roundRect(-31, -19, 62, 38, 6)
            .stroke({ color: accent, alpha: active ? 0.96 : 0.72, width: 2 });
          icon.roundRect(-22, -10, 44, 22, 3).fill({ color: COLORS.ink, alpha: 0.76 });
          icon.circle(-9, 1, 7).stroke({ color: accent, alpha: 0.86, width: 2 });
          icon.circle(9, 1, 7).stroke({ color: accent, alpha: 0.86, width: 2 });
          icon.moveTo(-2, -11).lineTo(2, 12).stroke({ color: accent, width: 2 });
        } else if (zone.kind === "review") {
          icon.roundRect(-22, -32, 44, 49, 6).fill({ color: accent, alpha: fillAlpha });
          icon
            .roundRect(-22, -32, 44, 49, 6)
            .stroke({ color: accent, alpha: active ? 0.96 : 0.72, width: 2 });
          icon.roundRect(-14, -20, 28, 5, 2).fill({ color: accent, alpha: 0.84 });
          icon.roundRect(-14, -7, 28, 5, 2).fill({ color: accent, alpha: 0.62 });
          icon.roundRect(-14, 6, 20, 5, 2).fill({ color: accent, alpha: 0.48 });
          icon.circle(0, -42, active ? 7 : 4).fill({ color: accent, alpha: active ? 0.95 : 0.58 });
        } else {
          icon.arc(0, 2, 27, Math.PI, Math.PI * 2).stroke({ color: accent, width: 4 });
          icon
            .moveTo(-27, 2)
            .lineTo(-27, 22)
            .lineTo(27, 22)
            .lineTo(27, 2)
            .stroke({ color: accent, width: 4 });
          icon.roundRect(-14, 6, 28, 17, 5).fill({ color: accent, alpha: fillAlpha });
          icon
            .circle(0, -1, active ? 9 : 6)
            .fill({ color: COLORS.text, alpha: active ? 0.84 : 0.36 });
        }
      }

      for (const zone of zones) {
        const halo = new Graphics();
        zoneLayer.addChild(halo);
        zoneHalos.push(halo);
        const platform = new Graphics();
        zoneLayer.addChild(platform);
        zonePlatforms.push(platform);
        const icon = new Graphics();
        icon.hitArea = new Rectangle(-64, -64, 128, 128);
        if (zone.kind === "plaza" || zone.kind === "workshop" || zone.kind === "review") {
          icon.eventMode = "static";
          icon.cursor = "pointer";
          icon.on("pointertap", () => onActivitySelectRef.current());
        }
        zoneLayer.addChild(icon);
        zoneIcons.push(icon);
        const label = new Text({
          text: zone.label,
          style: { fill: COLORS.text, fontFamily: "monospace", fontSize: 9, letterSpacing: 1.2 },
        });
        label.anchor.set(0.5, 0);
        label.alpha = 0.92;
        zoneLayer.addChild(label);
        zoneLabels.push({ node: label, zone: zone.id, offset: 43 });
        const sublabel = new Text({
          text: zone.sublabel,
          style: { fill: COLORS.muted, fontFamily: "monospace", fontSize: 8 },
        });
        sublabel.anchor.set(0.5, 0);
        sublabel.alpha = 0.8;
        zoneLayer.addChild(sublabel);
        zoneLabels.push({ node: sublabel, zone: zone.id, offset: 59 });
      }

      function redrawZones() {
        for (let index = 0; index < zones.length; index += 1) {
          const zone = zones[index];
          const point = cityPoint(zone.id);
          const active = activeZone === index;
          const halo = zoneHalos[index];
          halo.clear();
          halo.x = point.x;
          halo.y = point.y;
          halo
            .circle(0, 0, zone.kind === "vault" ? 58 : 50)
            .fill({ color: zone.color, alpha: active ? 0.1 : 0.045 });
          halo
            .circle(0, 0, zone.kind === "vault" ? 44 : 38)
            .stroke({ color: zone.color, alpha: active ? 0.58 : 0.32, width: 1 });
          const platform = zonePlatforms[index];
          platform.clear();
          platform.x = point.x;
          platform.y = point.y;
          platform.ellipse(0, 28, 68, 14).fill({ color: 0x020508, alpha: 0.64 });
          platform
            .roundRect(-56, 23, 112, 8, 3)
            .fill({ color: zone.color, alpha: active ? 0.16 : 0.08 });
          platform
            .roundRect(-44, 23, 88, 8, 3)
            .stroke({ color: zone.color, alpha: active ? 0.54 : 0.26, width: 1 });
          const icon = zoneIcons[index];
          icon.x = point.x;
          icon.y = point.y;
          drawBuilding(icon, zone, active);
          halo.alpha = active ? 1.35 : 1;
          platform.alpha = active ? 1.22 : 1;
        }
        for (const label of zoneLabels) {
          const point = cityPoint(label.zone);
          label.node.x = point.x;
          label.node.y = point.y + label.offset;
        }
      }

      drawScene();
      redrawZones();

      const header = new Text({
        text: "A-BRAIN WORLD  /  CONTINUITY LAB",
        style: { fill: COLORS.muted, fontFamily: "monospace", fontSize: 10, letterSpacing: 1.2 },
      });
      header.x = 20;
      header.y = 27;
      stage.addChild(header);
      const instruction = new Text({
        text: "a tiny city where memory survives the body",
        style: { fill: COLORS.text, fontFamily: "monospace", fontSize: 12 },
      });
      instruction.x = 20;
      instruction.y = 50;
      stage.addChild(instruction);
      const message = new Text({
        text: "BRAIN READY · TALK TO YOUR AGENT TO BEGIN",
        style: { fill: COLORS.muted, fontFamily: "monospace", fontSize: 10 },
      });
      message.anchor.set(0.5, 0.5);
      message.x = width() / 2;
      message.y = 113;
      stage.addChild(message);
      const progress = new Graphics();
      effectLayer.addChild(progress);
      const activityPulse = new Graphics();
      effectLayer.addChild(activityPulse);
      const activityCore = new Graphics();
      effectLayer.addChild(activityCore);
      const portalFlash = new Graphics();
      portalFlash.alpha = 0;
      effectLayer.addChild(portalFlash);
      const ambientDust: { node: Graphics; x: number; y: number; phase: number }[] = [];
      for (let index = 0; index < 24; index += 1) {
        const node = new Graphics();
        const x = 0.06 + ((index * 83) % 880) / 1000;
        const y = 126 + ((index * 47) % 380);
        node.circle(0, 0, index % 4 === 0 ? 1.5 : 0.8).fill({
          color: index % 3 === 0 ? COLORS.teal : index % 3 === 1 ? COLORS.gold : COLORS.blue,
          alpha: 0.16,
        });
        effectLayer.addChild(node);
        ambientDust.push({ node, x, y, phase: index * 0.7 });
      }
      const completionLabel = new Text({
        text: "ACTION UNLOCKED · MEMORY MADE IT POSSIBLE",
        style: { fill: COLORS.success, fontFamily: "monospace", fontSize: 10 },
      });
      completionLabel.anchor.set(0.5, 0.5);
      completionLabel.y = 542;
      completionLabel.alpha = 0;
      stage.addChild(completionLabel);
      const celebrationParticles: { node: Graphics; progress: number; angle: number }[] = [];
      const dissolveParticles: {
        node: Graphics;
        progress: number;
        angle: number;
        originX: number;
        originY: number;
      }[] = [];
      const portalRings: Graphics[] = [];
      for (let index = 0; index < 3; index += 1) {
        const ring = new Graphics();
        effectLayer.addChild(ring);
        portalRings.push(ring);
      }

      const agent = new Container();
      agent.eventMode = "static";
      agent.cursor = "pointer";
      agent.hitArea = new Rectangle(-58, -92, 116, 132);
      agent.on("pointertap", () => onAgentSelectRef.current());
      const agentGlow = new Graphics();
      const agentState = new Graphics();
      const agentBody = new Graphics();
      const agentFace = new Graphics();
      const agentShadow = new Graphics();
      agentShadow.ellipse(0, 18, 24, 7).fill({ color: 0x020508, alpha: 0.64 });
      effectLayer.addChild(agentShadow);
      const agentTrail: Graphics[] = [];
      for (let index = 0; index < 4; index += 1) {
        const trail = new Graphics();
        trail.circle(0, 0, 3 - index * 0.45).fill({ color: COLORS.teal, alpha: 0.12 });
        effectLayer.addChild(trail);
        agentTrail.push(trail);
      }
      const agentNameLabel = new Text({
        text: "Agent",
        style: { fill: COLORS.text, fontFamily: "monospace", fontSize: 11 },
      });
      agentNameLabel.anchor.set(0.5, 1);
      agentNameLabel.y = -43;
      const agentRoleLabel = new Text({
        text: "● PRIMARY",
        style: { fill: COLORS.teal, fontFamily: "monospace", fontSize: 8, letterSpacing: 0.7 },
      });
      agentRoleLabel.anchor.set(0.5, 1);
      agentRoleLabel.y = -56;
      const agentStatusLabel = new Text({
        text: "IDLE",
        style: { fill: COLORS.muted, fontFamily: "monospace", fontSize: 8, letterSpacing: 0.8 },
      });
      agentStatusLabel.anchor.set(0.5, 0);
      agentStatusLabel.y = 29;
      agent.addChild(
        agentGlow,
        agentState,
        agentBody,
        agentFace,
        agentNameLabel,
        agentRoleLabel,
        agentStatusLabel,
      );
      objectLayer.addChild(agent);

      let agentLifecycle: "active" | "despawning" | "respawning" = "active";
      let agentAlpha = 1;
      let animationClock = 0;

      function redrawAgent(mode: AgentMode, x: number, y: number) {
        const walking = Math.abs(agentTargetX - x) + Math.abs(agentTargetY - y) > 4;
        const bob =
          reducedMotion || agentLifecycle !== "active" ? 0 : Math.sin(animationClock / 460) * 2;
        const visualY = y + bob;
        agent.x = x;
        agent.y = visualY;
        agentShadow.x = x;
        agentShadow.y = visualY + 18;
        const signalColors: Record<string, number> = {
          teal: COLORS.teal,
          gold: COLORS.gold,
          violet: COLORS.violet,
          success: COLORS.success,
          muted: COLORS.muted,
        };
        const activeColor =
          mode === "offline"
            ? COLORS.danger
            : (signalColors[agentSignalColor(paletteRef.current, mode)] ?? COLORS.teal);
        const roleLabel =
          {
            primary: "PRIMARY",
            planner: "PLANNER",
            worker: "WORKER",
            reviewer: "REVIEWER",
          }[specializationRef.current] ?? "AGENT";
        const statusLabel =
          agentLifecycle === "despawning"
            ? "DISSOLVING"
            : agentLifecycle === "respawning"
              ? "FRESH BODY"
              : mode === "writing"
                ? "REMEMBERING"
                : mode === "recalling"
                  ? "RECALLING"
                  : mode === "acting"
                    ? walking
                      ? "MOVING"
                      : "WORKING"
                    : mode === "offline"
                      ? "BLOCKED"
                      : mode === "restored"
                        ? "RESTORED"
                        : "IDLE";
        agentNameLabel.text = npcNameRef.current.trim().slice(0, 24) || "Agent";
        agentRoleLabel.text = `● ${roleLabel}`;
        agentRoleLabel.style.fill = activeColor;
        agentStatusLabel.text = statusLabel;
        agentStatusLabel.style.fill = mode === "offline" ? COLORS.danger : COLORS.muted;
        agentGlow.clear();
        agentGlow
          .circle(0, 0, 31)
          .fill({ color: activeColor, alpha: mode === "offline" ? 0.08 : 0.15 });
        agentGlow.circle(0, 0, 23).stroke({ color: activeColor, alpha: 0.54, width: 1 });
        agentState.clear();
        if (mode === "offline") {
          agentState.circle(0, 0, 29).stroke({ color: COLORS.danger, alpha: 0.72, width: 2 });
          agentState
            .moveTo(-8, -8)
            .lineTo(8, 8)
            .moveTo(8, -8)
            .lineTo(-8, 8)
            .stroke({ color: COLORS.danger, width: 2.5 });
        } else if (mode === "recalling" || mode === "restored") {
          agentState.circle(0, 0, 29).stroke({ color: COLORS.gold, alpha: 0.62, width: 1.5 });
          agentState.circle(-18, -14, 2.5).fill({ color: COLORS.gold, alpha: 0.9 });
          agentState.circle(18, -9, 2).fill({ color: COLORS.gold, alpha: 0.74 });
          agentState.circle(14, 15, 2.5).fill({ color: COLORS.gold, alpha: 0.84 });
        } else if (mode === "writing" || mode === "acting") {
          const orbit = animationClock / 240;
          agentState
            .circle(Math.cos(orbit) * 26, Math.sin(orbit) * 26, 2.5)
            .fill({ color: activeColor, alpha: 0.92 });
          agentState
            .circle(Math.cos(orbit + 2.1) * 26, Math.sin(orbit + 2.1) * 26, 2)
            .fill({ color: activeColor, alpha: 0.72 });
        } else {
          agentState.circle(0, -28, 2.5).fill({ color: activeColor, alpha: 0.84 });
        }
        agentBody.clear();
        const step = walking && !reducedMotion ? Math.sin(animationClock / 85) * 3 : 0;
        const avatar = avatarKeyRef.current;
        if (avatar === "scout") {
          agentBody.roundRect(-15, -12, 30, 25, 10).fill({ color: COLORS.ink });
          agentBody.roundRect(-15, -12, 30, 25, 10).stroke({ color: activeColor, width: 2.5 });
          agentBody.roundRect(-11, -6, 22, 7, 3).fill({ color: activeColor, alpha: 0.52 });
          agentBody
            .moveTo(-9, 13)
            .lineTo(-12, 20 + step)
            .moveTo(9, 13)
            .lineTo(12, 20 - step)
            .stroke({ color: activeColor, width: 2.5 });
          agentBody.circle(-7, 8, 2).fill({ color: activeColor });
          agentBody.circle(7, 8, 2).fill({ color: activeColor });
        } else if (avatar === "orbiter") {
          agentBody.circle(0, -1, 16).fill({ color: COLORS.ink });
          agentBody.circle(0, -1, 16).stroke({ color: activeColor, width: 2.5 });
          agentBody.ellipse(0, -1, 24, 7).stroke({ color: activeColor, alpha: 0.76, width: 2 });
          agentBody.circle(0, 12, 3).fill({ color: activeColor });
        } else {
          agentBody.roundRect(-15, -13, 30, 27, 9).fill({ color: COLORS.ink });
          agentBody.roundRect(-15, -13, 30, 27, 9).stroke({ color: activeColor, width: 2.5 });
          agentBody
            .moveTo(-9, 14)
            .lineTo(-12, 22 + step)
            .moveTo(9, 14)
            .lineTo(12, 22 - step)
            .stroke({ color: activeColor, width: 2.5 });
          agentBody.moveTo(0, -13).lineTo(0, -24).stroke({ color: activeColor, width: 2 });
          agentBody.circle(0, -27, 3).fill({ color: activeColor });
          agentBody.circle(0, 12, 3).fill({ color: activeColor });
        }
        if (accessoryKeyRef.current === "antenna" && avatar !== "node") {
          agentBody.moveTo(0, -16).lineTo(0, -25).stroke({ color: activeColor, width: 2 });
          agentBody.circle(0, -28, 3).fill({ color: activeColor });
        } else if (accessoryKeyRef.current === "satchel") {
          agentBody.roundRect(13, 0, 8, 12, 2).fill({ color: COLORS.gold, alpha: 0.86 });
          agentBody.moveTo(13, 1).lineTo(21, 1).stroke({ color: COLORS.ink, width: 1 });
        }
        agentFace.clear();
        if (avatar === "orbiter") {
          agentFace.circle(-5, -3, 2.4).fill({ color: activeColor });
          agentFace.circle(5, -3, 2.4).fill({ color: activeColor });
          agentFace.moveTo(-4, 6).lineTo(4, 6).stroke({ color: activeColor, width: 1.5 });
        } else {
          agentFace.circle(-5, -2, 2.2).fill({ color: activeColor });
          agentFace.circle(5, -2, 2.2).fill({ color: activeColor });
          agentFace.moveTo(-4, 6).lineTo(4, 6).stroke({ color: activeColor, width: 1.5 });
        }
        agent.alpha = agentAlpha;
      }

      let agentX = cityPoint("home").x;
      let agentY = cityPoint("home").y - 53;
      let agentTargetX = agentX;
      let agentTargetY = agentY;
      let agentMode: AgentMode = "idle";
      redrawAgent(agentMode, agentX, agentY);
      const countLabel = new Text({
        text: "00 SHARDS IN BRAIN VAULT",
        style: { fill: COLORS.gold, fontFamily: "monospace", fontSize: 10 },
      });
      countLabel.anchor.set(0.5, 0.5);
      countLabel.y = 542;
      stage.addChild(countLabel);

      const shards: MotionShard[] = [];
      const seen = new Set<string>();
      const renderedMemoryIds = new Set<string>();
      const restingNodes = new Map<string, Container>();
      const restingCategories = new Map<string, MemoryVisualCategory>();

      function memoryForId(memoryId: string) {
        return memoriesRef.current.find((memory) => memory.memory_id === memoryId);
      }

      function drawMemoryGlyph(graphic: Graphics, category: MemoryVisualCategory, color: number) {
        if (category === "decision") {
          graphic
            .moveTo(0, -8)
            .lineTo(8, 0)
            .lineTo(0, 8)
            .lineTo(-8, 0)
            .closePath()
            .fill({ color, alpha: 0.28 })
            .stroke({ color, alpha: 0.95, width: 1.6 });
        } else if (category === "constraint") {
          graphic
            .moveTo(-8, -6)
            .lineTo(8, -6)
            .lineTo(8, 4)
            .lineTo(0, 9)
            .lineTo(-8, 4)
            .closePath()
            .fill({ color, alpha: 0.24 })
            .stroke({ color, alpha: 0.95, width: 1.6 });
          graphic.moveTo(-4, -1).lineTo(4, -1).stroke({ color, alpha: 0.9, width: 1.4 });
        } else if (category === "goal") {
          graphic
            .moveTo(0, -9)
            .lineTo(9, 7)
            .lineTo(-9, 7)
            .closePath()
            .fill({ color, alpha: 0.25 })
            .stroke({ color, alpha: 0.96, width: 1.6 });
        } else if (category === "history") {
          graphic.circle(0, 0, 8).fill({ color, alpha: 0.22 }).stroke({ color, width: 1.6 });
          graphic.moveTo(0, 0).lineTo(0, -5).lineTo(4, -2).stroke({ color, width: 1.4 });
        } else {
          graphic.roundRect(-8, -8, 16, 16, 5).fill({ color, alpha: 0.24 });
          graphic.roundRect(-8, -8, 16, 16, 5).stroke({ color, alpha: 0.96, width: 1.6 });
          graphic.circle(0, 0, 2.5).fill({ color, alpha: 0.95 });
        }
      }

      function createMemoryNode(memoryId: string, labelled: boolean) {
        const memory = memoryForId(memoryId);
        const category = memoryVisualCategory(memory?.concept ?? "preference");
        const color = memoryVisualColor(category);
        const container = new Container();
        const glow = new Graphics();
        glow.circle(0, 0, 14).fill({ color, alpha: 0.08 });
        const glyph = new Graphics();
        drawMemoryGlyph(glyph, category, color);
        container.addChild(glow, glyph);
        if (labelled) {
          const label = new Text({
            text: memoryVisualLabel(category),
            style: { fill: color, fontFamily: "monospace", fontSize: 7, fontWeight: "700" },
          });
          label.anchor.set(0.5, 0);
          label.y = 11;
          container.addChild(label);
        }
        container.eventMode = "static";
        container.cursor = "pointer";
        container.hitArea = new Rectangle(-14, -14, 28, labelled ? 34 : 28);
        container.on("pointertap", () => onMemorySelectRef.current(memoryId));
        return { container, color };
      }

      function addRestingShard(memoryId: string) {
        if (restingNodes.has(memoryId)) return;
        const { container: node } = createMemoryNode(memoryId, true);
        const category = memoryVisualCategory(memoryForId(memoryId)?.concept ?? "preference");
        const slot = restingNodes.size;
        const vault = cityPoint("vault");
        node.x = vault.x + ((slot % 5) - 2) * 18;
        node.y = vault.y + 49 + Math.floor(slot / 5) * 19;
        objectLayer.addChild(node);
        restingNodes.set(memoryId, node);
        restingCategories.set(memoryId, category);
      }

      function syncRestingCategory(memory: MemoryRecord) {
        const nextCategory = memoryVisualCategory(memory.concept);
        if (restingCategories.get(memory.memory_id) === nextCategory) return;
        const existing = restingNodes.get(memory.memory_id);
        if (!existing) return;
        const position = { x: existing.x, y: existing.y, scale: existing.scale.x };
        existing.destroy({ children: true });
        restingNodes.delete(memory.memory_id);
        restingCategories.delete(memory.memory_id);
        addRestingShard(memory.memory_id);
        const replacement = restingNodes.get(memory.memory_id);
        if (replacement) {
          replacement.x = position.x;
          replacement.y = position.y;
          replacement.scale.set(position.scale);
        }
      }

      function addMotionShard(memoryId: string, fromZone: ZoneId, toZone: ZoneId) {
        const from = cityPoint(fromZone);
        const to = cityPoint(toZone);
        const { container: node, color } = createMemoryNode(memoryId, false);
        node.x = from.x;
        node.y = from.y - 42;
        const halo = new Graphics();
        halo.circle(0, 0, 14).stroke({ color, alpha: 0.32, width: 1 });
        halo.circle(0, 0, 20).stroke({ color: COLORS.teal, alpha: 0.12, width: 1 });
        halo.x = node.x;
        halo.y = node.y;
        effectLayer.addChild(halo);
        objectLayer.addChild(node);
        shards.push({
          node,
          halo,
          progress: 0,
          fromX: from.x,
          toX: to.x,
          fromY: from.y - 42,
          toY: to.y - 42,
          memoryId,
          toZone,
        });
        if (fromZone === "vault") {
          const resting = restingNodes.get(memoryId);
          if (resting) resting.alpha = 0.18;
        }
      }

      function removeMemory(memoryId: string) {
        const resting = restingNodes.get(memoryId);
        resting?.destroy({ children: true });
        restingNodes.delete(memoryId);
        restingCategories.delete(memoryId);
        renderedMemoryIds.delete(memoryId);
        for (let index = shards.length - 1; index >= 0; index -= 1) {
          if (shards[index].memoryId === memoryId) {
            shards[index].node.destroy({ children: true });
            shards[index].halo.destroy();
            shards.splice(index, 1);
          }
        }
      }
      for (const memory of memoriesRef.current) {
        renderedMemoryIds.add(memory.memory_id);
        addRestingShard(memory.memory_id);
      }

      function belongsToWorld(event: DomainEvent) {
        const payload = event.payload;
        const isSessionEvent =
          event.event_type === "npc.session_terminated" ||
          event.event_type === "npc.session_restarted";
        const isMemoryEvent = event.event_type.startsWith("memory.");
        const isBehaviorEvent = event.event_type === "behavior.changed_by_memory";
        const isHandoffEvent = event.event_type.startsWith("handoff.");
        if (isSessionEvent || isMemoryEvent) {
          return (
            payload.npc_id === npcIdRef.current &&
            (isSessionEvent ||
              payload.owner_id === ownerIdRef.current ||
              payload.session_id === sessionIdRef.current)
          );
        }
        if (isHandoffEvent) {
          const agents = [payload.npc_id, payload.source_agent_id, payload.target_agent_id].filter(
            (value): value is string => typeof value === "string",
          );
          return payload.owner_id === ownerIdRef.current && agents.includes(npcIdRef.current);
        }
        return isBehaviorEvent && event.session_id === sessionIdRef.current;
      }

      function setAgentTarget(zone: ZoneId, mode: AgentMode) {
        const point = cityPoint(zone);
        agentTargetX = point.x;
        agentTargetY = point.y - 53;
        agentMode = mode;
      }

      function addCelebration() {
        const point = cityPoint("review");
        for (let index = 0; index < 12; index += 1) {
          const node = new Graphics();
          node.circle(0, 0, index % 3 === 0 ? 3 : 2).fill({ color: COLORS.success, alpha: 0.9 });
          node.x = point.x;
          node.y = point.y;
          effectLayer.addChild(node);
          celebrationParticles.push({ node, progress: 0, angle: (Math.PI * 2 * index) / 12 });
        }
      }

      function addDissolveEffect() {
        for (let index = 0; index < 10; index += 1) {
          const node = new Graphics();
          node
            .circle(0, 0, index % 2 === 0 ? 2.5 : 1.5)
            .fill({ color: COLORS.danger, alpha: 0.86 });
          node.x = agentX;
          node.y = agentY;
          effectLayer.addChild(node);
          dissolveParticles.push({
            node,
            progress: 0,
            angle: (Math.PI * 2 * index) / 10,
            originX: agentX,
            originY: agentY,
          });
        }
      }

      function markEvent(event: DomainEvent) {
        seen.add(event.event_id);
        if (event.event_type === "memory.object_materialized") {
          const memoryId = event.payload.memory_id;
          if (typeof memoryId === "string") {
            renderedMemoryIds.add(memoryId);
            addMotionShard(memoryId, "home", "vault");
            activeZone = 1;
            setAgentTarget("vault", "writing");
            message.text = "MEMORY CONFIRMED · SHARD ENTERING THE BRAIN VAULT";
          }
        } else if (event.event_type === "memory.recall_succeeded") {
          const recalled = Array.isArray(event.payload.memory_ids)
            ? event.payload.memory_ids.filter((value): value is string => typeof value === "string")
            : memoriesRef.current.slice(0, 3).map((memory) => memory.memory_id);
          for (const memoryId of recalled) addMotionShard(memoryId, "vault", "home");
          activeZone = 1;
          setAgentTarget("vault", "recalling");
          message.text = "RECALL CONFIRMED · THE VAULT IS RECONNECTING THE BODY";
        } else if (event.event_type === "memory.updated") {
          const memoryId = event.payload.memory_id;
          if (typeof memoryId === "string") {
            const resting = restingNodes.get(memoryId);
            if (resting) resting.scale.set(1.24);
          }
          activeZone = 1;
          setAgentTarget("vault", "writing");
          message.text = "MEMORY UPDATED · THE VAULT KEPT ITS PROVENANCE";
        } else if (
          event.event_type === "memory.archived" ||
          event.event_type === "memory.deleted"
        ) {
          const memoryId = event.payload.memory_id;
          if (typeof memoryId === "string") removeMemory(memoryId);
          activeZone = 1;
          setAgentTarget("vault", "writing");
          message.text =
            event.event_type === "memory.archived"
              ? "MEMORY ARCHIVED · REMOVED FROM THE ACTIVE VAULT"
              : "MEMORY FORGOTTEN · THE SHARD LEFT THE BRAIN";
        } else if (event.event_type === "npc.session_terminated") {
          activeZone = 5;
          agentLifecycle = "despawning";
          agentAlpha = 1;
          addDissolveEffect();
          setAgentTarget("gate", "offline");
          message.text = "SESSION ENDED · THE BODY IS GONE, THE BRAIN REMAINS";
        } else if (event.event_type === "npc.session_restarted") {
          activeZone = 5;
          const gate = cityPoint("gate");
          agent.x = gate.x;
          agent.y = gate.y - 53;
          agentX = gate.x;
          agentY = gate.y - 53;
          agentLifecycle = "respawning";
          agentAlpha = 0.05;
          setAgentTarget("vault", "restored");
          portalFlash.alpha = 1;
          const terminatedId =
            typeof event.payload.terminated_session_id === "string"
              ? event.payload.terminated_session_id.slice(-8)
              : "old";
          const freshId =
            typeof event.payload.fresh_session_id === "string"
              ? event.payload.fresh_session_id.slice(-8)
              : "new";
          message.text = `SESSION ${terminatedId} TERMINATED · FRESH BODY ${freshId} ENTERS`;
        } else if (
          event.event_type === "task.created" ||
          event.event_type === "task.started" ||
          event.event_type === "task.step_changed"
        ) {
          activeZone = 2;
          setAgentTarget("plaza", "acting");
          message.text =
            event.event_type === "task.created"
              ? "MISSION QUEUED · THE PLAZA HAS A NEW TASK"
              : "MISSION IN MOTION · THE WORKSHOP IS ACTIVE";
        } else if (event.event_type === "task.completed") {
          activeZone = 4;
          setAgentTarget("review", "acting");
          completionLabel.alpha = 1;
          message.text = "TASK COMPLETE · RESULT RETURNED WITH PROVENANCE";
          addCelebration();
        } else if (event.event_type === "task.blocked") {
          activeZone = 4;
          setAgentTarget("review", "offline");
          message.text = "TASK BLOCKED · MORE CONTEXT OR REVIEW IS REQUIRED";
        } else if (
          event.event_type === "handoff.created" ||
          event.event_type === "handoff.accepted" ||
          event.event_type === "handoff.started"
        ) {
          activeZone = 3;
          setAgentTarget("workshop", "acting");
          message.text = "SCOPED HANDOFF · SELECTED SHARDS CROSS TO THE WORKSHOP";
        } else if (event.event_type === "handoff.completed") {
          activeZone = 4;
          setAgentTarget("review", "acting");
          completionLabel.alpha = 1;
          message.text = "HANDOFF COMPLETE · WORKER RETURNED A PROVEN RESULT";
          addCelebration();
        } else if (event.event_type === "handoff.blocked") {
          activeZone = 4;
          setAgentTarget("review", "offline");
          message.text = "HANDOFF BLOCKED · SCOPED CONTEXT WAS NOT ENOUGH TO CONTINUE";
        } else if (event.event_type === "behavior.changed_by_memory") {
          activeZone = 4;
          setAgentTarget("review", "acting");
          completionLabel.alpha = 1;
          activityCore.alpha = 1;
          addCelebration();
          message.text = "DECISION CHANGED · MEMORY IS NOW ACTION";
        } else if (
          event.event_type === "continuity.failed" ||
          event.event_type === "memory.recall_failed"
        ) {
          activeZone = 5;
          agentLifecycle = "active";
          agentAlpha = 1;
          agentMode = "offline";
          message.text = "CONTINUITY BROKEN · ASK FOR THE MISSING CONTEXT";
        }
      }

      app.ticker.add((ticker) => {
        if (disposed) return;
        const delta = reducedMotion ? 1 : ticker.deltaTime;
        animationClock += delta * 16;
        const activeMemoryIds = new Set(memoriesRef.current.map((memory) => memory.memory_id));
        for (const memory of memoriesRef.current) {
          const memoryId = memory.memory_id;
          if (!renderedMemoryIds.has(memoryId)) {
            renderedMemoryIds.add(memoryId);
            addRestingShard(memoryId);
          }
          syncRestingCategory(memory);
        }
        for (const memoryId of [...renderedMemoryIds]) {
          if (!activeMemoryIds.has(memoryId)) removeMemory(memoryId);
        }
        for (const event of eventsRef.current) {
          if (!seen.has(event.event_id) && belongsToWorld(event)) markEvent(event);
        }

        const step = reducedMotion ? 1 : Math.min(1, delta * 0.075);
        agentX += (agentTargetX - agentX) * step;
        agentY += (agentTargetY - agentY) * step;
        const agentAtTarget = Math.abs(agentX - agentTargetX) + Math.abs(agentY - agentTargetY) < 3;
        if (agentLifecycle === "despawning" && agentAtTarget) {
          agentAlpha = Math.max(0, agentAlpha - (reducedMotion ? 1 : delta * 0.045));
          if (agentAlpha === 0) agentLifecycle = "active";
        } else if (agentLifecycle === "respawning") {
          agentAlpha = Math.min(1, agentAlpha + (reducedMotion ? 1 : delta * 0.04));
          if (agentAtTarget && agentAlpha > 0.92) agentLifecycle = "active";
        }
        redrawAgent(agentMode, agentX, agentY);
        for (let index = shards.length - 1; index >= 0; index -= 1) {
          const shard = shards[index];
          shard.progress = Math.min(1, shard.progress + (reducedMotion ? 1 : delta * 0.022));
          const eased = shard.progress * shard.progress * (3 - 2 * shard.progress);
          shard.node.x = shard.fromX + (shard.toX - shard.fromX) * eased;
          shard.node.y =
            shard.fromY + (shard.toY - shard.fromY) * eased - Math.sin(eased * Math.PI) * 24;
          shard.halo.x = shard.node.x;
          shard.halo.y = shard.node.y;
          shard.halo.rotation += reducedMotion ? 0 : 0.02 * delta;
          shard.halo.scale.set(0.8 + Math.sin(eased * Math.PI) * 0.3);
          shard.node.rotation += reducedMotion ? 0 : 0.035 * delta;
          shard.node.alpha = 0.35 + Math.sin(Math.min(1, shard.progress) * Math.PI) * 0.65;
          if (shard.progress >= 1) {
            shard.node.destroy({ children: true });
            shard.halo.destroy();
            shards.splice(index, 1);
            if (shard.toZone === "vault") addRestingShard(shard.memoryId);
            else {
              const resting = restingNodes.get(shard.memoryId);
              if (resting) resting.alpha = 1;
            }
          }
        }
        for (const resting of restingNodes.values()) {
          if (resting.scale.x > 1) {
            const nextScale = Math.max(1, resting.scale.x - delta * 0.012);
            resting.scale.set(nextScale);
          }
        }
        for (let index = celebrationParticles.length - 1; index >= 0; index -= 1) {
          const particle = celebrationParticles[index];
          particle.progress = Math.min(1, particle.progress + (reducedMotion ? 1 : delta * 0.035));
          const point = cityPoint("review");
          const distance = particle.progress * 54;
          particle.node.x = point.x + Math.cos(particle.angle) * distance;
          particle.node.y = point.y + Math.sin(particle.angle) * distance;
          particle.node.alpha = 1 - particle.progress;
          if (particle.progress >= 1) {
            particle.node.destroy();
            celebrationParticles.splice(index, 1);
          }
        }
        for (let index = dissolveParticles.length - 1; index >= 0; index -= 1) {
          const particle = dissolveParticles[index];
          particle.progress = Math.min(1, particle.progress + (reducedMotion ? 1 : delta * 0.035));
          const distance = particle.progress * 42;
          particle.node.x = particle.originX + Math.cos(particle.angle) * distance;
          particle.node.y =
            particle.originY + Math.sin(particle.angle) * distance - particle.progress * 18;
          particle.node.alpha = 1 - particle.progress;
          if (particle.progress >= 1) {
            particle.node.destroy();
            dissolveParticles.splice(index, 1);
          }
        }

        const now = performance.now();
        const pulse = reducedMotion ? 1 : 1 + Math.sin(now / 520) * 0.06;
        zoneHalos[1].scale.set(pulse);
        const plaza = cityPoint("plaza");
        const review = cityPoint("review");
        const workshop = cityPoint("workshop");
        const gate = cityPoint("gate");
        const activityActive = agentMode === "acting";
        activityPulse.clear();
        activityPulse.x = activityActive ? workshop.x : plaza.x;
        activityPulse.y = activityActive ? workshop.y : plaza.y;
        activityPulse
          .circle(0, 0, activityActive ? 42 + (reducedMotion ? 0 : Math.sin(now / 250) * 4) : 32)
          .stroke({
            color: activityActive ? COLORS.success : COLORS.violet,
            alpha: activityActive ? 0.7 : 0.16,
            width: 2,
          });
        activityCore.clear();
        activityCore.x = review.x;
        activityCore.y = review.y;
        const corePulse = activityActive ? 11 + (reducedMotion ? 0 : Math.sin(now / 180) * 2) : 7;
        activityCore.circle(0, 0, corePulse).fill({
          color: activityActive ? COLORS.success : COLORS.violet,
          alpha: activityActive ? 0.34 : 0.1,
        });
        activityCore.circle(0, 0, corePulse + 5).stroke({
          color: activityActive ? COLORS.success : COLORS.violet,
          alpha: activityActive ? 0.56 : 0.14,
          width: 1,
        });
        activityCore.alpha = activityActive ? 1 : 0.75;
        portalFlash.clear();
        portalFlash.x = gate.x;
        portalFlash.y = gate.y;
        portalFlash
          .circle(0, 0, 52 + (reducedMotion ? 0 : Math.sin(now / 130) * 7))
          .fill({ color: COLORS.blue, alpha: portalFlash.alpha * 0.16 });
        portalFlash
          .circle(0, 0, 36)
          .stroke({ color: COLORS.text, alpha: portalFlash.alpha * 0.48, width: 2 });
        portalFlash.alpha = Math.max(0, portalFlash.alpha - (reducedMotion ? 1 : delta * 0.035));
        for (const dust of ambientDust) {
          dust.node.x = dust.x * width();
          dust.node.y = dust.y + (reducedMotion ? 0 : Math.sin(now / 1600 + dust.phase) * 3);
          dust.node.alpha =
            0.08 + (reducedMotion ? 0.04 : Math.sin(now / 900 + dust.phase) * 0.05 + 0.05);
        }
        for (let index = 0; index < agentTrail.length; index += 1) {
          const trail = agentTrail[index];
          const offset = (index + 1) * 8;
          trail.x = agentX - (agentTargetX - agentX) * (index + 1) * 0.03;
          trail.y = agentY + 18 + offset;
          trail.alpha = agentMode === "offline" || reducedMotion ? 0 : 0.32 - index * 0.06;
        }
        progress.clear();
        progress.roundRect(28, 522, width() - 56, 2, 1).fill({ color: COLORS.line, alpha: 0.65 });
        progress
          .roundRect(
            28,
            522,
            Math.max(12, (width() - 56) * Math.min(1, renderedMemoryIds.size / 5)),
            2,
            1,
          )
          .fill({ color: COLORS.gold, alpha: 0.72 });
        countLabel.text = `${renderedMemoryIds.size.toString().padStart(2, "0")} SHARDS IN BRAIN VAULT`;
        countLabel.x = width() / 2;
        for (let index = 0; index < portalRings.length; index += 1) {
          const ring = portalRings[index];
          ring.clear();
          ring.x = gate.x;
          ring.y = gate.y;
          const radius = 29 + index * 10 + (reducedMotion ? 0 : (now / 20 + index * 16) % 8);
          ring.circle(0, 0, radius).stroke({
            color: COLORS.blue,
            alpha: agentMode === "offline" ? 0.16 : 0.3 - index * 0.06,
            width: 1,
          });
        }
        if (statusRef.current.includes("unavailable")) {
          agentMode = "offline";
          message.text = "CONTINUITY BROKEN · ASK FOR THE MISSING CONTEXT";
        }
        message.x = width() / 2;
        if (agentMode === "acting") {
          completionLabel.x = review.x;
          completionLabel.alpha = reducedMotion
            ? 1
            : Math.max(0.25, 1 - Math.max(0, agentX - review.x) / 260);
        } else if (celebrationParticles.length === 0) {
          completionLabel.alpha = 0;
        }
        redrawZones();
      });

      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(element);
    }

    void mount();
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      if (initialized) app.destroy(true);
    };
  }, []);

  return (
    <div className="pixi-host" ref={hostRef} aria-label="A-Brain tiny city event projection">
      {rendererState === "fallback" ? (
        <FallbackCity
          events={events}
          memories={memories}
          npcName={npcName}
          sessionId={sessionId}
          palette={palette}
          specialization={specialization}
          status={status}
          onAgentSelect={onAgentSelect}
          onMemorySelect={onMemorySelect}
          onActivitySelect={onActivitySelect}
        />
      ) : rendererState === "loading" ? (
        <p className="world-fallback">Preparing the agent city…</p>
      ) : null}
    </div>
  );
}
