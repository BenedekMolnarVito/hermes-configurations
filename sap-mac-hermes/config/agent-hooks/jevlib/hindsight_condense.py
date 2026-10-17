"""
jevlib/hindsight_condense.py — Recall condensation, dedup, and JEV rerank for Hindsight memories.

stdlib only. Python 3.9 compatible.

Public API
----------
condense_memories(memories_text, query, max_memories=15) -> str
    Full pipeline: parse -> dedup -> JEV rerank -> caveman compress -> reassemble.
    Fail-open: returns original text on any error.

dedup_memories(lines, threshold=0.7) -> list[str]
    Remove near-duplicate lines via Jaccard word-set similarity.

jev_rerank(query, memories, top_k=10) -> list[str]
    Rerank memories by JEV NOUL relevance; top_k most relevant returned.
    Falls back to input list if JEV unavailable.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deduplication — Jaccard word-set similarity
# ---------------------------------------------------------------------------

def _word_set(text: str) -> set:
    """Lowercase word tokens for Jaccard comparison."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedup_memories(lines: List[str], threshold: float = 0.7) -> List[str]:
    """Remove near-duplicate lines. Keep the first occurrence.
    threshold=0.7 means 70%+ word overlap = duplicate."""
    if not lines:
        return lines
    kept: List[str] = []
    kept_sets: List[set] = []
    for line in lines:
        ws = _word_set(line)
        is_dup = False
        for ks in kept_sets:
            if _jaccard(ws, ks) >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(line)
            kept_sets.append(ws)
    dropped = len(lines) - len(kept)
    if dropped:
        logger.debug("hindsight_condense: dedup dropped %d/%d memories", dropped, len(lines))
    return kept


# ---------------------------------------------------------------------------
# JEV NOUL reranking
# ---------------------------------------------------------------------------

def jev_rerank(query: str, memories: List[str], top_k: int = 10) -> List[str]:
    """Rerank memories by JEV NOUL relevance score; return top_k most relevant.

    Falls back to returning all memories (unchanged) if JEV is unavailable,
    if the query is empty, or on any error. Fail-open always.
    """
    if not query or not memories or len(memories) <= top_k:
        return memories
    try:
        from jevlib.jev_client import UNAVAILABLE, noul, safe_decide
    except ImportError:
        logger.debug("hindsight_condense: jevlib not available, skipping rerank")
        return memories

    try:
        questions = {
            "mem_%d" % i: noul(
                {"question": "Is this memory relevant to the current query?",
                 "query": query,
                 "memory": mem}
            )
            for i, mem in enumerate(memories)
        }

        answers = safe_decide({"note": "hindsight_rerank", "query": query}, questions)

        if answers is UNAVAILABLE:
            logger.debug("hindsight_condense: JEV unavailable, skipping rerank")
            return memories

        scored = []
        for i, mem in enumerate(memories):
            key = "mem_%d" % i
            ans = answers.get(key, {})
            scored.append((mem, ans.get("noul", 0)))

        scored.sort(key=lambda x: x[1], reverse=True)
        result = [mem for mem, _ in scored[:top_k]]
        logger.debug(
            "hindsight_condense: JEV reranked %d -> %d memories (min_noul=%.2f, max_noul=%.2f)",
            len(memories), len(result),
            scored[-1][1] if scored else 0,
            scored[0][1] if scored else 0,
        )
        return result
    except Exception as exc:
        logger.debug("hindsight_condense: JEV rerank failed (%s), returning all", exc)
        return memories


# ---------------------------------------------------------------------------
# Caveman compression pass
# ---------------------------------------------------------------------------

def _caveman_compress_memories(lines: List[str]) -> List[str]:
    """Apply caveman compression to each memory line. Fail-open: returns
    original lines if caveman is unavailable or disabled."""
    try:
        from jevlib.caveman import compress, enabled
    except ImportError:
        return lines
    if not enabled("hindsight_recall"):
        return lines
    result = []
    for line in lines:
        try:
            result.append(compress(line))
        except Exception:
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _parse_memory_lines(text: str) -> List[str]:
    """Split recall text into individual memory strings.
    Handles '- ' prefixed lines and numbered '1. ' prefixed lines."""
    lines = []
    for raw in text.strip().splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        # Strip leading "- " or "N. " prefix
        cleaned = re.sub(r"^(?:-\s+|\d+\.\s+)", "", stripped)
        if cleaned:
            lines.append(cleaned)
    return lines


def _reassemble(lines: List[str], omitted: int = 0) -> str:
    """Reassemble memory lines into the '- ' prefixed format Hindsight uses."""
    parts = ["- " + line for line in lines]
    if omitted > 0:
        parts.append("[%d lower-relevance memories omitted]" % omitted)
    return "\n".join(parts)


def condense_memories(
    memories_text: str,
    query: str = "",
    max_memories: int = 15,
    dedup_threshold: float = 0.7,
    rerank_top_k: Optional[int] = None,
) -> str:
    """Full condensation pipeline:
    1. Parse memory lines
    2. Deduplicate near-identical memories (Jaccard)
    3. JEV NOUL rerank by query relevance (if query provided)
    4. Caveman compress each memory line
    5. Reassemble with omission note

    Fail-open: returns original text unchanged on any error.

    Args:
        memories_text: Raw recall result text (newline-separated '- ...' lines).
        query: The user's query for relevance reranking. Empty = skip rerank.
        max_memories: Hard cap on memories after reranking.
        dedup_threshold: Jaccard similarity threshold for dedup (0.0-1.0).
        rerank_top_k: How many to keep after JEV rerank. Defaults to max_memories.
    """
    if not memories_text or not memories_text.strip():
        return memories_text

    try:
        lines = _parse_memory_lines(memories_text)
        if not lines:
            return memories_text

        original_count = len(lines)

        # 1. Dedup
        lines = dedup_memories(lines, threshold=dedup_threshold)

        # 2. JEV rerank (if query provided and enough memories to be worth it)
        effective_top_k = rerank_top_k if rerank_top_k is not None else max_memories
        if query and len(lines) > effective_top_k:
            lines = jev_rerank(query, lines, top_k=effective_top_k)

        # 3. Hard cap
        capped = lines[:max_memories]

        # 4. Caveman compress
        capped = _caveman_compress_memories(capped)

        omitted = original_count - len(capped)
        return _reassemble(capped, omitted=max(0, omitted))

    except Exception as exc:
        logger.debug("hindsight_condense: pipeline failed (%s), returning original", exc)
        return memories_text
