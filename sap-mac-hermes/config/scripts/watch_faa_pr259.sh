#!/usr/bin/env bash
# Cron wrapper: watch cfa-ai-incubation/fin-analyst-agent PR #259.
# Thin shim so the cron `script` field (bare filename, no args) can drive the
# generic, parameterized poller. To watch another PR, copy this file to
# watch_<slug>.sh, change --repo/--pr, and point a cron job at it.
exec python3 "$HOME/.hermes/scripts/poll_pr.py" \
  --repo cfa-ai-incubation/fin-analyst-agent \
  --pr 259 \
  --pr-author C5418860
