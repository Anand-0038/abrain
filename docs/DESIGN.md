# A-Brain World design brief

## Product and audience

A-Brain is persistent-context infrastructure for people who want an agent to remain useful
across sessions. The primary screen is for a first-time owner exploring their own NPC's brain,
not for an operations administrator.

## Primary screen job

Make one invisible fact spatially obvious: a temporary agent body can move, work, disappear, and
return while its Sibyl-backed brain remains available. The world should make the user want to
talk, remember, restart, and inspect the resulting causal chain.

## Visual direction

- Emotional tone: curious, calm, quietly alive.
- Three adjectives: inhabited, legible, tactile.
- Three anti-adjectives: dashboard-like, noisy, toy-like.
- Subject-world materials: dark road asphalt, cool block paving, small civic buildings, warm lamps,
  memory shards, and luminous event paths.
- Interaction metaphor: the agent is a resident moving through a tiny continuity district; the
  Memory Vault is infrastructure, not a decorative brain icon.
- Typography: the surrounding app uses editorial sans text; the Pixi city uses compact mono labels
  for signs and evidence. Labels are short enough to remain readable at narrow widths.

## City composition

The reusable map is a compact two-column, three-row neighborhood:

```text
HOME / SPAWN       MEMORY VAULT

MISSION PLAZA      WORKSHOP

REVIEW TOWER       SESSION GATE
```

Streets, a central arterial, block footprints, sparse trees, lamps, and civic markers give the
spaces a sense of place. Buildings are original procedural Pixi geometry, not copied illustrations
or story-specific locations. The map is deliberately small so the user can understand the entire
system in one viewport.

## Signature interaction

When a confirmed memory event arrives, a real memory ID becomes a shard that travels to the Vault.
When a fresh-session recall arrives, the returned IDs travel back toward the new body. Session death
uses the Gate; tasks and scoped handoffs move through the Plaza, Workshop, and Review Tower. The
renderer never announces a success before the backend event exists.

## Color and motion

The world uses the existing A-Brain semantic palette: ink/night ground, teal for the body and
continuity, gold for durable memory, violet for work, green for completed review, and blue for the
session gate. Motion is short and interruptible: compact agent travel, shard arcs, portal rings,
halo pulses, sparse dust, and a brief review burst. `prefers-reduced-motion` removes travel and
ambient movement while preserving position, labels, and state changes.

## Asset and licensing boundary

No external art family is bundled for this pass. Roads, blocks, buildings, trees, lamps, signs,
agent, shards, and effects are original PixiJS primitive geometry in
`frontend/src/components/pixi-world.tsx`. PixiJS itself is recorded as an MIT dependency in
`THIRD_PARTY_NOTICES.md`. Dribbble and other visual references remain inspiration only; no layout,
illustration, sprite, audio, or copied code was imported.

### NPC identity language

NPC identity is persistent data, not a hard-coded character. The owner chooses a palette, body
silhouette, and optional accessory during onboarding. Node, Scout, and Orbiter bodies share one
state language: the name and role stay stable across sessions, while `REMEMBERING`, `RECALLING`,
`WORKING`, `BLOCKED`, `DISSOLVING`, and `FRESH BODY` make the ephemeral runtime legible. The
Session Gate fades the old body and respawns the same brain with a new session through the
existing event stream.

## Rejected patterns

- A horizontal four-stop pipeline: it made a real event projection look like a dashboard diagram.
- A generic AI-town or story-specific building set: it would compete with the memory mechanism and
  make the product less reusable.
- A large asset pack, physics, or decorative city simulation: it would increase payload and polish
  work without strengthening the Sibyl continuity proof.
- Random glow or fake status animation: every meaningful movement must correspond to a confirmed
  backend event.
