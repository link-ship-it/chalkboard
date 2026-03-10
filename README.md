<p align="center">
  <h1 align="center">Chalkboard</h1>
  <p align="center">Multi-agent collaboration through shared Markdown files</p>
  <p align="center"><i>Your AI agents can't talk to each other. Chalkboard fixes that.</i></p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="Python 3.8+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="Zero Dependencies">
  <img src="https://img.shields.io/github/stars/link-ship-it/chalkboard?style=social" alt="Stars">
</p>

<p align="center">
  <a href="docs/quickstart.md">Quick Start</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/use-cases.md">Use Cases</a>
</p>

---

## The Problem

IM platforms (Feishu, Telegram, Discord, Slack) **don't let bots read each other's messages**. If you run multiple AI agents in a group chat, they're completely blind to one another.

## The Solution

**Chalkboard** gives your agents two superpowers:

1. **Shared task boards** (Markdown files) for structured collaboration — TODO tracking, work logs, turn control
2. **Message poller** that fetches ALL group messages (including other bots') via platform APIs, so agents have full context
3. **Decision engine** that triggers agents only when it's their turn, and forwards their responses back to the group chat

No database. No server. No external dependencies. Just Python + files.

```
User: "Research NVDA — Agent A does analysis, Agent B reviews"

  Chalkboard daemon (every 5 seconds):
    1. Poller    → fetches all group messages (Feishu/Telegram API)
    2. Decide    → Agent A has a TODO and it's their turn? → trigger
    3. Trigger   → openclaw agent --session-id → agent does the work
    4. Forward   → captures agent reply → sends to group chat
    5. Repeat    → Agent B's turn now → trigger Agent B
```

## Quick Start (2 minutes)

**Requirements:** Python 3.8+, [OpenClaw](https://github.com/openclaw/openclaw) with 2+ agent profiles

### Step 1: Clone

```bash
git clone https://github.com/link-ship-it/chalkboard.git
cd chalkboard
```

### Step 2: Discover your agents

```bash
python3 scripts/board.py agents
```

Auto-detects all OpenClaw agents and group chats on your machine:

```
Found 2 agent(s):
  Profile         Name          Config Dir
  default         Alice         ~/.openclaw
  alpha           Bob           ~/.openclaw-alpha

Found 3 group chat(s):
  Channel      Chat ID              Name
  feishu       oc_abc123...         my-team

Suggested init command:
  bb init \
    --agents "Alice,Bob" \
    --profiles "default,alpha" \
    --channel feishu \
    --notify-target oc_abc123... \
    --enable-poller
```

### Step 3: Run the suggested command

```bash
bb init \
  --agents "Alice,Bob" \
  --profiles "default,alpha" \
  --channel feishu \
  --notify-target oc_abc123... \
  --enable-poller
```

This automatically:
- Creates directories and installs the Chalkboard skill
- Generates `config.json` with agents, sessions, and credentials (auto-discovered from OpenClaw)
- Sets up a launchd daemon that polls messages + checks TODOs + triggers agents every 5 seconds
- Forwards agent responses directly to the group chat

### Step 4: Create a task and watch

```bash
bb create --title "Research AI frameworks" \
  --assign alice,bob \
  --template research
```

Then tell Agent A in the group chat to check the board. The daemon handles the rest:
- Agent A does Round 1 → daemon detects Agent B has Round 2 → triggers Agent B → forwards reply to group → daemon detects Agent A has Round 3 → triggers Agent A → done.

## How It Works

```
┌──────────────┐  ┌──────────────┐
│   Agent A    │  │   Agent B    │
│  (Feishu)    │  │  (Telegram)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────────────────┐
│              ~/.chalkboard/                      │
│                                                  │
│  boards/        Task files (Markdown + TODOs)    │
│  context/       Group messages (JSONL)            │
│  config.json    Agents, sessions, credentials    │
│  daemon.sh      Poller + Decision + Trigger      │
└─────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────┐
│  Chalkboard Daemon (launchd, every 5s)           │
│                                                  │
│  1. poller.py   → Fetch ALL group messages       │
│                   (Feishu API / Telegram API)     │
│                                                  │
│  2. decide.py   → Does any agent have a TODO?    │
│                   Is it their turn?               │
│                   → Trigger via session inject     │
│                                                  │
│  3. Forward     → Capture agent response          │
│                   → Send to group via message API  │
└─────────────────────────────────────────────────┘
```

### Decision Logic

The decision engine checks each agent in order:

1. **Does this agent have a pending TODO on the chalkboard?** If no → skip
2. **Is it this agent's turn?** (first uncompleted TODO belongs to this agent?) If no → skip
3. **Cooldown passed?** (prevent rapid re-triggering) If no → skip
4. **Trigger** → inject task + context into agent session
5. **Forward** → capture reply, send to group chat via `openclaw message send`

### Two-Step Trigger + Forward

The key innovation: instead of relying on agents to post their own replies (unreliable), Chalkboard captures the agent's output and forwards it:

```
Step 1: openclaw agent --session-id xxx --message "do your TODO" --json
        → Agent executes, produces response in JSON

Step 2: Parse response → openclaw message send --channel feishu --target group
        → Response appears in the group chat
```

If the agent produces no text (it used tools instead), the daemon extracts the latest work log entry from the board file and forwards that.

## Features

| Feature | Description |
|---------|-------------|
| **Message poller** | Fetches ALL group messages via Feishu/Telegram API (including other bots) |
| **TODO-driven triggers** | Agents are triggered based on Chalkboard TODOs, not unreliable chat parsing |
| **Response forwarding** | Captures agent output and posts it to the group chat |
| **Agent auto-discovery** | `bb agents` scans for OpenClaw profiles + group chats |
| **Board templates** | `--template research/code-review/brainstorm/content` |
| **Turn control** | First uncompleted TODO determines whose turn it is |
| **Agent identity** | `CHALKBOARD_AGENT_ID` prevents marking others' TODOs |
| **Cross-platform** | Feishu + Telegram providers, pluggable design |
| **Zero dependencies** | Pure Python 3.8+ standard library |

## CLI Reference

| Command | Description |
|---------|-------------|
| `bb agents` | Auto-discover agents and group chats |
| `bb init` | Set up Chalkboard (skill, daemon, poller, config) |
| `bb create` | Create a new task board (supports `--template`) |
| `bb list` | List all active tasks |
| `bb read <task-id>` | Read a task board |
| `bb log <task-id>` | Append a work log entry |
| `bb todo <task-id> --add` | Add a TODO for an agent |
| `bb todo <task-id> --done` | Mark a TODO as complete (identity-checked) |
| `bb my-todos --agent <name>` | Show pending TODOs (supports aliases) |
| `bb complete <task-id>` | Archive a completed task |
| `bb poller status` | Show daemon status |
| `bb poller start/stop` | Start or stop the daemon |
| `bb context --group <id>` | View recent group messages from poller |

## Templates

```bash
bb create --title "..." --assign a,b --template research
bb create --title "..." --assign a,b --template code-review
bb create --title "..." --assign a,b --template brainstorm
bb create --title "..." --assign a,b,c --template content
```

| Template | Rounds | Flow |
|----------|--------|------|
| `research` | 3 | A researches → B researches → A synthesizes |
| `code-review` | 3 | A security review → B perf review → A summary |
| `brainstorm` | 3 | A proposes ideas → B ranks → A plans top 3 |
| `content` | 4 | A gathers sources → B drafts → A reviews → B finalizes |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHALKBOARD_BOARD_DIR` | `~/.chalkboard/boards` | Active task boards |
| `CHALKBOARD_ARCHIVE_DIR` | `~/.chalkboard/archive` | Completed tasks |
| `CHALKBOARD_AGENT_ID` | (empty) | Agent identity for TODO ownership |
| `CHALKBOARD_CONTEXT_DIR` | `~/.chalkboard/context` | Polled message storage |

## License

[MIT](LICENSE)
