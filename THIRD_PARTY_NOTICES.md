# Third-party notices

A-Brain is released under the MIT License in `LICENSE`. Package versions and transitive licenses
remain recorded by the checked-in manifests and lockfiles.

## Runtime foundations

- Next.js, React, and React DOM — MIT.
- PixiJS — MIT.
- FastAPI, Pydantic, and Pydantic Settings — MIT.
- Uvicorn and HTTPX — BSD-3-Clause.
- Sibyl Memory client — MIT.

## Visual assets

### Kenney Tiny Town 1.1

- Creator: Kenney (`https://kenney.nl`)
- Source: `https://kenney.nl/assets/tiny-town`
- License: Creative Commons Zero 1.0 (CC0)
- Files included: a curated subset of 24 original 16-by-16 PNG tiles under
  `frontend/public/assets/kenney-tiny-town/`; 22 are currently referenced by the fallback city
  artwork, while `tile_0001.png` and `tile_0088.png` remain unused candidates
- Modifications: presentation-only scaling, filtering, layering, and animation in A-Brain's CSS;
  the source PNG files are unmodified
- Retrieved: 2026-09-01

The upstream license text is preserved beside the assets as
`frontend/public/assets/kenney-tiny-town/LICENSE.txt`. Attribution is not required by CC0, but is
included here for clarity and gratitude.

## Original A-Brain work

The continuity city composition, Brain Vault, memory shards, NPC state choreography, event-driven
movement, session portal, causal replay, and fallback renderer are A-Brain implementation work.
The Kenney tiles provide a coherent environmental vocabulary; they do not implement application
state or memory behavior.
