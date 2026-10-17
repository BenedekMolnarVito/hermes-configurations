# Probing what a DP can answer, and "can the agent see node X?" verification

For a triage/verification ask of the form "does the agent find <account node /
member>?" or "what can we query from <DP>?", answer from the LIVE MCP surface, not
by reading code. Two layers: the AGENT (does routing + answer generation) and the
RAW MCP tools (the cube's queryable surface). Use the agent for real figures; use
the raw tools for the schema and member catalog.

## Start the minimal surface

- Full stack (for agent `/v2/serve` probes): `DP_MCP_EXCHANGE_MODE=direct uv run
  python tests/local_execution/run_app.py`. `direct` mode is REQUIRED off the
  Destination-Service path — the default `destination` mode 404s
  (`data-product-gateway` BTP destination "Configuration not found"), which
  aborts the stack at the MCP whoami smoke-test so the agent/front-proxy never
  start. See the headless recipe in SKILL.md.
- Raw MCP tools ONLY (for schema/value_help, no agent needed): start just
  `DP_MCP_EXCHANGE_MODE=direct uv run python scripts/local_dev/dp_mcp_proxy.py`
  then drive it with `MCP_SERVER_URL=http://localhost:8765/mcp uv run python
  scripts/probe_mcp.py "$(cat .user_token)"`. A GET to :8765/mcp = 405 and a bare
  POST = 406 when the proxy is UP (needs MCP Accept headers); 000 = not
  listening.
- Before starting anything, decode `.user_token` `exp` vs now — a stale token
  means no login_server is keeping it fresh; ask the user to re-login rather than
  minting one. Kill any stale stack first: ports 80/5000/8765 already bound means
  a partial prior stack survives and your new launch collides on bind; free them
  via `/proc` (no `ps`/`pkill`) before relaunching.

## Enumerate the queryable surface (raw tools)

- `get_output_ports` returns, per DP: `cube`, `output_port_guid`, the full
  `measures` list, `dimensions` list, and `default_hierarchies` (dimension ->
  wire name, e.g. GL_ACCOUNT_ID -> `0102/YKON/TCO`). This is the authoritative
  "what can I query" answer — measures, dimensions, and which dims roll up as a
  hierarchy.
- `<slug>_value_help(dimension=, mode="flat"|"hierarchy", search=, hierarchy_wire_name=)`
  lists members / hierarchy nodes. `mode="hierarchy"` + the wire name +
  `search="<node>"` returns node objects carrying the FULL wire `key`
  (`[_GL_ACCOUNT_ID].[0102/YKON/TCO].&[0TCO-AM]`), description, level, and
  namepath/textpath — the ground truth for whether a named node exists.
- To settle "is concept X modelled at all", search EVERY plausible dimension for
  the term, not just one: for a Product-Steering "account node" that means the GL
  hierarchy AND the solution-area/product dims (WWPL1-4, ZZCMD0_PFH_IO,
  SOLD_PRODUCT_ID). A term absent from all of them (record_count 0 everywhere)
  is genuinely not in the cube — report "not in the data", not "agent failed".
  value_help returns member KEYS only (no text labels), so a code-prefix search
  ("AI" -> SAAI/SAINS) is not proof of a matching label; resolve via hierarchy
  mode namepath/textpath when a label matters.

## Distinguish "agent can't find it" from "not in the data" (agent probes)

Escalate framing across separate `/v2/serve` calls and read the `AgentSources`
block to see which cube it actually hit:
1. Verbatim user question — reveals routing. The agent may pick the WRONG domain
   (a Product-Steering/TCO question can route to P&L actuals); the `sources[].name`
   / `dataaccess_url` cube path tells you where it looked.
2. Domain-named reframe ("In Product Steering / TCO, ...") — forces the right
   cube; confirms the node is absent even when routed correctly.
3. "List all nodes in the <hierarchy>" — makes the agent enumerate the live
   hierarchy, so you SEE the real node set and can state the nearest concept.
A weak-routing observation (bare question picks the wrong domain) is a real
finding worth reporting even when it is not the ticket's subject.

## Raw execute_query filters 502 — get real figures through the AGENT, not raw MCP

Hand-crafting a `<slug>_execute_query` call with a `hierarchy_node` filter from
raw args (via probe_mcp/MultiServerMCPClient) commonly returns a firefly 502
`Cannot read properties of undefined (reading 'startsWith')` — regardless of
whether `node_wire_keys` holds the short node name OR the full wire key. The
agent's own tool wrapper assembles a payload shape the raw args do not reproduce.
So do NOT reverse-engineer the firefly wire format to fetch a node's roll-up
figure; ask the agent (`/v2/serve` with a domain-framed question) — it builds the
correct payload and returns the number with the SAC-validation slice. Reserve raw
tools for the SCHEMA and the member catalog (get_output_ports / value_help),
which work fine; use the agent for measured VALUES.

## Teardown

Kill the proxy/stack via `/proc` (match `dp_mcp_proxy.py`/`run_app.py`/
`front_proxy.py` in `/proc/<pid>/cmdline`, then `kill`), re-check the ports are
000, and confirm the working tree is clean.
