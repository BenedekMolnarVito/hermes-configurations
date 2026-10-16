---
name: llm-evaluation-ground-truth
description: "Use when maintaining LLM evaluation ground truth."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [evaluation, llm-as-judge, ground-truth, mlflow, datasets, testing]
    related_skills: [test-driven-development, systematic-debugging, plan]
---

# LLM Evaluation Ground Truth

Use this workflow when adding, correcting, or reviewing reference answers for an LLM or agent evaluation dataset.

## Procedure

1. Establish whether ground-truth editing is authorized before reading a plan as an implementation mandate. An explicit user instruction to preserve references makes the dataset read-only, even if a ticket or plan proposes edits; investigate agent, tool, scorer, or harness behavior instead. Treat executable configuration as authoritative when prose docs disagree.
2. Trace exactly what reaches the scorer. Check whether it receives only the reference answer or the complete expectations object; every field visible to the judge must be accurate and non-restrictive.
3. Capture a baseline row with the actual answer, tool trajectory, raw observations, judge verdict/rationale, model or prompt version, and run/trace identifiers.
4. Independently reproduce the expected result from the authoritative data source. Never promote an agent answer to ground truth merely because it is plausible or richer than the old reference. For an empty result, probe the same scope with raw fact keys and representative individual leaves before treating zero as authoritative; a key-shape translation bug can return a successful empty response. When the live backend is unreachable and the authoritative source is an external artifact (a reviewer's BI-tool screenshot, an export), transcribe every figure precisely — delegate image transcription to a vision-capable subagent, since not every model reads pixels — and cross-check it by reconciling the component parts to a total shown in the same artifact before trusting the numbers. Record that the figures came from that artifact (source, filters, date) in the provenance recipe and flag to the user that this is not a live-query verification.
5. Reconcile numeric totals programmatically and verify scope, period, measure, units, polarity, entity identifiers, hierarchy relationships, and aggregation grain. When a dimension supports both flat fact members and an external hierarchy, separately validate the filter key representation and group-by axis: a hierarchy key may not equal the booked fact key, and hierarchy expansion may return ancestors rather than the requested leaves. Exercise the exact identifier shape returned by lookup (including wire-form prefixes/member paths), not only the packaged canonical ID, because lookup-to-query round trips can otherwise bypass normalization.
6. For hierarchy answers, distinguish direct children from nested descendants. Record whether live data or a packaged fallback was authoritative and resolve differences explicitly. Do not claim that one lookup substantiates child lists or descendant counts unless its actual response contains them; when live search returns only node identity/path, attribute structural facts to the packaged source used.
7. Update the reference answer and its retrieval/provenance recipe together. Remove stale constraints from both; an accurate answer paired with a stale recipe can still bias an LLM judge.
8. Add focused regression tests for stable factual invariants. Parse values from the user-facing expected answer and reconcile them numerically; do not satisfy answer assertions with duplicate strings in the provenance recipe. For hierarchy cases, assert exact parent/direct-child relationships and descendant counts rather than token co-occurrence. Bind each guard to the intended row by an intrinsic anchor (the question text or a unique entity id), not only by dict key: dataset expectations are often keyed 0-indexed while humans, reviewers, and test NAMES refer to "case N" 1-indexed, so a guard titled `test_case_8` that reads key `"8"` may silently assert against the wrong row. A guard pointed at the wrong row is worse than none — run it and confirm it actually fails when the target answer is wrong before trusting a green result.
9. Update nearby schema and evaluation documentation in the same change whenever scorer name/model, metric name, dataset size, scorer-input semantics, or developer-tool capabilities/defaults are stale. Verify documented commands and bind/default behavior against executable code rather than preserving historical instructions.
10. Run local integrity and domain-tool tests, then a clean live evaluation. If the runner cannot select individual dataset IDs, generate a temporary filtered dataset/config outside the repository containing only the target rows; preserve the three aligned maps. Inspect the target rows, ensure the run has no prediction failures, and use a temporary negative control to confirm a materially wrong answer still fails.
11. When live evidence shows the agent reaching a correct conclusion only after abandoning an authoritative empty scope, treat it as an agent/prompt defect rather than a ground-truth mismatch. Add a narrowly scoped prompt or behavior regression test, then rerun the target rows with the updated prompt version.
12. Verify contamination handling end to end before accepting a live run: confirm failed predictions remain represented in the scored denominator (or make the run fail), and confirm dashboards read and exclude/flag contamination metadata. Logging a contamination tag is insufficient if the consumer ignores it or missing-trace rows are dropped before scoring.
13. Review the final diff for generated datasets, secrets, binary artifacts, submodule drift, and unrelated prompt/tool changes. If validation required an evidence-based scope expansion into runtime code, update the implementation plan and intended-file checklist instead of leaving them contradictory. Do not use a contaminated or incomplete run as acceptance evidence.

## Ground-truth writing rules

- Do not alter a reference dataset unless the user explicitly authorizes ground-truth changes for the current task. If a reference is accidentally changed despite that constraint, restore the affected files immediately and report the mistake plainly; do not justify it from a plan.
- Encode the complete substantive answer while allowing harmless variation in wording, formatting, ordering, and optional follow-up text.
- Keep chart/table grain consistent with analytical metadata. An analytic slice must reproduce the displayed rows through the real query path; omit it when the displayed aggregation is derived client-side and cannot be represented honestly. If both component and leaf detail are needed, present them as separate reconciled levels.
- State exclusions and sibling relationships explicitly when confusing them would change the total.
- Prefer closed periods or otherwise versioned snapshots for numeric references; record provenance sufficient to regenerate them.
- Re-anchoring a period-dated row when the backing data genuinely MOVED (a redeployed model/cube now holds the periods the old reference's period no longer has): confirm the old scope is empty AND locate where the data now lives (e.g. probe measure-by-period to find the populated fiscal year), then move the period embedded in BOTH the question text and the expected answer forward and re-probe the real figures for the new period — do not keep a stale figure under a new period, and do not leave the question asking for a period that is empty. This is distinct from a key-shape empty (rule 4): here the empty is real, so the fix is a period shift + fresh probe, not a filter-shape fix. Re-derive the moved-period narrative too — a 'closed, nets to zero' story from the old period may be false for the new one.
  Re-anchor marker convention: prefix the retrieval_recipe with `Re-anchored: <old period> → <new period> (<reason>).` This single token is used as the exemption trigger in any integrity guards that bar open-period rows — add a `recipe.lstrip().startswith("Re-anchored:")` branch alongside DATE-HORIZON and Budget/Forecast branches. The marker simultaneously serves as a self-documenting provenance note in the dataset.
- Cross-dataset rows (one question whose parts come from different data products/cubes): verify EACH part against ITS OWN source independently — one half can still be valid while the other is stale, because they can sit on separate cubes with separate data lifecycles. When re-anchoring, move every part to ONE coherent timeframe so the single question is internally consistent, rather than mixing a re-anchored part with a left-alone part at a different period.
- Structure/master-data rows (hierarchy node codes, children, company-code lookups) carry no period figure — if the live structure still matches the reference, DO NOT edit the row during a figure re-anchor; a failure there is an agent hallucination to fix in the prompt (rule 11), not a ground-truth change.
- Do not weaken a reference simply to turn a failing score green. If independent validation disagrees with the agent, classify it as an agent/tool defect and re-scope the work.
- If later evidence disproves a reference edited during the task, correct the reference and its provenance immediately, explicitly document why the earlier evidence was invalid, and rerun the active judge against the exact corrected dataset revision.

## Planning and execution ordering

When the user asks for prerequisite cleanup followed by a plan, perform the requested cleanup first and then write the plan. A planning skill's normal no-mutation rule does not override an explicit ordered request that includes bounded preparatory actions. Save the plan at the exact repository path requested by the user; use the default plan directory only when no target is specified.

## Editing the dataset programmatically

The FAA evaluation dataset is a structured JSON file with three parallel maps (`inputs`, `query_args`, `expectations`). Do NOT use `patch` to edit it — the file contains nested escaped JSON strings (chart-json blocks, analyticSlice objects) that `patch` cannot match once they differ by a single character. The correct approach:

1. Load with `json.loads(Path(...).read_text())` in `execute_code`.
2. Edit the Python dict in-memory (question text, expected_response, retrieval_recipe).
3. Verify assertions on the in-memory dict before writing.
4. Write back with `Path(...).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")`.
5. Reload from disk and re-assert to confirm the write landed correctly.

When live-probed figures are available from a prior session's scratch file, read that file first and treat its reconciled values as authoritative rather than re-probing — probing requires a running stack and is expensive.

## Verification gates

A ground-truth change is complete only when:

- the expected answer and provenance recipe agree;
- arithmetic and hierarchy structure are independently verified;
- focused integrity tests pass;
- the intended correct answer passes the active judge;
- a materially wrong negative control fails;
- the live run is complete and uncontaminated;
- documentation matches executable scorer behavior;
- the final diff is limited to intended source, test, and documentation files.
