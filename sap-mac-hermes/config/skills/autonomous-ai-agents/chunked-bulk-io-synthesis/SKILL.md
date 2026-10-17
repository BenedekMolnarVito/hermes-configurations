---
name: chunked-bulk-io-synthesis
description: "Use when bulky read/write/extract floods context."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [subagents, delegation, chunking, synthesis, context-management, bulk-io, map-reduce]
    related_skills: [subagent-execution-orchestration, jev-hermes-decision-hooks, parallel-review-subagents]
---

# Chunked Bulk I/O with a Synthesis Agent

When a read / web_extract / write is big enough to flood the long-running
orchestrator context, do NOT run it directly. Split it into chunks, hand each
chunk to a subagent that returns only a distilled result, and have ONE synthesis
agent reassemble the chunks into the whole. This is map-reduce for I/O: the bulk
tokens live and die inside the child contexts; the orchestrator keeps only the
final distilled artifact.

Grounded in Agentic-Design-KB: Domain 1 (parallel + hub-and-spoke orchestration,
subagent isolation — no shared memory, pass everything explicitly) and Domain 5
(5.1 context budgeting; 5.3 contain failures at the boundary, prefer partial
results with provenance; 5.4 delegate large scans to a subagent that returns a
distilled finding, never dump whole trees into context).

## When to Use

Trigger when a single tool call's VOLUME — not its difficulty — is the problem:
- read_file over a huge file / large `limit` whose content you will DISTILL,
  not edit verbatim (log triage, scanning a 3k-line file for a few facts).
- web_extract over many URLs, or a large `char_limit`, to be summarized.
- write_file / generation of a document large enough to truncate at the output
  limit (long report, migration, generated code set).
- Any "read all N / scan the tree / extract from these M pages" sweep.
- The `hook_bulk_io_guard.py` JEV gate BLOCKED your direct call (its message
  names this skill). The block is the signal: chunk-and-synthesize instead.

Do NOT use when:
- You genuinely need the content VERBATIM in your own context to reason over or
  edit it (the one file you are patching). Chunking would destroy the coherence
  you need. Bypass the gate with `JEVGUARD_BULK_IO=off` for that one call.
- The volume is modest (fits comfortably in context) — just do it directly.
- It is a bulk CLASSIFY/RANK/TRIAGE job → that is jev-decisions, not this skill
  (handled by hook_batch_guard.py).

## The pattern (map → reduce)

1. PARTITION into chunks that fit a child context with headroom, on a natural
   boundary (per-file, per-URL, per line-range, per report-section). Record the
   chunk index + its boundary so the synthesis agent can order and attribute.
2. MAP: dispatch one subagent per chunk (or one subagent per cluster of chunks)
   with delegate_task. Each child does the bulky I/O for ITS chunk ONLY and
   returns a DISTILLED result to a FILE, never inline. Tier = quick/standard
   (mechanical extraction/summarization); escalate only chunks needing judgement.
3. REDUCE: ONE synthesis agent reads every chunk's distilled file and produces
   the single coherent whole (merged summary, assembled document, deduped
   findings). The synthesis agent is the only place the chunks recombine.
4. The orchestrator receives only the synthesis agent's final artifact path +
   a short status — the raw bulk never enters its context.

## Reads vs. writes

READ / EXTRACT (fan-out, then reduce):
- Each map child reads its slice and returns a structured distillation
  (facts + provenance: which file/URL/line-range each fact came from — KB 5.3/5.6
  partial-results-with-provenance). The synthesis child merges + dedupes.
- For a scan-for-answer, children return only the hits; the orchestrator never
  sees the non-matching bulk.

WRITE / GENERATE (reduce by assembly):
- Partition the target document into sections. Each map child drafts ONE section
  to its own file. The synthesis child concatenates in order, fixes cross-section
  references, and writes the final file.
- This also beats the output-token limit: no single turn emits the whole giant
  document. (Complements the SOUL.md auto-chunk rule — that resumes a truncated
  turn; this prevents the giant turn existing at all.)

## Dispatch mechanics (inherit from subagent-execution-orchestration)

**REQUIRED BACKGROUND:** Use subagent-execution-orchestration for the delegation
mechanics. The load-bearing ones here:
- Hand chunks over as FILE PATHS, never inline. A chunk pasted into a dispatch
  prompt or printed back by a child stays resident in the orchestrator context
  for the rest of the session — which defeats the entire point. Write the chunk
  boundaries / input paths to files; the dispatch and the child's return carry
  only paths + a short status.
- Keep each dispatch prompt well under ~8K tokens (long prompts time out the
  stream). Short prompt: "read <chunk-spec-path>, it is authoritative; write your
  distilled result to <out-path>."
- Children have NO shared memory (KB 1.3): give each child everything it needs —
  its chunk boundary, the exact output format, the provenance it must attach.
- Resolve the model tier explicitly on every dispatch (never inherit).
- Verify each child's output on disk (the out-file exists + has real content),
  not the child's self-report, before handing the set to the synthesis agent.

## Parallel vs. serial

- READ/EXTRACT chunks are independent → fan out in parallel (one delegate_task
  batch). Map children write to DISJOINT output files, so no collision.
- WRITE sections that reference each other have ordering deps → the synthesis
  step is serial, but the section DRAFTS are still parallel (disjoint files).
- For code that must land on a branch, see the file-disjoint cluster rules in
  subagent-execution-orchestration (worktrees per cluster).

## The JEV bulk-io gate (enforcement)

`hook_bulk_io_guard.py` (pre_tool_call, matcher `read_file|web_extract|write_file`)
HARD-BLOCKS a direct bulky call and points here. How it decides:
- LOCAL prefilter (no JEV): sizes/counts vs. `bulk_io` thresholds in
  jev-guard.json (read_lines_min, extract_urls_min, extract_char_limit_min,
  write_chars_min). Below threshold → silent noop, no JEV call.
- Only if bulky → `decisions.is_bulk_io` asks JEV ONE question with a
  NON-content shape ({op, lines|url_count|content_chars, path_hint}) — never raw
  content. chunk_p ≥ `chunk_block_p` (0.7) → block. JEV says LOW when you need it
  verbatim, so a legit full read of your edit target is not blocked.
- Fail-open: no key / JEV down / any error → noop (never blocks on outage).
- Bypass one call: `JEVGUARD_BULK_IO=off`. Tune thresholds in jev-guard.json
  (zero code change); keep the DEFAULTS mirror in jevlib/config.py in sync.
- See jev-hermes-decision-hooks for the hook contract + fail-open invariants.

## Common Mistakes

- Chunking a file you must EDIT verbatim — you lose the coherence you need. Use
  JEVGUARD_BULK_IO=off and read it whole.
- Letting a map child print its chunk back inline — the bulk re-enters the
  orchestrator context. Children write to files; return only a path + status.
- Skipping the synthesis step and reading all chunk files yourself — that just
  re-floods your context. ONE synthesis agent reduces; you read only its output.
- Dropping provenance in the map step — the synthesis agent can't attribute or
  dedupe findings (KB 5.3/5.6). Each distilled fact carries its source.
- Trusting a child's "done" without verifying the out-file on disk.
- Partitioning on an unnatural boundary (mid-record, mid-function) so chunks
  can't be reasoned about independently. Split on real boundaries.
