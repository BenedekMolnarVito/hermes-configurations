# SAP JIRA MCP — Setup Details (confirmed 2026-08-25)

## Server coordinates

- URL: https://mcp.jira.tools.sap/mcp
- Config key used: sap-jira
- Auth type: OAuth 2.1 PKCE
- Tools discovered: 12

## OAuth flow details

The server uses standard OAuth 2.1 PKCE. On `hermes mcp login`:
- Authorization endpoint: https://mcp.jira.tools.sap/authorize
- client_id: qU_K4ZCiyig4xEjQP5NlT4XL8Q8c68F3
- code_challenge_method: S256
- scope: mcp
- Redirect: http://127.0.0.1:27890/callback (local loopback, Hermes listens)

The command opens the browser automatically on macOS and spins up the local
callback listener. After the user completes SSO in the browser, the token is
exchanged and stored in ~/.hermes/auth.json.

## Confirmed working tool list

jira_get_user_profile, jira_get_issue_watchers, jira_get_issue,
jira_search, jira_search_fields, jira_get_field_options,
jira_get_transitions, jira_get_worklog, jira_get_link_types,
jira_get_project_versions, jira_get_project_components, jira_get_issue_dates

## User context

- User: Molnar, Benedek (C5418860 / benedek.molnar01@sap.com)
- Primary project observed: CFAAI

## How the broken-auth situation arises

The server was originally added with `type: remote` and no auth field
(added via the config.yaml directly or a pre-OAuth `hermes mcp add`).
Without `auth: oauth`, every request returns "Server returned an error response"
with no useful body — looks like a connection failure, not a 401.

Fix sequence that worked:
1. hermes mcp remove sap-jira   (confirm Y)
2. hermes mcp add sap-jira --url https://mcp.jira.tools.sap/mcp --auth oauth
   (the add will fail to connect during setup — save anyway or set manually)
3. hermes config set mcp_servers.sap-jira.auth oauth
4. hermes config set mcp_servers.sap-jira.enabled true
5. hermes mcp login sap-jira    (completes in ~30s, browser opens automatically)
6. hermes mcp test sap-jira     (verify: Auth: OAuth 2.1 PKCE, Tools: 12)
