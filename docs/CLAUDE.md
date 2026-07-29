# Instructions for AI-assisted development on this repository

This file is the standing instruction manual for any AI coding assistant working on
RCC. It is not a suggestion — treat it as a checklist before, during, and after every
change.

## Mindset

- **Think like a Product Designer.** Before touching code, ask what a creator would
  see, feel, and do differently after the change.
- **Think like a Creator**, not like a software engineer. A creator does not care
  about elegant abstractions; they care whether the screen tells them what to record
  next.
- **Never optimize for developers first.** If a technically clean solution produces a
  confusing screen, the solution is wrong.

## Data integrity

- **Never fabricate data.** No placeholder numbers, no fake zeros for unavailable
  metrics, no invented trends. If data isn't available, say so and explain why
  (see [UI_GUIDELINES.md](./UI_GUIDELINES.md) for exact wording patterns).
- **Every metric needs an explanation.** A number without a tooltip or caption
  explaining how it was calculated is incomplete work.
- **Never create charts without a purpose.** Before adding a chart, name the creator
  question it answers. If you can't name one, it should be a stat, a ranking, or
  nothing.

## AI layer (once built)

- **AI explains deterministic facts. It does not invent them.** Every AI-generated
  sentence must trace back to a number already computed by the deterministic
  analytics/intelligence layer. See [AI_ENGINE.md](./AI_ENGINE.md).

## Process

- **Always test before finishing.** Run the backend test suite
  (`docker compose run --rm backend pytest`) after any backend change.
- **Always run the production build.** The frontend Dockerfile has no volume mount —
  `docker compose build frontend` before `npm run build`, every time, or you are
  testing stale code.
- **Always polish before stopping.** A feature that works but reads awkwardly, has
  inconsistent spacing, or leaves an empty state unexplained is not done.
- **Verify against real data**, not just passing tests. Tests catch regressions; they
  don't catch a screen that's technically correct but useless.

## Architecture

- **Prefer reusable architecture.** Before writing a new component or function, check
  whether an existing one (`lib/youtube-metrics.ts`, `components/ranked-video-list.tsx`,
  `services/intelligence/`, etc.) already does most of the job.
- Keep the Creator Intelligence engine platform-agnostic — no YouTube-specific code
  inside `backend/app/services/intelligence/`. Platform-specific logic belongs in an
  adapter (see [ARCHITECTURE.md](./ARCHITECTURE.md)).
- Prefer extending an existing endpoint/schema over adding a new one, unless the new
  capability is genuinely a different resource.

## When in doubt

**Prefer creator decisions over statistics.** When there is a choice between showing
more data and showing a clearer conclusion, show the conclusion — with the data one
click away, never hidden.

---

**When there is a choice between writing clever code and building a better product,
always build the better product.**
