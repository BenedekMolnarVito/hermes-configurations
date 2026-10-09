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

## Worktree Safety

Container selection requires the running container's bind mount source to equal the current Git top-level directory. This prevents commands for a worktree from accidentally running in the main checkout's container. Each worktree must have its own running devcontainer.

## Pitfalls

- The host and container share source files but not the `.venv` volume, installed CLIs, credentials, or Git LFS filters.
- Host-side LFS-tracked files may appear modified due to smudge/clean drift. Determine real status inside the container.
- Do not use `--no-verify` to work around missing host tooling.
- Do not select a container by image, arbitrary name, or repository basename alone; those can collide across worktrees.
- **`localhost` inside the container is the container, not the Mac host.** Any command inside the container that needs to reach a service running on the Mac (e.g. the FAA agent on port 8000) must use `host.docker.internal` instead of `localhost`. Confirm reachability first: `docker exec <cid> curl -s -o /dev/null -w "%{http_code}" http://host.docker.internal:<port>/health`.
- **Long-running commands (eval runs, full test suites) must use `docker exec` directly with `background=true` + `notify=true`**, not the `run-in-devcontainer` helper. The helper wraps the command and inherits Hermes's foreground timeout (max 600s); an eval run that dispatches multiple live agent requests and waits for a Gemini scorer easily exceeds this. Pattern: `terminal(background=true, notify=true, command='docker exec <cid> bash -c "cd /workspaces/fin-analyst-agent && uv run python ... 2>&1 | tee /tmp/output.log; echo EXIT:$?"')`.

## Verification

Before claiming success, the container command must establish:

- `git lfs version` succeeds.
- Tests/checks completed with exit code 0.
- After commit, `git rev-parse HEAD` reports the intended commit.
- After push, `git ls-remote origin refs/heads/<branch>` equals local `HEAD`.
