---
name: faa-data-product-wiring
description: "Wire/add/modify an FAA data product or cube."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [FAA, data-product, INA, OData, wiring]
    related_skills: [faa-devcontainer-execution, jira-onboard, change-integration-analysis]
---

# FAA Data Product Wiring

How the Financial Analyst Agent selects and queries a data product (DP), and
what you must touch to add or change one. A DP is a cube reachable by two
separate paths gated on landscape; wiring is a multi-surface registration, not a
single edit. Run all Git/tests inside the devcontainer (see
`faa-devcontainer-execution`).

## Confirm the integration path BEFORE wiring

A DP can be reached three ways. Decide which one this ticket demands FIRST — the
registration surfaces and where variable/parameter passing lives all differ by
path, and a mid-project directive can switch the target path and obsolete a plan
written for another. Do not assume the direct-connector path just because the
existing DPs use it; re-read the ticket/notes for an explicit gateway mandate.

1. Direct INA-to-DSP (FAA owns the InA payload): `AGENT_LANDSCAPE=dev` -> the
   INA tool (`query_ina`, `search_dimension_members`) is bound (gate in
   `tools/__init__.py`), the `<base>_ina` prompt loads, and INA hits a cube via
   a server-side query payload built in `connectors/ina_connector.py`.
2. Direct OData-to-DSP: anything else (`int`/`prod`/unset) -> INA tool is
   absent; only the OData tools (`list_data_products`, `query_financial_data` in
   `tools/odata_tools.py`) are bound, and the `<base>_odata` prompt loads.
   Fail-closed: unset landscape -> OData.
3. Via the Data Product Gateway (DPG) MCP server (firefly-proxy builds the InA
   query server-side): FAA becomes an MCP CLIENT of DPG rather than owning the
   InA payload. FAA has NO MCP-client code or `mcp` dependency today, so this
   path is net-new client plumbing (an MCP client + tool binding), NOT an edit
   to `ina_connector.py`. Feasibility of passing cube input parameters here
   depends on whether the DPG connector/firefly-proxy accepts a variables
   argument end-to-end — verify in the DPG repo, do not assume. When the ticket
   mandates this path, the direct-connector `build_payload` variables work is
   the WRONG surface; wire the MCP client instead.
- Version/scenario handling differs by path: on OData a plan version is a
  filterable DIMENSION (e.g. `VERSION_ID`); on INA it is an input PARAMETER
  (an INA `Variables` entry). Keep the two shapes separate; do not force one
  onto the other.

## Registration surfaces (all required to fully wire a DP)

1. `data_products/registry.py` -> `DATA_PRODUCTS[slug]`: prompt stem, Collibra/
   DSP/SAC URLs, `enabled_envs` gate (fail-closed). `resolve_prompt_name()` maps
   the stem to `<stem>_ina`/`<stem>_odata`.
2. `connectors/ina_cubes.py` -> `INA_CUBES[slug]` (`InaCubeSpec`): DataSource
   (Schema/Object/InstanceId), `hierarchy_meta`, `field_map`, measures,
   `time_fold`. `get_cube_spec()` falls back to `prodsteer` for an unknown slug.
3. `data/allowed_assets.json`: the OData allowlist `(space_id, asset_name)` pair,
   optional per-`landscapes` scope. Without it `query_financial_data` DENIES the
   asset even though it is registered.
4. `prompts/<stem>_ina.string_prompt_template` and/or `_odata` variant. Set
   `metadata.version` (bump per CLAUDE.md rules). Tune the `_ina` variant for dev
   traces, `_odata` only for int/prod.

Routing glue (usually no edit needed): `apps/schemas.py` `data_product` field ->
`apps/financial_analyst_agent_app.py:_resolve_dp` (400 unknown/env-disabled) ->
`request_context.data_product_var.set(slug)`; the globally-bound INA tool reads
that ContextVar per call to pick its cube.

## Pitfalls

- Registering a slug in `registry.py` alone does NOT make it queryable: the INA
  cube spec, the OData allowlist entry, and the prompt file are independent
  surfaces, each fail-closed on its own. A DP missing any one silently fails on
  that path.
- INA input parameters (SAC "Variables") ARE wired on the direct-InA path:
  `build_payload(variables=)` emits an `Analytics.Variables` block, `InaCubeSpec`
  carries `variables` (caller-arg -> technical name) + `default_variables` (full
  default slice), and `query_ina` exposes `forecast_version`. See
  `references/ina-view-input-parameters.md` for the exact wire shape, the cube
  spec fields, and the discovery/verification recipe. Variable passing is ALSO
  live on the DPG firefly-proxy path now (see that section) — the two transports
  are no longer split on this. Still grep the emitted payload body / probe the
  live tool schema, not just a connector's allowed-keys list, before assuming a
  capability is wired on any NEW cube/path.
- Demo/mock mode is `DEMO_MODE=true` (env var), NOT `USE_MOCK_ANSWERS` (the
  `.env` sample in CLAUDE.md is stale). It only mocks the OData tools
  (`_MOCK_DSP_CATALOG`/`_MOCK_FINANCIAL_ROWS`); the INA/dev path has NO mock
  branch, so INA wiring is verifiable only via unit tests / a mocked connector
  unless the dev DSP proxy is reachable.
- A new cube in the same DSP space likely reuses another cube's
  hierarchy_meta/field_map (e.g. the P&L space's GL/PC/Material hierarchies and
  the `FISCAL_YEAR_PERIOD` composite time fold), but dim-group names can differ
  by cube (prodsteer suffixes `_ID`); verify each reused dimension against the
  new cube's metadata, do not assume identity.
- A committed onboarding plan can be silently obsoleted by a later directive that
  changes the INTEGRATION PATH (e.g. "query this DP through the DPG MCP/
  firefly-proxy workflow, not FAA's own connector"). Before implementing an
  existing plan, re-confirm the required path against the latest ticket notes;
  if it changed, re-classify every task as required/changed/obsolete rather than
  executing the stale plan. The `variables`-in-`build_payload` tasks apply ONLY
  to the direct INA-to-DSP path.
- Without live DP access, `InstanceId`, the exact INA variable technical name/
  values, and Collibra/SAC URLs are unknowable — use placeholders and disclose
  that a live query will fail until they are filled from DSP `$metadata` or the
  DP owner. Structural wiring + demo/unit verification is still completable.

## FAA skill wiring under the mount-all SkillsMiddleware model (current architecture)

The direct-INA/OData `resolve_prompt_name` + `<stem>_ina`/`_odata` prompt-template
model is GONE on the dp-mcp branch (CFAAI-653). Current model: DeepAgents
`SkillsMiddleware` mounts EVERY enabled DP's `skills/<slug>/SKILL.md` and the LLM
self-routes by reading whichever matches. To make the agent answer about a new DP
that is already served by the DPG MCP server, wire exactly TWO FAA surfaces:

1. `data_products/registry.py` -> add a `DataProduct` to `DATA_PRODUCTS`. This is
   the real gate: `load_all_skills()` iterates `enabled_data_products()`, so a
   `SKILL.md` with NO registry entry is an orphan the middleware never mounts.
   The slug ALSO must be registered because the answer's `[ANSWER_ANALYTIC_SLICE]`
   `dataProduct` is validated by `_slice_known_dp_slugs()` (calls
   `get_data_product`, drops unknowns) — an unregistered slug silently breaks the
   `data_product` MLflow trace tag AND the "Validate in SAC" affordance.
2. `skills/<slug>/SKILL.md` — frontmatter `name`/`description` (SkillsMiddleware
   parses these) + `metadata.faa_prompt_version`/`faa_prompt_stem`; body carries the
   four URL placeholders `{collibra_metadata_url}`/`{dsp_dataaccess_url}`/
   `{dsp_dataaccess_url_detail}`/`{sac_analytic_url}` (substituted at load from the
   registry — never materialized to disk) and MUST end with a DP-specific
   `[ANSWER_ANALYTIC_SLICE]` section whose `dataProduct` == the registry slug.
   The legacy `prompt_name` field is still required on the dataclass but is inert
   (no `.string_prompt_template` is read).

Gating: `enabled_envs=None` = available in every ENVIRONMENT (what pnl/prodsteer
use); a restricted `frozenset({"dev"})` fail-closes when ENVIRONMENT is unset —
and `tests/local_execution/run_app.py` does NOT set ENVIRONMENT, so a dev-only
gate hides the DP from the LOCAL stack too. Mirror the sibling DP's gate
(`None`) unless you deliberately want env restriction.

Tests to update when adding a slug: `tests/unit_tests/test_data_product_registry.py`
(add availability tests) and `test_skill_loader.py::test_load_all_skills_returns_every_enabled`
+ its `fake_skills_root` fixture (both hardcode the enabled-slug SET — add the new
slug to the fixture corpus AND the assertion or it fails with the new DP either
missing from the set or FileNotFound in the fake corpus).

Pre-existing failure to ignore: `tests/unit_tests/langgraph_agent/prompts/test_prompt_variants.py`
(~14 tests) fails on this branch looking for removed `prompts/*_odata.string_prompt_template`
files — dead tests from the variant-split removal, unrelated to DP wiring.

Verifying the LIVE toolset: FAA gets its query tools from the DPG MCP server's
`tools/list`/`get_output_ports` at startup, NOT from the FAA skill. A correct FAA
skill still yields "no exposed query port" if the deployed MCP server version does
not yet serve that DP. Probe with
`MCP_SERVER_URL=http://localhost:8765/mcp uv run python scripts/probe_mcp.py "$(cat .user_token)"`
(no `--tool` lists tools). Tool names are `<dp_slug_underscored>_execute_query`/
list`, if the pair is absent, the FAA wiring is fine and the fix is a DPG
deploy (bump the deployed MCP server past the branch that added the DP to its
`data_products` list), NOT a FAA change.

### `default_tools` per-server gating + stale "tool missing" diagnostics

Which of `execute_query`/`get_output_ports`/`value_help` an MCP server exposes is
gated PER SERVER by the manifest's `default_tools` list, intersected with
`_ALL_DEFAULT_TOOLS` (DPG `registry/loader.py:57`). That manifest lives in the
DPG repo, NOT FAA: `data-product-gateway/.../registry/mcp-servers/<env>/<server>.yaml`
(one file EACH for dev/int/prod — do not assume they match; check all three).
Tools register ONCE at gateway startup (`register_tools` in `loader.py`), so a
`default_tools` change needs a gateway-pod restart/redeploy AND an FAA restart
(FAA caches `tools/list` at discovery), NOT the ~30s ConfigMap fast-patch.

Before drafting an "add the one-liner to `default_tools`" fix from a findings/
diagnostic doc that reports a tool (e.g. `value_help`) missing, VERIFY the claim
is not stale against the actual DPG repo state — a diagnostic written off an old
trace often lags the manifest. Check the line on `main`
(`git show main:<path> | grep value_help`) and when it landed
(`git log -S value_help -- <path>`); a `git diff main...HEAD -- <path>` shows
whether the branch even changes it. If the tool is ALREADY in `default_tools` on
`main`, the config half is done and the real gap is deployed-pod lag or FAA
discovery caching — the fix is a redeploy/restart plus correcting the stale doc,
NOT a config PR. Probe the DEPLOYED server's live `tools/list` (below) to decide
which half is actually unresolved before writing the plan.

Reaching a LIVE query for verification when off SAP VPN: local firefly-proxy
cannot run off-VPN (`npm install` fails — Artifactory `int.repositories.cloud.sap`
unresolvable, no node_modules), BUT the DEPLOYED DPG MCP server (dev Kyma, the
`MCP_UPSTREAM_URL` env var, a public `*.kyma.ondemand.com/mcp` URL) is reachable
over the public internet and fronts a deployed firefly-proxy — so an end-to-end
live agent call IS achievable from a laptop without VPN. The only live-access
blocker is then a FRESH FAA user token: `.user_token` is short-lived (~1h) and
auto-refreshed ONLY while `login_server` (:5000) is up; a stale-dated token means
no stack is running. Decode `.user_token` (`exp` claim vs now) to confirm before
probing. Getting a fresh token needs an interactive XSUAA browser login (start
the stack with `uv run python tests/local_execution/run_app.py`, open
`http://localhost:5000/login`) or a Bruno-pasted Bearer — both user actions; ask
rather than trying to mint one.

### Headless end-to-end smoke test against the DEPLOYED DPG MCP server (verified recipe)

When a valid `.user_token` already exists (decode `exp` vs now first), run the
WHOLE agent live off-VPN through the deployed dev Kyma DPG server — no browser
login, no local firefly-proxy. Two settings are load-bearing and easy to miss:

- `DP_MCP_EXCHANGE_MODE=direct` — makes `dp_mcp_proxy` do the XSUAA jwt-bearer
  exchange ITSELF using the DPG `mcp`-service creds (`DPG_CLIENT_ID/SECRET`,
  `DPG_AUTH_URL`) and forward to `MCP_UPSTREAM_URL`. The DEFAULT `destination`
  mode instead needs Destination-Service creds; pick `direct` for the
  reproduce-the-exchange-locally path. Both credential sets come from Vault
  `local-dev`.
- `ENVIRONMENT=dev` — enables an `enabled_envs={"dev"}` DP (e.g. bud_fc); the
  stack does not set it for the parallel path.

Steps (all in the devcontainer, from the FAA repo dir):

    # 1. Vault secrets -> export file (gives DPG_*, MCP_UPSTREAM_URL, XSUAA_*, JWT_*)
    uv run fetch_secrets vault_manifest.yaml --profile local-dev \
      --write-exports --export-file-path /tmp/.mcp_env.sh

fetch_secrets int-value crash (real framework bug, not an env failure): if the
export step dies with `TypeError: str expected, not int` (in
`set_environment_variables`, `os.environ[...] = value`) or `AttributeError:
'int' object has no attribute 'replace'` (in `_write_export_to_file`), the cause
is a Vault value stored as an int (`mcp_timeout` -> `MCP_TIMEOUT`) and the
submodule writer assuming str. This crash also blocks the stack launch (same
`SecretDistributor.set_environment_variables` path runs at startup). Fix both
sites in `submodules/AI_Factory_Template/.../secrets_client/fetch_secrets.py`
with `str(value)` coercion (the `os.environ` set and the `escaped_value =
value.replace(...)` line). It is a submodule edit outside most ticket scopes —
apply it to unblock, leave it UNCOMMITTED, and flag it to the user to upstream
(or store `mcp_timeout` as a string in Vault) rather than folding it into a
feature commit. A blank `.env` Vault bootstrap (`VAULT_ROLE_ID=` empty, no
`VAULT_SECRET_ID`) is a DIFFERENT failure: fetch_secrets falls back to
interactive OIDC and dies headless with `/dev/tty` `No such device` — that one
is the user's to populate, not a code fix.
    # 2. Launch headless, reusing .user_token (front on 8000 for curl/Bruno)
    source /tmp/.mcp_env.sh
    nohup env PARALLEL_STACK=1 DSP_PROXY_PORT=8080 AGENT_PORT=8001 \
      FRONT_PROXY_PORT=8000 DP_MCP_PROXY_PORT=8765 DP_MCP_EXCHANGE_MODE=direct \
      USER_TOKEN_FILE=$PWD/.user_token AGENT_LANDSCAPE=dev ENVIRONMENT=dev \
      uv run --no-sync python tests/local_execution/run_app.py > /tmp/faa_stack.log 2>&1 &

What proves each layer (grep /tmp/faa_stack.log): `principal propagation OK` for
dsp+ina; `MCP token exchange OK — incoming=aud=[...fin-analyst-agent...]
exchanged=aud=[...data-product-gateway...]` (the OAuth2UserTokenExchange the
design hinges on); `front_proxy ready`. Then probe the live toolset
(`MCP_SERVER_URL=http://localhost:8765/mcp uv run --no-sync python
scripts/probe_mcp.py "$(cat .user_token)"` — no `--tool` lists names+schema) and
finally `POST http://localhost:8000/v2/serve?request_identifier=<id>` with
`{"data":"<question>","data_product":"<slug>"}`. A 200 whose payload carries real
figures + the `analyticSlice`/`[ANSWER_ANALYTIC_SLICE]` echo (dataProduct ==
slug) is the pass. Confirm the answer's measures are POPULATED ones for the dev
landscape (per the DP's SKILL.md dev-coverage note) so an empty measure doesn't
look like a skill failure. Tear down via `/proc` (no `pkill`): match
`run_app.py|dsp_proxy.py|dp_mcp_proxy.py|front_proxy.py|login_server.py` in
`/proc/<pid>/cmdline`, `kill -9`, then re-check the ports are free; remove
`/tmp/.mcp_env.sh` (it holds live secrets).

Stray proxy from a browser-login flow: when the user does an interactive
`localhost:5000/login` to refresh an expired `.user_token`, that login flow
leaves its OWN `login_server.py` + `dp_mcp_proxy.py` running, and that proxy was
NOT started with `DP_MCP_EXCHANGE_MODE=direct` — so a `probe_mcp.py` through it
404s on `tools/list` (wrong-audience, the DEFAULT `destination` mode). Do not
debug the 404 as a wiring bug: kill the stray `login_server.py`/`dp_mcp_proxy.py`
first, then relaunch the full headless stack yourself with
`DP_MCP_EXCHANGE_MODE=direct` (which brings up its own correctly-configured
proxy). `.user_token` is ~1h and the parallel stack does NOT refresh it (no
login_server), so decode `exp` before every relaunch; ~2 min left is not enough
for a 50-100s query run — ask for a fresh browser login rather than racing it.

### Classify a `/v2/serve` answer: failed call vs empty result vs real data

A `0 EUR` / "no postings" answer is NOT evidence the backend is broken, and a
non-zero figure is NOT proof the formatting rule fired. Do not judge either from
the answer prose — read the MLflow trace tool spans. Fetch the trace by its
`trace_id` (in the `/v2/serve` response) via the CLAUDE.md Databricks recipe
(mint an OAuth token from `~/.databrickscfg` M2M creds, `MLFLOW_TRACKING_URI=
databricks`, `client.get_trace(tid)`), then inspect each `execute_query` /
`value_help` span's `outputs`:
- `success:true, record_count:0, data:[]` = successful-but-EMPTY (genuine no
  postings for that slice) — the agent narrating "0 EUR / no data" is CORRECT,
  not a failure. The sample `P&L_Sample_Questions.xlsx` prompts deliberately hit
  sparse slices (specific CC/account/month), so expect many legitimate zeros.
- `success:true, record_count:>=1, data:[{...figure...}]` = real data; the raw
  value in the span (e.g. `ACTUALS: -2311104613.86`) is what the agent SHOULD
  have formatted.
- An HTTP non-200 / `status != success` on the span (or the dp_mcp_proxy log
  showing a 4xx/5xx to the upstream) = an actual failed call.
To pick a slice that returns a LARGE non-zero figure (to exercise comma/scale
formatting), query a whole-company full-year rollup (e.g. "total Personnel
Expenses for the whole company in FY2025") rather than a narrow CC/account/month.

### A skill-prompt change needs a stack RESTART, and prompt-only may not stick

Skills are read ONCE at startup; after editing a `skills/<slug>/SKILL.md` you
MUST tear down and relaunch the stack (stale-stack trap) before re-probing —
otherwise you are testing the old prompt. Confirm the reload by checking the
trace: the `SkillsMiddleware.before_agent` span echoes each skill's
`faa_prompt_version`, and the agent's `read_file` of the SKILL.md shows the new
content.

Even correctly reloaded, a PROMPT-ONLY formatting rule does not reliably override
the agent model's defaults. Verified live (gpt-5.5): the number-format house-
style rules landed for millions (`€388.8m`), the mandatory `+` sign, and growth-
rate neutrality (`+413.4%`, no favorable/unfavorable), but the BILLIONS scale
kept rendering `-2.31B EUR` (forbidden `B` + ISO-after-value) through three
escalating prompt attempts — adding a `-€2.3bn` worked example and a literal
"`-2.31B EUR` is forbidden" callout did not fix it. Stop sharpening the same rule
after ~3 attempts; a bullet-proof fix for a format the model resists is a
deterministic OUTPUT post-processor (a regex filter in the response path), not
more prompt text. Record the residual honestly rather than presenting an
unreliable prompt rule as fully working.

## DPG firefly-proxy MCP path (alternative transport — CFAAI-858)

There are now TWO InA transports; do not conflate them with the OData/direct-InA
split above:

- FAA's OWN direct-InA path: `connectors/ina_connector.py` POSTs the full SAC
  payload to DSP `/v2/GetResponse`. `build_payload(variables=)` NOW emits an
  `Analytics.Variables` block when passed a non-empty mapping (input parameters
  ARE supported on this path — see `references/ina-view-input-parameters.md`);
  omit/empty keeps the payload byte-identical for variable-less cubes.
- DPG firefly-proxy path (data-product-gateway PR #476, merged): DPG's
  `connectors/ina.py` proxies to a separate `firefly-proxy` microservice
  (`POST /query {data_source,row_dimensions,column_dimensions,filters,sort}`,
  `GET /metadata`, `POST /value-help`), exposed to clients as MCP tools
  `{slug}_execute_query`/`{slug}_value_help`/`get_output_ports`. Cube identity
  lives in `registry/data-products/<env>/*.yaml` (`ina_service/object_name/
  schema_name/instance_id/default_hierarchies`).

InA input parameters (SAC "Variables") for parameterized cubes (e.g. BUD/FC with
BUDGET_VERSION/FORECAST_VERSION/CONTENT_AREA/REPORTING_VIEW) ARE now wired on the
DPG firefly-proxy path — verified live: the deployed dev Kyma DPG server exposes
them as first-class OPTIONAL args on the per-DP `<slug>_execute_query` tool
schema, each defaulting to the documented value (BUDGET_VERSION 'Current Budget',
CONTENT_AREA 'FINANCE', FORECAST_VERSION 'Current Forecast', REPORTING_VIEW
'PAC') when omitted, so the agent sets only the ones the question needs. This is
a server-side capability keyed to the DEPLOYED MCP server version (confirmed on
serverInfo `Financial Analyst Agent MCP` v3.4.x) — a raw firefly-proxy clone or
an older deployed server may still lack it. So determine variable support by
probing the LIVE tool schema (`scripts/probe_mcp.py`, no `--tool` lists tools +
their inputSchema), NOT by reading a local firefly-proxy/DPG checkout's
allowed-keys list, which can lag the deployed server.

### value_help tool missing from the live toolset is NOT a `default_tools` omission

When the agent reports "no value_help tool", do NOT assume the fix is adding
`- value_help` to the MCP-server manifest `default_tools`. On the FAA manifest
(`registry/mcp-servers/{dev,int,prod}/financial-analyst-agent-mcp.yaml`)
`value_help` has been present in `default_tools` on `main` since d4cbf6ef
(2026-09-15). The real gate is in `registry/loader.py` `_register_tools()`:
`value_help` is registered for a product ONLY IF `"value_help" in enabled_tools
AND any(isinstance(op.connection, InaConnection) for op in dp.output_ports)` —
i.e. it is InA-ONLY, keyed on a product actually having an InA output port. So
a live `tools/list` showing only `{slug}_execute_query` + `get_output_ports`
(no `{slug}_value_help`) means EITHER (a) the deployed pod predates the InA-port
conversion / value_help enablement and needs a REDEPLOY (not a config PR), OR
(b) the port YAML does not deserialize to `InaConnection` so the guard is False.
Verified live 2026-09-30: deployed dev server `Financial Analyst Agent MCP`
v3.4.4 served exactly 4 tools, NO value_help, even though all three FAA products
are InA ports (`connection: ina_service: dev-firefly-proxy-serving`) AND
value_help is in `default_tools` on main — pointing at a stale deployed build.
Diagnose deployed-version-vs-main FIRST; the manifest one-liner is already done.

### Live-probing the deployed DPG MCP server needs the local dp_mcp_proxy (direct mode) — a raw token 404s

Hitting `https://dev-financial-analyst-agent-mcp.c-4e68cea.kyma.ondemand.com/mcp`
directly with a raw FAA `.user_token` returns HTTP 404 from istio-envoy (wrong
audience; NOT 401). Probe THROUGH the local exchange proxy instead. The proxy
launched via `docker exec -d`/`nohup &` inside the devcontainer helper DIES when
the exec shell exits — start it as a Hermes-tracked `terminal(background=True)`
process wrapping `docker exec -i <cid> ... dp_mcp_proxy.py` so Hermes owns its
lifetime, then probe in a separate call:
  DP_MCP_EXCHANGE_MODE=direct DP_MCP_PROXY_PORT=8765 + DPG_CLIENT_ID/SECRET/
  DPG_AUTH_URL + MCP_UPSTREAM_URL (all from `fetch_secrets ... --profile
  local-dev --write-exports`), then
  `MCP_SERVER_URL=http://localhost:8765/mcp uv run --no-sync python
  scripts/probe_mcp.py "$(cat .user_token)"` (no `--tool` lists names+schema).
A bare POST to :8765/mcp returns 406 when the proxy IS up (needs MCP Accept
headers) — 406/200 = up, 000 = not listening. The correct upstream host is
`dev-financial-analyst-agent-mcp...` (the Bruno `dev-financial-analyst-mcp...`
shorthand 404s). Note: the deployed v3.4.4 exposes BUD/FC InA scenario params
(BUDGET_VERSION/CONTENT_AREA/FORECAST_VERSION/REPORTING_VIEW) as optional args
on `profit_and_loss_budget_forecast_execute_query`.

### "Output port not published" / placeholder GUID + instance_id — is querying blocked?

DPG has NO output-port-publication gate anywhere in the InA query path. `registry/
loader.py` loads ports purely from local YAML (no Collibra check); `connectors/
ina.py` resolves the cube ONLY by `data_source: {object_name, schema_name,
instance_id}` sent to firefly-proxy. So an unpublished Collibra output port, or a
placeholder/guessed `output_port_guid`, CANNOT by itself reject `execute_query` —
the GUID is only a registry lookup key + a Collibra display link. Do not chase the
port GUID as the cause of a query failure; it can only bite (a) the Collibra link
shown to users, or (b) schema discovery IF that ever routed through Collibra (for
InA ports it does not — schema comes from firefly `/metadata`).

The only cube-identity field that can actually break resolution is `instance_id`.
firefly-proxy `toFireflyDataSource()` (in `src/query-service.ts`) emits it as
`{DataSource:{Type:"InAModel",SchemaName,ObjectName,InstanceId}}` and includes
InstanceId ONLY `if (instanceId)` — so blanking/omitting it makes DSP resolve the
cube by `SchemaName`+`ObjectName` alone. That is the clean circumvention when a
placeholder instance_id is suspect. Before assuming a placeholder is wrong, check
whether a WORKING sibling DP in the SAME DSP space uses the same instance_id
(grep the sibling `registry/data-products/<env>/*.yaml` and the firefly-proxy
README curl example): instance_id keys the space/deployment instance, not the
individual model, so same-space cubes legitimately share it — the "placeholder"
comment is often over-cautious, not a real defect.

firefly-proxy specifics (repo at ~/VSCodeRepos/firefly-proxy, TS/Node wrapping
@sap/firefly): the InA query is built in `src/query-service.ts` `runQuery()` via
SDK convenience commands (`cmds.moveDimensionToAxis`, `addEqualityFilter`,
`applyFilters`/`applySort`); no variable was set in the pre-parameterized clone.
`QueryRequest` in `src/types.ts` historically had no `variables` field;
`Variables`/`VirtualDataSourceVariableValues` appear in the advertised
capabilities list (`src/ina-capabilities.ts`). The deployed server now DOES pass
variables (probe confirms the tool-schema args), so a clone that lacks them is
BEHIND the deployment, not the source of truth. If you must add/inspect variable
wiring in the clone: extend `QueryRequest`, add an `applyVariables()` step in
`runQuery()` before `processQueryExecution`, using the SDK variable API (a
variable-container accessor on `IQueryModel`, sibling to
`getFilter().getDynamicFilter()`). CANNOT confirm the exact @sap/firefly variable
method from a Mac clone: `npm install` fails off-VPN (Artifactory
`int.repositories.cloud.sap` unresolvable), so node_modules/.d.ts are absent.

## FAA-as-DPG-MCP-client scaffold (CFAAI-858 pattern)

When wiring FAA to consume a DP over the DPG MCP path:
- The MCP client belongs behind a fail-closed gate mirroring the INA gate: a new
  `connectors/dpg_mcp_client.py` with `dpg_mcp_enabled()` requiring BOTH a
  configured `DPG_MCP_SERVER_URL` AND the active `AGENT_LANDSCAPE` in
  `DPG_MCP_ENABLED_LANDSCAPES` (default dev). Guard the `langchain-mcp-adapters`
  import (NOT a declared FAA dep — `mcp`/`fastmcp` are only in uv.lock behind
  AI_Factory_Template's server extras) so the module imports cleanly without it
  and yields zero tools.
- `get_all_tools()` is SYNC and runs once at startup, but the user bearer lives
  on the per-request `user_token_var` ContextVar. So MCP tools loaded at startup
  must forward the CURRENT request's token at CALL time, not connection time —
  this per-request-token forwarding is the key open design decision, not solved
  by a startup `asyncio.run(load_dpg_tools())` bridge alone.
- `bud_fc` DP registration in `data_products/registry.py` + a
  `bud_fc_analyst_ina` prompt stub are the surviving pieces of the old
  direct-InA plan; on the DPG path DPG owns cube identity + variables.
- The two InA transports are NOT mutually exclusive at wiring time: a DP routed
  "MCP-only" by design/registry comment can still be served via the direct-InA
  path by adding an `INA_CUBES[slug]` entry — this session wired `bud_fc` that
  way and queried it live through `query_ina`. When the mandated MCP transport
  is down (DPG server 503 "no healthy upstream", a platform-side outage FAA
  cannot fix), the direct-InA path is the working fallback for local dev IF the
  cube's DataSource + variables are discoverable via the local dsp_proxy. Do not
  treat a registry "queried via DPG MCP, NOT direct-InA" comment as a hard
  blocker to a direct-InA cube spec.

### Is a gated tool layer actually active locally RIGHT NOW? (diagnostic)

Both INA and DPG-MCP are fail-closed gates keyed on `AGENT_LANDSCAPE`, so "is it
on" is answered by evaluating the gate, not by reading the code. Live-check
instead of guessing:

    uv run --no-sync python -c "from fin_analyst_agent.connectors.dpg_mcp_client import dpg_mcp_enabled, dpg_mcp_server_url, _active_landscape, _enabled_landscapes; print(_active_landscape(), bool(dpg_mcp_server_url()), sorted(_enabled_landscapes()), dpg_mcp_enabled())"
    uv run --no-sync python -c "from fin_analyst_agent.tools import ina_tools_enabled; print(ina_tools_enabled())"

`--no-sync` avoids `uv run` silently re-syncing the venv to the lock mid-probe
(it prints "Uninstalled N / Installed M" and can change import results under you).
A bare `python -c` does NOT auto-load `.env`, so it reflects the process env only
— cross-check by dumping the `.env` KEYS (`grep -oE '^[A-Z_]+=' .env`): if
`AGENT_LANDSCAPE`/`DPG_MCP_SERVER_URL`/`*_ENABLED_LANDSCAPES` are absent from both
`.env` and the shell, the layer is OFF locally regardless of the code being
present. DPG needs BOTH landscape-in-set AND a URL; INA needs only
landscape-in-set. Confirm the enabling direction too:
`AGENT_LANDSCAPE=dev DPG_MCP_SERVER_URL=... uv run --no-sync python -c ...` should
flip `dpg_mcp_enabled()` True.

- Ambient-dep trap: `langchain-mcp-adapters` can be importable in `.venv` today
  (e.g. 0.3.0) yet be in NEITHER `pyproject.toml` nor `uv.lock` (only `mcp` is
  locked, transitively). It "works now" but a clean `uv sync` removes it, after
  which `load_dpg_tools()` logs "not installed" and returns `[]` — the DPG path
  fails closed. Before reporting DPG as usable, verify the adapter is a DECLARED
  dep (grep pyproject.toml AND uv.lock), not just currently present; if
  undeclared, the real fix is adding it + `uv sync` in the devcontainer.
- Reading a revert vs. newer branch work: a revert of the MCP-only migration
  (restoring the pre-migration tree) does NOT delete DPG-MCP code added AFTERWARD
  on a feature branch that merged post-revert main. When MCP code is present on
  the current branch despite a known revert, `git log --oneline` the branch:
  scaffold added after the revert commit is net-new work, not reverted leftovers.
  Check what branch you are on before concluding the revert "removed" MCP.

## FAA host/devcontainer execution notes

- FAA package is NOT importable via bare `python -c` in the devcontainer — use
  `uv run python -c ...` (activates the editable install). Bare python gives
  ModuleNotFoundError: fin_analyst_agent.
- To check an optional dep is present on the host without importing: `python3 -c
  "import importlib.util as u; print(bool(u.find_spec('mcp')))"`.

### Local stack: the stale-stack trap and headless relaunch

- The stack (`uv run python tests/local_execution/run_app.py`) reads code and env
  ONCE at startup. Editing a source file or `.env` does NOTHING until you
  restart. An unexpected response — an old error the code no longer produces, or
  a `.env` toggle that "isn't taking effect" — is most often an old stack, not a
  code bug. Confirm what is actually running (which PID/branch) before debugging
  the code; after any edit that must take effect, tear down and relaunch.
- Relaunch WITHOUT an interactive browser login via the `PARALLEL_STACK=1` path:
  it reuses a fresh `.user_token` and skips login_server. Set every port
  explicitly; put front_proxy on 8000 so an existing Bruno `base_url` works:

      nohup env PARALLEL_STACK=1 DSP_PROXY_PORT=8080 AGENT_PORT=8001 FRONT_PROXY_PORT=8000 \
        USER_TOKEN_FILE=<abs>/.user_token \
        AGENT_LANDSCAPE=dev INA_ENABLED_LANDSCAPES=dev ENVIRONMENT=dev \
        uv run --no-sync python tests/local_execution/run_app.py > /tmp/faa_stack.log 2>&1 &

  It principal-propagates the reused token to the `dsp`/`ina` destinations at
  startup ("principal propagation OK") — that alone proves the InA transport is
  live before you query. Decode `.user_token` `exp` vs now first; a stale token
  fails the preflight. `run_app.py` does NOT set ENVIRONMENT, so pass
  `ENVIRONMENT=dev` to enable an `enabled_envs={"dev"}` DP locally — but only if
  its `skills/<slug>/SKILL.ina.md` exists, else the skill loader crashes startup
  with FileNotFoundError (the file may live only on another branch).
- Disable the DPG MCP path cleanly by leaving `DPG_MCP_SERVER_URL` unset (the
  gate is fail-closed on a missing URL) and `DPG_MCP_ENABLED_LANDSCAPES=none`;
  do NOT hack the module constants (renaming the env-var-name constant to
  "none" makes the gate read a nonexistent env var, not set a value).
- Minimal container has NO `ps`/`pkill`. Manage processes via `/proc`: match on
  `tr '\0' ' ' < /proc/<pid>/cmdline` then `kill -9`; to free a stuck port, map
  port -> listen inode in `/proc/net/tcp` (state `0A`, hex port) then find the
  PID whose `/proc/<pid>/fd` has `socket:[<inode>]`. A lingering
  `multiprocessing.spawn` uvicorn worker is the usual reason a port stays OPEN
  after killing the run_app tree. Run stack/cleanup commands from the FAA repo
  dir — the devcontainer helper selects the container by current git top-level,
  so a sibling repo (data-product-gateway) misses the FAA container.
- Bruno request docs live in `.bruno/*.bru` (front_proxy injects the Bearer, so
  no auth needed for localhost). Keep the request's default query on a POPULATED
  fiscal year and its docs accurate about which transport is used — a request
  whose docs claim "MCP required / not functional" after the direct-InA path
  works will mislead the next run.
- A `/v2/serve` "no healthy upstream" (Envoy 503) reply to a Bruno request is
  FIRST a Bruno-environment mistake, not a code/config bug: the active Bruno
  environment is "Dev" (base_url = the deployed Kyma DPG-MCP URL, whose
  firefly-proxy upstream is down) instead of "Local" (http://localhost:8000, the
  direct-InA stack). Check the environment dropdown before touching code. This
  error text comes from the DEPLOYED server (it is nowhere in the FAA codebase —
  grep confirms), so it can only appear when the request left localhost.

## Verify (in the devcontainer)

- `pytest tests/unit_tests -q` green including new registry/cube/allowlist tests.
- Startup logs `Loaded system prompt name=<stem>_ina ...` for the enabled slug.
- `POST /v2/serve` with `{"data_product": "<slug>"}` is accepted in the enabled
  landscape and rejected (400) outside it (governance gate).
- Scope the commit: `uv run`/`uv sync` mutate `uv.lock` as a side effect
  (re-resolving the AI_Factory_Template submodule's transitive deps —
  databricks-sql-connector specifiers, fastmcp bounds, langgraph entries), churn
  that is UNRELATED to a source-only DP-wiring change. Before committing, inspect
  the `uv.lock` diff; if the feature added no real dependency, `git checkout --
  uv.lock` and confirm the code still imports with the lock untouched. Do not
  bundle that lock churn into the feature commit. Likewise the LFS PDF/parquet
  smudge drift is not a real change — never stage it.

See `references/ina-view-input-parameters.md` for wiring + verifying cubes that
take SAC "Variables" (forecast/budget version) on the direct-InA path.

See `references/swapping-the-analytic-model.md` for the recurring AM-SWAP task
(re-point an existing DP at a new analytical model): the AM id lives ONLY in the
DPG `connection:` block, a swap is NOT just `object_name` (schema/instance_id/
hierarchy wire names change and come from a live `/metadata?expand=hierarchies`
call), firefly-proxy needs no code change, and FAA carries stale COSMETIC
references (deep-link URLs, allowed_assets, skill forbidden-strings + hierarchy
examples) to update in a separate PR.

See `references/probing-dp-queryable-surface.md` for the read-only verification
workflow: enumerating what a DP can query (get_output_ports measures/dimensions/
hierarchies, value_help member search), answering "can the agent see node X?" by
escalating `/v2/serve` framing, and the raw-`execute_query` `hierarchy_node`
filter 502 pitfall (fetch real figures through the agent, not hand-built raw MCP
calls).
