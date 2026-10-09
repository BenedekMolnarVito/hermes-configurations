# Exposing a DPG data product via an MCP server

Adding the data-product YAML makes the product LOAD; a tool is only EXPOSED when
an mcp-server manifest under `registry/mcp-servers/<env>/<server>.yaml`
references the product. Editing an existing server = three coordinated changes.

## MCP-server YAML shape

```yaml
slug: financial-analyst-agent-mcp
name: "..."
description: "... multi-line double-quoted scalar ..."
owner: "someone@sap.com"
default_tools:            # tools auto-generated per product
  - execute_query         # always include
  - get_output_ports      # open-ended "what data is available?" servers
  - value_help            # InA/firefly-proxy ports only (member value-help)
data_products:            # slugs from registry/data-products/<env>/*.yaml
  - product-steering-cost
  - profit-and-loss-budget-forecast
custom_tools:             # optional named fixed-query tools
  - output_port_guid: "<port-guid>"
    name: "get_profit_and_loss_budget_forecast"
    description: "..."
    entity_set: "3AM_MODEL/_3AM_MODEL"
```

To add a product: append its slug to `data_products`, extend `description`, and
(if a named tool is wanted) add a `custom_tools` entry.

## CustomTool = a fixed named query (registry/models.py::CustomTool)

A CustomTool bakes one fixed SQL or OData query into a closure at load time;
callers pass no parameters. Auth, access policy, and QueryGuard still apply.
Final tool name is `<product_slug>_<name>` (or just `<name>` when
`MCP_STRIP_SLUG_PREFIX=true`). Fields:
- `output_port_guid` (required) — the only link to a product; slug + connection
  type (SQL vs OData) are inferred from the registry lookup on this GUID, so
  nothing else about the product is declared here.
- InA/firefly-proxy ports CANNOT be a custom_tool: `build_custom_tool` only
  branches on SQL and OData connections; an InA port hits the else branch, logs
  "unrecognised connection type", and returns `(None, None)` — the tool silently
  never registers. So a request for an "InA query tool" is NOT a custom_tools
  entry. Expose an InA product through the built-in `execute_query` (which
  auto-dispatches to the InA connector when the port has `ina_service`) plus
  `value_help`, both from `default_tools`. When switching a DP from OData to
  InA, DELETE its custom_tools block entirely and rely on default_tools.
- `name`, `description` (required).
- SQL port: `query:` = raw `SELECT`/`WITH` statement.
- OData port: `entity_set` (+ optional `filter`, `select`, `orderby`, `top`,
  `apply`, `default_params`). `filter`/`select` are LOCKED (access-policy
  control), not caller-supplied.
- Invalid `custom_tools` entries are logged and SKIPPED at load, not fatal — but
  still validate with `CustomTool(**entry)` before committing.

## OData entity_set for a 3AM_ analytic model

Use the `<MODEL>/_<MODEL>` shape, e.g.
`3AM_PROFIT_AND_LOSS_ACT_BUD_FC_01/_3AM_PROFIT_AND_LOSS_ACT_BUD_FC_01` — the
repeated leading-underscore segment is the entity set inside the analytic model
service. This matches the other analytic-model custom tools in the repo; grep
sibling `custom_tools:` blocks to confirm the exact shape.

## "Simple OData query tool" = entity_set only

The minimal, always-valid OData custom tool is `output_port_guid` + `name` +
`description` + `entity_set`, with NO `select`/`filter`: it returns all columns
capped at the server default. Prefer this when you don't have verified column
names. Live `$metadata` (`.../analytical/<SPACE>/<MODEL>/$metadata`) is
Unauthorized without a SAML/bearer token, so column names are usually
unknowable from a dev box — do not guess a `select`; ship the bare entity_set
and offer to add `select` once the owner supplies the fields.

## Pitfall: multi-line description LSP false positive

A multi-line double-quoted `description:` scalar (bullets on their own lines
inside the quotes) makes the YAML LSP report "Implicit keys need to be on a
single line" / "Map keys must be unique". This is a linter artifact of its
line-by-line view — the real `yaml.safe_load` + Pydantic loader accept it. Trust
an actual parse (`uv run python -c 'yaml.safe_load(open(f))'`), not the LSP
diagnostics, before assuming the file is broken.

## Mixed-transport server is fine

A server can carry both InA/firefly-proxy products (which use `value_help`) and
OData products (which do not). The OData product simply ignores `value_help`;
`execute_query`/`get_output_ports` + any custom tool cover it. No conditional
per-product tool config is needed.
