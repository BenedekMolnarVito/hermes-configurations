---
name: agent-capability-adoption-eval
description: "Use when evaluating a skill for adopt/adapt/discard."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [evaluation, ab-testing, typesafe, jev, adopt-adapt-discard, agent-skills]
    related_skills: [typesafe-ai, llm-evaluation-maintenance]
---

# Agent Capability Adoption Evaluation

Decide whether to **adopt / adapt / discard** an external agent skill or capability
(e.g. a Joule Work Desktop skill) in a host agent, backed by controlled A/B probes
scored cheaply by a classifier. The deliverable is a documented recommendation with
per-probe evidence, not an opinion.

## Procedure

1. **Read the capability from its authoritative source, never guess.** For a skill,
   read its actual SKILL.md + reference files. If it is only reachable via an
   internal hub, fetch the real content before describing behaviour — inventing how
   an unknown skill works produces a confidently wrong brief. Separate what the
   capability DOES (retrieve data? render output? both?) from what it only restyles.

2. **Classify the capability as retrieval vs presentation.** A rendering/formatting
   capability does not fetch data — it restyles whatever the host already produced.
   This boundary decides everything downstream: hold retrieved data constant and you
   are grading presentation, not correctness.

3. **Run the output-surface feasibility gate BEFORE scoring probes** — see
   `references/feasibility-gate.md`. For a capability that emits rich artifacts
   (inline SVG/HTML/CSS, charts), its headline value is capped by whether the host
   surface can render those artifacts without sanitizer/CSP stripping, without
   streaming breaking mid-tag, and within the output-token budget. This gate decides
   adopt-vs-adapt regardless of how well the probes score: if the surface is
   text/markdown-only, the ceiling is ADAPT (keep the text-expressible subset).
   The surface is not a binary HTML-vs-text question — a production agent UI is
   often a **closed typed-component contract** (fixed JSON frame types validated
   against a schema, e.g. Markdown/BarChart/ChatTable). On such a surface, raw
   SVG/HTML the capability emits falls through as inert text in a Markdown frame,
   NOT a rendered artifact; the real split is per-rule — expressible as existing
   component-field data now vs. needs a new component + renderer. Inspect the host's
   actual response schema and chart/table validator to draw that line, never assume.

4. **Design one-rule-per-probe prompts.** Each probe isolates a single rule of the
   capability so an OFF/ON diff is attributable to that rule. Build prompts from the
   team's real sample questions so retrieved data is realistic. Include a deliberate
   **false-positive control probe** — a case where the naive implementation
   over-applies the rule (e.g. colouring a growth rate that must stay neutral); a
   capability that passes the rule probe AND keeps the control correct is applying
   the rule intelligently, not cosmetically, and that is the strongest adopt signal.

5. **Run each probe OFF then ON, holding retrieved data constant.** New session per
   variant. If the two runs disagree on the underlying numbers rather than
   formatting, the comparison is contaminated — re-run or pin the same dataset.

6. **Score every run with a classifier using fixed buckets** — see
   `references/typesafe-choice-rubrics.md` for the TypeSafe `Choice` contract. Each
   probe is one `Choice` call per run over a predetermined best→worst bucket set that
   INCLUDES a no-match outcome. Map buckets to an ordinal score and take
   `delta = score(ON) - score(OFF)` as the per-probe verdict. A regression on any
   probe, or the control probe failing ON, is a blocking finding.

7. **Gate low confidence to a human.** Route any run whose classifier confidence is
   below threshold to an SME reviewer rather than silently accepting the bucket —
   classifier confidence measures distribution concentration, not correctness, and
   this escalation is what satisfies a "SME review with and without" acceptance
   criterion.

8. **Aggregate into adopt/adapt/discard** against the feasibility gate result, not
   probe scores alone. Adopt only when the surface can host the artifacts AND the
   high-value probes improve with zero regressions; otherwise the ceiling is adapt
   (text subset) or discard (subset adds nothing over current behaviour).

9. **On an ADAPT verdict, write the low-hanging-fruit plan by mapping each
   text-expressible rule to the exact host prompt/skill line it changes.** The plan
   is not "adopt the text subset" in the abstract — rank the rules by value/effort and
   point each at the concrete file+line in the host that must change, so a future
   session edits on the first try. The single highest-value LHF is almost always a
   DIRECT CONFLICT: a rule where the host's own always-on style instruction already
   says the OPPOSITE of the capability's rule (e.g. host mandates `M EUR` / `M/B/T/Q`
   suffix display while the capability mandates symbol-first `€m` + comma thousands
   separators). Grep the host prompt/skill for the formatting instruction each probe
   tests BEFORE writing the plan; a conflict found there outranks any additive rule,
   because it is a visible every-answer win and resolving it is one text-block edit.
   When the host spreads the same style across several analyst skills, apply the
   identical replacement block to all of them in one pass for consistency.
   Cross-check the LHF list against any explicit user/reporter feedback on the
   originating ticket — the feedback item is a pre-validated LHF, promote it to #1.

## Pitfalls

- Do not conflate presentation with correctness. Run the host's existing correctness
  scorer OFF/ON too; a formatting capability must be correctness-neutral, and a
  correctness drop ON (e.g. a sign-convention restyle flipping polarity) is a blocker.
- Do not let the probe scores decide adopt-vs-adapt when the output surface can't
  render the artifacts — a chart probe that "passes" on a surface that strips SVG is
  a false pass; mark such probes as not-applicable up front.
- Account for the per-turn context/latency tax of loading a verbose capability on
  every matching query; a large always-injected ruleset can be unacceptable on a
  latency-sensitive tool at peak load even if its output is better.
- Capabilities with hard-pinned temporal constants (current year, rotating hierarchy
  codes) carry a standing yearly-maintenance obligation — record who owns the bump.
- An ADAPT plan edits the HOST's prompt/skill files, so it inherits the host's
  change discipline: bump the per-file prompt-version semver on every file touched
  (patch=typo, minor=behavior-preserving addition, major=rewrite) and note that
  prompt/skill edits load only on app restart/redeploy. A plan that changes wording
  without a version bump ships silently and breaks trace-to-prompt correlation.
- Keep the chart/table/layout rules OUT of the ADAPT plan explicitly, not by
  omission: list them under an "out of scope" heading tied to the surface gate, so a
  future reader sees the chart probes score NA (not REGRESSION) BY CONSTRUCTION and
  does not mistake the gap for unfinished work.
- Confirm the classifier API key is present before the run; the classifier fails
  closed without it, and the fallback is manual SME scoring, not a silent skip. This
  is an EVALUATION-process dependency, not an adoption gate — a missing classifier
  key never caps or blocks the adopt/adapt/discard verdict; it only changes who
  scores the probes. Keep it out of the technical gate list.
