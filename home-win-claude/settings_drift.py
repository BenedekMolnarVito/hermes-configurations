#!/usr/bin/env python
"""
settings_drift.py TEMPLATE LIVE CLAUDE_HOME

Read-only. Reports what the live settings.json has that the bundle template lacks
(hooks, env keys, plugins, marketplaces, permission rules) and template hooks missing
from live. Used by export.ps1 so live-only changes get folded into the template by hand
(keep {{CLAUDE_HOME}}, never paste secrets). Exit 0 always.
"""
import json
import pathlib
import sys


def _hooks(d, home):
    out = set()
    for event, groups in (d.get("hooks") or {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                out.add((event, g.get("matcher", ""), h.get("command", "").replace(home, "{{CLAUDE_HOME}}")))
    return out


def main():
    tmpl_p, live_p, home = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3].replace("\\", "/")
    tmpl = json.loads(tmpl_p.read_text(encoding="utf-8"))
    live = json.loads(live_p.read_text(encoding="utf-8")) if live_p.exists() else {}
    found = False
    for key in ("env", "enabledPlugins", "extraKnownMarketplaces"):
        extra = sorted(set(live.get(key) or {}) - set(tmpl.get(key) or {}))
        if extra:
            found = True
            print(f"live-only {key}: {', '.join(extra)}" + ("  (values not shown)" if key == "env" else ""))
    for key in ("allow", "deny", "ask"):
        extra = [r for r in (live.get("permissions") or {}).get(key, [])
                 if r not in (tmpl.get("permissions") or {}).get(key, [])]
        if extra:
            found = True
            print(f"live-only permissions.{key}: {extra}")
    lh, th = _hooks(live, home), _hooks(tmpl, home)
    for event, matcher, cmd in sorted(lh - th):
        found = True
        print(f"live-only hook: {event} [{matcher}] {cmd}")
    for event, matcher, cmd in sorted(th - lh):
        found = True
        print(f"template hook missing in live: {event} [{matcher}] {cmd}  (run install.ps1 -Apply)")
    if not found:
        print("settings drift: none")


if __name__ == "__main__":
    main()
