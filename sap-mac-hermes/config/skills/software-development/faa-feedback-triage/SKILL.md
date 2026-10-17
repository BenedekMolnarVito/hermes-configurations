---
name: faa-feedback-triage
description: "Use when triaging FAA user feedback into a fix plan."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [faa, feedback, triage, planning, mlflow, evaluation]
    related_skills: [llm-evaluation-maintenance, plan, faa-devcontainer-execution]
---

# FAA User-Feedback Triage

## When to Use

Use when the user hands you an FAA feedback export (a `feedback_review_*.xlsx` under
`docs/feedback/`, or the output of `feedback_review.py`) and asks to review it, plan
fixes, filter test feedback, or turn complaints into a backlog. Also use when the
feedback has already been bucketed into JIRA tickets and the user asks for a
solution plan for specific ticket IDs — see "Planning from JIRA tickets" below.

Turn the Financial Analyst Agent (FAA) user-feedback export into a prioritized,
actionable improvement plan. The recurring loop is export -> review -> plan, driven
by `tests/evaluation/feedback_review.py` (export/import subcommands) with the review
surface in `docs/feedback/feedback_review_*.xlsx`.

## What the Excel does and does NOT contain (read this first)

The sheet is one row per session. Columns: `status` (open/addressed/wontfix),
`avg_rating`, `n_feedback`, `first_query`, `comments` (each turn's comment joined by
` | `), `expected_answers`, `last_seen`, `session_link` (Databricks deep-link),
`session_id`.

- The Excel carries the user COMMENT and the FIRST QUERY only. It does NOT carry the
  agent's actual answer, its tool calls, the filters/measures/nodes used, or the
  trace spans. So any "wrong number / 0 / don't trust the data" complaint is NOT
  diagnosable from the Excel alone — you must open `session_link` and read the trace
  in Databricks (recipe in CLAUDE.md -> "Fetching MLflow Traces from Databricks").
- The committed ledger (`feedback_status.json`) stores only `session_id + avg_rating
  + status` — no content. All Excel content is re-fetched from MLflow at export time
  and the Excel is gitignored. Commit the ledger, never the Excel.

## Procedure

1. Read the whole sheet with `read_file` on the .xlsx (it auto-extracts to text; both
   the "Feedback Review" and "How to use" sheets come through). Note the status of
   each row — `addressed`/`wontfix` rows are already handled.

2. Filter out test/noise feedback (a standing user ask). Mark them `wontfix`.
   Test signals: comment is literally "test"/"Test, for feedback"/"Test feedback on
   prod", trivial greetings ("hi"/"hi"), or expected-answer joke text ("time for
   vacation"). See the trap below before removing anything.

3. Classify the remaining real sessions into THEMES, not per-row tickets. Aggregate
   sessions that share a root cause (formatting consistency, hierarchy completeness,
   wrong-number, latency/rambling, SAC-link, missing capability, etc.).

4. For each theme decide the FIX TYPE and whether the Excel is enough to act:
   - PROMPT/SKILL adherence — a rule ALREADY EXISTS in the prompt/skill and the model
     just isn't following it. Reinforce/clarify; do not add a contradictory new rule.
   - PROMPT/SKILL new-rule — genuinely new guidance. Add it.
   - CODE/PLATFORM — a real capability gap or bug in the app.
   - NEEDS-TRACE — cannot be diagnosed from the Excel; must open the Databricks trace.
   Before treating any complaint as new work, check the session's `prompt_version` /
   `prompt_commit` trace tags against the CURRENT prompt/skill version — the complaint
   may already be fixed by a later prompt revision.

5. Write the plan with the `plan` skill (deliverable under `.hermes/plans/`). Include
   a section that explicitly lists what the Excel does NOT give enough info to fix, so
   the next session knows what to gather before touching code. Priority order: P0
   housekeeping (mark test rows, harvest positives) -> P1 prompt/skill edits -> P2
   trace triage -> P3 code/platform.

6. Persist status edits: after marking rows in the Excel, run
   `uv run python tests/evaluation/feedback_review.py import` to write them into the
   ledger, then commit the ledger only.

## Planning from JIRA tickets (feedback already bucketed)

A later stage: the feedback themes have been written up as JIRA bugs and the user
names ticket IDs (bare numbers → CFAAI project, e.g. `1020` → `CFAAI-1020`). Fetch
them in one call via the sap-jira MCP `jira_search` with
`key in (CFAAI-1020, CFAAI-1021, ...)`, `fields=summary,status,issuetype,description,priority`
(see the `jira` skill for auth). FAA feedback tickets carry a structured body:
*Issue*, *User Feedback*, *Root Cause* (with `file:line` references), *Files to
Investigate*, *Proposed Solution*, *Evidence* (Sessions + Traces), *Done When*.

Ground the plan — do NOT take the ticket at face value:
- VERIFY every `file:line` the ticket cites by reading that exact range in the repo
  (`search_files` for the symbol, then `read_file` the block). Tickets drift from
  code; a plan built on a stale line reference misleads the implementer.
- Cross-map each ticket's Evidence "Sessions" (short `session_id` prefixes) back to
  rows in the feedback Excel so the plan is anchored in the feedback basis, not the
  ticket's prose. The Excel is still the source of truth for what the user actually
  said.
- Confirm claims of "no code map exists" / "delegated to value_help" by grepping
  `src/` yourself (e.g. product-ID aliases live only in `data/*.json` hierarchies,
  not a Python map) before planning a fix around that assumption.
- Check whether the symptom is ALREADY FIXED on an unmerged branch before planning new
  work or a duplicate ticket. FAA bucket fixes are often authored on `fix/<ticket>`
  branches (e.g. `fix/cfaai-1020-silent-failures`) that have NOT reached the deployed
  branch yet, so the failure still ships while a fix exists. When the user says main =
  deployed code, prove containment: `git merge-base --is-ancestor <commit> HEAD` (exit 0
  = in HEAD, else not deployed); find the candidate with `git log --grep=<ticket-or-symptom> -i --all`
  and `git branch -a --contains <commit>`. An unmerged fix means the correct triage
  outcome is "covered-by / duplicate-of <existing bucket ticket> — LINK it, do not open a
  new ticket"; add that reconciliation as a gate before any ticket-creation task.
- A triage story (RCA + reclassify + create follow-ups) cannot be "already implemented"
  in code — its staleness means the triage itself was done: search Jira for any OTHER
  ticket referencing the same session-id prefixes or trace IDs, and confirm the story is
  still open/unresolved/assigned, before planning. Discover the real existing bucket
  tickets by JQL (`summary ~ "Silent Failure"` etc., cross-checked — JQL `~` is stemmed,
  not substring) so follow-ups land in an EXISTING bucket, not a fresh one.

**Route classification-type decisions in the plan through the JEV API, not free-form
subagent reasoning.** Whenever the triage work involves picking one label from a fixed
set (which fix bucket a root cause belongs to), a yes/no (was the recursion limit the
cause? is a value_help failure present?), or a graded severity, the plan MUST instruct
the orchestrator and every subagent to decide it with a JEV `Choice`/`Noul`/`Score`
call and route on the returned confidence — the subagent supplies the evidence and
consumes JEV's typed answer, it does not substitute its own label. Gate the label: high
confidence and no rival option → accept; otherwise escalate to the human. This is a
standing user preference for FAA triage planning. API contract, SDK usage, the bucket
`Choice` template, and the confidence-gate thresholds are in
`references/jev-classification.md` (read `skill_view("typesafe-ai")` and the live docs
first — they are the source of truth).

When the user says do NOT rely on Databricks traces: treat the ticket's trace IDs as
labels only and reproduce from the Excel feedback + code instead. Then a "Done When"
phrased as "figures match SAC/BW references" is NOT deterministically provable
in-repo (no reference feed, no traces) — scope the plan to the fixable CLASSES
(reject cross-currency sums, correct top/flop sort direction, classify sign before
labeling favorable/unfavorable, keep leaves out of subtotal sums, one scale per
column) and state explicitly that the "matches BW" acceptance is closed by the
reporting users re-testing after deploy — never claim it as validated by your plan.

## Where fixes land — two repos

The FAA is **two** repos, and one feedback story often splits into a paired
backend-prompt PR + a UI PR that must state the SAME policy in both places
(e.g. an out-of-scope-redirect story adds the rule to the system prompt AND a
"how to prompt" help panel). When handed a PR number, confirm WHICH repo it
lives in before reading it — assuming a PR is backend when it is actually UI
burns a review cycle. When reviewing paired PRs, check the two for wording
consistency, not just each in isolation.

- **Backend** `fin-analyst-agent` — prompts, skills, tools, graph, app/stream
  pipeline. Paths below.
- **UI** `fin-analyst-agent-ui` — React + Vite + TypeScript + UI5 web
  components: WelcomeScreen, onboarding dialogs, `dataProducts.ts` (per-product
  copy, example prompts, scope notes), config. Onboarding / welcome-screen /
  help-dialog / example-prompt work lands here, NOT in the backend.

### Backend fix locations

- Shared/always-on behavior (output format, amount formatting, chart-json rules,
  scope discipline, sign convention): `src/fin_analyst_agent/langgraph_agent/prompts/system_prompt.py`
  — bump `SYSTEM_PROMPT_VERSION`.
- Dataset-specific rules (hierarchies, measures, tool quirks): `skills/pnl/SKILL.md`
  and `skills/prodsteer/SKILL.md` — bump each file's `faa_prompt_version` (patch =
  typo/format, minor = behavior-preserving addition, major = rewrite). Prompt/skill
  edits load only on app restart/redeploy.
- Stream/render pipeline (tables, charts, SAC link, sources): `apps/chart_stream_filter.py`,
  `apps/source_parser.py`, `apps/financial_analyst_agent_app.py`, `data_product_refs.py`.
- Validate P1 edits: add cases to `tests/evaluation/data/evaluation_data.json`, run
  `python tests/evaluation/run_evaluation.py`, then `pytest tests` (in the FAA
  devcontainer — see faa-devcontainer-execution).

## Pitfalls

- A `first_query` of the literal word "test" does NOT make a row test-noise — read the
  COMMENT. A "test" query with a comment like "No cost values / should display numbers"
  is a real defect report; keep it.
- Rating-5 "correct / perfect / validated with BW" rows are positive validation, not
  noise — harvest a few as golden eval cases and positive sentiment examples; never
  delete them.
- Do NOT attempt "wrong number" fixes from the Excel comment alone — the filters and
  measures that produced the number aren't in the sheet. Open the trace first, or the
  fix targets the wrong cause.
- Check whether a rule already exists before adding a new one — most FAA formatting/
  sign/scope complaints are ADHERENCE failures against rules already in
  `system_prompt.py`; adding a second, slightly different rule creates conflict and
  makes adherence worse, not better.
- A user asking for something a standing rule forbids (e.g. "add the technical node
  codes" vs. the "no raw IDs in prose" rule) is a product-policy conflict, not a bug —
  flag it for owner sign-off; do not silently override the standing rule.
- The "no raw internal identifiers in user-facing text" rule covers STATIC UI
  copy too, not only the agent's generated answers. Specifically, the raw
  authorization code `GCON/02` must never surface to users — describe access as
  "profit-center access permissions" in both the system prompt and any UI string
  (e.g. `dataProducts.ts` access notes). Grep both repos for `GCON/02` in
  user-visible copy when reviewing access/permission wording.
- Confirm a claimed-broken capability actually exists in the backend before writing a
  fix. "Excel export not working" has no backend tool behind it (`tools/__init__.py`
  loads only RAG at startup; data is MCP) — so it is a frontend feature or a
  capability the agent falsely claimed; the cheap fix is a guardrail stopping the
  agent from promising it.
