#!/usr/bin/env python3
"""Run the standalone jev-ultrafast agent on one browser goal and print its
step-by-step status. This is the fast/cheap path: a small operation/target model
drives the browser, a small text LLM writes field values only when needed.

A `done` status is the agent's own belief — ALWAYS verify the real page outcome
afterward (see references/jev-agent.md).

Usage:
    run_jev.py --url URL --goal GOAL [--goal GOAL ...] [--jev-dir DIR]

Pass --goal more than once for an ordered list of sub-goals (mirrors
examples/run.py, where --goal is appendable). Defaults --jev-dir to
~/.cache/jev-ultrafast (where setup_jev.sh clones it). Requires
TYPESAFE_API_KEY and TEXT_MODEL_API_KEY in <jev-dir>/.env.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Start URL")
    parser.add_argument(
        "--goal",
        action="append",
        required=True,
        help="Natural-language goal; repeat for an ordered list of sub-goals.",
    )
    parser.add_argument(
        "--jev-dir",
        default=str(Path.home() / ".cache" / "jev-ultrafast"),
        help="Path to the cloned jev-ultrafast repo",
    )
    args = parser.parse_args()

    jev_dir = Path(args.jev_dir).expanduser()
    if not (jev_dir / "pyproject.toml").exists():
        print(
            f"error: jev-ultrafast not found at {jev_dir}. Run scripts/setup_jev.sh first.",
            file=sys.stderr,
        )
        return 1
    env_file = jev_dir / ".env"
    if not env_file.exists():
        print(
            f"error: {env_file} missing. Copy .env.example and set TYPESAFE_API_KEY + TEXT_MODEL_API_KEY.",
            file=sys.stderr,
        )
        return 1

    cmd = ["uv", "run", "--env-file", ".env", "python", "examples/run.py", "--url", args.url]
    for goal in args.goal:
        cmd += ["--goal", goal]

    # Stream output live so the caller sees each step's elapsed_ms / action count / status.
    proc = subprocess.run(cmd, cwd=str(jev_dir), env={**os.environ})
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
