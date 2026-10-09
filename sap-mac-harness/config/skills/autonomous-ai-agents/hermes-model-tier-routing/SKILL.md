---
name: hermes-model-tier-routing
description: "Use when setting up Hermes tiered model routing."
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, delegation, model-routing, config, aliases, subagents]
---

# Hermes Model Tier Routing

Set up "route hard tasks to a strong model, easy tasks to a cheap one" in Hermes' own config. The user names tiers by task difficulty (e.g. deep/standard/quick); each tier maps to a concrete model, and delegated subagents run on the tier that fits the task.

## What Hermes actually supports (say this up front)

Hermes has NO built-in "detect task difficulty and auto-pick a model" router. The tier decision is made per-delegation by the orchestrating agent, guided by a written policy — not by the runtime. Do not promise automatic difficulty detection. What the config gives you is named, editable targets plus a sensible default; the policy makes the choice consistent. State this caveat to the user so they aren't expecting magic.

Exception the user may ask for: you CAN enforce a routing (or decision/classification offload) policy at the runtime boundary with Hermes hooks — a `pre_tool_call` shell/plugin hook can BLOCK or MODIFY a `delegate_task` call to pin the right tier, and `pre_llm_call` can inject a per-turn directive. This runs in every surface (CLI/gateway/desktop/TUI/dashboard), so the policy is applied at every turn instead of relying on agent goodwill. When the user wants routing or an external decision model (e.g. TypeSafe/Jev) enforced automatically, see `references/hook-enforcement.md` for the exact wire contract, the block/modify/inject directives, the fail-open rule that keeps a 'hard-block' policy from bricking sessions on an API outage, and the verified TypeSafe/Jev `systemone` request/response contract for a stdlib-only hook helper.

## The design (three pieces)

1. `model.aliases.<tier>` in config.yaml — one alias per tier. This is the SINGLE SOURCE OF TRUTH for which model each tier maps to. Remapping later = editing only the alias. A tier can carry BOTH a model and a reasoning-effort target (deep=high, standard=medium, quick=minimal); keep that pairing in the tier config so a remap moves both together.
2. `delegation.model` / `delegation.provider` — the default model for ad-hoc subagents spawned without an explicit tier. Set it to the everyday/middle tier so casual delegation doesn't burn the expensive model.
3. A routing policy in `~/.hermes/SOUL.md` (global) or the repo's `AGENTS.md` — maps task type -> tier and tells future sessions to pass the tier explicitly on each delegate_task. Reference tiers BY ALIAS NAME, not by hardcoded model id, so a remap needs no policy edit.

## Procedure

1. Read config.yaml to learn the provider setup: `model.provider`, `model.base_url`, `model.api_key`/key_env, and the list of available models. For a custom proxy the models are under `custom_providers[].models`.
2. Confirm with the user (clarify): the tier names, where the policy lives (global SOUL.md vs repo AGENTS.md), and the default model for untiered delegation. Put the recommended everyday-tier default first.
3. Add one alias per tier via `hermes config set`. Use the FULL form (model + provider + base_url + key_env) when models live behind a custom base_url — the short `provider/model` form does not carry the endpoint. Example per tier:
   - `hermes config set model.aliases.<tier>.model <model-id>`
   - `hermes config set model.aliases.<tier>.provider custom`
   - `hermes config set model.aliases.<tier>.base_url <proxy-url>`
   - `hermes config set model.aliases.<tier>.key_env <ENV_VAR_NAME>`
4. Set the delegation default: `hermes config set delegation.model <id>` and `hermes config set delegation.provider <provider>`.
5. Write the routing policy into the chosen instructions file with a `patch` that PRESERVES existing content (append a new `## Model routing for delegated work` section; do not overwrite the personality/soul text). The policy must: list each tier with the kinds of tasks it handles, name the default tier, and instruct reading the concrete model id from `model.aliases.<tier>` rather than hardcoding.
5b. Pair the tier map with a DELEGATE-WHAT policy in the same instructions file (a `## Delegate context-heavy work` section). Tier routing answers WHICH model; this answers WHEN to spawn a subagent at all. Without it the orchestrator keeps doing bulk work inline and the aliases go unused. State the delegate-by-default classes: bulk/multi-file reads, multi-URL extraction sweeps, log/trace/CI-output triage, verification passes (lint/build/test -> report pass/fail + failing lines only), and independent parallel workstreams. Instruct the subagent to return ONLY the distilled result, not the raw material. Give an explicit keep-inline carve-out (single-file reads, quick lookups, short edits, anything needing the full raw output in the orchestrator's own context, anything needing user interaction) and say minimal overhead is fine — delegate when context bloat is the real cost, not for every small step. A user who wants this is optimizing token budget; do not make the policy so strict it delegates trivial steps.
6. Verify: `python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"` for validity, and `hermes config check`. Print the resulting `model.aliases` and `delegation` blocks back.

## Pitfalls

- NEVER hand-edit config.yaml. Use `hermes config set KEY VALUE` — a stray indent corrupts the file and breaks the live gateway. This is a hard Hermes invariant.
- An alias with its own base_url authenticates with its OWN credential (`key_env` or `api_key`, which accepts `"${VAR}"`). With neither set, the key is resolved from the alias host, NOT carried over from the previously active provider — so always set key_env on a custom-proxy alias or auth silently fails.
- Reference tiers by alias name in the policy, never by hardcoded model id. Hardcoding means every remap requires editing two places and they drift. If the user adds/renames a TIER (not just remaps a model), the policy's tier list does need updating too — call that out.
- Aliases and delegation defaults take effect for NEW sessions/delegations, not the current one mid-conversation (prompt-caching invariant). Don't claim the running session switched.
- The same aliases double as interactive `/model <tier>` switches — mention this; it's free UX.
- The `hermes-agent` bundled skill's `references/providers-and-models.md` documents alias forms and `references/configuration.md` lists the `delegation.*` and `model.aliases` keys. Load those for exact field semantics rather than guessing.
- Model override is PER-CALL on `delegate_task` (a `pre_tool_call` modify hook can inject `model`/`provider` per task); reasoning EFFORT is NOT a confirmed per-call arg — it is config-level (`delegation.reasoning_effort`, or `auxiliary.<task>.reasoning_effort`). So a hook can route the model per task cheaply, but to route effort it must `hermes config set delegation.reasoning_effort` at profile scope BEFORE the children spawn, which makes effort batch-scoped (one level per delegate_task call, not per task). Do not promise per-task effort injection without first proving a per-call override is accepted — probe it empirically (dispatch a child with the override, read the real request via a `pre_api_request` observer) and fall back to profile-scoped effort if the probe fails. Effort levels: none/minimal/low/medium/high/xhigh/max/ultra (default medium), plus a disable-reasoning toggle; providers clamp to supported levels (never escalate past what a model accepts).
- The delegate-what policy is a peer of the tier map, not an afterthought: the tiers only pay off if heavy work is actually delegated. When you set up routing, write both sections in one pass.
