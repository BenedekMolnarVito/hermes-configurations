# Enforcing routing / decision-offload at the runtime boundary with Hermes hooks

The SKILL.md caveat stands: Hermes has no built-in difficulty router. But hooks let you
ENFORCE a routing or decision policy at the tool/turn boundary across EVERY surface, so the
orchestrator cannot silently skip it. This is the mechanism to reach for when the user wants
routing (or any decision/classification offload) applied automatically at every turn, not just
by agent goodwill.

## Which hook does what (authoritative contract)

Three hook systems; the one that enforces across all sessions is SHELL HOOKS (drop-in, no
plugin authoring, run in CLI + Gateway + Desktop + TUI + dashboard chat). Plugin hooks (Python,
in-process) have the same behavior-changing powers; gateway hooks are gateway-only and cannot
block.

| Hook | Category | Can it change flow? | Use for |
|---|---|---|---|
| `pre_tool_call` | directive/control | BLOCK or MODIFY args before dispatch | force a `delegate_task` onto the right tier; reject a raw-LLM call that should be offloaded; rewrite args |
| `pre_llm_call` | directive | inject `{"context": "..."}` into the turn | push a per-turn directive (e.g. a style/caveman instruction, a routing reminder) with zero extra inference |
| `transform_tool_result` | transform | replace a tool result string | post-process any tool output deterministically |
| `transform_llm_output` | transform | replace final assistant text | classical-programming rewrite of the answer, no inference tokens |
| `pre_verify` | directive | keep the agent going at the stop gate | require a check before "done" |
| `post_tool_call`, `subagent_*`, `on_session_*`, api/aux observers | observer | NO (return ignored) | telemetry/audit only |

Key precedence rule for `pre_tool_call`: any valid `block` wins over any `approve`; `modify`
returns are shallow-merged into the tool args.

## Shell-hook wire contract (what a drop-in script sees and returns)

Declare under `hooks:` in config.yaml (scripts live in `~/.hermes/agent-hooks/` by convention):

```yaml
hooks:
  pre_tool_call:
    - matcher: "delegate_task"        # regex; pre/post_tool_call only
      command: "~/.hermes/agent-hooks/route.py"
      timeout: 10                     # default 60, capped at 300
      fail_closed: false              # pre_tool_call only; see fail-open note
```

stdin JSON the script receives:
`{"hook_event_name","tool_name","tool_input","session_id","cwd","profile","extra":{...}}`
(`tool_name`/`tool_input` are null for non-tool events; `extra` carries event kwargs such as
`user_message`, `conversation_history`, `child_role`, `duration_ms`.)

stdout JSON directives (both Hermes-canonical and Claude-Code shapes accepted):
- block:    `{"action":"block","message":"..."}`  or  `{"decision":"block","reason":"..."}`
- modify:   `{"action":"modify","args":{...}}`     or  `{"decision":"modify","tool_input":{...}}`
- escalate: `{"action":"approve","message":"...","rule_key":"..."}`  (Hermes-only; routes to the human approval gate. NOTE: Claude-Code `{"decision":"approve"}` means auto-ALLOW and is NOT mapped here.)
- inject (pre_llm_call): `{"context":"..."}`
- continue (pre_verify): `{"action":"continue","message":"..."}`
- no-op: empty / non-matching stdout.

Exit code 2 on a `pre_tool_call` hook also blocks (message = stdout block JSON, else first 400
chars of stderr, else a generic default) — the simplest possible blocker is `echo ... >&2; exit 2`.

## Fail-open vs fail-closed — the rule that keeps 'hard-block' from bricking sessions

Default shell hooks FAIL OPEN: spawn error, timeout, or unparseable stdout logs a warning and
the action proceeds. `fail_closed: true` (pre_tool_call only) inverts that — a crashed/timed-out
/non-JSON hook then BLOCKS. Timed-out or still-running `pre_tool_call` callbacks fail CLOSED by
default on the plugin path (block), so a hung policy hook blocks the tool.

Design rule: when the user wants a decision model (e.g. TypeSafe/Jev) to hard-block the raw path
and force the offloaded path, keep the hook FAIL-OPEN on service/key outage. 'Hard-block' means
"block the raw-LLM branch and force the decision-model branch," NOT "block everything if the
decision service is unreachable." A fail-closed policy hook that depends on an external API turns
every API outage into a dead agent across all surfaces. Gate the external call, time it out
short, and fall open to the normal path (with a logged warning) when it can't answer.

## Verify discovery/behavior

`hermes hooks test` replays a payload and prints the `parsed` block shape the dispatcher would
receive — use it to confirm a block/modify directive is well-formed before trusting it live.
`hermes config set` for config edits; never hand-edit config.yaml (indent corruption breaks the
live gateway). First-use consent prompts once per `(event, command)` pair unless
`hooks_auto_accept: true`.

## TypeSafe / Jev decision-model wire contract (verified against live docs)

When the offloaded decision model is TypeSafe's Jev, this is the exact contract a stdlib-only
hook helper needs (no SDK, no pip — `urllib.request` + `json` + `os` is enough):

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`
- Auth: `Authorization: Bearer $TYPESAFE_API_KEY` (SDK also honors `TYPESAFE_BASE_URL`,
  `TYPESAFE_DEFAULT_MODEL`). Keys live in `~/.hermes/.env`; the hook env must export it.
- Request: `{"state": <string|object|array>, "model": "jev-latest", "questions": {"<id>": <q>}}`.
  You choose each question id; the id is NOT sent to the model (put the real question in
  `instructions`). Batch MANY independent questions in ONE request — they run in parallel and
  cannot see each other's answers (docs: 13 questions in 1 call ≈ 12x cheaper, 10x faster than 13
  calls). A second request is needed only when a later question's options/state depend on an
  earlier answer.
- Question objects (discriminated by `type`):
  - noul:   `{"type":"noul","instructions":"<yes/no question>","criteria":{"true":"...","false":"..."}}` (criteria optional)
  - choice: `{"type":"choice","instructions":"...","criteria":{"<opt>":"<desc or null>"}}` (max 255 options)
  - score:  `{"type":"score","instructions":"...","criteria":["level0","level1",...]}` (2..10 ordered levels)
  - `instructions` and each `criteria` value may be a string OR an object/array; nested data is
    referenced from the question by backticked field name. You name those fields; the model sees them.
- Response: `{"model":"jev-<ver>","answers":{"<id>":<ans>},"usage":{...}}`. Answer shapes:
  - noul:   `answers[id].noul` -> float 0..1 (NO confidence field; threshold the float directly)
  - choice: `answers[id].choice` (winning key) + `.probabilities` (map) + `.confidence` (0..1 distribution concentration)
  - score:  `answers[id].score` (probability-weighted, can land between levels) + `.legend` (string-int keys) + `.probabilities` + `.confidence`
- Errors: 401 (bad/missing key), 422 (validation — body names the offending field), 429 (rate), 529
  (overloaded). Retry 429/529 with exponential backoff. No numeric RPM/TPM documented. SDK default
  timeout 10s; a stdlib hook helper should use >=30s.
- Confidence is distribution concentration, NOT workflow correctness or permission to act. Typical
  gate: >0.8 act, mid confirm/flag, <0.5 route to human. Choice confidence = `(p_max - 1/n)/(1 - 1/n)`.
- TypeSafe ships its own agent skill at `https://docs.typesafe.ai/agent-skill` with the request/
  response shapes — install it before writing an integration so the shapes are loaded, rather than
  re-deriving them. The subagent-reported "OpenAI-compatible /chat/completions, batch unsupported"
  shape is WRONG — verify the primitive contract above against live docs, do not trust that guess.

Pitfall: when a research subagent returns an API contract, its INLINE summary can be a generic-
OpenAI hallucination even when its written file is correct (seen for the Jev contract). Verify the
decisive wire fields (endpoint, batch support, answer path) against the live docs yourself before
designing the helper around them.

## Caveman / compressed-speech token saving (grounded, not folklore)

Systematic study (arXiv 2503.01141, "Token Complexity"): reasoning accuracy tracks CoT LENGTH,
not composition. All compression styles (be-concise, bullet, no-grammar/caveman, Chinese,
no-spaces) lie on ONE universal accuracy-vs-length Pareto curve; "NoProperGrammar" (~caveman)
preserves accuracy about as well as "be concise" while cutting ~50% of tokens (GPT-4o DefaultCoT
81%/586tok -> NoProperGrammar 79%/189tok, ~3x). HARD FLOOR: each problem has an intrinsic
token-complexity threshold; compress below it and accuracy collapses regardless of style.

Apply this when the user asks to save tokens with terse/caveman prompting:
- Safe win: AGENT-FACING I/O only — inter-subagent briefs/reports, intermediate notes — plus
  opt-in on quick/classification turns. Deliver it via `pre_llm_call` `{"context": ...}` scoped
  to those turns, or bake it into subagent dispatch prompts.
- NEVER force caveman on human-facing output, and NEVER blanket-force it on hard-reasoning CoT
  (the floor makes that lose accuracy). Make it opt-in/task-scoped, not a global mandate.
