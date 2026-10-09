# Watching a PR for a re-review (from a CLI / no-public-endpoint session)

After you push fixes and reply to a reviewer, the user may ask you to "observe"
the PR and re-verify when a re-review lands. Pick the mechanism by what the
session actually is, then build the watcher.

## Webhook vs. polling — decide first, do not default to "webhook"

A GitHub webhook is a PUSH model: GitHub POSTs events to a public HTTPS URL you
run. From a laptop/CLI agent session that model does NOT fit, for three reasons
worth stating to the user up front (they often ask for "a webhook" by reflex):

- No public always-on endpoint. A CLI session has nowhere for GitHub to POST;
  you'd need a tunnel (ngrok/cloudflared) + a long-running server that dies on
  sleep/session-end.
- No process that outlives the turn. Even a cron job created from a CLI session
  is local-only here — nothing wakes the agent to "auto-re-verify".
- Webhook admin. GHE repo webhooks need repo-admin rights (and org policy often
  blocks arbitrary webhook URLs); an external contributor usually lacks this.

So on a CLI session use POLLING: a scheduled job that uses the existing `gh`
auth to diff the PR's reviews/comments against a stored watermark. It survives
restarts, needs no public endpoint and no admin. Only reach for a real webhook
if the user has a public host AND repo-admin AND wants true push.

## The polling watcher pattern

State lives under `~/.hermes/cache/<name>/` (watermark `state.json` +
append-only `new_activity.md`). The poller:

1. Reads `state.json.last_seen` (ISO8601 UTC); on first run seed it to the
   newest existing other-author event so only NEW activity triggers.
2. Fetches all three comment surfaces and keeps events newer than the watermark:
   `pulls/{N}/reviews` (formal reviews), `pulls/{N}/comments` (inline), and
   `issues/{N}/comments` (conversation tab — do not forget this one; see the
   main skill's comment-endpoint pitfalls).
3. FILTERS OUT the PR author's own login and CI bots (`github-actions[bot]`),
   so your own fix-commits and reply comments never self-trigger the watcher.
4. On new activity: append a dated report to `new_activity.md`, advance
   `last_seen` past the newest event, set a `pending_review` flag. On no
   activity: advance `last_seen` to now and STAY SILENT (print nothing).

`gh api` uses global auth, not repo cwd — the poller runs from any directory.

## Scheduling it as a cron job

- Cron scripts MUST live under `~/.hermes/scripts/` and be referenced by bare
  filename (`poll_prNNN.py`); an absolute or `~/`-relative path is rejected by
  cronjob_manage. Keep the canonical copy there — do not also leave a stale copy
  under the cache dir that drifts from the scheduled one.
- Use `no_agent=true` + `script=<name>`: the scheduler runs the script and
  delivers stdout verbatim with NO LLM cost. EMPTY stdout delivers nothing
  (watchdog pattern) — which is why the poller must be silent when there's no
  new activity, or you spam the log every tick.
- `deliver='local'` saves output (viewable via cronjob list) without a channel.

## The honest limitation — state it, don't over-promise

A cron job created from a CLI session CANNOT message the user or auto-wake the
agent to re-verify: there is no messaging gateway wired up, and local cron
output is not delivered back into any session. So the loop is: watcher silently
records new activity to disk; the USER (or the agent next session) checks it and
runs the re-verify. Do not tell the user a `deliver='local'`/`origin` cron job
will ping them. Real push + auto-re-verify needs a messaging gateway
(deliver='telegram'/'all') — offer that as the alternative, don't fake it.

## Hand back a re-verify command, not just a watcher

Ship a companion helper (a `.sh` the user runs) that: prints the pending
`new_activity.md`, re-fetches current review state, and prints the exact
re-verify gate for THIS project (for FAA: the devcontainer render+assert+lint
sequence from the faa-kyma-helm-deployment skill), plus the one-liner to clear
the `pending_review` flag afterward. The watcher detects; the helper is how the
next session actually re-checks the claims and decides if a new fix is needed.
