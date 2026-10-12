---
name: faa-devcontainer-execution
description: "Run FAA Git, tests, and smoke checks in its devcontainer."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [FAA, Devcontainer, Git, Testing]
    related_skills: [github-pr-workflow]
---

# FAA Devcontainer Execution

Run repository commands inside the active Financial Analyst Agent devcontainer even when Hermes itself runs on the macOS host. This avoids host Git LFS drift and ensures commands use the container's dependencies, secrets, network, and tooling.

## When to Use

- Any `git add`, `git commit`, `git push`, or other state-changing Git command in the FAA repository.
- Unit, integration, evaluation, smoke, or local-stack runs for FAA.
- Pre-commit, formatting, linting, builds, and dependency operations for FAA.
- Read-only host inspection is acceptable, but do not use host output to validate executable behavior.

## Prerequisites

- Docker Desktop is running.
- The repository's VS Code devcontainer is running and mounts the current Git worktree.
- Use `scripts/run-in-devcontainer` from this skill directory.

## Procedure

1. Use `terminal` to invoke the helper with one quoted shell command:

   `~/.hermes/skills/software-development/faa-devcontainer-execution/scripts/run-in-devcontainer 'git status --short --branch'`

   Python commands MUST be prefixed with `uv run` — the container's base
   interpreter has no project deps (`python -m pytest` fails with `No module
   named pytest`). Use `cd /workspaces/fin-analyst-agent && uv run python -m
   pytest ...` and `uv run pre-commit run --files ...`.

2. For commits, execute staging, commit hooks, and commit inside the container. Never bypass hooks because Git LFS is absent on the Mac; the container has Git LFS.
3. For pushes, run `git push` inside the container and verify the exact remote ref there with `git ls-remote`.
   - **Credential bridge (github.tools.sap):** the container has git-lfs but NO
     saved credentials; the host has osxkeychain creds but NO git-lfs (the LFS
     pre-push hook blocks a host push). Do NOT use `gh auth token` — it is
     rejected (SSO-gated). Pull the working token from the host keychain and
     pass it into a one-shot container push via `docker exec -e GH_TOKEN=...`
     (the run-in-devcontainer helper does NOT forward host env, so select the
     container id yourself and call `docker exec` directly). Use the
     `x-access-token:$GH_TOKEN` basic-auth URL form, scrub the token from logs:
     ```
     TOKEN=$(printf 'protocol=https\nhost=github.tools.sap\n\n' | git credential-osxkeychain get | sed -n 's/^password=//p')
     cid=<container bind-mounting the worktree>
     docker exec -i -e GH_TOKEN="$TOKEN" -w /workspaces/fin-analyst-agent $cid bash -lc \
       'git push "https://x-access-token:$GH_TOKEN@github.tools.sap/<org>/<repo>.git" <branch> 2>&1 | sed -E "s/(gho_|ghp_|x-access-token:)[A-Za-z0-9_-]+/REDACTED/g"'
     ```
4. For tests or smoke runs, run the complete command inside the container. If starting a service, use a container-executed background process and verify its exposed endpoint from the appropriate side.
5. If the helper reports no matching container, FIRST try to start it yourself before asking the user: `docker ps -a` for a stopped `vsc-fin-analyst-agent-*` container, confirm it bind-mounts the EXACT worktree (`docker inspect <cid> --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'` shows `/Users/.../fin-analyst-agent -> /workspaces/fin-analyst-agent`), then `docker start <cid>` and retry the helper. A plain `docker ps` can look empty while the container is merely stopped (exited) — check `-a`. Only if Docker is down, or no FAA container exists at all, or none bind-mounts this worktree, ask the user to open it in VS Code. Do not silently fall back to the host or another checkout's container.

## Restarting the host stack before an eval

The eval runs IN the container but queries the FAA agent served on the macOS host
(`http://host.docker.internal:8000`). Skills (SKILL.md analyst prompts) load ONCE at
agent startup, so after editing any `skills/*/SKILL.md` you MUST restart the host
stack before the eval tests the new prompt — otherwise it silently tests the old
version still resident in the running agent. Check the agent process start time vs.
the skill file mtime to confirm which version is live.

SKIP THE RESTART WHEN THE RUNNING AGENT ALREADY POSTDATES THE EDIT. The restart is
disruptive (it kills the user's whole stack + the login_server that refreshes
`.user_token`), so prove it is actually needed first rather than restarting on reflex:
`ps -o lstart= -p $(pgrep -f run_app.py | head -1)` vs. `stat -f '%Sm %N' skills/<slug>/SKILL.md
<edited prompt .py>`. If the agent's start time is AFTER every edited file's mtime, the
running process already loaded the new prompt — do NOT restart. Confirm it positively with
ONE live smoke query of the edited behavior (e.g. a named-product/TCO row that used to
clarify) and check the answer reflects the new routing/figures; a correct live answer is
proof the new version is resident. Only restart if the agent predates an edit, or the smoke
query still shows old behavior. This turns a mandatory disruptive step into a conditional one.

Restart recipe (host, from the repo root) — only when the skip-check above says a restart IS needed:
1. Kill the old tree: `pkill -f run_app.py; pkill -f front_proxy.py; pkill -f dp_mcp_proxy.py; pkill -f login_server.py`, then confirm ports 8000/8001/8765/5000 are free with `lsof -nP -iTCP:<port> -sTCP:LISTEN`.
2. Fetch + source Vault secrets FIRST — the stack aborts at login_server with `KeyError: 'XSUAA_URL'` / `missing required env vars` if they are absent:
   `uv run fetch_secrets vault_manifest.yaml --profile local-dev --write-exports --export-file-path /tmp/.faa_secrets.sh && source /tmp/.faa_secrets.sh`
3. Launch as a tracked background process with a generous agent-start timeout:
   `AGENT_START_TIMEOUT_S=300 uv run python tests/local_execution/run_app.py` (background=true). Cold starts load MLflow/Databricks + run MCP tool discovery and routinely exceed the orchestrator's default 120s agent wait; the env knob (added for this) prevents a false `agent did NOT start within 120s` shutdown.
4. Wait for readiness by polling `lsof` on :8000, not a blind sleep. The orchestrator prints `Stack ready` and `MCP token exchange OK` when the full chain is up.
5. Smoke-test the live chain with ONE query before the full eval, reading three distinct outcomes:
   - A real answer WITH a figure -> MCP works, prompt behaves; proceed.
   - A `403` / "I can't access the data" answer -> proxy/exchange is broken (see leaked-`MCP_SERVER_URL` pitfall below), fix before evaluating.
   - A CLARIFYING QUESTION back (e.g. prodsteer asking "P&L or Product Steering?") instead of attempting the drill -> the agent IS reaching data, but the analyst prompt is not steering the query confidently. This is NOT a proxy failure; it is a prompt/routing signal that predicts low eval correctness, because the eval ground truth expects the agent to attempt the drill directly, not ask. Note it, then let the eval quantify it rather than treating it as success. Passing `data_product` in the request body does NOT by itself suppress a clarify-question; the prompt's routing rules do.
   Response shape of `/v2/serve`: `{component, payload, trace_id}` where `payload` is a list of `{text}` / `{sources}` items (NOT an `answer` key); read `payload[*].text` to see the reply.

## Worktree Safety

Container selection requires the running container's bind mount source to equal the current Git top-level directory. This prevents commands for a worktree from accidentally running in the main checkout's container. Each worktree must have its own running devcontainer.

## Pitfalls

- The host and container share source files but not the `.venv` volume, installed CLIs, credentials, or Git LFS filters.
- Host-side LFS-tracked files may appear modified due to smudge/clean drift. Determine real status inside the container.
- Do not use `--no-verify` to work around missing host tooling.
- Do not select a container by image, arbitrary name, or repository basename alone; those can collide across worktrees.
- **`localhost` inside the container is the container, not the Mac host.** Any command inside the container that needs to reach a service running on the Mac (e.g. the FAA agent on port 8000) must use `host.docker.internal` instead of `localhost`. Confirm reachability first: `docker exec <cid> curl -s -o /dev/null -w "%{http_code}" http://host.docker.internal:<port>/health`.
- **A leaked `MCP_SERVER_URL` env var silently kills MCP.** The orchestrator only launches the local `dp_mcp_proxy` (and runs the principal-propagation smoke test) when `MCP_SERVER_URL` is UNSET; if it is exported in your shell (e.g. left over from a probe), the orchestrator skips the proxy and points the agent at a dead `:8765`, so every data query returns 403 / "can't access the data" and the eval scores garbage. `unset MCP_SERVER_URL` before launching the stack, and treat a 403/"can't access" smoke answer as a dead proxy, not an agent bug.
- **Long-running commands (eval runs, full test suites) must use `docker exec` directly with `background=true` + `notify=true`**, not the `run-in-devcontainer` helper. The helper wraps the command and inherits Hermes's foreground timeout (max 600s); an eval run that dispatches multiple live agent requests and waits for a Gemini scorer easily exceeds this. Pattern: `terminal(background=true, notify=true, command='docker exec <cid> bash -c "cd /workspaces/fin-analyst-agent && uv run python ... 2>&1 | tee /tmp/output.log; echo EXIT:$?"')`.
- **The eval's scoring phase can appear hung for minutes without being dead — do NOT kill it on a stale log alone.** After the `Answering questions: 100%` bar, the harness enters `mlflow.search_traces` + per-trace blob download against the Databricks trace backend; this phase emits `Failed to download trace data for trace tr-...` and `Connection pool is full, discarding connection: ...blob.core.windows.net` warnings and the log mtime can freeze for 2–4 min while urllib3 retries, then resume to `Evaluating: 100% [scorers: 100%]` on its own. Distinguish slow-but-alive from a true deadlock before intervening: `stat -c %Y /tmp/eval.log` for freshness, and inspect the python PID's threads — all threads in `futex_do_wait` with ONE in `wait_woken` plus many ESTABLISHED sockets to the blob host (`cat /proc/<pid>/net/tcp | awk '$4=="01"'`) is a live network retry, not a hang. Let it ride within budget; only fall back to reading partial MLflow run scores if the log stays frozen well past the trace-retry window.
 - **Only the AGGREGATE score is readably retrievable; do NOT burn time hunting per-row pass/fail.** The harness prints just progress bars + a final summary box (`Correctness: X% (n/11)`) to stdout — no per-question scores inline. The per-row `eval_results` DataFrame is persisted to Delta ONLY when `output.path` is set in the eval config (FAA's local config does not set it), so it is NOT a downloadable MLflow artifact, and reconstructing per-row from the Databricks trace assessments fails on the same flaky trace-download that stalls scoring. The authoritative result is the run's logged metric `correctness/mean` (fetch via the MLflow client with the Databricks token recipe: `client.get_run(run_id).data.metrics['correctness/mean']`, times 11 = pass count) plus `prediction_total` / `prediction_failures`. Report the aggregate + the qualitative smoke-test signal (e.g. clarify-question behavior) and stop; state per-row detail is environment-blocked rather than digging through submodule source or retrying trace fetches.

## Verification

Before claiming success, the container command must establish:

- `git lfs version` succeeds.
- Tests/checks completed with exit code 0.
- After commit, `git rev-parse HEAD` reports the intended commit.
- After push, `git ls-remote origin refs/heads/<branch>` equals local `HEAD`.
