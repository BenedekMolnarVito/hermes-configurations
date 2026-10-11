---
name: jira
description: "Use when querying or updating JIRA issues via Hermes MCP."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [jira, mcp, issue-tracker, jql, sap, oauth, atlassian]
    related_skills: [github-issues, sdlc-review]
---

# JIRA via Hermes MCP

JIRA operations in Hermes run through a remote MCP server that exposes 12 tools
(search, get issue, get user profile, transitions, worklog, watchers, etc.).
The MCP server must be authenticated before any tool call works.

## Quick orientation

- MCP server key in config: `sap-jira` (or whatever name was used on `mcp add`)
- Transport: HTTP / StreamableHTTP with OAuth 2.1 PKCE
- Tools are only callable inside a running Hermes session (not from raw curl)
- To invoke tools from this CLI session, use `hermes chat -q '...'`

## Setup (first time or after auth breaks)

If the server is missing or was added without auth:

```bash
# 1. Remove any existing entry (answers Y to confirmation)
hermes mcp remove sap-jira

# 2. Re-add with OAuth
hermes mcp add sap-jira --url https://mcp.jira.tools.sap/mcp --auth oauth
# When prompted "Continue without authentication?" answer N / let it save disabled

# 3. Set auth and enable explicitly if the add left it disabled
hermes config set mcp_servers.sap-jira.auth oauth
hermes config set mcp_servers.sap-jira.enabled true

# 4. Complete the OAuth flow
hermes mcp login sap-jira
# Opens a browser tab automatically. Complete the SSO login.
# On success prints: "Authenticated — 12 tool(s) available"
```

Verify with:
```bash
hermes mcp test sap-jira
# Expected: Transport: HTTP, Auth: OAuth 2.1 PKCE, Tools discovered: 12
```

## Running queries

MCP tools are available only inside a live Hermes agent session. From the CLI,
use one-shot mode:

```bash
# All open tickets assigned to me
hermes chat -q 'Use jira_search to run JQL: assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC'

# Specific issue detail
hermes chat -q 'Use jira_get_issue to fetch issue PROJ-123 with all fields'

# Issues updated today in a project
hermes chat -q 'Use jira_search with JQL: project = CFAAI AND updated >= startOfDay() ORDER BY updated DESC'

# Transition an issue
hermes chat -q 'Use jira_get_transitions to list transitions for PROJ-123, then use jira_transition_issue to move it to In Progress'
```

## Available MCP tools (sap-jira)

| Tool | Purpose |
|---|---|
| jira_search | JQL search — primary entry point for finding issues |
| jira_get_issue | Full issue detail including epic, subtasks, links |
| jira_get_user_profile | User profile by account ID or email |
| jira_get_issue_watchers | Who is watching an issue |
| jira_get_transitions | Available status transitions for an issue |
| jira_get_worklog | Worklog entries on an issue |
| jira_get_link_types | All issue link type definitions |
| jira_get_project_versions | Fix versions for a project |
| jira_get_project_components | Components for a project |
| jira_get_issue_dates | Date info + status transition history |
| jira_search_fields | Search/discover custom field names (fuzzy) |
| jira_get_field_options | Allowed values for a custom field |

## Useful JQL patterns

```
# My open tickets
assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC

# My in-progress tickets
assignee = currentUser() AND status = "In Progress"

# My project tickets updated this week
project = CFAAI AND assignee = currentUser() AND updated >= startOfWeek()

# Unresolved tickets I reported
reporter = currentUser() AND resolution = Unresolved ORDER BY created DESC

# High-priority open tickets
assignee = currentUser() AND priority in (High, Highest) AND statusCategory != Done
```

## Creating an issue (the MCP has NO create tool)

The `sap-jira` MCP tool set is READ-ONLY for issues (search / get / transitions /
profile) — there is no create-issue or issue-edit tool. The MCP being authed lets
you READ but NOT create; creating always needs the browser create dialog below.

PREREQUISITE — the browser must be able to complete interactive SSO. Jira create/
edit redirects to Microsoft SSO (email -> password -> MFA), which only the user can
do in a VISIBLE window. Hermes' default `browser.backend: browser-use` drives a
HEADLESS Chromium (UA `HeadlessChrome`, `navigator.webdriver=true`, chromium args
show `--headless=new`) that the user cannot see or sign into — and it IGNORES
`browser.headed: true` / `AGENT_BROWSER_HEADED=1` (those only affect the local
agent-browser path, not the browser-use driver). The read-only MCP's OAuth is a
separate auth and does NOT carry a Jira web session. So before attempting a
browser create, make the browser visible:
  - PREFERRED durable fix (reuses the user's own SSO so no re-login): `hermes
    config set browser.backend off` + `browser.headed true` + `browser.use_real_profile
    true` + `browser.real_profile_autoclose true`. Real-profile copies the user's
    active Chrome profile (cookies/logins) into a snapshot and launches their real
    Chrome binary on it, so SAP SSO cookies carry over. macOS GOTCHA: Chrome must
    be FULLY QUIT when the real-profile session launches — a running Chrome holds a
    hot write-lock on `Login Data`/`Web Data` and the snapshot fails signed-out
    (`Cookies` snapshots fine, the login DBs do not). autoclose lets Hermes OFFER
    to close Chrome (asks first). Multiple Chrome profiles -> pin with
    `browser.real_profile_pin='Profile N'`.
  - Minimal visible fix (clean throwaway profile, user still signs in once):
    `browser.backend off` + `browser.headed true`.
  - Or `/browser connect` to the user's own already-SSO'd Chrome.
  - Or hand the user ready-to-paste title + wiki-markup body, let them create it,
    then verify the key via the MCP. On a headless-only session this last path is
    the only one that works THIS turn.
  Any config change above needs a NEW Hermes session to take effect (toolset/backend
  switch cannot apply mid-conversation — prompt-caching invariant), and stale
  `browser_harness.daemon` / `Chrome for Testing` processes must be killed so the
  next spawn re-reads config.
Never type a password/MFA code yourself and never ask for one in chat.

1. Open `https://<jira-host>/secure/CreateIssue!default.jspa`. A non-empty page
   title (e.g. "Create Issue - SAPJIRA") means you are already SSO-authenticated;
   if it redirects to login, the session is not authed — fix the browser per the
   PREREQUISITE above, do not guess creds.
2. Dismiss the blocking info popup first: `document.querySelector('#infoPopupOkButtonId')?.click()`.
   It sits over the form and swallows the Next click otherwise.
3. Step 1 of the dialog is Project + Issue Type. Project may already be correct.
   Issue type is a text field `#issuetype-field` (display) backed by hidden
   `#issuetype`; to change it, focus `#issuetype-field` to open the suggestions,
   then click the option li (ids like `#bug-1`, `#epic-2`). Advance with
   `#issue-create-submit` (the "Next" button).
4. Step 2 is the detail form. Fill long fields with JS `el.value=...` + dispatch
   an `input` event — NOT the char-by-char `fill_input`, which times out on long
   multi-paragraph descriptions and can leave the page navigated to about:blank.
   Description uses Jira wiki markup (`h3.`, `*` bullets), not Markdown.
5. Component/s is an AUI multiselect with a real underlying `<select id="components">`;
   set `option.selected` by value and dispatch `change`. Jira submits from the
   `<select>`, so the missing visual lozenge does not matter. Get the numeric
   component value from `select.options` (e.g. "Financial Analyst Agent").
6. Submit with `#issue-create-submit` (now labelled "Create"). Read the created
   key from the redirect URL (`/browse/CFAAI-\d+`) and the page title.
7. VERIFY every created key back through the MCP (`jira_search` with
   `key in (...)`) — confirm issue_type, project, and components landed. A
   redirect URL alone is not proof the fields saved.

CFAAI conventions: project `CFAAI`, component `Financial Analyst Agent`. When a
ticket tracks tool-layer tech debt, split it Bug (the defect) + User Story (the
proper fix), reference the driving PR and parent story in the description, and
put the parent key in the body (a User Story parent cannot be set via the Epic
Link field).

## Updating fields that the MCP does not expose

The SAP Jira MCP tool set may expose issue reads and transitions without a general
issue-edit operation. For fields such as Sprint, use this workflow:

1. Fetch every target issue first and verify the requested preconditions, such as
   `assignee = currentUser()` and the current field value. Do not rely on the ticket
   numbers alone.
2. Discover the exact field and destination value before editing. For Sprint, search
   Jira for issues already in the named sprint and capture the canonical sprint name,
   numeric ID, state, and board; display names may include a project prefix.
3. If no MCP edit tool exists, open each issue in the authenticated browser, choose
   Edit, select the canonical value from the field's autocomplete results, and submit.
   Select the suggestion rather than merely typing text, because Jira submits the
   hidden option ID.
4. Read back each exact issue after submission and confirm the destination value is
   visible before reporting success. Verify every ticket independently; one successful
   edit does not establish that the batch succeeded.
5. Report only the changed issue keys and final canonical value unless a blocker needs
   explanation.

## Checking whether a ticket is still valid (ticket-vs-codebase)

When asked "is ticket X still a valid issue?", fetch it, then classify each acceptance criterion as satisfied / partial / missing against the CURRENT default-branch code. Deliver a verdict — valid / partially-stale / obsolete — with a per-AC evidence table (use `path:line`). No implementation plan, no saved docs unless asked.

- The acceptance criteria are often stored inline in the description (a "Done When" / "Acceptance Criteria" section), not a separate custom field — read the full description body, not just the summary.
- A Jira comment or status saying the ticket is "outdated" / "already done" is a HYPOTHESIS to test against the code, never a verdict to accept — reporters guess; the checkout is ground truth. Trace every AC and report where the code contradicts the comment.
- Distinguish "AC unmet" from "the ticket's stated premise is stale." A ticket can be simultaneously still-valid (features absent) AND mis-framed — e.g. a `[UI]` tag on work that is actually a backend change, or a count like "only N chips" that a later merge already changed. Report both; the reporter needs the framing correction as much as the verdict.
- An AC may span more than one repo (UI + backend). Check every repo the ticket references before declaring an AC missing; find the sibling repo by convention (an adjacent checkout dir) rather than assuming a single repo.
- When an AC names a scope/routing concept, verify a grep hit is the SAME concept, not a homonym — text like "out of scope" / "redirect" can mean inter-dataset routing in one place and infrastructure-query handling in another. Read the matched block before counting the AC as satisfied.
- Before treating a dirty working tree as real changes, check for Git-LFS smudge/clean drift (`git check-attr filter -- <path>` shows `filter: lfs`; a tiny "N -> M bytes" binary diff with 0 insertions/deletions is the pointer artifact). LFS-tracked binaries flagged modified are usually NOT real edits, so current main is effectively clean.

## Pitfalls

- ADDING WITHOUT `--auth oauth` causes all requests to fail with
  "Server returned an error response" — no useful error, just a silent 401.
  Fix: remove and re-add with `--auth oauth`, then `hermes mcp login`.

- `hermes mcp login` needs an interactive terminal (browser redirect). On macOS
  it opens a browser tab automatically. If running non-interactively, run it
  via `terminal(background=True)` and poll output to capture the auth URL.

- MCP tools are NOT available from `execute_code` or raw terminal calls. Always
  use `hermes chat -q '...'` to invoke them from a CLI session.

- The server name in config must match exactly when calling `hermes mcp test`,
  `hermes mcp login`, etc. Check with `hermes mcp list`.

- `hermes config set mcp_servers.<name>.auth oauth` shows `***` in output —
  expected, the value is redacted, not missing.

## Reference files

- `references/sap-jira-setup.md` — SAP OAuth details and confirmed tool list
  (2026-08-25).
