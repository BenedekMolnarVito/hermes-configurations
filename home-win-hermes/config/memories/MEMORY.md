CFAAI LLM wiki use ONLY when user say wiki. Path: /Users/C5418860/VSCodeRepos/cfaai-llm-wiki/vault. Skill cfaai-wiki-save-and-lint do ingest+lint.
§
FAA repo: run ALL commit push test smoke lint build dep command INSIDE devcontainer, even when Hermes on mac. Git LFS only in container. Use faa-devcontainer-execution skill. Never host run. Never --no-verify. Host LFS binary change = smudge drift, not real change.
§
Truncation: auto-chunk + resume silently (hard rule, ~/.hermes/SOUL.md slot 1; engine auto-continue caps at 4).
§
User work folder = /Users/C5418860/VSCodeRepos. Work repos there: cfa-agentic-hub, cfaai-llm-wiki, data-product-gateway, dsp-mcp-manager, fin-analyst-agent (FAA, main), fin-analyst-agent-ui, fin-analyst-agent.wiki, firefly-proxy, octoroute-tenants-qa, product-insight-agent. Also folders: sample_projects, mcp-test, TEMP.
§
delegate_task quirk: large inline dispatch/review prompts (~8K+ tokens) time out the stream. Fix: write brief/instructions to a file in the workspace, dispatch a SHORT prompt 'read <path> first, authoritative'. Subagent reports/diffs go to files, never inline.
§
SDD parallelization (proven): group plan tasks into FILE-DISJOINT clusters (zero file overlap); shared-file tasks stay serial within a cluster. Clusters run in parallel, each in OWN git worktree+branch (npm ci per worktree). One subagent owns a cluster, runs its tasks serially. Merge branches --no-ff = zero conflicts. Still review each FR's commit individually.
§
Windows: Hermes PATH puts bundled Node 26 (AppData/Local/hermes/tools) before scoop Node 25 (/c/Users/molna/scoop/apps/nodejs/current). Prepend scoop dir for project npm/vitest (native modules built for Node 25).
§
tier-router gotcha: a model removed from model.aliases also leaves the router eligible set — if delegation.model still points at it, delegate requests pass UNROUTED (tell: no tier-router.jsonl 'selected' entry) and fail on the dead target. Change BOTH alias and delegation.model. Aliases re-read live per new subagent session.