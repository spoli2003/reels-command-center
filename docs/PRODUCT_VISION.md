# Product Vision

RCC is **not** an analytics dashboard.

RCC is a **Content Operating System**.

Statistics are not the product. **Decisions are the product.**

Every screen should answer:

1. What happened?
2. Why?
3. What deserves attention?
4. What should I do next?

If a screen only answers "here are some numbers," it is not finished.

## Principles that follow from this

- **Every feature must improve creator decision-making.** A chart, table, or badge that
  doesn't change what a creator does next is decoration, not product.
- **Creator experience is always more important than technical elegance.** An
  architecturally pure solution that confuses a first-time user is the wrong solution.
- **Never fabricate.** If data isn't available (not synced yet, not covered by the
  current integration, sample too small), say so honestly. A guess dressed as a number
  is worse than an empty state.
- **Explainability over cleverness.** A recommendation without a reason a creator can
  check against their own memory of the video is not trustworthy, no matter how
  sophisticated the math behind it.
- **Deterministic first, AI second.** Every number and category in RCC today is
  produced by a plain, auditable formula. AI (see [AI_ENGINE.md](./AI_ENGINE.md)) will
  eventually sit on top of this layer to *narrate* it — never to replace it or invent
  numbers of its own.

## Who RCC is for

A creator running one or more channels who wants to spend less time staring at raw
YouTube Studio numbers and more time deciding what to record next. RCC assumes the
creator is not a data analyst — every number on screen carries its own explanation.
