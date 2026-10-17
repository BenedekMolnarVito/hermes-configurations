# Live verification against the running FAA agent stack

When a data product "was down" and should now return plausible values, or before
accepting a ground-truth change, prove the running agent returns real data
end-to-end. Run everything inside the devcontainer.

## 1. Start the full local stack (primary, NOT parallel)

```
nohup uv run python tests/local_execution/run_app.py >/tmp/run_app.log 2>&1 &
```

- If the devcontainer helper is a foreground `docker exec`, a plain invocation
  dies when the exec returns. Launch long-running services with `nohup ... &`
  to a log file, then poll the log in later calls.
- `run_app.py` defaults `AGENT_LANDSCAPE=dev`, which loads the `*_ina` prompts
  and binds the INA tool. Product Steering / INA-path fixes are only exercised
  on the dev landscape; do not verify them on `int`/`prod`.
- Start the PRIMARY stack, not `PARALLEL_STACK=1`, when you might need to
  authenticate: parallel mode starts no login_server (XSUAA only whitelists the
  fixed `:5000`/`:3000` callback) and merely reuses an existing token. The
  primary stack starts login_server on `:5000` with a background token-refresh
  loop.

## 2. Token reality — start the stack BEFORE asking the user to log in

A `.user_token` whose access-token `exp` is days old is NOT proof you must
re-authenticate. XSUAA access tokens live ~1h, but the stored refresh_token
lasts far longer, and login_server mints a fresh access token from it at boot.
Start the stack and read the log: `token refreshed (expires in 3600s)` and
`principal propagation OK for host=ina` mean you are authenticated with no
browser step. Only when the refresh token itself is revoked does the stack block
at `Waiting for .user_token`; that is when to ask the user to open
`http://localhost:5000/login`. Never type or handle SSO credentials yourself.
Confirm with `curl -s http://localhost:8000/token-status` → `valid:true`.

## 3. Direct in-process tool probe (isolates the tool from agent reasoning)

The most surgical proof a tool returns real values. Load the fresh token into the
request-scoped ContextVars the connector reads, set the data product, then
`.ainvoke` the LangChain tool object directly (they are `@tool`, so call
`.ainvoke(argdict)`, not the raw function):

```python
import sys; sys.path.insert(0, "/workspaces/fin-analyst-agent/src")
from pathlib import Path
from fin_analyst_agent.request_context import data_product_var, user_token_var
raw = Path("/workspaces/fin-analyst-agent/.user_token").read_text().strip()
user_token_var.set(raw.split()[-1] if " " in raw else raw)
data_product_var.set("prodsteer")
from fin_analyst_agent.tools.ina_tools import query_ina
r = await query_ina.ainvoke({"filters": {...}, "measures": ["ACTUALS_CY"], "group_by": ["GL_ACCOUNT_ID"]})
```

`query_ina` reads `data_product_var` (default `prodsteer`); the connector
(`InaConnector.from_env(prefix="DSP_INA")`) reads `user_token_var`. Both must be
set in the same process. Reconcile a grouped breakdown against the same query
with NO `group_by` (the node-level scalar total): equal totals prove leaf
expansion is correct and the result is not a false zero.

## 4. Full agent path via /v2/serve

```
curl -s -X POST 'http://localhost:8000/v2/serve?request_identifier=<id>' \
  -H 'Content-Type: application/json' -d '{"data":"<question>"}' -m 200
```

A single serve call can exceed a foreground helper's exec timeout; launch the
curl to a file in the background and poll for the file rather than treating the
helper timeout as a failure. Confirm the answer's `analyticSlice` shows the
intended retrieval path and that figures/polarity/currency reconcile with the
direct probe.

## 5. Wire-level confirmation, then teardown

The stack tees each service to `.claude/worktrees/logs/{dsp_proxy,agent,...}.log`.
A `dsp_proxy.log` line `← 200 https://.../dwaas-core/sap/bc/ina/service/v2/GetResponse`
with a byte count is a live, authenticated upstream round trip.

Teardown when the container lacks `pkill`/`pgrep`: scan `/proc/*/cmdline` and
`kill -TERM` the pids matching `run_app.py`/`dsp_proxy.py`/`login_server.py`/
`front_proxy.py`, then verify `:8000`/`:5000` no longer respond and that
`git status` shows no source edits (a verification task must leave the tree
clean).
