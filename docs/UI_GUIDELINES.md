# UI Guidelines

## Design inspiration

RCC should feel closer to **Linear, Vercel, Notion, Stripe Dashboard, and PostHog**
than to a generic admin template. Those products share: restrained color use, dense
but uncluttered information, dark-mode-native design, and a bias toward showing a
conclusion before the raw numbers behind it.

## Avoid

- **Admin-template look** — generic sidebar + card grid with no point of view on what
  matters most on the page.
- **Meaningless charts** — a chart is only justified if it answers a specific creator
  question better than a number, ranking, or sentence would. (RCC removed a
  views-vs-likes scatter plot and a raw upload-frequency bar chart in Sprint 4.1 for
  exactly this reason — neither one changed what a creator would do next.)
- **Empty screens** — if a page can show real data, it must. If it can't yet
  (unfinished integration, insufficient history), it must say so honestly rather than
  render blank stat cards showing zero.
- **Duplicated information** — the same list of videos should not appear twice on one
  page in different visual clothing. (The YouTube panel's video grid was removed from
  the Home page in Sprint 4.1 once "latest uploads" covered the same ground.)

## Prefer

- **Cards** over dense grid tables for anything the user should scan quickly (best
  video, biggest opportunity, platform overview).
- **Summaries** over raw tables where a single sentence + number tells the story.
- **Insights** — a sentence with the actual number behind it
  ("Engagement jest 28% poniżej mediany kanału"), never a bare label.
- **Rankings** over bar charts when the question is "which one wins" rather than
  "what's the shape of the distribution."
- **Actionable recommendations** — every recommendation names a specific video and
  states the metric that justifies it (see `Recommendation` in
  [ARCHITECTURE.md](./ARCHITECTURE.md) and [AI_ENGINE.md](./AI_ENGINE.md)).

## Concrete rules already in force

- **Every calculated metric has a tooltip** (native `title` attribute, via
  `StatCard`'s `tooltip` prop) stating the exact formula, in addition to a short
  visible hint.
- **Every displayed video is clickable** — thumbnail and title open its internal
  detail page; a separate small external-link icon opens YouTube in a new tab. Never
  nested inside the same anchor (see `components/external-link.tsx`).
- **Status/labels never rely on color alone** — every badge (confidence, performance
  label, trend) pairs an icon or text with its color.
- **Empty states explain what to do next**, not just that data is missing — e.g.
  *"Za mało filmów w wybranym zakresie (min. 3), aby obliczyć wiarygodny ranking"*
  rather than a bare "No data."
- **Unavailable metrics are labeled, not hidden or faked** — see the "not currently
  available" card pattern on the video detail page.
- **Every ranking score is auditable in place** — show the exact weights,
  normalized inputs, points added and points not earned; link to the full
  methodology rather than asking the creator to trust an unexplained number.
- **Dark theme only**, RCC's existing palette (`#070a11` background, `#5cf0ac` accent)
  — do not introduce a second visual language.
- **Every platform uses the same information architecture** — Dashboard,
  Materiały, Porównanie, Co dalej?, Komentarze. A tab may disappear only when a
  provider objectively cannot supply or support that capability.
- **Synchronization is operational UI, not analytics** — connection controls,
  schedules, errors and run history live on `/synchronization`; platform
  dashboards only show the compact shared status strip and a link to that center.
