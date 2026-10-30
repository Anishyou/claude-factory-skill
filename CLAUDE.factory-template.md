
<!-- Software factory: the sections every agent reads. `/factory init` fills
     the TODOs from your stack interview; keep your own text where it exists. -->

## Overview
TODO: what this project is, in a paragraph. Name the requirements source
(for example `docs/build-brief.md`, with stable IDs like `FR-AUTH-01`) and the
stack (see `docs/stack.md`).

## Setup (fresh checkout)
The commands that turn a clean clone into a working checkout. The factory runs
these in every new worktree.

```bash
TODO: e.g. pnpm install / uv sync / go mod download
```

## Dev server
TODO: how to start each service, on which port, and which environment
variables it reads. Agents start the app on `portBase` + an offset from
`factory/factory.config.json`, so make the port configurable.

## Validation
Must pass before work is done. Keep this list identical to `validation` in
`factory/factory.config.json`: the gate hook runs that list, the agents read
this one.

```bash
TODO: lint
TODO: typecheck
TODO: test
TODO: build
```

## Tests
TODO: runner, where tests live (must match `testPaths` in
`factory/factory.config.json`), and how to run one file. Group tests in
`describe("<REQUIREMENT-ID> …")` blocks so coverage can be traced.

## Conventions
TODO: code style, error handling, naming, how decisions are recorded
(the builder writes an ADR in `docs/decisions/` for each non-obvious choice).

## Important paths
TODO: one line per package or app and what lives there.

## Do not touch
- The requirements source: propose changes in the PR description instead.
- Anything in `protectedPaths` in `factory/factory.config.json`.

## Software factory
This repo uses a Claude Code software factory. `/factory plan` turns the brief
into `factory/roadmap.md` and the backlog; `/factory next` runs a job through
spec → tests → build → review → approve → PR; `/factory verify` checks a
finished milestone against the brief and writes `factory/coverage.md`.
Standing decisions for the agents live in `docs/policies.md`. Job state in
`factory/jobs/` is local runtime state and is gitignored.
