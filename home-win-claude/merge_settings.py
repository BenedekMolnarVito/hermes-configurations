#!/usr/bin/env python
"""
merge_settings.py TEMPLATE LIVE CLAUDE_HOME [--apply]

Merge the bundle's settings template into a live settings.json without losing local
entries: dicts deep-merge (template wins on scalar conflicts), hook groups are appended
per event only when their command is not already present (idempotent), lists of
permission rules are unioned. Prints the result; with --apply writes it (after a
.bak-<timestamp> backup).
"""
import datetime
import json
import pathlib
import sys


def _commands(groups):
    return {h.get("command") for g in groups for h in g.get("hooks", [])}


def merge_hooks(live, tmpl):
    for event, groups in tmpl.items():
        cur = live.setdefault(event, [])
        have = _commands(cur)
        for g in groups:
            if not _commands([g]) <= have:
                cur.append(g)
    return live


def merge(live, tmpl):
    for k, v in tmpl.items():
        if k == "hooks" and isinstance(v, dict):
            live[k] = merge_hooks(live.get(k) or {}, v)
        elif isinstance(v, dict) and isinstance(live.get(k), dict):
            merge(live[k], v)
        elif isinstance(v, list) and isinstance(live.get(k), list):
            live[k] += [x for x in v if x not in live[k]]
        else:
            live[k] = v
    return live


def main():
    tmpl_p, live_p, home = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
    apply = "--apply" in sys.argv
    tmpl = json.loads(tmpl_p.read_text(encoding="utf-8").replace("{{CLAUDE_HOME}}", home.replace("\\", "/")))
    live = json.loads(live_p.read_text(encoding="utf-8")) if live_p.exists() else {}
    before = json.dumps(live, sort_keys=True)
    out = merge(live, tmpl)
    if json.dumps(out, sort_keys=True) == before:
        print("settings.json: already up to date")
        return
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    if not apply:
        print("settings.json would become:\n" + text)
        return
    if live_p.exists():
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        live_p.with_name(live_p.name + ".bak-" + ts).write_text(live_p.read_text(encoding="utf-8"), encoding="utf-8")
    live_p.write_text(text, encoding="utf-8")
    print("settings.json: merged")


if __name__ == "__main__":
    main()
