# Import-guide section skeleton (ships INSIDE the bundle as IMPORT_GUIDE.md)

Write the guide in plain text (it may be read in a terminal). Sections, in order:

0. DECRYPT THE BUNDLE (target machine)
   - exact `openssl enc -d -aes-256-cbc -pbkdf2 -iter <N>` line, then `tar -xzf`.
   - note OpenSSL ships with Git for Windows (Git Bash); offer 7-Zip AES as an alt.
   - how to verify the SHA-256 in MANIFEST.txt.

1. INSTALL HERMES ON THE TARGET (if absent)
   - WSL2 path (POSIX, fewest surprises): `wsl --install` then the install.sh one-liner.
   - native Windows path: point at the docs' Windows install, then confirm `hermes --version`
     AND `python --version` both work in a NEW terminal (PATH updated). Python is REQUIRED
     for shell hooks.
   - baseline launch once (`hermes`) to create the home dir, then exit.

2. IMPORT THE FILES
   - Option A: a scripted importer (PowerShell for native Windows / shell for WSL).
   - Option B: manual copy table into `$HERMES_HOME` (or `%USERPROFILE%\.hermes`), with
     `chmod 600` / owner-only ACL on `.env` and `auth.json`.
   - the Notepad-BOM warning for config.yaml.

3. INSTALL THE PLUGINS the config's `plugins.enabled` lists (`hermes plugin install <name>`).

4. APPROVE THE SHELL HOOKS once (allowlist was not ported; first `hermes` session prompts).

5. FIX THE MODEL PROVIDER if `base_url` is a localhost service not replicated on the target
   (`hermes model` picker; keys already in .env).

6. RE-AUTH OAUTH MCP servers on first use; final `hermes doctor`.

Also include at the top: a WHAT-IS-IN-THIS-BUNDLE tree and an explicit NOT-INCLUDED list
(session history, codebase, caches, runtime-local state), and a CAVEATS SUMMARY mapping each
macOS->Windows difference to the step that handles it. End with the built-in-full-backup
alternative (`hermes backup` / `hermes import`) for a complete clone including history.

## Windows importer essentials (if you ship a .ps1)
- resolve home from `$env:HERMES_HOME` else `%USERPROFILE%\.hermes`.
- pre-flight: warn (don't die) if `hermes` or `python` missing from PATH.
- prompt before overwriting existing files unless `-Force`.
- tighten secret ACLs: `icacls <path> /inheritance:r /grant:r "$($env:USERNAME):(F)"`.
- do NOT auto-approve hooks; print the manual next-steps list.
