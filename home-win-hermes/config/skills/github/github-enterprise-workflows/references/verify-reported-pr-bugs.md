# Verifying reported PR-review bugs before fixing

When a PR review comment claims a bug (e.g. "this drops package Y", "this is
hardcoded for dev", "the display map is wrong"), the claim is often made
against an assumption about dependency versions, submodule commits, or config
that does NOT match what is actually locked/committed. Reproduce the reviewer's
reasoning against the real artifacts FIRST — several "confirmed bugs" are false
positives once checked.

## Dependency-extra semantics

If the claim is "extra X drops package Y":

- Read the ACTUAL extra definition in the locked dependency / submodule, at the
  pinned commit — NOT the version the reviewer assumed.
- Example: a claim that `[gen-ai]` drops `langchain_hana` was true for submodule
  v2.5.2 but FALSE for the v2.3.0-26 the PR actually pins (that version's
  `[gen-ai]` extra still lists `langchain_hana` and `hdbcli`).
- Command: `git submodule status` then inspect
  `submodules/<name>/pyproject.toml` at the locked commit
  (`git -C submodules/<name> show $(git ls-tree HEAD submodules/<name> | awk '{print $3}'):pyproject.toml`).

## Lockfile vs pyproject consistency

If told "uv.lock is out of sync with pyproject":

- Run `uv lock --check` AND inspect the committed lock for the package in
  question.
- A regenerated-from-scratch lock (plain `uv lock`) can DROP packages the
  committed lock had (e.g. fastapi) — so do NOT blindly `uv lock` to "fix" a
  claimed mismatch. First confirm the committed lock is actually broken.
- If the committed lock is self-consistent for the locked submodule, the claim
  is a false positive. Restore the committed lock (`git checkout HEAD --
  uv.lock`) and do NOT regenerate.
- Note: in dev-container workflows the app resolves deps via `uv sync --dev`
  against `uv.lock`; the host's `uv` (different Python, e.g. 3.14 vs 3.12) is
  NOT representative. Regenerating the lock on the wrong Python can corrupt it.

## Config / env wiring

If told "X is hardcoded for dev":

- Grep the actual config files per environment (dev/int/prod). A value may be
  correctly per-env already, or the "hardcoded" line may only run for one
  environment.
- For GHE CI, config is often loaded by a script (e.g. `load_config.py`) that
  selects `deployment/<env>/config.conf`; check both the conf and the loader.

## Tool-name / API-shape claims

If told "the display map / collision guard is wrong":

- Inspect the ACTUAL tool names the server returns and the ACTUAL code path.
- A claim based on assumed tool names (e.g. assuming the MCP server exposes
  OData-style names) is often wrong — check `docs/` and the discovery output.

## Rule

Reproduce the reviewer's reasoning against the real artifacts. If the claim does
not hold for the locked state, mark it "not a bug at this state" and say so
explicitly — do NOT apply a fix that diverges from the committed baseline just
to satisfy a false-positive review comment.
