#!/usr/bin/env python3
"""
Chalkboard Decision Engine v2 — Chat-first, board-optional.

Primary trigger: a bot posted a message mentioning another agent's name.
Secondary trigger: a human mentioned an agent but got no reply in 60s.
Fallback trigger: board TODO pending.

Dedup by message ID (not cooldown). Retry on failure.
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
MAX_RETRIES = 3


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_messages(group_id: str) -> list:
    safe_id = group_id.replace("/", "_").replace(":", "_")
    path = CONTEXT_DIR / f"group-{safe_id}.jsonl"
    if not path.exists():
        return []
    messages = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def _format_context(messages: list, last_n: int = 15) -> str:
    parts = []
    for msg in messages[-last_n:]:
        name = msg.get("sender_name", "?")
        bot = " [bot]" if msg.get("is_bot") else ""
        text = msg.get("content", "")
        if text and text != "请升级至最新版本客户端，以查看内容":
            parts.append(f"{name}{bot}: {text}")
    return "\n".join(parts)


def _agent_names_in_text(text: str, agent_cfg: dict) -> bool:
    """Check if any of this agent's names appear in the text."""
    text_lower = text.lower()
    names = [agent_cfg["name"].lower()] + [a.lower() for a in agent_cfg.get("aliases", [])]
    return any(name in text_lower for name in names)


def _find_bot_handoff(messages: list, target_agent: dict, all_agents: list) -> dict:
    """Find the most recent bot message that mentions the target agent."""
    target_names = [target_agent["name"].lower()] + [a.lower() for a in target_agent.get("aliases", [])]

    for msg in reversed(messages[-20:]):
        if not msg.get("is_bot"):
            continue

        sender_name = msg.get("sender_name", "").lower()
        is_self = any(name in sender_name for name in target_names)
        if is_self:
            continue

        text = msg.get("content", "").lower()
        if any(name in text for name in target_names):
            return msg

    return {}


def _find_unresponded_mention(messages: list, target_agent: dict) -> dict:
    """Find a human message mentioning this agent that got no bot reply within 60s."""
    target_names = [target_agent["name"].lower()] + [a.lower() for a in target_agent.get("aliases", [])]
    now = int(time.time())

    for msg in reversed(messages[-20:]):
        if msg.get("is_bot"):
            continue

        text = msg.get("content", "").lower()
        msg_ts = msg.get("ts", 0)

        if now - msg_ts < 60:
            continue
        if now - msg_ts > 300:
            break

        if any(name in text for name in target_names):
            has_reply = False
            for later_msg in messages:
                if later_msg.get("ts", 0) > msg_ts and later_msg.get("is_bot"):
                    later_sender = later_msg.get("sender_name", "").lower()
                    if any(name in later_sender for name in target_names):
                        has_reply = True
                        break
            if not has_reply:
                return msg

    return {}


def _get_board_todos(aliases: list) -> list:
    if not BOARD_DIR.exists():
        return []
    aliases_lower = [a.lower() for a in aliases]
    results = []
    for f in sorted(BOARD_DIR.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        todos = re.findall(r"^- \[ \] .+$", content, re.MULTILINE)
        my_todos = [t for t in todos if any(f"@{a}" in t.lower() for a in aliases_lower)]
        if my_todos:
            all_pending = re.findall(r"^- \[ \] .+$", content, re.MULTILINE)
            first = all_pending[0] if all_pending else ""
            is_my_turn = any(f"@{a}" in first.lower() for a in aliases_lower)
            if is_my_turn:
                title = "(untitled)"
                for line in content.splitlines():
                    if line.startswith("# Task:"):
                        title = line[7:].strip()
                        break
                results.append({"task_id": f.stem, "title": title, "todos": my_todos})
    return results


def trigger_and_forward(agent_name: str, profile: str, session_id: str,
                        reason: str, context_str: str, group_id: str,
                        channel: str, trigger_detail: str):
    """Trigger agent, capture response, forward to group."""

    prompt_parts = []
    if context_str:
        prompt_parts.append(f"[Recent group chat]\n{context_str}")

    if reason == "handoff":
        prompt_parts.append(
            f"[Action] Another agent just handed off work to you. "
            f"Context: {trigger_detail}\n"
            f"Read the conversation above, then do the requested work (review, analysis, etc)."
        )
    elif reason == "unresponded":
        prompt_parts.append(
            f"[Action] Someone mentioned you in the group chat but you haven't replied yet. "
            f"Read the conversation and respond appropriately."
        )
    elif reason == "board_todo":
        prompt_parts.append(
            f"[Action] You have pending TODOs on the chalkboard:\n{trigger_detail}\n"
            f"Read the task board (bb read <task-id>), do your work, log results."
        )

    prompt_parts.append(
        "IMPORTANT: Write your response as plain text. Do NOT use cards, "
        "interactive elements, or rich formatting. Start with a clear summary "
        "of your findings/review. This text will be posted to the group chat."
    )

    message = "\n\n".join(prompt_parts)

    cmd = ["openclaw"]
    if profile and profile != "default":
        cmd.extend(["--profile", profile])
    cmd.extend(["agent", "--session-id", session_id, "--message", message, "--json"])

    agent_reply = ""
    success = False

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and result.stdout:
            try:
                json_start = result.stdout.find("{")
                if json_start >= 0:
                    data = json.loads(result.stdout[json_start:])
                    for p in data.get("result", {}).get("payloads", []):
                        text = p.get("text", "")
                        if text:
                            agent_reply += text + "\n"
                    if not agent_reply:
                        summary = data.get("summary", "")
                        if summary and summary != "completed":
                            agent_reply = summary
            except (json.JSONDecodeError, ValueError):
                pass
            success = True
            print(f"  Agent {agent_name} responded ({len(agent_reply)} chars)", file=sys.stderr)
        else:
            print(f"  Agent {agent_name} failed (exit={result.returncode})", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  Agent {agent_name} timeout", file=sys.stderr)
    except FileNotFoundError:
        print(f"  openclaw not found", file=sys.stderr)

    # If no text reply, try to extract from board work log
    if success and not agent_reply.strip():
        aliases = [agent_name]
        if BOARD_DIR.exists():
            for f in sorted(BOARD_DIR.glob("*.md"), reverse=True):
                try:
                    content = f.read_text(encoding="utf-8")
                    for alias in aliases:
                        entries = re.findall(
                            r"### " + re.escape(alias) + r".+?\n(.*?)(?=\n### |\n## |\Z)",
                            content, re.DOTALL
                        )
                        if entries:
                            latest = entries[-1].strip()
                            if latest and len(latest) > 20:
                                agent_reply = latest
                                break
                    if agent_reply:
                        break
                except OSError:
                    continue

    # Forward to group chat
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
                print(f"  Forwarded to {channel}:{group_id}", file=sys.stderr)
            else:
                print(f"  Forward failed: {fwd_result.stderr[:100]}", file=sys.stderr)
        except Exception as e:
            print(f"  Forward error: {e}", file=sys.stderr)
    else:
        print(f"  No reply to forward", file=sys.stderr)

    return success


def run_decisions(config: dict):
    state = _load_state()
    triggered_for = state.get("triggered_for", {})
    retry_counts = state.get("retry_counts", {})

    for group_id, group_cfg in config.get("groups", {}).items():
        channel = group_cfg.get("provider", "feishu")
        all_agents = group_cfg.get("agents", [])
        messages = _read_messages(group_id)

        if not messages:
            continue

        context_str = _format_context(messages)

        for agent_cfg in all_agents:
            agent_name = agent_cfg["name"]
            profile = agent_cfg.get("profile", "default")
            session_id = agent_cfg.get("session_id", "")
            aliases = [agent_name] + agent_cfg.get("aliases", [])

            if not session_id:
                continue

            trigger_key = f"{group_id}:{agent_name}"
            reason = ""
            trigger_msg_id = ""
            trigger_detail = ""

            # Trigger 1: Bot handoff
            handoff_msg = _find_bot_handoff(messages, agent_cfg, all_agents)
            if handoff_msg:
                msg_id = handoff_msg.get("msg_id", "")
                already_triggered = triggered_for.get(trigger_key) == msg_id
                retries = retry_counts.get(f"{trigger_key}:{msg_id}", 0)

                if not already_triggered and retries < MAX_RETRIES:
                    reason = "handoff"
                    trigger_msg_id = msg_id
                    trigger_detail = handoff_msg.get("content", "")[:200]

            # Trigger 2: Unresponded human mention
            if not reason:
                unresponded = _find_unresponded_mention(messages, agent_cfg)
                if unresponded:
                    msg_id = unresponded.get("msg_id", "")
                    already_triggered = triggered_for.get(trigger_key) == msg_id
                    retries = retry_counts.get(f"{trigger_key}:{msg_id}", 0)

                    if not already_triggered and retries < MAX_RETRIES:
                        reason = "unresponded"
                        trigger_msg_id = msg_id
                        trigger_detail = unresponded.get("content", "")[:200]

            # Trigger 3: Board TODO (fallback)
            if not reason:
                board_todos = _get_board_todos(aliases)
                if board_todos:
                    todo_key = f"board:{board_todos[0]['task_id']}"
                    already_triggered = triggered_for.get(trigger_key) == todo_key
                    if not already_triggered:
                        reason = "board_todo"
                        trigger_msg_id = todo_key
                        todo_lines = []
                        for t in board_todos:
                            for item in t["todos"]:
                                todo_lines.append(item)
                        trigger_detail = "\n".join(todo_lines)

            if not reason:
                continue

            print(f"[{agent_name}] Triggering (reason: {reason})")

            success = trigger_and_forward(
                agent_name, profile, session_id,
                reason, context_str, group_id, channel, trigger_detail,
            )

            if success:
                triggered_for[trigger_key] = trigger_msg_id
            else:
                retry_key = f"{trigger_key}:{trigger_msg_id}"
                retry_counts[retry_key] = retry_counts.get(retry_key, 0) + 1

    state["triggered_for"] = triggered_for
    state["retry_counts"] = retry_counts
    _save_state(state)


def main():
    parser = argparse.ArgumentParser(description="Chalkboard Decision Engine v2")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    run_decisions(config)


if __name__ == "__main__":
    main()
