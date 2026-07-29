# AI Engine (design for a not-yet-built layer)

**No AI is implemented in RCC today.** Every score, trend, category, and
recommendation currently in the product is produced by plain deterministic code in
`backend/app/services/intelligence/` and `frontend/lib/youtube-metrics.ts`. This
document describes how a future AI layer should plug into that work — it is a design
target, not a shipped feature.

## The one rule that governs everything below

> **AI never invents. AI explains.**
> Deterministic analytics are the source of truth.

Concretely: an AI layer consumes the structured `Recommendation` / metadata objects
already produced by the intelligence engine and turns them into better-phrased
narration. It never computes a number itself, never claims a trend the deterministic
layer didn't already detect, and never asserts causation the confidence-gating system
wouldn't itself support.

## Planned AI capabilities

| Capability | Deterministic layer it narrates | Status |
|---|---|---|
| **Topic Intelligence** | `intelligence/topics.py` keyword-stem clustering + per-topic medians | Deterministic layer built (Sprint 4); AI narration not built |
| **Hook Intelligence** | Would require transcript/opening-seconds data RCC does not currently import | Not started — data prerequisite missing |
| **Title Intelligence** | `intelligence/title_patterns.py` rule-based pattern detection | Deterministic layer built (Sprint 4/5); AI narration not built |
| **Publishing Advisor** | `intelligence/engine.py::publishing_intelligence` (best weekday/hour/cadence, streaks) | Deterministic layer built; AI narration not built |
| **Follow-up Suggestions** | `intelligence/engine.py::follow_up_opportunities` | Deterministic layer built; AI narration not built |
| **Content Recommendations** | `intelligence/engine.py::content_recommendations` (topic-vs-median, keyword-in-top-10, topic velocity) | Deterministic layer built; AI narration not built |

## Integration point (when built)

The `Recommendation` dataclass (`intelligence/types.py`) already carries exactly what
an AI narrator needs and nothing it should be allowed to add to:

```python
@dataclass
class Recommendation:
    id: str
    category: str
    headline: str
    explanation: str
    confidence: Confidence          # high | medium | low
    supporting_metrics: dict        # the raw numbers behind the claim
    supporting_video_ids: list[str]
```

A future AI endpoint (e.g. `POST /intelligence/narrate`) would take a list of these as
input and return improved prose — constrained to only rephrase the provided
`explanation`/`supporting_metrics`, never to generate new figures. This keeps the
deterministic engine as the single source of truth: if the AI service is down,
degraded, or removed entirely, RCC still functions exactly as it does today, just with
plainer sentences.

## Non-negotiable constraints for any future AI work

- Never phrase a recommendation as certain causation ("this always performs better").
  Use hedged, evidence-citing language ("based on your historical data...").
- Never surface a recommendation whose deterministic confidence is below the
  `compute_confidence()` gate (see `content_metrics.py`) — AI polish does not override
  a "not enough data" result.
- Never let the AI layer read raw database rows directly. It consumes the already-computed,
  already-audited output of the intelligence engine only.
