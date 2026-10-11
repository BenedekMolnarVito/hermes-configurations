---
name: llm-evaluation-maintenance
description: "Use when reviewing or changing an LLM evaluation system."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [evaluation, llm-as-judge, ground-truth, mlflow, datasets, onboarding]
    related_skills: [systematic-debugging, test-driven-development]
---

# LLM Evaluation Maintenance

## Goal

Explain or modify an evaluation system from executable evidence, not from documentation alone. Trace one dataset row end to end: input, live prediction, trace correlation, scorer input, aggregate metric, and review UI.

## Procedure

1. Read the work item completely, including comments, acceptance criteria, and change history. Extract the stated symptom, affected cases, desired behavior, and any ambiguity; do not infer acceptance criteria that are absent.

2. Establish repository state before interpreting the ticket:
   - inspect branch, status, and base comparison;
   - distinguish existing workspace noise from ticket changes;
   - inspect relevant history for prior scorer or dataset migrations.

3. Locate evaluation artifacts in parallel:
   - runner or CLI entry point;
   - active config and workflow invocation;
   - active dataset and schema documentation;
   - scorer implementation and scorer factory;
   - inherited framework execution path;
   - serving endpoint trace tags;
   - result viewer or evaluation bench.

4. Follow executable truth in this order:
   - dataset loader and row schema;
   - prediction source and endpoint;
   - request concurrency and identifiers;
   - trace generation and retrieval;
   - scorer construction;
   - exact values passed into the scorer;
   - per-row assessment and aggregate metric names;
   - UI/read-model interpretation.

5. Verify configuration against prose documentation. Report mismatches explicitly, especially:
   - active scorer versus documented scorer;
   - judge model version;
   - dataset row count and ID range;
   - metric and assessment names;
   - whether provenance fields are truly excluded from judging.

6. For a ground-truth complaint, inspect the complete affected rows: question, expected response, provenance recipe, actual answer if available, and hierarchy/reference data. Determine whether the failure comes from wrong facts, incomplete facts, inconsistent granularity, or judge instructions.

7. Check the scorer call boundary. Never assume only `expected_response` is graded because documentation says so; verify whether the scorer receives that string or the entire `expectations` object. If the whole object is passed, restrictive or stale provenance text can affect the verdict too.

8. For hierarchy answers, distinguish:
   - direct children from all descendants;
   - aggregation nodes from leaf members;
   - requested grouping level from the rows shown;
   - static packaged hierarchy data from live hierarchy output.
   Compute counts programmatically rather than by inspection.

9. For numeric ground truth, require reconciliation:
   - component values sum to the headline total;
   - the hierarchy level in metadata matches the displayed grain;
   - filters, period, measure, currency, and polarity match the question;
   - omitted zero components are identified as zero, not silently treated as nonexistent.
   - Before accepting a zero result, differential-test the same scope through independent query shapes: the tool's normal filter path, raw fact-key scalar/list filters, and representative single leaves known or suspected to be booked. A successful empty response proves only that the emitted filter matched nothing, not that the business scope is empty.
   - Inspect the exact filter payload after translation. Cube-specific fact keys and external-hierarchy keys may differ; validate both key representation and row-axis mode against live results.

10. Treat an instruction to preserve ground truth as an absolute scope boundary, even when a plan recommends changing expected answers or provenance. Do not edit dataset references, recipes, or integrity tests that encode them; instead use the unchanged row as the acceptance oracle and fix the prediction path or report that the agent is factually wrong.

11. Before editing a dataset, obtain explicit authorization for that exact file and change after independently validating the source data. A plan alone is not authorization when the user has prohibited ground-truth edits. Update both the expected answer and any scorer-visible provenance consistently only when authorized. Add or strengthen integrity tests when the mismatch could recur structurally.

12. Verify in layers:
   - JSON/schema and dataset integrity tests;
   - scorer unit tests;
   - hierarchy/tool tests;
   - targeted live evaluation for affected rows when supported;
   - result inspection in the same UI or MLflow view maintainers use.
   After every dataset edit, regenerate any targeted dataset fixture from the current repository file immediately before the live run; a temporary copy made before the edit silently tests stale ground truth.
   - To verify a "data product was down, now returns values" claim without the full scored run, drive the live agent directly: see `references/live-stack-verification.md` for starting the local stack, the token-refresh reality, the in-process tool probe that reconciles a grouped breakdown against the node total, the `/v2/serve` path, and wire-level confirmation.

## Reporting Format

Lead with a one-sentence problem statement, then cover:
- how evaluation flows end to end;
- exact code locations;
- what each affected case tests;
- why the current reference can misgrade a correct answer;
- likely implementation and verification scope;
- documentation drift or unresolved evidence.

Use `path:line` references. Clearly separate confirmed repository facts, work-item claims, and conclusions that still require a live trace.

## Pitfalls

- Treat active configuration as authoritative over docs because scorer migrations often leave prose stale.
- Do not call semantic similarity and correctness interchangeable; they optimize different failure modes.
- Do not claim a dataset field is documentation-only until the scorer invocation proves it is excluded.
- Do not accept a richer answer merely because it contains more detail; verify every added figure and hierarchy relationship against an authoritative source.
- Do not use a single aggregate when the question asks for a component breakdown, and do not present leaf rows while metadata claims component-level grouping.
- Do not silently rewrite ground truth to match one stochastic model response; establish the complete domain-correct answer first, then make the reference tolerant only to non-substantive variation.
- When a live run passes only after local dataset edits, discard it as acceptance evidence and rerun against the restored committed reference; the scorer evaluates the data loaded at run time.
- Inspect the trace's tool spans and final answer, not only `correctness/mean`: a passing or failing judge verdict does not prove that the agent retained the requested hierarchy scope through all tool calls.
- When hierarchy lookup returns padded leaf IDs, verify the exact filter representation accepted by the live cube before calling a zero result authoritative; hierarchy identifiers and fact-table wire values can differ.
- Do not present a newly edited reference as live-verified until a new run has loaded that exact dataset revision and returned row-level scorer results; matching a prior response by inspection is not equivalent to scorer execution.
- When reading tee'd/append-only service logs to judge a run, filter by today's date first; these files accumulate 403/500/currency errors from every prior session, and an unfiltered grep makes a healthy run look broken by surfacing historical failures.
- A stale-looking on-disk auth token is not proof re-authentication is needed: start the stack and check for a refresh-loop success line before asking the user to log in, because a long-lived refresh_token mints a fresh short-lived access token at boot.
