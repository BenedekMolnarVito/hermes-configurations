---
name: faa-prodsteer-am-swap
description: "Swap a DPG data product's InA analytic model to a new one."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [FAA, DPG, data-product, InA, analytic-model, swap]
    related_skills: [dpg-data-product-registry, faa-data-product-wiring, faa-analyst-skill-prompt-editing, faa-devcontainer-execution]
---

# FAA / DPG Analytic-Model Swap

Swap an existing data product's InA cube to a NEW analytic model (AM) while
keeping the same DPG slug. Recurring task; verified on CFAAI-1069 (Product
Steering: old `3AM_PRODSTEER_TCO_PHIL_SOLAREA` -> new `3AM_PRODUCT_STEERING_01`).

The AM id lives in the DATA-PRODUCT-GATEWAY repo, NOT in FAA and NOT in
firefly-proxy. FAA is MCP-unaware of the cube; firefly-proxy resolves the cube
dynamically from the DataSource DPG sends it. So the swap is a DPG registry edit
plus FAA cosmetic/behavioral reference cleanup.

## When to Use

- A ticket says "wire/switch <DP> to new analytic model <3AM_...>" and the DP is
  already an InA/firefly-proxy port in DPG.
- NOT for onboarding a brand-new DP (use `dpg-data-product-registry`), nor for
  changing answer FORMAT only (use `faa-analyst-skill-prompt-editing`).

## Making the DP an 'alpha' source in the UI (fin-analyst-agent-ui)

When a model swap turns a product into early-access, mirror the EXISTING alpha
DP (bud_fc). The alpha behavior is driven ENTIRELY by `src/app/dataProducts.ts`
— `SettingsDialog.tsx` already renders the Alpha badge + notice generically for
ANY `isAlpha` DP, so NO component change is needed. Two (or three) edits:
- The DP entry: add `isAlpha: true`.
- `DEFAULT_ENABLED_SLUGS`: REMOVE the slug so it is off-by-default (user opts in
  via Settings) — this is what makes it 'alpha' alongside the badge.
- `DEFAULT_DATA_PRODUCT`: if it pointed at the now-alpha slug, repoint to a
  non-alpha default-enabled slug (e.g. pnl). NOTE it may be UNUSED by App.tsx
  (the active DP derives from the enabled set) — grep before assuming it matters.
- Fix the stale `App.tsx` comment that enumerates the default set.
Verify: `npx tsc -b` (typecheck), `npx vite build` (one-shot but the agent's
server-heuristic flags `vite` — run it background+notify), `npx vitest run`. A
pre-existing `streamUtils.test.ts` failure on main is UNRELATED — confirm by
stashing your edits and re-running. Do NOT stage the `test-results/` dir vitest
creates.

## Git / PR workflow (both repos are GitHub Enterprise github.tools.sap)

`gh` is authed to the enterprise host; prefix commands with `GH_HOST=
github.tools.sap`. Per-repo, when asked for a PR off fresh main: `git stash` any
in-progress edits, `git checkout main && git pull --ff-only origin main`, `git
checkout -b feat/CFAAI-<n>-...`, `git stash pop`, finish edits, commit ONLY the
intended files, push, `GH_HOST=github.tools.sap gh pr create --base main`. DPG
and FAA-UI are SEPARATE repos -> SEPARATE PRs. DPG has no devcontainer/LFS
constraint (that is FAA-app-only); the UI is a plain Vite/React repo, also host-
runnable. The `output_port_guid` is the real Collibra port GUID (CFAAI-1069:
019edcc0-...) — distinct from `instance_id` (cube pin, still blank) and
`data_product_guid` (DP-level); confirm which field a supplied GUID is before
writing it.

## Where the model id lives

`data-product-gateway/src/data_product_gateway/registry/data-products/{dev,int,prod}/<slug>.yaml`
-> the InA `connection:` block. One file per env; edit all three.

## DPG edit (the actual swap)

In each env's `<slug>.yaml` `connection:` block change:
- `object_name` -> the new AM id (e.g. `3AM_PRODUCT_STEERING_01`).
- `schema_name` -> the new model's Datasphere space (ASK; may be unchanged).
- `instance_id` -> per-env GUID for the NEW model. The old GUID belongs to the
  OLD model and mis-pins the cube. firefly resolves by schema+object alone
  (`InstanceId` emitted only `if (instanceId)` in `toFireflyDataSource`), so
  BLANK it (`instance_id: ""`) with a `TODO(<ticket>)` until the new per-env
  value is confirmed from live InA metadata. Do NOT keep the old GUID.
- `default_hierarchies` -> the new model's per-dimension hierarchy WIRE NAMES.
  These are keyed by business DIMENSION name and almost always change with a new
  AM. Keys that are FLAT on the new model (no hierarchy) must be OMITTED, not set
  to a UI label like `"Flat presentation"` (a label is not a wire name and
  firefly will try to resolve it -> 502).
- Keep `ina_service` per env (`dev-/int-/prod-firefly-proxy-serving`).
- `data_product_guid`/`output_port_guid`: usually unchanged (same governed
  DP/port, only the cube identity moves) — but if the new AM was onboarded as a
  NEW Collibra port, the ticket/user may hand you a NEW `output_port_guid`. When
  it DOES change, you MUST also run the mcp-server manifest audit below, or you
  orphan every custom tool wired to the old GUID.

Validate each file loads AND passes the Pydantic model (from the DPG repo):

    for env in dev int prod; do PYTHONPATH=src uv run --no-sync python -c "
    import yaml; from data_product_gateway.registry.models import DataProduct
    b=yaml.safe_load(open('src/data_product_gateway/registry/data-products/'+'$env'+'/<slug>.yaml'))
    s=next(iter(b)); d=dict(b[s]); d['data_product']=s
    c=DataProduct(**d).output_ports[0].connection
    print('$env',type(c).__name__,c.object_name,c.schema_name,repr(c.instance_id),c.default_hierarchies)"; done

The `mcp_server experimental UserWarning` is benign.

## mcp-server manifest audit (REQUIRED when output_port_guid OR object_name changed)

After the swap, grep every `registry/mcp-servers/{dev,int,prod}/*.yaml` for the
OLD `output_port_guid` AND the OLD `object_name`:

    grep -rnE '<OLD_GUID>|<OLD_MODEL>' src/data_product_gateway/registry/mcp-servers/

Two places go stale and MUST be fixed in the SAME PR as the swap:
- `custom_tools:` entries whose `output_port_guid` points at the OLD port. The
  loader (`tool_builders.build_custom_tool`) resolves the tool via
  `registry.get_port_by_guid(ct.output_port_guid)`; a GUID no longer in the port
  index returns `None` -> the tool is SILENTLY skipped (logged error, invisible
  in tools/list), while its `entity_set` still names the retired model. Fix =
  either repoint the GUID+entity_set to the new port/model, or REMOVE the custom
  tool. Prefer REMOVE when a sibling env (usually dev) already dropped it and
  serves the InA port through the generic `execute_query`/`value_help` tools —
  match the leanest existing env rather than re-wiring an unverifiable
  parametrized InA `entity_set`.
- The server `description:` string embeds per-product Collibra asset links
  (`.../asset/<GUID>`); update the Product Steering link to the new GUID.

The mcp-server `description`/`custom_tools` are a multi-line double-quoted scalar
with `- ` bullets inside — the editor's YAML LSP mis-flags "Implicit keys / Map
keys must be unique" on the bullet lines. These are FALSE POSITIVES; confirm the
file is valid with `yaml.safe_load`, not the LSP diagnostics.

Note: `dpg-data-product-registry` says the DP-YAML and mcp-server tool wiring are
normally SEPARATE PRs. The exception is a GUID/model swap that ORPHANS an
existing custom tool — that breakage is a direct consequence of the swap, so fix
it atomically in the swap PR, not a follow-up.

## FAA reference cleanup (does NOT affect query correctness, but keep in sync)

FAA never names the cube to the MCP server, so the query works without any FAA
change. But FAA carries references that go stale:
- `src/fin_analyst_agent/data_product_refs.py` — DSP databuilder deep-link URLs
  embed the old `<SPACE>/<MODEL>` path; update MODEL. The Collibra GUID + SAC
  shortcut are separate asset ids — only change them if the ticket/user gives new
  ones.
- `src/fin_analyst_agent/data/allowed_assets.json` — legacy OData allowlist
  `(space_id, asset_name)`; update asset_name. Dead path on the InA cube but keep
  it consistent.
- `skills/<slug>/SKILL.md` — the behavioral surface. Update: the
  "DO NOT USE"/forbidden-string asset name; every dimension-name-keyed rule,
  worked example, and the canonical dimension palette. A new AM typically RENAMES
  dimensions (CFAAI-1069: `PACCFUNC`->`FUNCTIONAL_AREA_ID` now flat;
  `SOLD_PRODUCT_ID`->`STEERING_PRODUCT` for name/filter + `DERIVED_SOLUTION_AREA`
  for breakdown rows; new `PRODUCT_COSTING_COMPONENT` hierarchy `0000/TCO_B`).
  Bump `faa_prompt_version` (behavior-changing rename = MAJOR). Leave migration
  notes in-file explaining old->new so the next reader isn't confused.
- Cached hierarchy JSON (e.g. `data/derived_functional_area_hierarchy_*.json`)
  is from the OLD model; it is now stale. Flag it; a true refresh needs a live
  export of the new model's hierarchy.
- Member-name enrichment (`apps/member_resolver.py` `_DIM_TO_FAMILY`) maps OLD
  MDX dim tokens to member-index families. Adding new dims needs matching
  member-index files you likely don't have — LEAVE IT (wrong mapping is worse
  than none; it falls back to showing the raw code). Flag as follow-up.

## Dependency check (what you canNOT skip verifying)

- firefly-proxy: NO change. `config/cube.yaml` default is a P&L cube, but DPG
  overrides schema/object per request; the prodsteer cube is NOT hardcoded. Grep
  the clone to confirm (`3AM_PRODSTEER`/`3AM_PRODUCT_STEERING` appears only in
  docs). Its clone also can't `npm install` off-VPN, so it's not runnable anyway.
- FAA code: only the reference files above; no connector/tool change (FAA is an
  MCP client, cube identity is DPG's).

## Discovering the new model's connection details (hierarchies + instance_id)

Schema/instance_id/hierarchy wire names are NOT in any repo. Sources, in order:
1. The user/data team hands you the values (fastest; CFAAI-1069 path).
2. Live firefly-proxy `/metadata?schema=<SPACE>&object=<MODEL>&expand=hierarchies`
   from the firefly-proxy clone (needs SAP VPN + the 4 `.env` SAML/login secrets
   `JWT_CLIENT_ID/SECRET`, `DESTINATION_CLIENT_ID/SECRET` filled + SSO login).
   See `dpg-data-product-registry` -> `references/firefly-proxy-live-metadata.md`.
   `instance_id` is OPTIONAL and NOT returned by `/metadata`; `expand=hierarchies`
   is the ONLY way to get the per-dimension wire names.
Validate user-supplied hierarchy values: a hierarchy VALUE must be a wire name
(`0102/YKON/TCO`, `SOLAREA.2026`, `0000/TCO_B`), never a UI label. If a dim is
flat, omit it. Confirm any truncated-looking dimension name before writing it.

## CAVEATS (the ones that bite)

- INSTANCE_ID REVERT TRAP: when a reviewer flags `instance_id: ""`, the question
  is always about TEST COVERAGE, not about filling in a value. Never restore the
  old model's instance_id as a placeholder — it belongs to the retired cube and
  mis-pins the new model's cube resolution. Firefly resolves by schema+object
  alone (`InstanceId` emitted only `if (instanceId)` in `toFireflyDataSource`),
  so blank is correct and intentional. The fix for the reviewer's concern is to
  add tests: (a) assert `InaConnector(instance_id="").query(...)` omits
  `instance_id` from the POST `/query` `data_source` block, and (b) assert the
  inverse (non-empty instance_id IS carried through). Both confirm the omit
  behavior is deliberate, not accidental.
- DEPLOY GAP: the DEPLOYED DPG MCP server serves the OLD model until the DPG
  change is MERGED and the gateway pod REDEPLOYED. Local YAML edits do NOT change
  what the deployed server returns, and FAA caches `tools/list` at startup. So a
  live smoke test BEFORE deploy exercises the OLD cube and proves nothing about
  the new model — defer the live validation to post-merge+redeploy. A pass/fail
  pre-deploy is misleading.
- Live smoke test needs BOTH a fresh `.user_token` (decode `exp` vs now) AND
  non-empty Vault bootstrap creds in FAA `.env` (`HASHICORP_VAULT_ROLE_ID/
  SECRET_ID`) — blank ones make `fetch_secrets` fall back to interactive OIDC and
  die headless; the token-exchange proxy then can't load DPG `mcp` creds. A valid
  token alone is NOT enough.
- STASH/WORKTREE TRAP: if the user is switching branches/worktrees mid-session,
  the working tree shifts under you. A `git stash pop` can leave `<<<<<<<`
  conflict markers in `skills/<slug>/SKILL.md` (seen on CFAAI-1069: an existing
  stash `"new prodsteer wiring"` had the SAME work half-done). Symptoms: `patch`
  warns "modified since last read", two `faa_prompt_version` lines, `git status`
  shows `UU`. FIX: resolve BOTH conflict blocks (keep the new-model side), delete
  markers, re-check with `git grep '^<<<<<<<'`, then `git add` to clear `UU`.
  Re-verify branch/worktree with `git worktree list` + `git branch --show-current`
  before trusting any edit landed where you think.
- faa_prompt_version merge trap: if `origin/main` advanced past your branch's
  version, bump ABOVE main's number (CFAAI-1069: main was 4.0.0 while branch HEAD
  was 3.1.0 — bumped to 5.0.0). The loader reads the WORKING-TREE file; make
  working tree and index agree or the render check reports a stale number.

## Live-cube execute_query contract (verified on 3AM_PRODUCT_STEERING_01, MCP server 3.4.4)

When probing/validating the new AM through `product_steering_cost_execute_query`
(via the local dp_mcp_proxy on :8765), the on-wire call shape is NOT what the
prodsteer SKILL.md currently tells the agent. Confirmed by direct probe:
- There is NO top-level `measures` param (passing one -> pydantic "unexpected
  keyword argument"). Pass the measure as a FILTER clause:
  `{"kind":"measure","members":["ACTUALS_CY"]}` inside `filters`. The cube
  rejects the bare `ACTUALS` measure; use `ACTUALS_CY`.
- Product filter uses dimension `SOLD_PRODUCT_ID` with a LEAF `kind:list` filter
  (`{"kind":"list","field":"SOLD_PRODUCT_ID","values":["LPR823"]}`). The skill's
  instruction to filter products via `STEERING_PRODUCT`+`SOLAREA.2026` is WRONG
  on the live cube: value_help/filter on `STEERING_PRODUCT` 502s ("fieldName
  does not belong to the specified hierarchy"); the `hierarchy_node` filter on
  `LPR823.2026` returns 0 rows even for a populated year. Only the leaf list
  filter returns data. (Fix the skill prompt accordingly before re-eval.)
- GL TCO rows need `initial_drill_level` (plain `level` is ignored):
  `row_dimensions=[{"name":"GL_ACCOUNT_ID","hierarchy_wire_name":"0102/YKON/TCO","initial_drill_level":1}]`.
- Real TCO L1 nodes under `0102/YKON/TCO`: `0TCO-AM / 0TCO-IS / 0TCO-RE-USE /
  0TCO-SUP / 0TCO-OTHER` (no `0TCO-L1`, no `0TCO-RUS-EX`).

DATA-YEAR SHIFT TRAP: after a model redeploy the fiscal data can move years. On
3AM_PRODUCT_STEERING_01 (Oct 2026) `ACTUALS_CY` by FISCAL_YEAR = {2024:0, 2025:0,
2026:-2.178bn} — FY2025 is EMPTY cube-wide; real postings are FY2026. An eval
ground truth authored for FY2025 then scores the agent's faithful "0 EUR" as
wrong. Before blaming the agent or the prompt for zero/empty TCO answers, probe
`ACTUALS_CY` by FISCAL_YEAR to find where the data actually lives; a zero is only
meaningful once you've confirmed the slice is populated for SOME year.

## Verify

- DPG: `uv run --no-sync python -m pytest tests/unit_tests/registry -q` green;
  the per-env `DataProduct(**body)` load above prints the new object/hierarchies.
- FAA (in the devcontainer, `faa-devcontainer-execution`):
  `uv run --no-sync python -m pytest tests/unit_tests -q` green, and render the
  skill through the PRODUCTION loader to prove the version bump + new dimension
  names are in the on-wire text and no `{...url}` placeholder leaked:

      uv run --no-sync python -c "from fin_analyst_agent.data_products.registry import get_data_product; from fin_analyst_agent.langgraph_agent.prompts.skill_loader import load_skill_document; ls=load_skill_document(get_data_product('<slug>')); print(ls.version, ls.commit, 'STEERING_PRODUCT' in ls.full_text, '{collibra_metadata_url}' not in ls.full_text)"

- Scope the commit: NEVER stage LFS PDF/parquet smudge drift or `uv.lock` churn.
  Per `dpg-data-product-registry`, the DP-YAML change and any mcp-server tool
  wiring are SEPARATE PRs; a model swap is DP-YAML only (slug already in
  `default_tools`).
- Post-deploy ONLY: run the headless end-to-end smoke test
  (`faa-data-product-wiring` -> "Headless end-to-end smoke test") and classify
  each answer via the MLflow trace spans (empty vs failed vs real), using
  POPULATED measures/slices for the new model.

## Confirming WHICH cube the deployed gateway actually serves (read-only)

To PROVE the live gateway is serving the new AM (not take the URL on faith),
call `get_output_ports` through the running local exchange proxy and read the
`cube` + `output_port_guid` straight out of the schema — no agent, no graph:

    MCP_SERVER_URL=http://localhost:8765/mcp \
      uv run python scripts/probe_mcp.py "$(cat .user_token)" --tool get_output_ports

The prodsteer port block returns `"cube": "3AM_PRODUCT_STEERING_01"`, the
`output_port_guid`, the Collibra link, the full `measures` + `dimensions`
lists, and `default_hierarchies` (the authoritative per-dim wire names — use
this to confirm the swap landed, not just the URL). FAA is cube-unaware, so the
`MCP_UPSTREAM_URL`/`MCP_SERVER_URL` the agent runs with tells you NOTHING about
the cube identity; only the server's `get_output_ports` response does.
The `dimensions` fingerprint also confirms the rename set (new AM shows
`SOLD_PRODUCT_ID` text "Steering Product", `DERIVED_GL_ACCOUNT_ID` text
"Product Costing Component", `FUNCTIONAL_AREA_ID` flat).

## InA execute_query arg shape (the gotcha that burns probe cycles)

The `<slug>_execute_query` tool has NO top-level `measures` parameter. Its
params are: output_port_guid, entity_set, query, filter, select, orderby, top,
skip, row_dimensions, column_dimensions, filters, sort. Passing `measures=[...]`
fails server-side with pydantic `unexpected keyword argument` — and the MCP
error surfaces as `isError:True` with an EMPTY content payload, which looks
IDENTICAL to "cube returned no data." So an empty `[]` result is ambiguous:
always read `res.isError` AND the raw `content[].text` before concluding a data
gap — the text carries the real validation error. Measures go through the InA
measure structure via `column_dimensions`, not a bare `measures` kwarg; confirm
the exact column shape from the port's `usage` string or `value_help` rather
than guessing. `value_help` working (returns members) does NOT prove
`execute_query` is well-formed — they are separate code paths.

## Running the prodsteer eval (correctness scorer)

`tests/evaluation/run_evaluation.py --data_product prodsteer` scores the 11
prodsteer questions. Two things bite:
- Run it in the FAA devcontainer via `docker exec <cid> bash -c '...'` with
  background+notify (an eval dispatches 11 live agent calls + a Gemini judge and
  far exceeds the `run-in-devcontainer` helper's 600s foreground cap).
- The agent endpoint from inside the container is `http://host.docker.internal:8000`
  (NOT `localhost` — that is the container itself).
- The correctness scorer (Gemini judge via SAP AI Core) fails SILENTLY as
  `N/N failed` -> `Correctness: n/a` when AI Core creds are absent from the eval
  shell. `source .devcontainer/set_secrets.sh` in the SAME `bash -c` that runs
  the eval (sourced exports do NOT persist across separate `docker exec` calls).
  Pull per-question verdicts from MLflow with the Databricks M2M token flow in
  CLAUDE.md; the assessment `value` comes back as `yes`/`no` strings, not 1/0.
