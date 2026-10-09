# Subagent toolset scoping — the honest capability split

User priority: each subagent should have access to ONLY the tools its domain
needs. Do NOT overpromise. Verify against the running build before claiming a
mechanism works — the model-facing surface has changed across versions.

## What the current build actually does (verified in tools/delegate_tool*.py)

The internal spawn path fully supports per-child toolsets:
`_resolve_child_toolsets(parent_agent, toolsets, role)` intersects an explicit
`toolsets` list with the parent's (composite-expanded) toolsets and passes
`enabled_toolsets` / `disabled_toolsets` to the child session.

BUT the MODEL-FACING `delegate_task` tool schema does NOT expose `toolsets`
(or `model`). The schema's only spawn params are:
`tasks[{goal, context, output_schema, images, group}]`, plus `action`,
`subagent_id`, `message`. The source comments say so explicitly
("there is no model-facing toolsets argument"; batch children pass
`toolsets=None,  # always inherit the parent's toolsets`) and warn NOT to
re-add the removed params. So from a delegate_task call you CANNOT hand a
child a narrow toolset.

What IS deterministic even via delegate_task:
- Children never exceed the parent's toolsets (child = parent ∩ request, and
  request isn't model-settable, so child ⊆ parent).
- These are ALWAYS stripped from children: delegate_task (no recursive
  delegation unless role=orchestrator), clarify, memory, send_message,
  cronjob_manage, plus the whole `delegation` and `kanban` toolsets.

## Deterministic per-domain narrowing: spawn a process with -t

The reliable way to give a worker ONLY its domain tools is to spawn a fresh
hermes process with an explicit toolset. That child literally cannot call a
tool outside `-t`:

```bash
# research worker: web + files only, cheap model
hermes chat -q '<self-contained goal>' -t 'web,file' -m anthropic--claude-4.5-haiku

# code worker: terminal + files, standard model, preload the domain skill
hermes chat -q '<goal>' -t 'terminal,file' -m anthropic--claude-4.6-sonnet -s faa-devcontainer-execution

# long/interactive worker: tmux + PTY (see hermes-agent skill spawning section)
```

Flags: `-t/--toolsets` (comma-separated), `-m/--model`, `-s/--skills`
(repeatable), `--provider`. Background a long one with the terminal tool's
background=true. This is the path to recommend when the user wants genuine
tool isolation per domain.

Suggested domain → toolset map (tune per user):
- research / fetch / summarize : `web,file`
- codebase read / analysis     : `terminal,file`
- code edit + test             : `terminal,file` (+ `-s` the repo's skill)
- verification / lint / build  : `terminal`
- git / PR ops                 : `terminal` (+ `-s github-*`)

## Probabilistic fallback (when you must use delegate_task)

If spawning a separate process is overkill and you use delegate_task:
1. Pre-narrow the PARENT session toolset (`hermes tools disable <x>` or start
   the parent with `-t`) — children inherit the reduced set. This is the only
   way delegate_task children get fewer tools.
2. Scope the child's `goal`/`context` tightly to its domain and name the
   tools it should use, so it probabilistically stays in its lane even though
   the schema still exposes the parent's full set.
3. Pick the model tier in the goal framing per hermes-model-tier-routing
   (delegate_task also can't set model from the schema; the delegation.model
   config default applies — set it to the everyday tier).

## Before writing any of this into a plan

Re-verify: `grep -n toolsets tools/delegate_tool.py` and check whether the
schema in `DELEGATE_TASK_SCHEMA` has gained a `toolsets` property. If a future
build exposes it, prefer the deterministic delegate_task(toolsets=[...]) path
over spawning processes.
