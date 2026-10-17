# InA view input parameters (SAC "Variables") on the direct-InA path

Some DSP cubes expose mandatory input parameters (SAC "Variables") that select a
slice — e.g. the Budget/Forecast P&L cube (`3AM_PROFIT_AND_LOSS_ACT_BUD_FC_01`)
takes BUDGET_VERSION / CONTENT_AREA / FORECAST_VERSION / REPORTING_VIEW1. This
file is the wire shape, the cube-spec fields, and how to discover + verify them.
Direct-InA path only (`connectors/ina_connector.py`); the DPG firefly-proxy path
does not support variables.

## Wire shape (the ONLY container/key that filters)

`build_payload(variables={technical_name: value})` emits, when non-empty, an
`Analytics.Variables` list SIBLING of `Definition`:

    "Analytics": {
      ...,
      "Variables": [{"Name": "FORECAST_VERSION", "SimpleStringValues": ["Current Forecast"]}, ...]
    }

- One entry per variable, keyed by `Name` + a single-element `SimpleStringValues`.
- `VirtualDataSourceVariableValues` is accepted by the server but SILENTLY
  IGNORED — never emit it; only the `Variables`/`SimpleStringValues` shape above
  actually changes the result.
- When `variables` is None/empty, emit NO `Variables` block so variable-less
  cubes (pnl/prodsteer) stay byte-identical.

## Cube spec fields (`InaCubeSpec` in `connectors/ina_cubes.py`)

- `variables`: Mapping caller-facing arg name -> INA technical name, e.g.
  `{"forecast_version": "FORECAST_VERSION", ...}`. Empty for variable-less cubes.
- `default_variables`: the FULL default slice `{technical_name: value}` sent on
  every query for the cube (all mandatory params with their server-side
  defaults). A caller override is merged OVER this — send the whole slice, not
  just the one overridden param, because the params are mandatory.
- Watch exact technical names: the reporting-view param's technical name can be
  `REPORTING_VIEW1` (trailing digit), not `REPORTING_VIEW`. Read it from the
  cube metadata; a wrong name is silently ignored, not an error.

## Tool + skill surface

- Expose EVERY declared variable as its own optional `query_ina` arg
  (`forecast_version`, `budget_version`, `content_area`, `reporting_view`), not
  just the first one — an unexposed variable is uncontrollable by the agent even
  though the connector already sends its default. Resolve them with a single loop
  over `(caller_param, value)` pairs, not a per-param `if` block: seed
  `dict(spec.default_variables)`, then for each supplied override look up
  `spec.variables[caller_param]` (the technical name) and set it; a supplied
  override whose caller_param is not in `spec.variables` is a clear error, and
  ANY override on a variable-less cube (pnl/prodsteer) is a clear error (not a
  silent no-op). Adding a new overridable variable is then three edits and NO
  connector change: the tool arg, one line in the override tuple, and the
  `spec.variables` mapping in `ina_cubes.py`.
- Confirm the LangChain schema actually exposes each new arg:
  `query_ina.args_schema.model_json_schema()["properties"]` must list all four —
  a param the LLM never sees is dead wiring.
- The `skills/<slug>/SKILL.ina.md` must tell the LLM: query_ina is the sole data
  path, do NOT call the MCP/OData tools; give a param->tool-arg table for all
  variables; each arg overrides ONLY its own variable (omitted ones keep
  defaults); to compare two versions issue ONE `query_ina` call per version
  (there is no single-call multi-version form); and, because an unknown value
  silently returns 0 rather than erroring, do not guess a label — ask when unsure
  and treat a 0-under-override as a likely wrong label, not a real zero.

## Discovery + verification recipe (live, through the local dsp_proxy)

1. Discover the params and their defaults by live-probing the cube through the
   dsp_proxy (`DSP_INA_BASE_URL=http://ina:<port>`), not by guessing.
2. Prove a variable actually takes effect with a three-way check on a POPULATED
   fiscal year (dev BUD/FC is populated for 2026/2027; FY2025 returns 0 — do not
   mistake an unpopulated-year 0 for a wiring failure):
   - default slice -> baseline figure
   - a real alternate version -> a DIFFERENT figure
   - a bogus version string -> 0 (proves the server APPLIES the variable rather
     than ignoring an unknown key)
   Three distinct outcomes = the `Variables` block is live and effective.
3. Prefer a direct `query_ina.ainvoke({...})` probe (set `user_token_var` from
   `.user_token`) to isolate the connector/variable wiring from the agent's own
   scope choices — the full agent may add an implicit hierarchy filter (e.g. a
   PROFIT_CENTER root node) that changes the figure independently of the version.

## Where the VALID VALUES of a variable live (and why you can't list them locally)

A variable's valid value SET is not enumerable through any endpoint the local
stack can reach. Do not burn time trying to "query the value help from a metadata
endpoint" — confirmed dead ends this class of task keeps rediscovering:

- A `query_ina` RESULT response carries Grids/DataSource only, never the variable
  catalog.
- A DataSource metadata `GetResponse` (even with the full 194-flag capability
  list) returns dimensions/measures, not the variable value help; the InA server
  enumerates variable values only through SAC's own SDK variable-manager path.
- firefly-proxy DECLARES the `Variables`/`MetadataDynamicVariable` capabilities
  (`src/ina-capabilities.ts`) but implements NO variable value-help — its
  `CubeMetadata` is measures + dimensions only. DPG's metadata is the same. So
  nothing in the FAA/DPG/firefly stack reads variable values today.
- The SAC input-parameter value LABELS (e.g. "Current Forecast"/"Previous
  Forecast") are NOT the same as the members of any dimension. The cube may have
  a version dimension (e.g. `VERSION_ID` with bare codes like V07/V09, listable
  via `search_dimension_members`), but the variable maps a semantic label to a
  server-side version assignment — pinning FORECAST_VERSION reassigns which
  VERSION_ID rows carry data. Do not present dimension members as the variable's
  valid values; they are a different axis.

Authoritative sources for the value list, in order of practicality: (1) SAC /
Datasphere Data Analyzer on the model — the variable prompt dropdowns are ground
truth (needs the model's SAC URL, often still a placeholder in the registry);
(2) the Datasphere analytic model's design-time variable definition; (3) the
data-product owner. Until firefly-proxy is extended to expose variable value help
(on-VPN work), treat the override as a free-string the user supplies and
self-validate by round-trip: a wrong value returns 0 (the bogus-version check
above), which the skill can detect and report rather than inventing a value list.

## Measure/scope notes seen on the BUD/FC dev cube

- `ACTUALS` is the populated actuals default (no currency conversion, P&L-style);
  `FORECAST` is populated; `BUD` is empty (0) even at the default budget version.
- A cube in the same DSP space often reuses a sibling's hierarchy_meta/field_map,
  but dim-group names can differ (BUD/FC uses `_ID`-suffixed `_GL_ACCOUNT_ID`/
  `_PROFIT_CENTER_ID` like prodsteer, not the bare P&L forms). Verify each reused
  dimension against the new cube's metadata.
