CFAAI LLM wiki use ONLY when user say wiki. Path: /Users/C5418860/VSCodeRepos/cfaai-llm-wiki/vault. Skill cfaai-wiki-save-and-lint do ingest+lint.
§
FAA repo: run ALL commit push test smoke lint build dep command INSIDE devcontainer, even when Hermes on mac. Git LFS only in container. Use faa-devcontainer-execution skill. Never host run. Never --no-verify. Host LFS binary change = smudge drift, not real change.
§
truncation (finish_reason length): auto-chunk, no ask. Rule in ~/.hermes/SOUL.md slot 1. Engine auto-continue but cap 4 (agent/turn_truncation.py). Split big output up front. Resume next turn. Never wait for continue.
§
User work folder = /Users/C5418860/VSCodeRepos. Work repos there: cfa-agentic-hub, cfaai-llm-wiki, data-product-gateway, dsp-mcp-manager, fin-analyst-agent (FAA, main), fin-analyst-agent-ui, fin-analyst-agent.wiki, firefly-proxy, octoroute-tenants-qa, product-insight-agent. Also folders: sample_projects, mcp-test, TEMP.
§
delegate_task quirk: large inline dispatch/review prompts (~8K+ tokens, e.g. pasting full briefs/rubrics) time out the stream. Fix: write the brief/instructions to a file in the workspace/worktree, dispatch a SHORT prompt that says 'read <path> first, it is authoritative'. Subagent reports/review-packages/diffs also go to files, never inline.
§
SDD parallelization pattern (proven): to run plan tasks in parallel, group remaining tasks into FILE-DISJOINT clusters (verify zero file overlap first). Tasks that share files collide -> must stay serial within a cluster; disjoint clusters run in parallel, each in its OWN git worktree+branch (npm ci per worktree since node_modules isn't shared). One subagent owns a cluster and runs its tasks serially. Merge disjoint branches back with --no-ff at the end = zero conflicts. Still review each FR's commit individually. Each subagent resolves the model alias correctly from config when you pass the tier.
§
Windows host: Hermes terminal PATH has bundled Node 26 (AppData/Local/hermes/tools) before user's scoop Node 25 (/c/Users/molna/scoop/apps/nodejs/current). Prepend scoop dir for project npm/vitest work (native modules built for Node 25).