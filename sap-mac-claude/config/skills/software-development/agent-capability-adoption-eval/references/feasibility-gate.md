# Output-Surface Feasibility Gate

Run this BEFORE scoring behavioural probes. For a capability that emits rich
artifacts, probe scores are meaningless if the host surface cannot render them.
Resolve the BLOCKER items first; an unresolved blocker caps the recommendation at
ADAPT (text subset) or DISCARD no matter how good the probes look.

## The deciding question (BLOCKER)

Can the host's response channel render the capability's artifacts?

- What is the surface — a web UI that renders HTML, a chat widget (markdown only),
  an API returning JSON/text, or a **closed typed-component contract** (fixed JSON
  frame types validated against a schema — e.g. Markdown/BarChart/LineChart/ChatTable)?
  A mix of a buffered and a streaming endpoint counts as two surfaces; test the one
  users actually see.
- Does the streaming path preserve HTML/SVG, or does token streaming break mid-tag?
  Inline SVG streamed token-by-token can render as broken markup even on an
  HTML-capable client, making the chart half infeasible in practice.
- Is there a sanitizer or CSP that strips `<svg>`, `<style>`, inline CSS, or
  `<script>`? A strict policy silently drops exactly the elements rich capabilities
  depend on, so a chart/table probe can "pass" while the user sees nothing.

## If the surface is a closed typed-component contract (the common production case)

Most shipped agent UIs are neither free-form HTML nor plain markdown: they accept a
fixed set of component frames validated against a schema. Here the adopt/adapt line
is drawn per-rule by what maps onto that contract, not by the capability's quality:

- Inspect the host's actual response schema AND the chart/table validator (the code
  that accepts or rejects a chart payload) before judging. Guessing the surface is
  how a confidently-wrong feasibility brief gets written.
- Rules that map to an EXISTING component field are implementable now with no code
  change (often just capability-text / prompt steering) — e.g. a `unit` field that
  already applies scale/decimal formatting, `yKeys` for multi-series data, a `totals`
  footer. These are closer to free than a capability written for HTML assumes.
- Raw SVG/HTML/CSS the capability emits does NOT render — it falls through as inert
  text inside a text/Markdown frame. Mark those rules unfeasible-now, needing a NEW
  component + renderer, not merely a prompt tweak.
- When estimating the renderer gap, account for a frontend the host team may NOT own
  (a separate widget repo/team). That cross-team coordination is usually the dominant
  cost and risk, dwarfing the backend schema change — state it explicitly, and split
  every estimate into backend-contract vs UI-renderer effort.
- `<script>` execution and arbitrary-SVG passthrough open an XSS/exfil surface that
  typically contradicts the host's own untrusted-data rules — treat those as discard,
  not an effort line item, unless security sign-off is in scope.

## If the surface is text/markdown-only (the ADAPT branch)

- Identify which rules survive as plain text (number formatting, terminology,
  markdown-table structure) versus which are lost (true charts, colour, hatch/outline
  fills, HTML dashboard layout).
- The honest verdict is DISCARD even on this branch if the surviving text subset does
  not beat the host's current formatting — the number/terminology probes answer this
  empirically.

## Integration-cost checks (not blockers, but shape adopt-vs-adapt)

- **Loading model & context tax.** A verbose capability loaded on every matching
  query is a persistent per-turn token cost. Measure the prompt-token delta ON vs
  OFF; prefer on-demand reference loading over flattening the whole ruleset into the
  prompt when the capability is written to be read step-by-step.
- **Latency at peak.** Quantify added latency; a large ruleset may be unacceptable on
  a tool used heavily at month/quarter-end close even if its output is better.
- **Precedence conflict.** If the capability says it must override the host's existing
  formatting behaviour, confirm it actually wins on matching queries and does not
  fight the host — a tie produces inconsistent output, worse than either alone.
- **Output-length truncation.** A capability that emits long inline SVG/HTML can hit
  the model's max-output-token cap and emit broken markup; test with the largest
  artifact (full table + chart in one turn).

## Correctness-neutrality check (BLOCKER)

Run the host's existing correctness scorer OFF/ON. A pure-presentation capability
must be correctness-neutral; a drop ON means it is corrupting data presentation
(e.g. a cost-sign convention flipping polarity) — a hard blocker for adoption.

## Decision gates (answer in order; stop at first unmet blocker)

1. Output surface renders the artifacts? If no → ADAPT branch only; mark artifact
   probes not-applicable up front, and split the surviving rules into
   implementable-now (maps to an existing component field) vs. needs-new-renderer.
2. Context/latency tax acceptable at peak volume? If no → defer or discard.
3. Correctness neutral ON? If regression → blocker, do not adopt.

Only when 1–3 pass does the probe-score aggregate decide ADOPT vs ADAPT vs DISCARD.
If 1 fails but 2–3 pass, the ceiling is ADAPT regardless of probe scores.

The classifier API key is NOT a gate — it is an evaluation-process dependency. A
missing key never caps or blocks the verdict; it only switches probe scoring from
the cheap classifier to manual SME grading. Confirm it before the run so you know
which scoring path you're on, but keep it out of the gate sequence.
