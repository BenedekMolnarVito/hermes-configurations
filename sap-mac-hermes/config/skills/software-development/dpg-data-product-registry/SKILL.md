---
name: dpg-data-product-registry
description: "Add/edit a data-product-gateway registry YAML file."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [DPG, data-product-gateway, registry, OData, datasphere, MCP]
    related_skills: [faa-data-product-wiring]
---

# DPG Data Product Registry Wiring

Adding a data product to the **data-product-gateway** (DPG) repo = adding ONE
YAML file to `src/data_product_gateway/registry/data-products/<env>/` (env =
`dev`/`int`/`prod`). The loader reads every `*.yaml` in the active env dir, so a
new file is auto-discovered; no other surface needs editing to make the product
load. This is a DIFFERENT repo and registration model from FAA — do NOT apply
the `faa-data-product-wiring` surfaces (registry.py / ina_cubes.py /
allowed_assets.json) here.

## Procedure

1. Copy the closest existing sibling as the template — prefer one in the SAME
   Datasphere space or the same protocol path over a generic one; it already has
   the right `destination`, `base_path` shape, and field conventions. The user
   may name a specific template file; honor it.
2. Fill identity from the Collibra asset page
   (`https://sap.collibra.com/asset/<data_product_guid>` — usually loads without
   a login wall; read `document.body.innerText`): `name`, `description`,
   `domain` (the breadcrumb like "09 - Finance & Admin - Controlling ..."),
   `owner` (the "maintained by Team" value, e.g. `PFI_032 | ...` — match the
   sibling's owner style for consistency), `tags`.
3. `data_product_guid` and `output_port_guid` come from the ticket/user or the
   Collibra output-port row. Use exactly what the user supplies.
4. Parse connection from the Datasphere databuilder URL of the form
   `https://<host>.hcs.cloud.sap/dwaas-core/index.html#/databuilder&/db/<SPACE>/<MODEL>/...`:
   - SPACE (e.g. `PROFIT_LOSS_REP`) -> the last segment of `base_path`.
   - MODEL (e.g. `3AM_PROFIT_AND_LOSS_ACT_BUD_FC_01`) -> `analytical_models` entry.
   - host `bdc-dsp1-dev...` -> `destination: bdc-dsp1-dev-dsp-saml` (match the
     env: dev host -> dev-saml destination).
5. Pick `base_path` protocol segment by the MODEL PREFIX, not by guessing:
   `3AM_` (analytic model) -> `/api/v1/datasphere/consumption/analytical/<SPACE>`;
   relational fact views (e.g. `3GVF_..._01`) -> `.../consumption/relational/<SPACE>`.
   Confirm against siblings: `grep -rn 'consumption/analytical' registry/data-products/<env>/`.
6. Filename and top-level YAML key MUST match and are the SLUG. The loader turns
   the slug into the tool name `<slug>_execute_query`, so `profit-and-loss-...`
   file -> `profit-and-loss-...:` key -> that tool name. Do NOT wrap in a
   `registry:` key; the loader injects `data_product: <slug>` itself.
7. Validate before declaring done (see Verify).

## Choosing the port type (OData vs InA/firefly-proxy)

Within DPG a `3AM_` cube can be exposed two ways — do not conflate:
- **OData analytical** port (this skill's default, product-360 template): flat
  `connection: {destination, base_path, analytical_models}`. Plan version
  (ACT/BUD/FC) is a filterable DIMENSION on this path.
- **InA / firefly-proxy** port (e.g. `profit-and-loss-actuals-p-l.yaml`):
  `connection: {ina_service, object_name, schema_name, instance_id,
  `default_hierarchies}` — server-side hierarchy roll-up. `default_hierarchies`
  wire names come from a live firefly-proxy `/metadata?...&expand=hierarchies`
  call (see `references/firefly-proxy-live-metadata.md`); `instance_id` is
  optional (firefly resolves the cube by schema+object). InA input
  PARAMETERS (variables) are not passable end-to-end. Only use this shape when
  the ticket explicitly asks for server-side aggregation; otherwise follow the
  OData template the user pointed at.

An "InA query tool" is NOT a custom_tool — the InA tool IS the built-in
`execute_query` (routes to the InA connector when the port has `ina_service`)
plus `value_help`, both from the server's `default_tools`. The port type lives
entirely in the DP YAML connection block; the mcp-server side just lists the
slug under `data_products` (no custom_tools). So "expose this DP over InA" =
switch the DP connection to the InA shape AND remove any custom_tools entry for
it. `instance_id` differs per cube — never reuse a sibling cube's id even in the
same space; leave it empty with a TODO until a live `/metadata` call confirms
it, the DP still loads (both fields are optional) but live queries need them.

## Verify

- Validate the file loads AND passes the Pydantic model:
  `PYTHONPATH=src uv run python -c '<load yaml, set body["data_product"]=slug,
  DataProduct(**body)>'` — catches a misconfigured product now.
- The directory-mode loader (`registry/loader.py::_load`) does NOT crash on an
  invalid product: it SKIPS + logs it and loads the rest, so a malformed edit
  silently drops the product (its `<slug>_execute_query` tool just never
  registers) and surfaces only as a missing tool in a running pod — never as a
  startup failure. A one-shot `uv run python -c` check is therefore not enough;
  add a CI test so a bad edit fails the build, not production.
- Preferred durable check — a parametrized pytest that loads the REAL registry
  YAML through the loader's exact transform (`DataProduct.model_validate({
  "data_product": slug, **product_data})`), scoped to the file(s) this change
  touches (not a repo-wide `*/*.yaml` glob — that trips unrelated pre-existing
  products with empty required fields like `when_to_use`; flag those separately,
  do not fix them here). Mirror the existing `test_server_slug_hygiene.py` glob
  pattern; a new sibling is `tests/unit_tests/registry/test_data_product_yaml_loads.py`.
- An InA connection change (new model, cleared `instance_id`) is tested at the
  connector wire level, not just model-validation: `InaConnector._data_source()`
  emits `instance_id` only when truthy, so an empty value must be ABSENT from the
  POST `/query` `data_source` block. Assert that in `tests/unit_tests/connectors/
  test_ina_connector.py` (capture the outbound request via a client stand-in
  patched in through `ina._get_client`, same as the existing metadata tests) —
  the GET `/metadata` omit-identity test does NOT cover the POST `/query` path.
- Bare `python3 -c` gives `ModuleNotFoundError: No module named 'pydantic'` —
  the deps live in the uv env; always use `uv run python`, never bare python3.
  Same for pytest: `PYTHONPATH=src uv run python -m pytest ...`, not bare pytest.
- Repo black/isort/pylint run at line-length 135 (via `.pre-commit-config.yaml`
  / `setup.cfg`), NOT black's 88 default. A bare `black --check` on the host
  reports spurious reformats; always pass `--line-length=135` (and
  `--target-version=py312` to silence the "can't parse 3.15" host warning) or
  the diff is noise. Pre-existing `protected-access` / missing-class-docstring
  pylint hits in a test file are the file's own convention — do not "fix" them
  when your addition follows the same shape.
- First `uv run` may rebuild the AI_Factory_Template submodule (~30s) and emit an
  `mcp_server` experimental UserWarning — both are benign.

## Notes

- Adding the registry YAML makes the product LOAD, but a tool is only EXPOSED
  when an mcp-server YAML under `registry/mcp-servers/<env>/` references it in
  `default_tools`. Offer to wire that if the user wants the tool live; the
  data-product file alone is enough for the registry.
- Ship the data-product YAML and the mcp-server tool wiring as TWO SEPARATE
  PRs on separate branches, even when done in one session — the registry entry
  (DP onboarding) and exposing it as an MCP tool are reviewed by different
  owners, and bundling them gets the MCP change blocked. When the branch you
  are on is named for one half (e.g. `...add-<dp>-dp` vs `...add-<tool>-to-<server>-mcp`),
  keep that half's diff alone on it; the other half belongs on its own branch,
  already committed in the base. Confirm with `git log --oneline -- <path>`
  that the DP file is already in HEAD before staging only the mcp-server edit.
- For the full mcp-server edit — add the slug to `data_products`, extend
  `description`, and add a `custom_tools` OData query tool (the
  `<MODEL>/_<MODEL>` entity_set shape, the "simple tool = entity_set only"
  rule, and the multi-line-description LSP false positive) — see
  `references/mcp-server-wiring.md`.
- `output_port_guid` placeholders are common (siblings carry `#as a placeholder`
  / TODO(GUID) comments). If the user gives a real GUID, use it verbatim and
  drop the placeholder comment.
