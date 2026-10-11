# Live firefly-proxy /metadata call (discover InA cube identity + hierarchies)

When an InA/firefly-proxy DP port needs its `instance_id` and
`default_hierarchies` wire names filled, the source of truth is a live call to
the firefly-proxy `/metadata` endpoint. firefly-proxy (repo at
`~/VSCodeRepos/firefly-proxy`, TS/Node wrapping `@sap/firefly`) vendors the
WHOLE local chain (SAML hop + browser login) under `src/local-dev/`, so you run
it from a lone clone — no FAA, no other repo, no Python.

## The call that gives you what the DP YAML needs

    TOKEN=$(cat ~/VSCodeRepos/firefly-proxy/.user_token)
    curl -s "http://127.0.0.1:8020/metadata?schema=<SPACE>&object=<MODEL>&expand=hierarchies" \
      -H "Authorization: Bearer $TOKEN"

- `schema` + `object` query params OVERRIDE `config/cube.yaml` (see
  `server.ts` /metadata handler), so you point at ANY cube without editing
  config: e.g. `schema=PROFIT_LOSS_REP&object=3AM_PROFIT_AND_LOSS_ACT_BUD_FC_01`.
- `?expand=hierarchies` runs the live `$$HierarchyName$$` InA catalog query and
  merges per-dimension external BW hierarchy WIRE NAMES (e.g.
  `0102/YKON/ZUSGAAP-01.2026`) into each dimension entry. This is the ONLY way
  to get `default_hierarchies` values; the base (non-expand) response carries NO
  hierarchies at all by design. `expand` is uncached — a live call every time.
- The base response gives `measures` + business `dimensions` (technical `_`- and
  `$`-prefixed and lowercase-bearing dims are filtered out), useful for skill
  guidance and confirming dimension names.

## instance_id is OPTIONAL — do not block on it

`toFireflyDataSource()` (query-service.ts) only pins `InstanceId` into the InA
DataSource block WHEN present (`if (instanceId)`); firefly resolves the cube by
`SchemaName` + `ObjectName` alone. So both `/metadata` and `/query` work without
it, and a DP YAML with `instance_id: ""` still queries. The base `/metadata`
response does NOT return an instance_id anyway (only `cube`/`measures`/
`dimensions`/`fetched_at`) — it is an out-of-band cube property, hard-coded in a
sibling's `config/cube.yaml`/DP YAML, not something the metadata call discovers.
Treat the live call as being about HIERARCHIES first; instance_id is a nice-to-
have pin, not a hard requirement.

## Running the local chain

1. Prereqs the RUNNER needs (not you): SAP VPN up, and 4 secrets filled in
   `.env` (git-ignored): `JWT_CLIENT_ID`/`JWT_CLIENT_SECRET` (login server),
   `DESTINATION_CLIENT_ID`/`DESTINATION_CLIENT_SECRET` (SAML hop). The two URLs
   (`XSUAA_URL`, `DESTINATION_BASE_URL`) ship pre-filled. Check presence without
   printing values: `for k in ...; do v=$(grep "^$k=" .env|cut -d= -f2-|tr -d \"\\'\"); [ -n "$v" ] && echo "$k SET" || echo "$k EMPTY"; done`.
2. `npm install && npm run build` (-> `dist/`). Needs the committed `.npmrc`
   (SAP Artifactory) AND VPN: off-VPN, install dies with
   `ENOTFOUND int.repositories.cloud.sap` because `@sap/firefly` only resolves
   through corporate Artifactory. This is an environment prereq, not a repo bug.
3. Host alias: the SDK uses one host value for BOTH the TCP connect target AND
   the outgoing `Host` header. `/etc/hosts` needs sudo (often unavailable to
   this user). AVOID it entirely by exporting `FIREFLY_INA_HOST=127.0.0.1` —
   the `.env.example` documents this override, and the dsp-hop routes on its
   `*` wildcard regardless of the Host value, so it is safe.
4. Run: `FIREFLY_INA_HOST=127.0.0.1 bash scripts/run-local.sh`. It sources
   `.env`, starts dsp-hop (:8091) + login-server (:5000), opens the browser to
   the XSUAA login (the USER completes SSO here — this is the interactive step),
   writes `.user_token`, then launches firefly-proxy on :8020. Ctrl-C tears down
   all three. The runner is FOREGROUND/long-lived — start it as a background
   process, then curl `/health` and `/metadata` from follow-up calls.
5. The browser SSO login and the 4 client secrets are DIFFERENT credential
   sets — completing the browser login does not substitute for the missing
   startup secrets. Both must be satisfied before a live call works.

## Path-doubling gotcha (why FIREFLY_INA_PATH is empty, not unset)

The runner sets `FIREFLY_INA_PATH=""` (empty, NOT unset). firefly's InA layer
appends its own `/sap/bc/ina/service` mount, and the datasphere destination base
URL already ends at the tenant root (`.../dwaas-core`). `connectionConfigFromEnv()`
reads the var with `??`, so an empty string overrides the default mount; UNSETTING
it falls back to `/dwaas-core/sap/bc/ina/service` and doubles the path -> 404.
