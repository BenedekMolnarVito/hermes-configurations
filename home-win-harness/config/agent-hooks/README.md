# Jev-Guard — operations README

Global JEV (TypeSafe System One) decision layer for Hermes. Enforces JEV usage via shell hooks,
routes subagents to configurable model+effort by Jev-judged complexity, and caveman-compresses
agent-facing I/O. Lives under `~/.hermes/agent-hooks/` (code) + `~/.hermes/skills/jev-*` (skills).
Design: `~/.hermes/plans/jev-guard-design.md`. Plan: `~/.hermes/plans/jev-guard-implementation.md`.

## Runtime requirement: TYPESAFE_API_KEY
Hooks read `TYPESAFE_API_KEY` from the environment. In a normal Hermes session the agent process
loads `~/.hermes/.env`, and hook subprocesses inherit that env — so hooks route live automatically.

NOTE: `hermes hooks test` and `hermes hooks doctor` run the hook subprocess WITHOUT loading `.env`,
so they will show fail-open `{}` (stdout empty / no directive) rather than a live Jev verdict. That is
EXPECTED and is the fail-open invariant working, not a failure. To verify live routing, run a real
`hermes chat -q` that triggers the hook, or call the jevlib helper directly in a shell that has the key.

## The 7 hooks (wired in config.yaml `hooks:`)
pre_tool_call:
  - hook_delegate_route.py   delegate_task        → inject per-task model (ACHIEVABLE effort via config)
  - hook_batch_guard.py      delegate_task|web_extract → HARD-BLOCK bulk classify/rank (size>=8 prefilter)
  - hook_browser_select.py   browser_click        → MODIFY to Jev-selected ref / BLOCK on error page
  - hook_citation_guard.py   write_file|patch     → ADVISE only (logs citation_warn; never blocks)
  - hook_jira_classify.py    jira_create_issue    → MODIFY (attach component/priority) / BLOCK on dup
pre_llm_call:
  - hook_skill_route.py      (all turns)          → inject "Relevant skill: X" context (ADVISE)
transform_tool_result:
  - hook_caveman_report.py   delegate_task        → caveman-compress subagent reports (zero inference)

## Consent / allowlist (REQUIRED before hooks fire)
Shell hooks fire only after first-use consent. `hermes hooks doctor` shows "not allowlisted" until then.
Approve either by confirming at the TTY prompt the first time each fires, or ahead of time with
`--accept-hooks` on a hermes invocation. Allowlisting grants these scripts run-as-you in every session,
so review each `hook_*.py` before approving (they are stdlib-only, fail-open, and never read secrets
beyond the API key, which they never log).

## Config = source of truth: jev-guard.json
Edit `~/.hermes/agent-hooks/jev-guard.json` to change routing — NO code change needed:
  routing.{deep,standard,quick} = {provider, model, reasoning_effort}  (Claude defaults)
  routing.thresholds.{deep_min, standard_min}  (Jev complexity score → tier)
  caveman.{enabled, apply_to}
  jev.{model, timeout_seconds, fail_open}

## Effort routing = ACHIEVABLE mode
Per-call reasoning_effort is NOT honored by delegate_task (probed: EFFORT_PER_CALL_SUPPORTED false),
so hook_delegate_route sets `delegation.reasoning_effort` (profile-scoped config) to the batch's max
tier via `hermes config set` before children spawn. One delegate batch shares one effort level.

## Env flags
- JEVGUARD_CAVEMAN=off         → disable all caveman compression (kill-switch)
- JEVGUARD_CAVEMAN=reasoning   → opt-in caveman on quick-tier reasoning turns (OFF by default)
- JEVGUARD_SKIP_CONFIG_WRITE=1 → hook does not call `hermes config set` (used by tests)
- JEVGUARD_EFFORT_PER_CALL=1   → inject per-task reasoning_effort into args (IDEAL mode; OFF — probe said unsupported)

## Fail-open invariant
Any Jev outage (missing key, 401/429/529, timeout, bad JSON) → hook emits `{}` (no-op), tool proceeds.
A JEV outage can never brick a session. The only exception: a per-entry `fail_closed: true` in
config.yaml on a pre_tool_call hook (none set by default). Outages log to `~/.hermes/logs/jev-guard.jsonl`.

## Tests
`cd ~/.hermes/agent-hooks && python3 -m unittest discover -s tests -p 'test_*.py' -v`  (131 tests)

## Rollback
1. `cp ~/.hermes/config.yaml.pre-jevguard.bak ~/.hermes/config.yaml`  (restores pre-Jev-Guard hooks block)
   OR `hermes config set hooks '{}'` to just unwire the hooks.
2. Optionally disable the skills: `hermes skills disable jev-decisions jev-engineering jev-team-roles`.
3. The `~/.hermes/agent-hooks/` dir and skills can be deleted entirely to remove all traces.
