# Third-party notices

A-Brain is released under the MIT License in `LICENSE`. The following direct dependencies are
used by the local application. Frontend versions are pinned in the package manifest/lockfile;
backend versions below are the verified local environment versions within the ranges declared in
`backend/pyproject.toml`.

## Runtime dependencies

| Package             | Version | License      | Source                                        |
| ------------------- | ------- | ------------ | --------------------------------------------- |
| Next.js             | 15.4.6  | MIT          | https://github.com/vercel/next.js             |
| React               | 19.1.1  | MIT          | https://github.com/facebook/react             |
| React DOM           | 19.1.1  | MIT          | https://github.com/facebook/react             |
| PixiJS              | 8.9.2   | MIT          | https://github.com/pixijs/pixijs              |
| FastAPI             | 0.141.1 | MIT          | https://github.com/fastapi/fastapi            |
| Uvicorn             | 0.52.4  | BSD-3-Clause | https://github.com/Kludex/uvicorn             |
| Pydantic            | 2.13.4  | MIT          | https://github.com/pydantic/pydantic          |
| Pydantic Settings   | 2.15.0  | MIT          | https://github.com/pydantic/pydantic-settings |
| HTTPX               | 0.28.1  | BSD-3-Clause | https://github.com/encode/httpx               |
| Sibyl Memory client | 0.7.0   | MIT          | https://github.com/Sibyl-Labs/Sibyl-Memory    |

## Development dependencies

| Package    | Version | License    | Source                                  |
| ---------- | ------- | ---------- | --------------------------------------- |
| TypeScript | 5.8.3   | Apache-2.0 | https://github.com/microsoft/TypeScript |
| ESLint     | 9.29.0  | MIT        | https://github.com/eslint/eslint        |
| Prettier   | 3.6.2   | MIT        | https://github.com/prettier/prettier    |
| Vitest     | 3.2.4   | MIT        | https://github.com/vitest-dev/vitest    |
| pytest     | 8.4.2   | MIT        | https://github.com/pytest-dev/pytest    |
| mypy       | 1.20.2  | MIT        | https://github.com/python/mypy          |
| Ruff       | 0.16.4  | MIT        | https://github.com/astral-sh/ruff       |

## Original world art and asset manifest

The application does not bundle third-party image, audio, sprite, tileset, or copied game assets.
The A-Brain World tiny-city map uses original procedural PixiJS primitives authored in
`frontend/src/components/pixi-world.tsx`: roads, blocks, reusable buildings, trees, lamps,
sign-like labels, agents, memory shards, and event effects. No Kenney or other external art pack is
claimed or required. PixiJS remains the MIT-licensed rendering dependency listed above.

Transitive dependencies remain governed by their package licenses in the generated lockfiles and
installed distribution metadata.
