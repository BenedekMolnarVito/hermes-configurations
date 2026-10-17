#!/usr/bin/env python3
"""Query the Agentic System Architecture knowledge base.

Searches the 30 lesson KB files and the 257 classified drill examples for a
topic / design question and prints the most relevant lessons, their keyed
principles, and matching drill examples (correct answer + each incorrect answer
with its Jev-classified trap family). Run this instead of reasoning the answer
from memory when the agentic-architecture-design skill applies.

Usage:
    python3 query_kb.py "how should an agent loop decide when to stop"
    python3 query_kb.py --lesson 1-2            # dump one lesson's examples

Stdlib only. Falls back gracefully if the KB path is absent.
"""
import json, os, re, sys

def _resolve_kb_root():
    # 1) explicit override
    env = os.environ.get("AGENTIC_KB_ROOT")
    cands = []
    if env:
        cands.append(env)
    # 2) common known locations
    cands += [
        os.path.expanduser("~/temp/claude-cert-guide"),
        "/Users/C5418860/temp/claude-cert-guide",
    ]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "kb")):
            return c
    return cands[0] if cands else ""

_ROOT = _resolve_kb_root()
KB = os.path.join(_ROOT, "kb")
QBL = os.path.join(_ROOT, "drill", "questions_by_lesson.json")

STOP = set("the a an of to in for and or is are how should when what which do i "
           "my our can use using with on at by be it this that as".split())

def tokens(s):
    return [w for w in re.findall(r"[a-z0-9_]+", s.lower()) if w not in STOP and len(w) > 2]

def load_lessons():
    if not os.path.isdir(KB):
        return {}
    out = {}
    for fn in os.listdir(KB):
        if not fn.endswith(".md") or fn == "index.md":
            continue
        if not re.match(r"\d-\d", fn):
            continue
        out[fn[:-3]] = open(os.path.join(KB, fn)).read()
    return out

def load_qbl():
    if not os.path.exists(QBL):
        return {}
    return json.load(open(QBL)).get("by_lesson", {})

def score(text, qtoks):
    tl = text.lower()
    return sum(tl.count(t) for t in qtoks)

def print_examples(qs, limit=3):
    for q in qs[:limit]:
        cls = q.get("_classified") or {}
        print(f"    [{q['id']}] {q['stem'][:150]}")
        for o in q["options"]:
            if o.get("isCorrect"):
                print(f"      OK  {o['id']}: {o['text'][:150]}")
        for o in q["options"]:
            if o.get("isCorrect"):
                continue
            trap = (cls.get("trap_by_option") or {}).get(o["id"], {})
            tf = trap.get("trap", "?")
            print(f"      X   {o['id']} (trap={tf}): {o['text'][:130]}")
        if (cls.get("answer_is_best") or 1) < 0.5:
            print(f"      ! CONTESTED key (Jev {cls['answer_is_best']:.2f}) — verify vs Anthropic docs")
        print()

def main():
    args = sys.argv[1:]
    print(f"[query_kb] KB root: {_ROOT or '(unresolved)'}  kb_exists={os.path.isdir(KB)}")
    lessons = load_lessons()
    qbl = load_qbl()
    if not lessons:
        print("KB not found at", KB, "\u2014 set AGENTIC_KB_ROOT=/path/to/claude-cert-guide, "
              "or fall back to wiki [[agentic-architecture-guide]] and the core "
              "decision rules in SKILL.md.")
        return 2
    if args and args[0] == "--lesson":
        key = [k for k in lessons if k.startswith(args[1])]
        for k in key:
            print(f"### {k}\n")
            print_examples(qbl.get(k, []), limit=99)
        return 0
    query = " ".join(args).strip()
    if not query:
        print(__doc__)
        return 1
    qtoks = tokens(query)
    ranked = sorted(((score(t, qtoks), k) for k, t in lessons.items()), reverse=True)
    top = [(s, k) for s, k in ranked if s > 0][:4] or ranked[:2]
    print(f"Query: {query!r}\nTop lessons:\n")
    for s, k in top:
        body = lessons[k]
        m = re.search(r"^title:\s*(.+)$", body, re.M)
        title = m.group(1) if m else k
        print(f"== {k}  {title}  (relevance {s}) ==")
        # keyed principles: pull the 'Key principle' lines
        for kp in re.findall(r"\*\*Key principle:\*\* (.+)", body)[:2]:
            print(f"  principle: {kp[:220]}")
        # matching drill examples for this lesson
        qs = qbl.get(k, [])
        qs_ranked = sorted(qs, key=lambda q: score(q["stem"], qtoks), reverse=True)
        print_examples(qs_ranked, limit=2)
    print("Full lesson file: " + KB + "/<lesson>.md   |   wiki: [[agentic-architecture-guide]]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
