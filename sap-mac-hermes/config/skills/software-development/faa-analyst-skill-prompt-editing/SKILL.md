---
name: faa-analyst-skill-prompt-editing
description: "Edit FAA analyst answer prompts: format, versioning, verify."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [FAA, prompt, skill, information-design, house-style]
    related_skills: [faa-data-product-wiring, faa-devcontainer-execution, faa-feedback-triage]
---

# FAA Analyst Skill Prompt Editing

Editing the CONTENT of FAA's analyst prompts — the three `skills/<slug>/SKILL.md`
files (`pnl`, `prodsteer`, `bud_fc`) that drive how the agent reasons about and
*writes* answers. This is prompt engineering on the answer surface (number
format, sign/notation, routing, output rules), NOT wiring a data product across
registration surfaces (that is `faa-data-product-wiring`). Run every Git/test
command inside the devcontainer (`faa-devcontainer-execution`).

## When to Use

- A ticket asks to change how FAA answers READ: number/currency/scale format,
  +/- signs, abbreviations, routing/scope wording, commentary style, output
  rules in `pnl`/`prodsteer`/`bud_fc` `SKILL.md`.
- Applying a controller/Information-Design style guide to FAA as text rules.
- Bumping `faa_prompt_version` after any analyst-prompt edit.
- NOT for adding/wiring a new data product (use `faa-data-product-wiring`), nor
  for Hermes's own skill library.

## What these files are

- `skills/pnl/SKILL.md` — P&L actuals analyst (revenue + GL-account opex). No
  plan/budget measures; figures are actuals and growth.
- `skills/prodsteer/SKILL.md` — Product Steering / TCO cost analyst. Carries cost
  variances.
- `skills/bud_fc/SKILL.md` — Budget/Forecast cube (dev-landscape only); the one
  cube with vs-budget / vs-forecast deviations. Watch its Graceful-degradation
  rules (HL Revised / (V) volume deviation are NOT measures here).
- Each has YAML frontmatter `metadata.faa_prompt_version` (semver) +
  `faa_prompt_stem`. SkillsMiddleware mounts all enabled DPs' SKILL.md and the
  LLM self-routes; the body carries URL placeholders substituted at load and ends
  with a DP-specific `[ANSWER_ANALYTIC_SLICE]` section.

## Procedure

1. Read all three target files fully before editing — the same rule often lives
   in each with per-cube wording (sign convention, EUR-no-rescale, abbreviation
   table, output rules). A presentation rule the ticket states once usually must
   land in ALL THREE for consistency; the user's plans say so explicitly ("apply
   the identical block to all three").
2. Make the edit with `patch`. For a cross-cutting house-style rule, author ONE
   coherent block and insert it at the same logical home in each file (e.g. a
   `### Number & display formatting (house-style)` subsection under each skill's
   `Output` / data-product-specific-rules section). Adapt only the per-cube
   clauses (prodsteer: variances; bud_fc: subordinate to Graceful degradation so
   `ACTUALS_BUD`/`FC_BUD` is never relabeled "(V)"; pnl: note it has no plan
   measures so favorable/unfavorable applies only to a genuine vs-plan delta).
3. When you ADD a display convention that contradicts an existing one, FIX the
   old sentence in place — do not leave both. The classic conflict: the old
   `M/B/T/Q EUR` suffix + worked example `-1.44 M EUR` directly contradicts the
   Information-Design `€m`/`€k` symbol-first rule. Rewrite the
   `Values are already in EUR — do NOT rescale` worked example to the new scale
   notation while KEEPING the "use the raw full-EUR value for the math, only the
   display changes" instruction intact.
4. Reconcile, don't duplicate: for an abbreviations/notation change, diff FAA's
   existing table against the target and add only the MISSING canonical forms;
   never append a second table.
5. Bump `faa_prompt_version` in the frontmatter of EVERY file you touched
   (CLAUDE.md rule): patch = typo/format, minor = additive clarification
   (the common case for house-style rule additions), major = behavior-changing
   rewrite. Skills load once at startup; a restart/redeploy is needed to pick up
   the edit. The bump rule applies to ANY behavioral addition — even when the
   content edit was made in a previous commit or session and the version bump was
   deferred or forgotten. Check the current version against what the content
   actually reflects before finishing; a reviewer WILL catch a missing bump and
   it breaks the MLflow trace↔prompt-content correlation the versioning exists to
   guarantee. The semver + git short-SHA become MLflow trace tags
 (`prompt_version` / `prompt_commit`, suffix `-dirty` when uncommitted).
 AFTER ANY MERGE/REBASE of a feature branch that touched these files, re-check
 each `faa_prompt_version` against `origin/main` before finishing — because the
 `faa_prompt_version` line is the usual merge CONFLICT, and resolving it by
 taking main's number silently flattens your bump to EQUAL main while your
 content still differs from main. That breaks the trace-tag contract: a trace
 from your branch gets tagged with main's version for a different prompt.
 Diagnose with a content-vs-version diff that excludes the version line:
 `diff <(git show origin/main:$f | grep -v faa_prompt_version) <(git show :$f | grep -v faa_prompt_version)` — if content differs but staged version ==
 main version, bump ABOVE main (the branch's old pre-merge bump target is now
 stale since main advanced past it; compute the new bump from the CURRENT main
 number, not the branch's earlier one). Confirm the staged content is a correct
 SUPERSET (both main's intervening changes AND your branch's block present)
 before bumping, so you bump a real merge, not a clobber. Note: these edits
 land UNSTAGED on top of the (already-staged) files, so re-`git add` the three
 SKILL.md paths after the version bump or the stale staged version commits.
6. Verify (see below), then report. Do NOT commit unless asked (standing user
   rule); never stage the LFS PDF/parquet smudge drift or `uv.lock` churn.
7. If a live smoke test shows the model does NOT reliably obey the new rule,
   escalate to a deterministic post-processor rather than more prompt text (see
   "When a prompt rule won't stick").
8. When a display rule affects typed components, audit the sibling UI repository
   before calling the rule end-to-end ready. Freeze both branch SHAs, then trace
   the payload through every rendered surface: chart axis, tooltip, table body,
   totals footer, copied value, and recoverable/preformatted string cells. Keep
   raw numeric chart payloads unchanged and implement number presentation at the
   renderer boundary; only normalize a string cell when an anchored full-cell
   pattern proves the entire value is a financial figure, because recursively
   rewriting arbitrary payload strings can corrupt labels, titles, keys, and
   analytic metadata. Verify non-target currencies and units remain unchanged.

## Porting earlier prompt edits onto a branch that renamed the wire names

When you re-apply prompt edits authored earlier (a stash, an abandoned branch, a
requirements doc written against PLACEHOLDER column names) onto a branch that has
SINCE established the real/confirmed wire names, do NOT paste the old prose
verbatim. Two mechanical swaps must happen together or the committed prompt is
self-contradictory:

1. Swap every placeholder wire name to the confirmed one from the target branch
   (the real product-id dimension for a filter/name lookup, or the real
   breakdown-row dimension for grouping). Export the source prose first
   (`git stash show -p stash@{0} > /tmp/x.diff`) and read it, then adapt — do not
   re-pop a stash onto a diverged tree (it conflicts). CRITICAL: "confirmed on
   the branch" is NOT the same as "confirmed against the live cube." A wire name
   a prior branch/doc asserted as real can still be wrong — re-probe it via
   `get_output_ports` yourself before trusting it (see the alias-map pitfall).
2. DELETE the "<name> is a placeholder — re-verify" caveats for every name the
   target branch confirmed. Leaving them in commits a prompt that calls a now-
   real wire name a placeholder, which tells the model (and the next editor) the
   dimension is unverified when it is live — the opposite of the branch's state.

Keep a verify-note ONLY on items that are STILL genuinely unconfirmed on the
target branch (an AM-swap PR typically renames dimensions but does NOT add a new
measure or a new customer dimension — those stay unverified). For a still-
unconfirmed name, do NOT invent a literal wire name as fact anywhere, especially
in the canonical palette: describe the capability ("surface the pre-calculated
margin measure; discover its exact wire name via `get_output_ports`") and flag
the palette entry UNCONFIRMED rather than pinning a guessed `MARGIN`/`CUSTOMER_ID`
that a future query will send and the model will trust. Also scope-check what the
target branch ALREADY changed: do not re-apply an old block that regresses it
(e.g. re-introducing a hierarchical functional-area dim the branch already
flattened), and do not drag in unrelated house-style from the source branch —
port only the logical blocks the task names.

## When a prompt rule won't stick — escalate to a deterministic post-processor

A formatting rule can land for some cases and silently fail for others. Verified
live (gpt-5.5): the number house-style held for millions (`€388.8m`), the
mandatory `+` sign, and growth-rate neutrality, but the BILLIONS scale kept
rendering the forbidden `-2.31B EUR` (capital `B` + ISO-after-value) through
three escalating prompt attempts (adding a `-€2.3bn` worked example and a literal
"`-2.31B EUR` is forbidden" callout did NOT fix it). Mechanism worth knowing: a
model obeys the scale form that appears DENSELY across the prompt's worked
examples (`€m`) and ignores a scale that appears only once or twice (`€bn`) —
adding one more `€bn` example does not change that, which is why
prompt-sharpening plateaus and a deterministic filter is the fix, not better
examples. Rule: stop sharpening the
same prompt rule after ~3 attempts; piling on more prompt text has diminishing
returns against a model's entrenched default. The bullet-proof fix is a
deterministic output filter in the response path. In FAA the answer passes TWO
chokepoints and you MUST patch BOTH or the streaming path diverges from
`/v2/serve`:
- Non-stream: `_FinalAnswerMiddleware.after_agent` in
  `langgraph_agent/deep_graph.py` sets `final_answer` — normalize the extracted
  text there.
- Stream: `_emit_from_chunk` in `apps/financial_analyst_agent_app.py` emits the
  `Markdown` segment (after chart-json/sources/slice are already peeled off by
  the filter chain) — normalize `result.emit` there.

  CHUNK-BOUNDARY TRAP (critical, verify this when implementing OR reviewing the
  stream chokepoint): `result.emit` is a per-LLM-token fragment, NOT a complete
  line. `SourceStreamFilter.feed` only holds back a partial `[ANSWER_SOURCES]`
  open-tag prefix — it does NOT align emits to number/word boundaries. gpt-5.5
  routinely tokenizes `-2.31B` and ` EUR` as separate chunks, so a regex that
  needs `number + scale-letter + EUR` contiguous matches NEITHER fragment and
  the forbidden form streams through UNNORMALIZED — while the whole-text
  non-stream path works, giving false confidence that the fix is live. A naive
  `normalize_scale_notation(result.emit)` per chunk is therefore BROKEN on the
  primary user path (`/v2/serve_stream`). Fix: either normalize the fully
  accumulated answer at stream-finish and re-emit a corrected trailing Markdown
  frame, or give the emit path a hold-back buffer that never splits a
  `number+scale+EUR` token sequence across emits. Always add a chunk-boundary
  regression test (feed `["was ", "-2.31B", " EUR", "."]` through the real
  `SourceStreamFilter` + normalizer and assert the output is `-€2.31bn` — note
  the preserved source decimals per the DECIMAL CONTRACT below, NOT a rounded
  `-€2.3bn`) — the per-chunk bug has zero coverage from whole-string unit tests.
  IMPLEMENTED FIX (CFAAI-951, chosen approach): a stateful
  `ScaleNotationStreamNormalizer` class in `number_format.py` with a hold-back
  buffer — `feed(chunk)` returns the safe-to-emit normalized prefix and retains
  any trailing fragment that could still complete into a forbidden form
  (anchored `_HOLDBACK_TAIL` regex: number + optional scale + partial
  EUR/TEUR/MEUR), `finish()` flushes the remainder at stream end. One instance
  per request, threaded through `_emit_from_chunk`/`_emit_finish`/`_emit_shutdown`
  as an optional `scale_normalizer` param (None → stateless whole-text fallback
  for the non-stream chokepoint, which keeps using plain
  `normalize_scale_notation`). This was chosen over re-emitting a corrected
  trailing frame because NDJSON frames already sent cannot be retracted. Also
  fixed in the same pass: `_emit_finish` now normalizes `source_filter`
  `trailing_text` (post-`[/ANSWER_SOURCES]` prose) — it previously emitted it
  raw, a latent gap. And a `+`-sign test was added (see sign note below).
Put the normalizer in its own module (e.g.
`langgraph_agent/number_format.py`) with unit tests, so both chokepoints import
one implementation. The normalizer MUST mask and NEVER rewrite inside fenced
code blocks, `chart-json`, inline code spans, `[ANSWER_SOURCES]`, and
`[ANSWER_ANALYTIC_SLICE]` — those carry raw full-magnitude figures and MDX keys
that the chart components, the "Validate in SAC" affordance, and MLflow traces
need byte-exact; only PROSE is restyled (chart data stays raw, the UI formats
axis labels itself). Make it idempotent and skip any text with no currency
token (fast path), and do not rewrite a bare number that has no currency context
(it may be a count/FTE/percentage). The forbidden EUR scale forms the regex must
catch and rewrite to symbol-first `€<num><k|m|bn>`: `-2.31B EUR` / `bn EUR` /
`M EUR` / `m EUR` / `k EUR`, the glued ISO forms `TEUR` (→ k) / `MEUR` (→ m) /
`EURm` / `EURbn`, and a bare capital `B`/`M`/`K` suffix on a value that carries a
EUR designator — all currency-anchored, never a bare number. A post-processor is a code change, so a
stack restart is required to load it, and the probe plan's text-surface probes
(P1–P3, P7–P8) run against `/v2/serve` after the restart.

DECIMAL CONTRACT — the normalizer REFORMATS, it does not RESCALE. `_canon` only
restyles the number the model already typed (`-2.31B EUR` → `-€2.31bn`); it never
computes a scale conversion, so "decimal count" is whatever the model wrote.
Resolved convention for this codebase (CFAAI-951, user decision): PRESERVE the
model's source decimals in `_canon` — do NOT round. The prompt examples still
teach the model to WRITE 1 decimal (`-€1.4m`, `-€2.3bn`); the normalizer only
fires on a forbidden form the model slipped into, so a correctly-formatted
answer shows 1 decimal and a rescued one shows the model's raw decimals. That
cosmetic drift on rescued answers was accepted deliberately over forcing a round
in `_canon`. Do NOT add rounding to `_canon` and do NOT bump the example
decimals to 2 — the two were reconciled this way on purpose. (The earlier
guidance here said round `_canon` to 1dp; that was reversed.)

`_canon` SIGN HANDLING: `_NUM` allows a leading `+`, but the forbidden-form
regexes capture sign via a separate `(?P<neg>-?)` group with the `+`/`-` stripped
from the number group — so a `+5 M EUR` input leaves the `+` inside `num` and
emits `€+5m`. Fold `+` into the sign group or strip a leading `+` in `_canon`,
and add a `+`-prefixed test case; house-style says positive base figures carry
no sign, but a stray `+` must not produce malformed output.

## Verify

- `uv run --no-sync python -m pytest tests/unit_tests -q` green in the
  devcontainer. The skill-loader + registry tests exercise that every enabled
  skill still loads.
- Confirm the EDITED on-wire prompt actually carries the new rules by rendering
  each skill through the PRODUCTION loader (not just reading the file) — this is
  the fallback verification when a live smoke test is blocked:

      uv run --no-sync python -c "
      from fin_analyst_agent.data_products.registry import get_data_product
      from fin_analyst_agent.langgraph_agent.prompts.skill_loader import load_skill_document
      for slug in ['pnl','prodsteer','bud_fc']:
          ls = load_skill_document(get_data_product(slug))
          print(slug, ls.version, ls.commit, 'HEADER' in ls.full_text)
      "

  `load_skill_document` does the URL-placeholder substitution and reads the
  bumped version, so this proves: version bump landed, no `{collibra_...}`/
  `{dsp_...}`/`{sac_...}` placeholder leaked un-substituted, and the new rule
  text is present in the exact document the model receives. `_read_version(raw,
 slug)` on the raw file text is a lighter check of just the frontmatter.
 - Rendering the on-wire text proves the rule is PRESENT in the document the model
 receives — it does NOT prove the model will OBEY it. The model can carry the
 rule verbatim in context and still emit a forbidden form (see the billions
 case). So the render-check is the floor; a live large-figure probe is the real
 gate whenever Vault creds are available — and a formatting rule that fails live
 gets a post-processor, not another prompt pass.
- `load_all_skills()` needs the DP registry gating (bud_fc is dev-only); prefer
  per-slug `load_skill_document(get_data_product(slug))` which bypasses the
  landscape gate for a pure render check.

## Restarting the host local stack to load a SKILL.md edit (and run the eval against it)

Skills load once at app startup, so the running agent keeps the OLD prompt until
the stack is restarted — confirm with `ps -o lstart= -p <agent_pid>` vs. the
SKILL.md mtime before trusting any live result; an agent started before your
edit is testing the old version. Restart recipe + the traps that cost the most:

- SOURCE VAULT EXPORTS INTO THE LAUNCHING SHELL FIRST. `run_app.py` (host stack)
  needs `XSUAA_URL`, `JWT_CLIENT_ID/SECRET`, `DPG_*`, `MCP_UPSTREAM_URL` in its
  env or login_server dies with `KeyError: 'XSUAA_URL'` and the orchestrator
  shuts down. Fetch + source once per shell:
  `uv run fetch_secrets vault_manifest.yaml --profile local-dev --write-exports`
  `--export-file-path /tmp/.faa_secrets.sh && source /tmp/.faa_secrets.sh`.
- UNSET A LEAKED `MCP_SERVER_URL` BEFORE RELAUNCH (the single most deceptive
  trap). The orchestrator starts the local `dp_mcp_proxy` (:8765) ONLY when
  `MCP_SERVER_URL` is unset (`if not os.environ.get("MCP_SERVER_URL")`). A value
  leaked from an earlier shell/iteration (e.g. `http://localhost:8765/mcp`) makes
  it SKIP launching the proxy AND skip the principal-propagation smoke test, so
  the agent points at :8765 where nothing listens → every MCP call 403s and the
  agent answers "I'm stuck - I can't access the data." That produces a FULL eval
  of access-failure answers that looks like a prompt regression but is pure env.
  `unset MCP_SERVER_URL` before relaunch; confirm the boot log shows
  `✓ dp_mcp_proxy ready on 127.0.0.1:8765` AND `✓ MCP token exchange OK` (the
  exchanged aud must be `data-product-gateway`), not a jump straight from
  login_server to agent.
- THE AGENT-START WAIT IS A HARDCODED 120s THAT COLD STARTS EXCEED. `run_app.py`
  waits `timeout_s=120` for the agent on :8001; a cold start (MLflow/Databricks
  init + MCP tool discovery + model init) routinely runs longer and the
  orchestrator then kills the whole stack mid-init. The wait is env-configurable
  via `AGENT_START_TIMEOUT_S` (if your checkout predates that, it's a one-line
  `float(os.environ.get("AGENT_START_TIMEOUT_S","120"))` patch at the agent
  `wait_for_port` call — revert it after so the feature-branch diff stays clean).
  Launch with `AGENT_START_TIMEOUT_S=300`.
- RELAUNCH as a tracked background process (never nohup/disown — Hermes rejects
  shell background wrappers; use `terminal(background=true, notify=[...])`), then
  poll ports for readiness, no blind sleep: the stack is up when :8000
  (front_proxy), :8001 (agent), :8765 (dp_mcp_proxy), :5000 (login_server) all
  listen and the log prints `✅  Stack ready`.
- RESTART IS DISRUPTIVE — it kills the user's whole local stack (and the
  login_server that keeps `.user_token` refreshed). Ask before restarting when
  it's an autonomous/loop iteration; the user may be using the stack
  interactively.
- A direct `curl /v2/serve` does NOT replicate the eval's request shape. The eval
  harness passes per-row `query_args`; a hand-rolled POST (even with
  `data_product:"prodsteer"`) can trigger the agent's P&L-vs-ProductSteering
  CLARIFYING question on data rows that the GT recipe forbids. Use a direct curl
  only to prove the MCP chain is live (real figure, not a 403/"can't access");
  let the eval harness be the authority on per-row pass/fail. If the live agent
  returns a clarify question on a data row whose GT says answer-directly, that is
  a real finding to report (prompt not enforcing the no-clarify rule), not a
  curl-shape artifact to wave away.

### The 1024-char Agent Skills description limit (silent truncation)

`deepagents.middleware.skills` enforces the Agent Skills spec limit of 1024 chars
on each SKILL.md frontmatter `description`; an over-long one is truncated to the
first 1024 chars and the rest is DROPPED from what the model sees when deciding
whether to use the skill (logged as a WARNING at load, easy to miss in boot
spam). A prompt rewrite that grows the `description` past 1024 silently loses its
tail. After any edit that touches the frontmatter description, check its length
and keep it under 1024 — the body has no such limit, so move detail into the body
and keep the description a tight trigger.

## Live smoke test — token valid is NOT enough; Vault data-plane creds gate it

To run the example prompts against a live `/v2/serve` you need BOTH a fresh
`.user_token` AND the DPG token-exchange secrets. A valid `.user_token` alone is
insufficient: the `dp_mcp_proxy` (direct mode) does the XSUAA jwt-bearer exchange
with DPG `mcp`-service creds (`DPG_CLIENT_ID/SECRET`, `DPG_AUTH_URL`,
`MCP_UPSTREAM_URL`) pulled from Vault `local-dev`. If `.env`'s Vault bootstrap
creds are EMPTY (`VAULT_ROLE_ID=` blank / no `VAULT_SECRET_ID`), `fetch_secrets`
falls back to interactive OIDC and dies headless with
`OSError /dev/tty` / `Failed to start OIDC callback server` — the data-plane
secrets never load and a live query fails at the MCP layer. The `.user_token`
`exp` being in the future does NOT mean the stack can query. Diagnose this gap
by `grep -oE '^[A-Z_]+=' .env` (keys present but values blank) and the
`⚠ Secrets not loaded` banner the devcontainer helper prints. When blocked,
verify via the loader-render check above and report the blocker honestly with
the exact missing creds — never fabricate a figure to stand in for a live
result. Full live recipe (when creds ARE available): see
`faa-data-product-wiring` → "Headless end-to-end smoke test".

## Mining a stakeholder discussion into a requirements doc (PRE-edit step)

Before editing a `prodsteer`/`pnl`/`bud_fc` SKILL.md from a meeting transcript or
recorded stakeholder discussion, FIRST produce a structured requirements
reference and get the decisions confirmed — do NOT jump straight to prompt
patches. The transcript is raw signal; the edit needs resolved decisions. Steps:

1. Read the transcript AND the current target SKILL.md in the same pass, so each
   requirement is written as a GAP vs. current behavior ("contradicts current
   X", "already covered", "new rule"), not as a free-floating wish. A "gap" that
   the skill already handles is noise — classify every item against the live
   prompt.
2. Write the doc to `docs/<slug>_<topic>_business_requirements.md` in the FAA
   repo (co-located with the code it drives, not scratch). Use the template at
   `templates/business_requirements.md`.
3. Give every requirement a stable ID (R1, R2, …) and a type
   (Prompt / Wiring-verify / Docs-catalog / Process / Feature). The ID lets the
   later prompt-edit and the data wiring reference the same requirement; the
   type routes it: Prompt → this skill, Wiring-verify → `faa-data-product-wiring`
   / `faa-prodsteer-am-swap`, Process/Docs → not a code change.
4. Attribute each requirement to the speaker + timestamp so a future reader can
   re-listen. Transcripts of accented / non-native speakers are imperfect VTT:
   flag probable mis-hearings inline as `[transcript: "<heard>" → probably
   <meaning>]` (e.g. GCON numbers, BDP/BWP, product names) rather than silently
   "correcting" — the business confirms the real value later.
5. Collect every genuine ambiguity into an explicit "open questions" section and
   ASK the user (one `clarify` call, batch the independent questions,
   recommended option first). A scope-reversing decision (e.g. a measure moving
   from out-of-scope to in-scope) is NOT yours to assume — it gates the whole
   edit. After answers come back, REWRITE the open-questions section in place as
   "Resolved decisions" and fold any answer that refines a requirement back into
   that requirement (a user answer often differs from your proposed option —
   e.g. "try-then-degrade" instead of "decline"; make the requirement match the
   answer, don't leave your original guess standing).
6. Only after decisions are confirmed do you apply the prompt edits (the
   Procedure above) — in a later session / explicit go-ahead, not implicitly in
   the same requirements-gathering turn.

This doc is the durable artifact a `/loop` or recurring "review the discussion"
task should produce each iteration; the prompt edit is downstream. Report
LOOP_COMPLETE once the doc + resolved decisions exist, not once the prompt is
edited.

## Mapping an external style guide onto the text surface (ADAPT pattern)

FAA's answer surface is a fixed component list (Markdown + BarChart/LineChart/
ChatTable + a `chart-json` fence) — NO HTML/SVG injection path. So a visual style
guide (e.g. HICHERT®SUCCESS / Information Design) adapts to FAA as TEXT rules
only: typography, thousands separator, symbol-first scale notation, explicit
+/- signs, color-SEMANTICS-as-words (favorable/unfavorable vs. a plan is a
performance verdict; a growth rate YoY/@cc/QoQ is a neutral factual observation
— never call a growth rate favorable/unfavorable), and message-first commentary.
Anything requiring SVG/CSS/pixel layout (inline bars, hatch fills, no-Y-axis
chart restyling, HEX colors, fonts) is OUT of scope for a prompt-only change —
FAA's chart components own their own rendering. When a controller's feedback is
"format numbers like X", that is a text rule in prose but may also require a UI
formatter change for typed chart/table frames; when it is "draw the chart like
Y", that usually needs an explicit payload contract plus renderer work.

Do not let the UI infer finance semantics from a numeric sign alone. A positive
or negative sign is not equivalent to favorable or unfavorable: performance
color depends on line type and is valid only for a deviation against
BUD/FC/TGT, while YoY/@cc/QoQ growth must remain neutral. If the typed payload
has no semantic role field, render signed values neutrally rather than applying
a generic green/red class. Adding semantic color requires an explicit backend
field (for example a constrained role enum), validation, and UI tests covering
both a plan deviation and a neutral growth control.

## Pitfalls

- Edit the three analyst skills, not Hermes's own skill library — these are FAA
  in-repo prompt files under `skills/<slug>/`, versioned with the code.
- ALIAS-MAP TRAP (the single most expensive wire-name error): a cube's
  `get_output_ports` returns a `default_hierarchies` map keyed by LOGICAL /
  display names (e.g. `STEERING_PRODUCT`, `DERIVED_SOLUTION_AREA`,
  `PRODUCT_COSTING_COMPONENT`) that are NOT filterable dimension wire names.
  Filtering/grouping on an alias key fails with HTTP 502 "fieldName does not
  belong to the specified hierarchy." ALWAYS take filter/row dimension names from
  `schema.dimensions[].name` (the real wire names, e.g. `SOLD_PRODUCT_ID`,
  `DERIVED_SOLUTION_AREA_ID`, `DERIVED_GL_ACCOUNT_ID`), never from the
  `default_hierarchies` keys. In the skill, state explicitly that the alias keys
  are display aliases and must never be filtered on, so a future editor does not
  re-pin them.
- RE-VERIFY FILE CONTENT AT COMMIT TIME, not just at edit/verify time. A file
  you confirmed correct early in a session can be silently reverted or
  overwritten on disk before you stage it (an editor, a parallel subagent, a
  stray tool, a git op). Immediately before `git add`, re-read the ACTUAL bytes
  you are about to commit (`git show :<path>` for the staged blob, or re-parse
  the file and assert a known sentinel value — e.g. a re-anchored figure like
  `459,399,116.80` must be present and the old `85,044,582.43` absent). A commit
  MESSAGE that claims a change the staged CONTENT does not contain is worse than
  no commit: it mislabels history and misleads review. Likewise, an eval/test run
  only validates what was ON DISK WHEN IT RAN — confirm the file carried the
  intended content at run time (check mtime vs. run start, or diff the run's
  recorded inputs) before trusting the score; a passing/failing number against a
  stale dataset proves nothing about your edit.
- TRUST THE ON-DISK EVAL DATA FILE OVER A HANDOFF/SCRATCH NOTE for row text,
  fiscal year, and GT figures. A handoff reflects a PRIOR snapshot; the eval data
  can be re-anchored (e.g. FY2026->FY2025) between sessions, so a handoff that
  lists a question as "Q2 2026 ... total -459m" while
  `tests/evaluation/data/evaluation_data_<slug>.json` says "Q2 2025 ... total
  -85m" means the FILE is authoritative — probe the EXACT phrasing + GT number
  from the file, never the handoff's remembered values, or you re-probe the wrong
  question and misread a correct answer as a miss. The file shape is a dict with
  `inputs`/`expectations`/`query_args` keyed by question-id string; read
  `inputs[id].data` for the verbatim question and `expectations[id]` for the GT.
  THE SAME AUTHORITY APPLIES TO A HANDOFF'S DONE/TODO LIST, not just its figures:
  when resuming a multi-session task, re-verify COMPLETION STATE on disk before
  re-doing anything the handoff marks TODO — a handoff is a point-in-time snapshot
  and a prior session often lands more than it recorded. Programmatically scan the
  file for the expected figures + the removal of the stale narrative (e.g. a
  `-?\d[\d,\.]*\s*(?:bn|B|M|m|k|K)\s*EUR` forbidden-scale scan over the PROSE only,
  and a presence check for each authoritative figure) before touching a row; if a
  'TODO' row already carries the correct values, mark it done rather than rewriting
  it, because re-editing a correct row risks regressing it.
- RE-PROBE BEFORE OVERWRITING A "CONFIRMED" WIRE NAME. When a handoff, a prior
  branch, or the skill's own text asserts a dimension/measure is real, verify it
  against the live cube (`get_output_ports`) before writing it into a prompt or
  believing a one-line "it's wrong" note — the skill reflects what SOME earlier
  session observed, which may be an AM swap out of date. One `get_output_ports`
  call settles product vs. solution-area vs. TCO-component dimension names, which
  measures exist (margin/revenue/`ACTUALS_PY`/`ACTUALS_CC`), and which dims are
  `filter_kind: hierarchy_node` vs. flat — do that read first, then edit.
- A flat dimension (`filter_kind` absent, e.g. a product/solution-area leaf dim)
  takes a `kind: "list"` leaf filter; a `hierarchy_node` filter on its `.YYYY`
  node key returns 0 rows silently. Only dims with `filter_kind: hierarchy_node`
  (typically `GL_ACCOUNT_ID`, `PROFIT_CENTER_ID`) take `kind: "hierarchy_node"`.
  A 0-row result from a hierarchy-node filter on a flat dim looks exactly like
  'no data' — check the schema's `filter_kind` before concluding the slice is
  empty.
- Do NOT assume `ACTUALS_PY` / `ACTUALS_CC` / `GROWTH_CY` exist for YoY/@cc just
  because the skill lists them — a cube may expose only `ACTUALS_CY`. Confirm
  each measure in `schema.measures` before an edit teaches the model to send it,
  and flag absent ones as 'verify via get_output_ports' rather than pinning them.
- When a routing rule references a measure or dimension whose wire name is STILL
  UNCONFIRMED on the live cube, do NOT invent a literal name. Instead: add an
  HTML comment `<!-- TODO: after <deploy event>, confirm <measure/dim> wire name
  via get_output_ports smoke test, update palette, remove this note -->` at the
  routing site, and describe the capability in prose without pinning a literal
  ("discover via `get_output_ports`"). Never pin `MARGIN` or `CUSTOMER_ID` as
  guesses — the model treats palette entries as authoritative and will use them
  in live queries.
- A standing-obligation note (e.g. the skill pins `currentYear`/fiscal-year
  suffixes `.26AC`/`.2026`) must stay in sync at fiscal-year rollover — flag it
  when you touch adjacent rules; owner = FAA skill maintainer.
- Keep each cube's sign-convention and EUR-no-rescale blocks authoritative for
  the MATH; a display-format rule governs only how the number is WRITTEN. State
  that split explicitly in the added block so a future reader does not rescale.
- Do not report a prompt-only formatting rule as "working" off a single probe
  that happened to return 0 / a sparse slice — exercise it on a slice that
  returns a LARGE non-zero figure (a whole-company full-year rollup) so the
  comma/scale path actually fires, and classify a 0-EUR answer as empty-vs-failed
  via the MLflow trace span (see `faa-data-product-wiring` → classify an answer)
  before blaming the backend or the rule.
- When a rule proves unreliable in prompt form, capture the residual honestly and
  add the deterministic post-processor; never dress up an untested or
  partially-working prompt rule as validated guidance.
