#!/usr/bin/env python3
"""
Chalkboard Decision Engine v2 — TODO-driven agent triggering.

Checks Chalkboard TODOs as the PRIMARY trigger source.
When an agent has pending work, triggers it via openclaw agent,
captures the response, and forwards it to the group chat.

No longer relies on parsing chat messages for @mention/handoff detection.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BOARD_DIR = Path(os.environ.get("CHALKBOARD_BOARD_DIR", os.path.expanduser("~/.chalkboard/boards")))
CONTEXT_DIR = Path(os.environ.get("CHALKBOARD_CONTEXT_DIR", os.path.expanduser("~/.chalkboard/context")))
STATE_FILE = Path(os.path.expanduser("~/.chalkboard/decide_state.json"))


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_context(group_id: str, last_n: int = 15) -> str:
    """Read recent messages for context injection (not for triggering)."""
    safe_id = group_id.replace("/", "_").replace(":", "_")
    path = CONTEXT_DIR / f"group-{safe_id}.jsonl"
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    parts = []
    for line in lines[-last_n:]:
        try:
            m = json.loads(line)
            name = m.get("sender_name", "?")
            bot = " [bot]" if m.get("is_bot") else ""
            text = m.get("content", "")
            if text and text != "请升级至最新版本客户端，以查看内容":
                parts.append(f"{name}{bot}: {text}")
        except json.JSONDecodeError:
            continue
    return "\n".join(parts)


def _get_my_todos(aliases: list) -> list:
    """Find pending TODOs for this agent across all boards."""
    if not BOARD_DIR.exists():
        return []

    aliases_lower = [a.lower() for a in aliases]
    results = []

    for f in sorted(BOARD_DIR.glob("*.md")):
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
            # Check if it's my turn: the first uncompleted TODO should be mine
            all_pending = re.findall(r"^- \[ \] .+$", content, re.MULTILINE)
            first_pending = all_pending[0] if all_pending else ""
            is_my_turn = any(f"@{alias}" in first_pending.lower() for alias in aliases_lower)

            results.append({
                "task_id": f.stem,
                "title": title,
                "todos": my_todos,
                "is_my_turn": is_my_turn,
            })

    return results


def trigger_and_forward(agent_name: str, profile: str, session_id: str,
                        todos: list, context_str: str, group_id: str,
                        channel: str, aliases: list):
    """Two-step: trigger agent, capture response, forward to group chat."""

    # Build the prompt
    todo_lines = []
    for t in todos:
        todo_lines.append(f"[{t['task_id']}] {t['title']}")
        for item in t["todos"]:
            todo_lines.append(f"  {item}")
    todo_text = "\n".join(todo_lines)

    prompt_parts = []
    if context_str:
        prompt_parts.append(f"[Recent group chat for context]\n{context_str}")

    prompt_parts.append(f"[Your pending TODOs]\n{todo_text}")
    prompt_parts.append(
        "[Action] You have pending work on the chalkboard. "
        "1. Read the task board (bb read <task-id>) "
        "2. Do ONLY your current round of work "
        "3. Log your results (bb log <task-id> --agent <your-name> --content '...') "
        "4. Mark your TODO done (bb todo <task-id> --done '...') "
        "5. Do NOT mark other agents' TODOs as done "
        "6. Write a brief summary of what you did and found."
    )

    message = "\n\n".join(prompt_parts)

    # Step 1: Trigger agent and capture response
    cmd = ["openclaw"]
    if profile and profile != "default":
        cmd.extend(["--profile", profile])
    cmd.extend(["agent", "--session-id", session_id, "--message", message, "--json"])

    agent_reply = ""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout[result.stdout.find("{"):])
                payloads = data.get("result", {}).get("payloads", [])
                for p in payloads:
                    text = p.get("text", "")
                    if text:
                        agent_reply += text + "\n"

                if not agent_reply:
                    summary = data.get("summary", "")
                    if summary and summary != "completed":
                        agent_reply = summary
            except (json.JSONDecodeError, ValueError):
                pass

            print(f"  Agent {agent_name} responded ({len(agent_reply)} chars)", file=sys.stderr)
        else:
            stderr = result.stderr[:200] if result.stderr else ""
            print(f"  Agent {agent_name} failed: {stderr}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  Agent {agent_name} timeout", file=sys.stderr)
        return
    except FileNotFoundError:
        print(f"  openclaw not found", file=sys.stderr)
        return

    # If agent produced no text reply, extract latest work log from board
    if not agent_reply.strip():
        for t in todos:
            board_path = BOARD_DIR / f"{t['task_id']}.md"
            if board_path.exists():
                board_content = board_path.read_text(encoding="utf-8")
                log_entries = re.findall(
                    r"### " + re.escape(agent_name) + r".+?\n(.*?)(?=\n### |\n## |\Z)",
                    board_content, re.DOTALL
                )
                if not log_entries:
                    for alias in aliases[1:] if len(aliases) > 1 else []:
                        log_entries = re.findall(
                            r"### " + re.escape(alias) + r".+?\n(.*?)(?=\n### |\n## |\Z)",
                            board_content, re.DOTALL
                        )
                        if log_entries:
                            break
                if log_entries:
                    latest = log_entries[-1].strip()
                    if latest and len(latest) > 20:
                        agent_reply = f"[{t['title']}] {agent_name} completed:\n\n{latest}"
                        break

    # Step 2: Forward response to group chat
    if agent_reply and agent_reply.strip():
        forward_msg = agent_reply.strip()
        if len(forward_msg) > 4000:
            forward_msg = forward_msg[:4000] + "\n...(truncated)"

        fwd_cmd = ["openclaw"]
        if profile and profile != "default":
            fwd_cmd.extend(["--profile", profile])
        fwd_cmd.extend([
            "message", "send",
            "--channel", channel,
            "--account", "main",
            "--target", group_id,
            "--message", forward_msg,
        ])

        try:
            fwd_result = subprocess.run(fwd_cmd, capture_output=True, text=True, timeout=30)
            if fwd_result.returncode == 0:
                print(f"  Forwarded {agent_name}'s reply to {channel}:{group_id}", file=sys.stderr)
            else:
                print(f"  Forward failed: {fwd_result.stderr[:100]}", file=sys.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  Forward error: {e}", file=sys.stderr)
    else:
        print(f"  Agent {agent_name} had no reply to forward", file=sys.stderr)


def _auto_create_board(messages: list, all_agents: list, config: dict):
    """Detect multi-agent collaboration in chat and auto-create a board if none exists.
    
    Scans recent messages for patterns like:
    - "@agentA ... 让/给 agentB 来 review/做/check"
    - User mentioning 2+ agents in one message
    """
    state = _load_state()
    last_auto_create = state.get("last_auto_create", 0)
    if time.time() - last_auto_create < 120:
        return

    agent_names_lower = set()
    for a in all_agents:
        agent_names_lower.add(a["name"].lower())
        for alias in a.get("aliases", []):
            agent_names_lower.add(alias.lower())

    collab_patterns = ["让", "给", "review", "check", "来做", "来看", "帮忙", "接力", "轮到"]

    for msg in messages[-10:]:
        if msg.get("is_bot"):
            continue

        text = msg.get("content", "").lower()
        ts = msg.get("ts", 0)

        if ts <= last_auto_create:
            continue

        mentioned_agents = []
        for a in all_agents:
            names_to_check = [a["name"].lower()] + [x.lower() for x in a.get("aliases", [])]
            if any(f"@{n}" in text or n in text for n in names_to_check):
                mentioned_agents.append(a)

        has_collab_intent = any(p in text for p in collab_patterns)
        if len(mentioned_agents) < 2 and has_collab_intent:
            for a in all_agents:
                if a in mentioned_agents:
                    continue
                names_to_check = [a["name"].lower()] + [x.lower() for x in a.get("aliases", [])]
                if any(n in text for n in names_to_check):
                    mentioned_agents.append(a)
                    break

        if len(mentioned_agents) >= 2:
            existing_boards = list(BOARD_DIR.glob("*.md")) if BOARD_DIR.exists() else []
            has_pending = False
            for b in existing_boards:
                try:
                    content = b.read_text(encoding="utf-8")
                    if re.findall(r"^- \[ \]", content, re.MULTILINE):
                        has_pending = True
                        break
                except OSError:
                    continue

            if not has_pending:
                raw_text = msg.get("content", "")
                title_match = re.search(r"研究.*?(\S{2,10})", raw_text)
                title = title_match.group(1) if title_match else "collaboration task"

                agent_names = [a["name"] for a in mentioned_agents]
                first_agent = agent_names[0]
                second_agent = agent_names[1] if len(agent_names) > 1 else agent_names[0]

                BOARD_DIR.mkdir(parents=True, exist_ok=True)
                from datetime import datetime as _dt
                date_part = _dt.now().strftime("%Y%m%d")
                seq = len(list(BOARD_DIR.glob(f"task-{date_part}-*.md"))) + 1
                task_id = f"task-{date_part}-{seq:03d}"

                board_content = f"""---
id: {task_id}
created_by: auto-detect
created_at: {_dt.now().astimezone().isoformat(timespec='seconds')}
status: in_progress
priority: normal
---

# Task: {title} analysis

## Goal
{raw_text}

## Context
Auto-created from group chat message.

## Work Log

(No entries yet.)

## TODOs
- [ ] @{first_agent}: Research and write findings
- [ ] @{second_agent}: Review findings, challenge assumptions
"""
                board_path = BOARD_DIR / f"{task_id}.md"
                board_path.write_text(board_content, encoding="utf-8")
                print(f"[auto] Created board {task_id} for: {', '.join(agent_names)}")

                state["last_auto_create"] = int(time.time())
                _save_state(state)
                return


def run_decisions(config: dict):
    """Check TODOs and trigger agents that have pending work."""
    state = _load_state()

    for group_id, group_cfg in config.get("groups", {}).items():
        channel = group_cfg.get("provider", "feishu")
        context_str = _read_context(group_id)

        all_agents = group_cfg.get("agents", [])
        messages = []
        safe_id = group_id.replace("/", "_").replace(":", "_")
        ctx_path = CONTEXT_DIR / f"group-{safe_id}.jsonl"
        if ctx_path.exists():
            for line in ctx_path.read_text(encoding="utf-8").strip().splitlines()[-20:]:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        _auto_create_board(messages, all_agents, config)

        for agent_cfg in all_agents:
            agent_name = agent_cfg["name"]
            profile = agent_cfg.get("profile", "default")
            session_id = agent_cfg.get("session_id", "")
            aliases = [agent_name] + agent_cfg.get("aliases", [])

            if not session_id:
                continue

            state_key = f"{group_id}:{agent_name}"
            last_triggered = state.get("last_triggered", {}).get(state_key, 0)

            cooldown = group_cfg.get("cooldown", 60)
            if time.time() - last_triggered < cooldown:
                continue

            my_todos = _get_my_todos(aliases)
            actionable = [t for t in my_todos if t["is_my_turn"]]

            if not actionable:
                continue

            print(f"[{agent_name}] Has {len(actionable)} actionable TODO(s), triggering...")

            trigger_and_forward(
                agent_name, profile, session_id,
                actionable, context_str, group_id, channel, aliases,
            )

            if "last_triggered" not in state:
                state["last_triggered"] = {}
            state["last_triggered"][state_key] = int(time.time())
            _save_state(state)


def main():
    parser = argparse.ArgumentParser(description="Chalkboard Decision Engine v2")
    parser.add_argument("--config", required=True, help="Path to chalkboard config.json")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("Config must be valid JSON", file=sys.stderr)
        sys.exit(1)

    run_decisions(config)


if __name__ == "__main__":
    main()
