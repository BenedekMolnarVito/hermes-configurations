---
name: sap-sso-browser
description: "Drive SAP SSO web flows via a visible real-profile browser."
version: 1.0.0
author: Benedek Molnar (C5418860), Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [browser, sap, sso, jira, config, macos]
    related_skills: [jira, hermes-agent]
---

# SAP SSO Browser

Drive authenticated SAP web flows (JIRA create form, any Microsoft-SSO-gated
SAP page) through a VISIBLE browser that reuses the user's own Chrome logins, so
SAP SSO cookies carry over and no interactive password/MFA is needed mid-session.
This exists because the default headless browser-use backend cannot do SSO.

## When to Use

- A task needs an authenticated SAP page the user is SSO'd into (JIRA create
  dialog, SAP wiki edit, BTP cockpit, etc.).
- Creating/editing a JIRA issue: the `sap-jira` MCP is READ-ONLY (search / get /
  transitions only, NO create or general-edit tool), so writes go through the
  browser create/edit form.
- Don't use for: pure JIRA reads (use the `sap-jira` MCP), or public pages
  (plain `web_extract` / default browser is fine).

## Why the default browser fails

The `browser-use` backend only ever launches Chromium with `--headless=new` and
ignores `browser.headed: true` / `AGENT_BROWSER_HEADED=1`. A headless window is
invisible to the user, so interactive Microsoft SSO (email -> password -> MFA)
can never be completed. Verified: the live chromium args keep `--headless=new`
even after setting the config and killing/respawning the harness daemons.

## Required config (one-time, already set 2026-10-01)

Set via `terminal(command="hermes config set <key> <val>")` (never hand-edit
config.yaml). All four are in `~/.hermes/config.yaml`:

- `browser.backend` = `off` -- forces the built-in local agent-browser tools
  (`browser_navigate`, `browser_click`, ...), which honor the headed toggle.
  NOT `browser-use`.
- `browser.headed` = `true` -- visible Chromium window, kept open between turns.
- `browser.use_real_profile` = `true` -- snapshots the user's ACTIVE Chrome
  profile (cookies/logins) and launches the real Chrome binary on it, so SAP SSO
  cookies load.
- `browser.real_profile_autoclose` = `true` -- Hermes ASKS before closing Chrome
  to grab the profile lock; never closes it unattended.

Verify: `terminal(command="hermes config get browser")` shows backend=off,
headed=true, use_real_profile=true.

## Activation (MANDATORY sequence)

1. The config toolset switch (browser-use's single `browser_exec` -> the
   built-in browser tools) takes effect ONLY in a NEW Hermes session. It CANNOT
   apply mid-conversation (prompt-cache invariant). After changing backend, tell
   the user to start a new session.
2. On macOS, Chrome must be FULLY QUIT when the real-profile session launches --
   a running Chrome holds a hot write-lock on `Login Data` / `Login Data For
   Account` / `Web Data`, so the SQLite online-backup snapshot fails and the
   session opens signed-out. With `real_profile_autoclose: true` Hermes offers to
   close it (asks first). The user may reopen Chrome once the agent window is up.
3. In the new session, the FIRST `browser_navigate` opens a visible Chrome
   window already carrying the user's SAP SSO -- the gated page loads logged-in.

## Creating a JIRA ticket (CFAAI conventions)

1. `browser_navigate` to `https://jira.tools.sap/secure/CreateIssue!default.jspa`.
   A real page title (not a Microsoft "Sign in") means SSO is live.
2. Dismiss the blocking info popup: click `#infoPopupOkButtonId` if present.
3. Step 1 = Project + Issue Type. Project `CFAAI`. Issue type via `#issuetype-field`
   (display) backed by hidden `#issuetype`; focus the field, pick the option li.
   Advance with `#issue-create-submit` ("Next").
4. Step 2 = details. Fill long fields by setting `el.value=...` + dispatching an
   `input` event (NOT char-by-char typing, which times out on long bodies).
   Description uses Jira WIKI markup (`h3.`, `*` bullets), not Markdown.
5. Component/s: real `<select id="components">`; set `option.selected` by value +
   dispatch `change`. CFAAI component value is "Financial Analyst Agent".
6. Submit `#issue-create-submit` ("Create"). Read the `CFAAI-\d+` key from the
   `/browse/...` redirect URL.
7. VERIFY via the `sap-jira` MCP (`jira_search` with `key in (...)`) that
   issue_type, project, and component actually landed -- a redirect URL is not
   proof the fields saved.

## Pitfalls

- Changing `browser.backend` and expecting it live THIS session -- it only takes
  effect next session. Don't retry browser calls hoping it flips.
- Exporting `AGENT_BROWSER_HEADED=1` in a `terminal` shell does nothing:
  `browser_exec` spawns its daemon from Hermes's process env, not the shell's.
- macOS TCC blocks `terminal`/`search_files` from reading
  `~/Library/Application Support/Google/Chrome` ("Operation not permitted"); the
  real-profile launcher runs as the Hermes process and still works. Can't
  enumerate Chrome profiles from a shell.
- Multiple Chrome profiles -> agent uses last-used by default; pin the work one
  with `browser.real_profile_pin='Profile N'` (directory name under the Chrome
  user-data dir). A pin naming a missing dir fails closed, no silent fallback.
  Symptom when the pin is wrong/unset: snapshot error `No such file or directory:
  .../Google/Chrome/Default` (the launcher tries `Default`, which this user does
  NOT have -- the SAP-logged-in profile is `Profile 1`). Set the pin, don't guess
  repeatedly.
- PERSISTENT "chrome is running and has its profile locked" after Chrome is fully
  quit (verified: `ps aux | grep -i chrome` = 0 procs, no `Singleton*` lock files
  at the user-data-dir root or in `Profile 1`, `hermes browser close-profile` says
  "no matching browser process", snapshot dir cleared): this is a deterministic
  false-positive in the launcher's lock detection, NOT a real Chrome lock. It did
  NOT clear this session via any of: osascript quit, pkill, close-profile,
  removing lock files, clearing `~/.hermes/browser-profile/chrome`, or user doing
  a clean Cmd+Q. Treat the real-profile browser as BLOCKED for the session and
  fall back to the hand-the-user-ticket-text + verify-via-MCP path. Suspected
  root cause: the launcher spawns its own transient Chrome probe that races its
  own lock check; a fresh Hermes session may be required to reset launcher state.
- Real-profile browsing is consent-gated convenience, NOT isolation -- the agent
  browses AS the user with their cookies. Revoke with
  `browser.use_real_profile false` (Hermes deletes the profile snapshot on next
  browser use).

## Verification

- `terminal(command="hermes config get browser")` -> backend=off, headed=true,
  use_real_profile=true, real_profile_autoclose=true.
- New session: first `browser_navigate` to a SAP SSO page loads logged-in (no
  Microsoft "Sign in" redirect) in a VISIBLE window.
- Any created JIRA key independently confirmed through the `sap-jira` MCP.
