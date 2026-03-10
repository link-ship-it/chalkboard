#!/usr/bin/env python3
"""
Cron script for Chalkboard.
Checks for pending TODOs assigned to a specific agent.
Supports multiple aliases (e.g. "agent-a,Alice,researcher").

If --notify is set, sends a message directly to the specified chat
via `openclaw message send`, bypassing the cron announce mechanism.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

BOARD_DIR = Path(
    os.environ.get("CHALKBOARD_BOARD_DIR", os.path.expanduser("~/.chalkboard/boards"))
)


def check(aliases: list) -> str:
    """Check all boards for pending TODOs matching any of the given aliases."""
    if not BOARD_DIR.exists():
        return ""

    aliases_lower = [a.lower() for a in aliases]
    files = sorted(BOARD_DIR.glob("*.md"))
    results = []

    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        current_turn = ""
        for line in content.splitlines():
            m = re.match(r"^current_turn:\s*(.+)$", line)
            if m:
                current_turn = m.group(1).strip().lower()
                break

        if current_turn and current_turn not in aliases_lower:
            continue

        title = "(untitled)"
        for line in content.splitlines():
            if line.startswith("# Task:"):
                title = line[7:].strip()
                break

        todos = re.findall(r"^- \[ \] .+$", content, re.MULTILINE)
        my_todos = [
            t for t in todos
            if any(f"@{alias}" in t.lower() for alias in aliases_lower)
        ]

        if my_todos:
            items = "\n".join(f"  {t}" for t in my_todos)
            results.append(f"[{f.stem}] {title}\n{items}")

    if not results:
        return ""

    header = "You have pending TODOs on the board:\n\n"
    body = "\n\n".join(results)
    footer = (
        "\n\nRead the task: bb read <task-id>"
        '\nUpdate when done: bb todo <task-id> --done "<description>"'
    )
    return header + body + footer


def notify(channel: str, target: str, message: str, profile: str = ""):
    """Send a message to a specific chat via openclaw message send."""
    cmd = ["openclaw"]
    if profile and profile != "default":
        cmd.extend(["--profile", profile])
    cmd.extend([
        "message", "send",
        "--channel", channel,
        "--target", target,
        "--message", message,
    ])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"Notified via {channel} -> {target}", file=sys.stderr)
        else:
            print(f"Notify failed: {result.stderr}", file=sys.stderr)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Notify error: {e}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: check_todos.py <name>[,<alias>,...] [--notify <channel> <target>] [--profile <name>]", file=sys.stderr)
        print("  Example: check_todos.py agent-a,Alice --notify feishu oc_xxx", file=sys.stderr)
        sys.exit(1)

    aliases = [a.strip() for a in sys.argv[1].split(",") if a.strip()]

    notify_channel = ""
    notify_target = ""
    profile = ""

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--notify" and i + 2 < len(args):
            notify_channel = args[i + 1]
            notify_target = args[i + 2]
            i += 3
        elif args[i] == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        else:
            i += 1

    msg = check(aliases)

    if msg:
        print(msg)
        if notify_channel and notify_target:
            notify(notify_channel, notify_target, msg, profile)

    sys.exit(0)


if __name__ == "__main__":
    main()
