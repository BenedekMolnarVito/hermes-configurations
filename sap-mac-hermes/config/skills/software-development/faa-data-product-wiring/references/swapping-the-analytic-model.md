# Swapping the analytic model (AM) behind an existing FAA data product

A recurring task distinct from onboarding a new DP: an existing DP keeps its
slug, name, GUID, mcp-server registration, and FAA skill, but the underlying
Datasphere analytical model is replaced (e.g. a Datasphere-native model swapped
for a data-lake-backed one). The business goal is "point the DP at the new
model and validate"; the code change is narrow but easy to under-scope.

## Where the AM id lives (the ONLY place to change the model)

NOT in FAA, NOT in firefly-proxy. The cube identity lives in the DPG registry
data-product YAML, one file per env:

    data-product-gateway/src/data_product_gateway/registry/data-products/{dev,int,prod}/<slug>.yaml

For an InA/firefly-proxy port the model is the `connection:` block:
`object_name` (the AM technical name), `schema_name` (DSP space), `instance_id`
(per-env, optional), `default_hierarchies` (per-dimension wire names). The slug,
`data_product_guid`, `name`, and the mcp-server manifest (`registry/
mcp-servers/<env>/*.yaml` listing the slug under `data_products`) do NOT change
— a model swap re-points an existing tool, it does not add one.

## An AM swap is NOT just `object_name` — this is the central pitfall

Changing only `object_name` to the new model and leaving `schema_name`,
`instance_id`, and `default_hierarchies` as-is will usually BREAK queries. A new
AM commonly has a different schema (space), a new per-env `instance_id`, and
DIFFERENT external-hierarchy wire names (BW hierarchy ids like `0102/YKON/TCO`,
`SOLAREA.2026`). The hierarchy wire names in particular are baked into the DP
YAML `default_hierarchies` AND into the FAA skill's filter examples — stale ones
make every hierarchy filter 502/`hierarchy not found`. Treat schema, instance_id
and every `default_hierarchies` value as unknown-until-confirmed for the new
model; only reuse an old value after you have confirmed it still applies.

`instance_id` is OPTIONAL — firefly `toFireflyDataSource()` pins it only
`if (instanceId)`, so blanking it makes DSP resolve the cube by
`schema_name`+`object_name` alone. The live base `/metadata` response does NOT
return instance_id (it is an out-of-band tenant/deployment property). So prefer
leaving the NEW model's `instance_id: ""` with a TODO over carrying the OLD
model's value, which can mis-pin to the wrong cube. The `int`/`prod` instance_id
values are per-tenant and will NOT come from a single dev metadata call —
mirror the dev wiring and keep the existing `⚠️ DEPLOY PREREQUISITE` comments.

## firefly-proxy needs NO code change for an AM swap

firefly-proxy does not hardcode the DP's cube: its `config/cube.yaml` default is
unrelated (a P&L cube), and for a DPG-routed query DPG sends the cube identity
(`schema`/`object`/`instance_id`) per request in the DataSource; firefly
resolves it live via `/metadata`+`/query`. So "check firefly-proxy for
dependencies" resolves to: confirm it resolves the cube dynamically (it does) —
not a source edit. The only reason to touch firefly-proxy is variable/parameter
wiring, which is a different task.

## Discover the new model's values via a live firefly-proxy `/metadata` call

The schema/hierarchy wire names come from a live call — see
`dpg-data-product-registry/references/firefly-proxy-live-metadata.md` for the
full runner recipe. Summary for the AM-swap use:

    FIREFLY_INA_HOST=127.0.0.1 bash scripts/run-local.sh   # background; user does SSO
    curl -s "http://127.0.0.1:8020/metadata?schema=<SPACE>&object=<NEW_MODEL>&expand=hierarchies" \
      -H "Authorization: Bearer $(cat .user_token)"

- `schema`+`object` query params OVERRIDE config, so you point at the new model
  with no config edit. `?expand=hierarchies` is the ONLY way to get the
  per-dimension wire names for `default_hierarchies`; the base response omits
  them. A successful call also doubles as the "is the new model live?" check the
  data team is often still confirming.
- Prereq the USER satisfies (never you): SAP VPN up AND the 4 git-ignored `.env`
  secrets filled — `JWT_CLIENT_ID`/`JWT_CLIENT_SECRET` (login server) and
  `DESTINATION_CLIENT_ID`/`DESTINATION_CLIENT_SECRET` (SAML hop). Check presence
  without printing values; if any is empty, STOP and ask the user to fill them —
  do not try to mint/supply secrets. The two URLs (`XSUAA_URL`,
  `DESTINATION_BASE_URL`) ship pre-filled. The runner is foreground/long-lived
  and opens a browser for interactive SSO: start it background, then curl from a
  follow-up call. The metadata call hits ONE tenant (whatever
  `DESTINATION_BASE_URL` points at — usually dev).
- If running firefly-proxy is not possible, the same values can come from the
  data team / SAC Data Analyzer — accept them from the user and skip the runner.

## FAA carries stale COSMETIC references to the old model — update them too

FAA is unaware of the cube for querying (DPG owns it), so the query works after
the DPG edit alone. But FAA hardcodes the old model name/schema in places that
drive user-facing links, labels, and agent guidance; grep FAA for the old
`object_name` and `schema_name` and update:

- `src/fin_analyst_agent/data_product_refs.py` — Collibra/DSP databuilder/SAC
  deep-link URLs (the `{..._url}` placeholders the skill substitutes).
- `src/fin_analyst_agent/data/allowed_assets.json` — the legacy OData allowlist
  `(space_id, asset_name)` pair (dead on the InA path, but keep it consistent).
- `skills/<slug>/SKILL.md` — the "DO NOT USE / forbidden string" asset-name
  callouts AND every hierarchy wire name in filter rules / worked
  `[ANSWER_ANALYTIC_SLICE]` examples (`0102/YKON/TCO`, `SOLAREA.2026`, etc.).
  Bump `metadata.faa_prompt_version` per CLAUDE.md severity when you touch it.
- Any cached hierarchy export JSON under `src/fin_analyst_agent/data/` sourced
  from the old model.

## Ship as separate PRs / branches

The DPG registry edit and the FAA reference updates are different repos with
different reviewers — two PRs. Within DPG, the data-product YAML change and any
mcp-server change are also reviewed separately (see `dpg-data-product-registry`
Notes). Run all FAA Git/tests in the devcontainer; the FAA LFS PDF/parquet
smudge drift (10 "modified" binaries) is NOT a real change — never stage it.
