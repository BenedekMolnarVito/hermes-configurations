# Memory Provider Token Optimization

Reduce per-turn token cost from external memory providers (Hindsight, Honcho, Mem0, etc.).
The main offender is auto-recalled context injected into the system prompt every turn;
auto-retained content is secondary (it does not enter context, but inflates the server-side
store and slows recall precision over time).

## Measure first

```bash
hermes prompt-size            # total system prompt; memory injection is part of this
hermes prompt-size --json     # machine-readable breakdown
```

The memory-provider block shows in the system prompt as "# Hindsight Memory" (or the
provider's equivalent). Eyeball its size in the prompt-size output to know the actual cost.

## Hindsight-specific config levers (zero code, immediate effect)

Edit `~/.hermes/hindsight/config.json` (or `$HERMES_HOME/hindsight/config.json` for a profile):

| Key | Default | What it does | Recommended |
|-----|---------|-------------|-------------|
| `recall_max_tokens` | 4096 | Hard cap on recalled memory tokens per turn | 1024–2048 for most workflows |
| `recall_budget` | `mid` | Server-side retrieval thoroughness (low/mid/high) | `low` for routine work; `mid` for research-heavy |
| `recall_types` | `observation` | Fact types recalled. Observations are pre-consolidated summaries — already the densest option. Adding `world,experience` re-ships the raw evidence observations already summarize | Keep `observation` (default) |
| `retain_every_n_turns` | 1 | Retain every Nth turn | 2–3 to halve/third write volume without losing much |
| `memory_mode` | `hybrid` | `hybrid` = auto-inject + tools; `tools` = recall only on explicit tool call; `context` = inject only, no tools | `tools` eliminates auto-injection entirely (nuclear) |
| `recall_max_input_chars` | 800 | Truncate the query sent to recall | Lower if queries are long; irrelevant tokens in the query broaden retrieval |
| `auto_recall` | true | Master switch for per-turn recall | false to disable entirely |
| `recall_sync` | false | false = recall runs against previous turn (background); true = current turn (higher relevance, adds latency) | false is fine; the stale-by-one-turn tradeoff saves a blocking call |
| `recall_prompt_preamble` | (default header) | Custom header prepended to injected memories | Can instruct the model to treat memories as compressed hints |

A quick first pass: set `recall_max_tokens: 1536` and `recall_budget: low`.

Temper the expectation: when `auto_recall` is on and `memory_mode: hybrid`, this first pass
alone often moves the needle little, because `recall_max_tokens`/`recall_budget` only bound
the recall RESULT size — the auto-inject path (`_do_recall` -> system prompt every turn) is
the real drain and is unaffected by the budget knob if the recalled set is already under the
cap. If the user reports "token usage not reduced significantly" after a config-only pass,
do NOT re-tune the same knobs; move to the structural levers: `auto_recall: false` or
`memory_mode: tools` (eliminate auto-injection entirely), raise `retain_every_n_turns`, or
the `_do_recall` monkey-patch below. Confirm with `hermes prompt-size` before and after so
the claim rests on a measured delta, not a hunch.

## Reverting a config change (no git, no backup)

`~/.hermes/hindsight/config.json` and most user-scoped Hermes config live OUTSIDE any git
repo and have no automatic `.bak`, so "revert to how it was yesterday" has no VCS to lean on.
Recover the prior state from the artifacts the earlier change left behind, in this order:

1. The plan file that drove the change (`~/.hermes/plans/<date>-<topic>.md`). A well-written
   plan records the EXACT before-state ("currently contains: {json}") and the diff per key
   ("`recall_budget`: `mid` -> `low`"), so it is the authoritative baseline to restore to.
2. The delegation manifest (`~/.hermes/cache/delegation/live/deleg_*/manifest.json` and the
   per-task `task-N.log`), which records each subagent's goal verbatim — enough to see which
   files were touched and what values were written.
3. `session_search(query=...)` over past sessions, then read the matching session; the
   original edit turn shows the pre-edit `read_file`/`cat` output.

Build the baseline from those, write it back, and VERIFY with a `python3 -c` json.load +
exact-dict assertion before telling the user it's reverted.

Scope-confirm first: a Hindsight optimization effort usually spans TWO things — the
`config.json` knobs AND the hook/plugin/jevlib condensation machinery. "Revert the config"
is ambiguous between them; `clarify` which parts to revert before touching the harder-to-undo
machinery (hooks, a monkey-patch plugin), since restoring one `config.json` is trivial but
ripping out hooks is not.

## Architecture of the two paths (know which one you're optimizing)

### Auto-recall (the main token drain)
Flow: `queue_prefetch()` → background thread → `_do_recall()` → `arecall()` API →
results formatted as `"- {text}"` lines → stored in `_prefetch_result` → consumed by
`prefetch()` next turn → `_finish_prefetch()` wraps with header → injected into system prompt.

This path does NOT go through the Hermes tool-call pipeline. Shell hooks
(`pre_tool_call`, `transform_tool_result`) do NOT fire. To intercept it you must
patch the plugin code itself (`_finish_prefetch()` or `_do_recall()` in
`~/.hermes/plugins/hindsight/__init__.py`).

### Auto-retain (secondary concern)
Flow: `sync_turn()` → `_build_turn_messages()` (full verbatim user+assistant as JSON) →
queued to writer thread → `aretain_batch()` API. Hindsight server-side then extracts
observations (consolidated, deduplicated summaries). So the server already does
condensation on the STORED side — the raw content is intermediate, not what recall returns.

Retain condensation (compressing before sending to server) is lower priority because
the server's observation layer already distills. It mainly helps if the server's
extraction LLM is slow or expensive on long inputs.

### Tool-invoked recall/retain
`hindsight_recall` and `hindsight_retain` go through the normal tool pipeline, so
Hermes shell hooks DO fire:
- `transform_tool_result` on `hindsight_recall` can condense returned memories
- `pre_tool_call` on `hindsight_retain` can condense content before storing

But these only cover explicit agent-initiated tool calls, not the auto paths above.

## Advanced: condensation via a SEPARATE user-plugin monkey-patch

To condense auto-recalled memories before injection (the main win), monkey-patch the
provider from your OWN plugin — do NOT edit the installed Hindsight plugin's files.
A separate plugin survives `hermes plugins update hindsight` because it never touches
that plugin's source; editing `~/.hermes/plugins/hindsight/__init__.py` in place loses
the patch on every update. Likewise never edit `~/.hermes/hermes-agent/` (overwritten on
`hermes update`). Everything stays user-scoped under `~/.hermes/`.

Patch `_do_recall(self, query) -> (text, count)`, NOT `_finish_prefetch`. `_do_recall`
has the `query` in scope (required for relevance reranking) and sits on BOTH the sync
(`recall_sync=true`) and background prefetch paths, so one wrap covers both; `_finish_prefetch`
has no query and only formats the header. Patch point verified at ~line 1204 of the
Hindsight `__init__.py`; the recall branch returns `"\n".join(f"- {r.text}" ...), len(results)`.

User-plugin shape (auto-discovered from `~/.hermes/plugins/<name>/`): a `plugin.yaml`
(`name`/`version`/`description`) plus a module exposing `def register(ctx)`. In `register`,
wrap the method and set an idempotency flag so a second `register` call does not double-wrap:

```python
def register(ctx):            # ctx unused — the patch runs at register time
    import hindsight
    cls = hindsight.HindsightMemoryProvider
    if getattr(cls, "_patched", False):
        return
    orig = cls._do_recall
    def wrapped(self, query):
        text, count = orig(self, query)
        if not text.strip():
            return text, count
        new = condense_memories(text, query=query)   # your fn; fail-open inside
        n = sum(1 for ln in new.splitlines() if ln.strip().startswith("- "))
        return new, (n or count)   # recount so the recall indicator stays honest
    cls._do_recall, cls._patched = wrapped, True
```

EVERY path must fail open: if the `hindsight` module is not importable yet, the method
signature changed, or condensation errors — return the original `(text, count)` unchanged.
A memory optimizer that can crash the turn is worse than verbose memory.

Condensation options (cheapest to most effective; a real pipeline chains them):
1. Jaccard dedup (no LLM call): drop lines whose lowercased word-set overlaps a kept line
   above a threshold (~0.7). Catches residual near-duplicates that survive to the recall
   result. Pure stdlib, zero latency.
2. JEV NOUL rerank (relevance, not truncation): score each memory against the query with a
   `noul` question, keep the top-k, drop the rest. Beats blind `recall_max_tokens` truncation
   because it keeps the RELEVANT memories, not the first N. See the `jev-decisions` skill's
   `scripts/rerank.py` for the exact `noul`/`safe_decide` call shape (pass a dict to `noul`,
   read `ans.get("noul", 0)`); it is `UNAVAILABLE`-safe (fall through to all memories when JEV is down).
3. Rule-based telegraphic compression (no LLM): the `jevlib.caveman.compress()` helper strips
   filler while protecting code/paths/numbers; gate it on `caveman.enabled("<kind>")` keyed in
   `~/.hermes/agent-hooks/jev-guard.json`. ~30% reduction, zero latency.
4. Cheap LLM call (Haiku/Gemini Flash): "Compress to essential facts. Telegraphic style.
   Keep entity names and numbers exact. Max N tokens." ~60% reduction, +200-500ms/turn.

Tool-invoked `hindsight_recall`/`hindsight_reflect` additionally need a
`transform_tool_result` shell hook (the monkey-patch only covers the AUTO path). The hook
reads a JSON payload on stdin (`hook_event_name`, `tool_name`, `extra.result`, and the tool
args under `extra.arguments`/`extra.args` — recover `query` from there for reranking) and
writes the REPLACEMENT text to stdout; empty stdout means leave unchanged. Register it under
`hooks.transform_tool_result` in `config.yaml` with a `matcher` regex on the tool name.
Fail open: any error -> emit nothing, exit 0.

## Honcho-specific levers

| Key | Default | What it does |
|-----|---------|-------------|
| `contextTokens` | null (uncapped) | Hard token budget for auto-injected context per turn |
| `contextCadence` | 1 | Minimum turns between context API calls |
| `dialecticCadence` | 2 | Minimum turns between LLM reasoning calls |
| `dialecticDepth` | 1 | Reasoning passes per invocation (1-3) |

Set `contextTokens: 2000` and raise `dialecticCadence` to 3-4 for immediate savings.

## Literature techniques (for custom implementations)

- **Token budgeting** (Mem0): hard ceiling on memory tokens, fill in priority order, stop
  when budget hit, append "[N memories omitted]". Hindsight's `recall_max_tokens` is the
  native version of this.
- **Hierarchical summarization**: group related memories and summarize groups before
  injection. Requires a custom condensation step.
- **Ebbinghaus eviction**: decay old/infrequently-accessed memories. Server-side concern;
  Hindsight handles this internally.
- **Jaccard self-curation**: deduplicate near-identical memories. Hindsight already does
  this server-side at storage time via observation consolidation, so a RETAIN-side client
  dedup is low-gain (don't bother). A RECALL-side client dedup is still worth it — it catches
  residual near-duplicates that survive consolidation into the recall result (see the Jaccard
  step in the condensation pipeline above).
- **Zero-token memory ops** (arXiv 2607.29377): use structured retrieval (entity graphs,
  temporal hierarchy) with no LLM calls for memory operations — only the final QA reader
  invokes an LLM. Hindsight's knowledge graph already does this; the issue is result
  verbosity, not retrieval cost.
