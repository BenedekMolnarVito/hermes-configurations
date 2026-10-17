---
name: hermes-update-recovery
description: "Fix a hung/timed-out hermes update or git fetch."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, update, git, fetch, timeout, troubleshooting, install]
---

# Hermes Update Recovery

## When to Use

Use when `hermes update` or a `git fetch` on the Hermes checkout hangs, times out, or
errors (429, slow transfer, RPC failed). Not for auth failures (see `github-auth`) or for
trimming context bloat (see `hermes-tool-skill-consolidation`).

Recover a `hermes update` that hangs, times out, or errors on its `git fetch`.
The git checkout lives at `$HERMES_HOME/hermes-agent` (default `~/.hermes/hermes-agent`);
resolve `$HERMES_HOME` first, never hardcode `~/.hermes`.

## Diagnose before you delete anything

A user's proposed fix ("delete empty objects, delete salvage refs, prune-fetch") is a
hypothesis, not the cause. Confirm the actual repo state and reproduce the real failure
first — deleting refs/objects blindly on a healthy repo is destructive and usually fixes
nothing.

1. Locate the checkout and confirm it is the git install:
   `echo $HERMES_HOME; ls -d $HOME/.hermes/hermes-agent/.git`
2. Inspect state (read-only):
   - `git remote -v` and `git branch --show-current`
   - `git for-each-ref` — see EXACTLY which refs exist. The default fetch refspec is
     narrowed to `+refs/heads/main:refs/remotes/origin/main`, so only `main` is fetched;
     extra local refs (e.g. `refs/hermes-update-backups/orphan-main-*` left by prior
     updates) are local-only and do NOT affect fetch — leave them.
   - `git count-objects -v` — `count:` is loose objects; `garbage:` + the
     `warning: garbage found: .git/objects/pack/tmp_pack_*` lines flag leftover
     partial-fetch packs.
3. Reproduce the failure and READ THE HTTP ERROR — the error names the cause:
   `HTTP 429` = GitHub rate-limiting (often self-inflicted by repeated retries, which
   also leave the `tmp_pack_*` files behind); a slow ref-listing that returns 200 but
   takes tens of seconds = server-side throttling, not repo corruption. Neither is fixed
   by deleting refs.

## macOS has no `timeout` binary

`timeout git fetch ...` fails with `command not found` on stock macOS. To bound a fetch,
use git's own low-speed abort instead of a wall-clock timeout — it aborts cleanly when
throughput stalls rather than killing mid-write:

```
GIT_HTTP_LOW_SPEED_LIMIT=500 GIT_HTTP_LOW_SPEED_TIME=60 \
  git fetch origin --prune --progress
```

(aborts if throughput drops below 500 B/s for 60s). For a long fetch, run it as a
background process with a generous timeout rather than polling.

## Safe cleanup vs. risky cleanup

- SAFE: `rm -f .git/objects/pack/tmp_pack_*` — these are abandoned partial downloads from
  interrupted fetches; removing them is harmless (verify `garbage: 0` after).
- DON'T delete refs or objects to "fix" a fetch timeout. `count: 0` means no loose/empty
  objects; if `for-each-ref` shows no salvage refs, that part of the user's plan is moot.
- On 429 / throttling, STOP retrying — each retry restarts the pack download and can
  re-trigger the rate limit, worsening it and accumulating more `tmp_pack_*`. Let one
  bounded attempt run to completion, or wait for the window to reset.

## Probe reachability without triggering the fetch

GET the ref-advertisement endpoint to separate auth/reachability from transfer speed:

```
curl -s -o /dev/null -w 'HTTP=%{http_code} time=%{time_total}s\n' \
  'https://github.com/NousResearch/hermes-agent.git/info/refs?service=git-upload-pack'
```

HTTP 200 that takes tens of seconds = throttled-but-reachable (wait it out, or fetch in
background). A HEAD/`curl -I` on that endpoint returns 405 — that is normal (it only
accepts GET), not an error.

## After a clean fetch

Run `hermes update` (or `git pull` for the checkout) once the fetch succeeds.
