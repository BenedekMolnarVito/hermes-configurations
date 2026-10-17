#!/usr/bin/env python3
"""Generic PR re-review poller (reusable across repos/PRs).

Checks a GitHub PR for NEW activity (formal reviews, inline review comments,
general issue/PR comments) by authors OTHER THAN the PR author (and other than
CI bots) since the last-seen watermark. New activity is appended to a per-PR
report file and the watermark is advanced.

Pure `gh` (uses existing auth). Safe to run from cron / no_agent watchdog:
emits stdout ONLY when there is new activity, stays silent otherwise.

Usage:
    poll_pr.py --repo OWNER/REPO --pr N [--pr-author LOGIN] [--extra-ignore a,b]
               [--state-dir DIR] [--baseline ISO8601|now]

  --pr-author   login whose activity is ignored (self). If omitted, resolved
                from the PR's own `user.login` via the API.
  --extra-ignore  comma-separated extra logins to ignore (beyond CI bots).
  --baseline    only on FIRST run (no state file yet): seed the watermark.
                'now' (default) = ignore everything up to now; an ISO8601
                timestamp = report activity strictly after it. Ignored once a
                state file exists.
  --state-dir   base dir for state/report (default ~/.hermes/cache/pr_watch).
                Files are keyed per repo+PR, so many PRs coexist safely.

State:  <state-dir>/<owner>__<repo>__pr<N>/state.json
Report: <state-dir>/<owner>__<repo>__pr<N>/new_activity.md
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BOTS = {"github-actions[bot]", "github-actions"}


def gh_json(path):
    out = subprocess.run(
        ["gh", "api", path, "--paginate"], capture_output=True, text=True
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {out.stderr.strip()}")
    txt = out.stdout.strip()
    if not txt:
        return []
    try:
        data = json.loads(txt)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items, dec, idx = [], json.JSONDecoder(), 0
        while idx < len(txt):
            while idx < len(txt) and txt[idx] in " \n\r\t":
                idx += 1
            if idx >= len(txt):
                break
            obj, end = dec.raw_decode(txt, idx)
            items.extend(obj) if isinstance(obj, list) else items.append(obj)
            idx = end
        return items


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(description="Generic PR re-review poller")
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--pr", required=True, help="PR number")
    ap.add_argument("--pr-author", default=None, help="self login to ignore")
    ap.add_argument("--extra-ignore", default="", help="comma-separated logins")
    ap.add_argument("--baseline", default="now", help="'now' or ISO8601 (first run only)")
    ap.add_argument(
        "--state-dir",
        default=str(Path.home() / ".hermes" / "cache" / "pr_watch"),
    )
    args = ap.parse_args()

    repo = args.repo.strip()
    pr = str(args.pr).strip()
    owner, _, name = repo.partition("/")
    key = f"{owner}__{name}__pr{pr}"
    state_dir = Path(args.state_dir) / key
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    report_file = state_dir / "new_activity.md"

    ignore = set(DEFAULT_BOTS)
    if args.extra_ignore:
        ignore |= {x.strip() for x in args.extra_ignore.split(",") if x.strip()}

    # Resolve self (PR author) once.
    pr_author = args.pr_author
    if not pr_author:
        pr_author = (gh_json(f"repos/{repo}/pulls/{pr}") or {}).get(
            "user", {}
        ).get("login")
    if pr_author:
        ignore.add(pr_author)

    # Load or seed state.
    first_run = not state_file.exists()
    if first_run:
        if args.baseline == "now":
            seed = now_iso()
        else:
            seed = parse_ts(args.baseline).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {
            "repo": repo,
            "pr": pr,
            "pr_author": pr_author,
            "ignore": sorted(ignore),
            "last_seen": seed,
            "note": f"baseline seeded at watcher setup for {repo}#{pr}",
        }
        if not report_file.exists():
            report_file.write_text(
                f"# {repo} PR #{pr} — new activity by other authors (append-only)\n\n"
                f"PR author (ignored): {pr_author}\n"
                f"Baseline watermark: {seed}\n"
            )
    else:
        state = json.loads(state_file.read_text())
        # keep ignore list fresh if caller changed it
        state["ignore"] = sorted(ignore)
        state["pr_author"] = pr_author or state.get("pr_author")

    last_seen = parse_ts(state["last_seen"])
    events = []

    def consider(ts, builder):
        if ts and parse_ts(ts) > last_seen:
            events.append(builder())

    for r in gh_json(f"repos/{repo}/pulls/{pr}/reviews"):
        u = (r.get("user") or {}).get("login", "?")
        if u in ignore:
            continue
        consider(
            r.get("submitted_at"),
            lambda r=r, u=u: {
                "ts": r["submitted_at"], "kind": "REVIEW", "user": u,
                "state": r.get("state"), "body": (r.get("body") or "").strip(),
                "url": r.get("html_url"),
            },
        )

    for c in gh_json(f"repos/{repo}/pulls/{pr}/comments"):
        u = (c.get("user") or {}).get("login", "?")
        if u in ignore:
            continue
        consider(
            c.get("created_at"),
            lambda c=c, u=u: {
                "ts": c["created_at"], "kind": "INLINE", "user": u,
                "path": c.get("path"), "line": c.get("line"),
                "body": (c.get("body") or "").strip(), "url": c.get("html_url"),
            },
        )

    for c in gh_json(f"repos/{repo}/issues/{pr}/comments"):
        u = (c.get("user") or {}).get("login", "?")
        if u in ignore:
            continue
        consider(
            c.get("created_at"),
            lambda c=c, u=u: {
                "ts": c["created_at"], "kind": "COMMENT", "user": u,
                "body": (c.get("body") or "").strip(), "url": c.get("html_url"),
            },
        )

    now = now_iso()

    if not events:
        # Nothing new: advance watermark, stay SILENT (no_agent watchdog sends nothing).
        state["last_seen"] = now
        state["last_poll"] = now
        state_file.write_text(json.dumps(state, indent=2))
        return 0

    events.sort(key=lambda e: e["ts"])
    lines = [f"\n## {repo}#{pr} — new activity at poll {now} ({len(events)} event(s))\n"]
    for e in events:
        head = f"- **{e['ts']}** {e['kind']} by @{e['user']}"
        if e.get("state"):
            head += f" ({e['state']})"
        if e.get("path"):
            head += f" — `{e['path']}`:{e.get('line')}"
        lines.append(head)
        if e.get("body"):
            lines.append("  " + e["body"].replace("\n", "\n  "))
        if e.get("url"):
            lines.append(f"  {e['url']}")
        lines.append("")
    report = "\n".join(lines)

    with report_file.open("a") as f:
        f.write(report)

    newest = max(parse_ts(e["ts"]) for e in events)
    state["last_seen"] = newest.strftime("%Y-%m-%dT%H:%M:%SZ")
    state["last_poll"] = now
    state["pending_review"] = True
    state_file.write_text(json.dumps(state, indent=2))

    print(f"[{now}] {repo}#{pr}: {len(events)} NEW event(s) by other authors "
          f"— appended to {report_file}")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
