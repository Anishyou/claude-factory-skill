# Factory policies

Standing decisions for the software factory. The spec-writer and planner read
this before writing; the approver reads it before escalating. A question
answered here is decided: agents apply it and cite the section, they do not
ask again. Anything not covered still goes to a human via ESCALATE.

Change a policy by editing this file in a normal PR; the change applies to
jobs started after the merge.

**How to grow this file:** every time the approver escalates, ask whether you
would give the same answer next time. If yes, write it down here. On the
project this factory was first used on, five of the first eleven jobs
escalated; after their answers went into this file, the next eight escalated
none.

## 1. Dependencies

- **Approved runtime dependencies** (no escalation needed, any version in the
  same major): TODO, e.g. your web framework, validation library, ORM, logger.
- **Approved dev dependencies**: TODO, e.g. test runner, type checker, linter.
- **Any other new dependency is allowed when all of these hold**, and the
  spec says which: permissive licence (MIT, Apache-2.0, BSD, ISC); release in
  the last 12 months; no native binary; fewer than 20 transitive packages;
  recorded in the job's ADR with the alternative that was rejected.
- **Always escalate**: a dependency that phones home, or one that replaces a
  package listed above.
- Lockfile changes that come only from an allowed dependency are expected;
  the planner adds `(allow: <lockfile>)` to such jobs up front.

## 2. Security defaults

- TODO: rate limits, session lifetime, password rules, CORS, headers.
  Write the numbers down once so jobs stop re-opening them.

## 3. Data access

- TODO: how data is scoped (per user, per tenant), which layer enforces it,
  and which changes count as an access decision a human must see.

## 4. Migrations and protected paths

- Migrations are protected; the planner marks jobs that need one with
  `(allow: <migrations path>)` so the human unlocks it when the job starts,
  not after it blocks. A migration must be forward-only.

## 5. What always goes to a human

Regardless of reviews: payments and billing; anything that messages real
people (email, SMS, push); deleting user data; legal and compliance text;
public copy about pricing; CI, hosting and deploy configuration.

## 6. Defaults the spec-writer may assume

- Mock external providers in every test; live provider tests are opt-in
  behind an environment flag and never run in the gate.
- The simplest option that meets the requirements, recorded as an ADR.
