---
name: jev-hermes-decision-hooks
description: "Enforce Jev/TypeSafe decisions in Hermes via shell hooks."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [typesafe, jev, hooks, routing, token-saving, enforcement, delegate_task]
    related_skills: [typesafe-ai, hermes-model-tier-routing, auto-discoverable-skills]
---

# Enforcing Jev/TypeSafe decisions across Hermes sessions

Wire TypeSafe's System One model (Jev) in as a fast/cheap/semi-deterministic DECISION
primitive (classify / route / rank / extract / verify / gate) and ENFORCE its use at
tool/turn boundaries with Hermes hooks, so high-value decisions go through Jev instead
of an expensive, non-deterministic LLM step. This is the HOW for building that layer;
for building Jev into an app's own code use the `typesafe-ai` skill instead.

## When to Use

- Building a Hermes integration that routes subagents to models/effort by task complexity,
  classifies/reranks lists, or gates tool calls through a cheap typed judgment.
- Adding `pre_tool_call` / `pre_llm_call` enforcement that must apply to EVERY Hermes
  session (CLI, gateway, desktop, TUI, dashboard).
- Any "make the agent use Jev at every turn for X" request.

Don't use for: building Jev into a product's own backend code (-> `typesafe-ai`);
static model-tier config with no Jev judgment (-> `hermes-model-tier-routing`).

## Order of work

1. Brainstorm + design + plan FIRST (this is architectural, not bounded): the
   superpowers brainstorming gate applies — classify architectural, get design
   approval section-by-section, then writing-plans. Do not write hook code before
   the design is approved.
2. Verify the two contracts that the whole design rests on BEFORE designing around
   them (see references/hermes-hook-contract.md and references/typesafe-api.md).
   Delegate the use-case web research to parallel subagents; verify the API shape
   yourself (subagents guess OpenAI `/chat/completions` when they cannot find the
   real fields -- that is wrong for Jev; see the API reference).
3. Before executing the plan, PREFLIGHT the target env once and adapt the plan to
   what you find (these vary per machine; checking up front turns three mid-run
   rulings into one step): is `$HERMES_HOME` a git repo (`git -C <home> rev-parse
   --is-inside-work-tree`)? If not, drop every `git commit` step and track progress
   in a plain-file ledger instead. Python version (`python3 --version`): no `tomllib`
   below 3.11 -> ship config as `jev-guard.json` and make json the PRIMARY parse path.
   No `pytest` -> write tests with stdlib `unittest` (`python3 -m unittest discover -s
   tests -p 'test_*.py' -v`); this also keeps the stdlib-only invariant for tests.
   Confirm `TYPESAFE_API_KEY` is in `.env` and `hermes config get hooks` is `{}`
   (clean slate) before wiring.
4. Build the shared stdlib client + decision helpers, then the hooks, then the
   auto-discoverable skills, then wire config, then a behavioral test suite.

## Deploying + verifying a new hook (end-to-end evidence)

A registered hook is not a working hook until it is allowlisted AND exercised with a
real Jev call. The three traps, in the order they bite:
- A NEWLY-ADDED hook is NOT in the first-use allowlist, so it SILENTLY does not fire
  at runtime (`hermes hooks doctor` shows `not allowlisted -- hook will NOT fire`).
  Approve it non-interactively with one `hermes --accept-hooks -z '<trivial prompt>'`
  run (the top-level chat flag approves unseen hooks; there is no `--accept-hooks` on
  `hooks test`), then re-run `hermes hooks doctor` and confirm `allowlisted` + a clean
  JSON smoke test. Editing an already-approved hook flips it to `modified since
  approval` (a warning, still fires) -- `hermes hooks revoke` + re-approve to clear.
- `hermes hooks test <event> --payload-file f.json` MERGES your file onto a synthetic
  payload and does NOT preserve a large `tool_input` field, so a SIZE-gated hook sees
  stub content and returns `{}` -- a false negative that looks like the hook is broken.
  Get real end-to-end evidence by piping the real payload straight into the hook
  subprocess (`cat payload.json | python3 hook_x.py`): a sub-50ms return proves Jev
  was NOT called (prefilter miss or fail-open); a multi-hundred-ms return + the
  expected directive + a log line in `logs/jev-guard.jsonl` proves the real path fired.
- A hook/config change takes effect only in the NEXT fresh session -- the current
  session's tool registry is already built. Verify with a fresh `hermes ... -z` run or
  the direct-subprocess method, never by expecting the running session to pick it up.
- Fail-open "no API key" TESTS must redirect `HERMES_HOME` to a keyless temp dir, not
  just pop `TYPESAFE_API_KEY` from the child env: the hook calls `envload.ensure()`
  which reloads the real key from `$HERMES_HOME/.env`, so a bare pop leaves the key
  present and the no-key assertion fails. Point `HERMES_HOME` at an empty TemporaryDirectory
  so envload finds no `.env`. (jevlib stays pure os.environ; only the hook calls ensure().)

## Always-on rules

- STDLIB-ONLY runtime code. Hooks run as bare subprocesses with whatever interpreter
  the shebang names; a pip import will crash them. Use `urllib.request`+`json`+`os`
  for the HTTP client and `tomllib` (3.11+) with a json fallback for config. Ship no
  pip dependency in any hook or helper.
- FAIL OPEN on Jev outage is a hard invariant. Missing `TYPESAFE_API_KEY`, 401/429/529,
  timeout, or malformed response -> the hook emits `{}` (no-op) and the tool proceeds.
  "Hard-block broadly" means block the un-Jev'd PATH when Jev is reachable, never block
  on infrastructure failure -- blocking on outage bricks every session at once. Only an
  explicit per-entry `fail_closed: true` inverts this, and only on `pre_tool_call`.
- NEVER hand-edit `config.yaml`; wire hooks via the CLI. A stray indent corrupts the
  file and breaks the live gateway. Back it up first and verify it still yaml-parses
  after. `hermes config set hooks '<json>'` REFUSES a whole-section write (`hooks`
  has sub-keys) -- set the LEAF instead: read `hermes config get hooks --json`, append
  your entry to the `pre_tool_call` list, and `hermes config set hooks.pre_tool_call
  '<json-list>'` (or pass `--force` to replace the whole section). Make the append
  idempotent (skip if the command path is already present) so re-running the wiring
  doesn't double-register the hook.
- Resolve the profile home from `$HERMES_HOME` (fallback `~/.hermes`) in code; never
  hardcode `~/.hermes` -- a wrong path silently targets the default profile.
- Secrets stay in `.env`. Read `TYPESAFE_API_KEY` from the env; never read, print, log,
  or commit its value. Telemetry logs reasons, never the key or raw secret-bearing args.
- Enforcement is TIERED by consequence, not "block everything": HARD-BLOCK only where
  skipping Jev is a real regression; MODIFY (`{"action":"modify","args":{...}}`) to
  silently correct args (e.g. inject per-task model) with no friction; ADVISE
  (`pre_llm_call` `{"context":...}` / `transform_*`) to hint/annotate, never block.
- Scope every `pre_tool_call` hook with BOTH a `matcher` regex AND an in-script
  arg-shape gate -- otherwise a broad matcher calls Jev on every write/delegate and
  burns credits + latency. Batch all independent questions into ONE Jev request
  (12x cheaper, 10x faster than N calls); only make a 2nd request when an answer
  determines the next evidence/options.

## Caveman / compressed-speech token-saving (user's standing scope)

- Apply caveman compression to AGENT-FACING I/O ONLY: inter-subagent briefs (compress
  `delegate_task` context/goal at dispatch) and subagent reports (compress the returned
  summary via `transform_tool_result`). These are ON by default and are a real ~1.5-3x
  token win.
- NEVER compress human-facing output (the final assistant turn the user sees). NEVER
  register a caveman `transform_llm_output` on human-facing turns.
- Quick-turn reasoning compression is OFF by default (opt-in `JEVGUARD_CAVEMAN=reasoning`):
  quick turns produce short answers so caveman adds little and risks the token-complexity
  floor. Global kill-switch `JEVGUARD_CAVEMAN=off`.
- WHY the floor: reasoning accuracy tracks CoT LENGTH, not composition -- every problem
  has an intrinsic token-complexity threshold; compress below it and accuracy collapses
  regardless of style (arXiv 2503.01141). So caveman is safe on I/O and bulk/quick turns,
  dangerous forced on hard reasoning. Protect code/paths/URLs/numbers/quotes/IDs verbatim
  with a regex; only drop connective prose.

## Bulky-I/O gate (chunk-and-synthesize enforcement)

A `pre_tool_call` HARD-BLOCK gate (`hook_bulk_io_guard.py`, matcher
`read_file|web_extract|write_file`) stops a bulky DATA read/write/extract from
running directly in the orchestrator and forces the map->reduce chunk-and-
synthesize path (skill: chunked-bulk-io-synthesis). This is the VOLUME
complement to `hook_batch_guard.py` (which blocks bulk CLASSIFY/RANK/TRIAGE and
routes to jev-decisions) -- distinct triggers, so a distinct hook.
Contract, mirroring the always-on rules above:
- LOCAL prefilter FIRST (no Jev call): a compact NON-content io_shape
  (sizes/counts/path-hint) vs. the `bulk_io` thresholds in jev-guard.json
  (read_lines_min / extract_urls_min / extract_char_limit_min / write_chars_min).
  Below threshold -> immediate noop, Jev never called. This is the arg-shape gate
  the matcher regex alone can't do.
- Only if bulky -> ONE batched Jev question via `decisions.is_bulk_io`, sending
  ONLY the io_shape, NEVER raw content (keeps the request small + secret-free).
  `chunk_p >= chunk_block_p` (0.7) -> `{"action":"block", ...}`. Jev scores LOW
  when the agent needs the content verbatim (its edit target) so a legitimate
  full read is not blocked -- the judgement the prefilter cannot make.
- FAIL-OPEN: no key / Jev down / any error -> noop. Blocking on outage is the
  one thing a hard-block gate must never do.
- Escape: `JEVGUARD_BULK_IO=off` -> always noop. Thresholds are config-tunable
  with zero code change; keep the DEFAULTS mirror in jevlib/config.py in sync
  with jev-guard.json (both must carry the `bulk_io` block).

## Model + effort routing

- Keep the complexity->model+effort map in a TOML config file as the single source of
  truth; change models there with zero code change. Claude is the user's default
  (deep=opus/high, standard=sonnet/medium, quick=haiku/minimal); default tier when Jev
  is unavailable or ambiguous is `standard`.
- `delegate_task` accepts a per-task `model`/`provider` override -> inject it per task
  via a MODIFY directive (fully achievable).
- Reasoning effort is `delegation.reasoning_effort` at CONFIG scope (honored for
  subagents), NOT a confirmed per-call `delegate_task` argument. Ship the ACHIEVABLE
  mode (hook sets the profile's `delegation.reasoning_effort` to the batch max tier
  before children spawn, restores after) as the floor. Only ship per-task effort in
  the MODIFY directive (IDEAL mode) if a verify-first probe proves the override is
  honored. KNOWN RESULT (verified): the per-task `reasoning_effort` override is
  SILENTLY DROPPED by the delegate_task schema -> ACHIEVABLE mode is the one to ship;
  do not re-probe unless a Hermes release changes the delegate_task argument list.
- Probe mechanism caveat: an observer plugin's `pre_api_request` fires only in the
  PARENT process, so it does NOT capture a delegated CHILD's provider request -- the
  capture file stays empty and tells you nothing. To check effort actually landed,
  assert `hermes config get delegation.reasoning_effort` equals the batch max tier
  after a real delegate run, and read the child's model from the delegation live
  transcript / `subagent_start`; do not rely on capturing the child's wire request.

## References

- references/hermes-hook-contract.md -- hook events, directive shapes, wire protocol,
  fail-open semantics (the enforcement mechanism).
- references/typesafe-api.md -- the verified Jev HTTP API contract + stdlib client shape.
- references/behavioral-test-suite.md -- how to prove the layer works with real evidence.
