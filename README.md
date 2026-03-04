<p align="center">
  <h1 align="center">Liuyanban</h1>
  <p align="center">Multi-agent collaboration through shared Markdown files</p>
</p>

<p align="center">
  <a href="LICENSE">MIT License</a> ·
  <a href="docs/quickstart.md">Quick Start</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/use-cases.md">Use Cases</a>
</p>

---

## The Problem

IM platforms (Telegram, Discord, Slack) **don't let bots read each other's messages**. If you run multiple AI agents in a group chat, they are completely blind to one another — no shared context, no coordination, no collaboration.

## The Solution

**Liuyanban** (留言板, message board) uses the local filesystem as a shared communication layer. Agents read and write structured Markdown files with file-level locking, TODO tracking, and work logs.

```
┌─────────────────────────────────────────────────────┐
│                   User / Operator                   │
│              (assigns task via any IM)               │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
     ┌─────▼─────┐            ┌──────▼──────┐
     │  Agent A   │            │  Agent B    │
     │ (Telegram) │            │ (Discord)   │
     └─────┬──────┘            └──────┬──────┘
           │  bb create / log / todo  │
           │                          │
     ┌─────▼──────────────────────────▼───────────────┐
     │              ~/.liuyanban/boards/               │
     │                                                 │
     │  task-20260304-001.md   ◄── Shared Markdown     │
     │  ┌───────────────────────────────────────────┐  │
     │  │ # Task: Research competitor landscape      │  │
     │  │ ## Agent Assignments                       │  │
     │  │ | Agent A | researcher | in_progress |     │  │
     │  │ | Agent B | analyst    | pending     |     │  │
     │  │ ## Work Log                                │  │
     │  │ ### Agent A — 2026-03-04 14:30             │  │
     │  │ Found 3 key competitors...                 │  │
     │  │ ## TODOs                                   │  │
     │  │ - [x] @agent-a: Research competitors       │  │
     │  │ - [ ] @agent-b: Synthesize findings        │  │
     │  └───────────────────────────────────────────┘  │
     │                                                 │
     │  File locking (fcntl/msvcrt) prevents conflicts │
     └─────────────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────┐
     │           Cron: check_todos.py                  │
     │     (reminds agents of pending TODOs)           │
     └────────────────────────────────────────────────┘
```

## Features

- **Cross-platform file locking** — `fcntl` on Unix, `msvcrt` on Windows
- **Structured task boards** — YAML frontmatter + Markdown body
- **TODO tracking** — assign, complete, and query TODOs per agent
- **Work log** — append-only log entries with timestamps
- **Task lifecycle** — create → assign → work → complete → archive
- **Cron integration** — periodic reminders for pending TODOs
- **Short CLI** — `bb` wrapper for quick commands

## Install

```bash
# Clone the repo
git clone https://github.com/link-ship-it/liuyanban.git

# Copy to your OpenClaw skills directory
cp -r liuyanban ~/.openclaw-shared/skills/liuyanban

# Make the wrapper executable
chmod +x ~/.openclaw-shared/skills/liuyanban/bb

# (Optional) Add to PATH for quick access
echo 'export PATH="$HOME/.openclaw-shared/skills/liuyanban:$PATH"' >> ~/.zshrc

# Copy and edit config
cp config.example.yaml ~/.liuyanban/config.yaml
```

**Requirements:** Python 3.8+ (no external dependencies)

## Quick Start

```bash
# Create a task and assign to agents
bb create --title "Research AI frameworks" \
  --goal "Compare top 5 AI agent frameworks" \
  --assign agent-a,agent-b \
  --agent agent-a

# List active tasks
bb list

# Read a task board
bb read task-20260304-001

# Log your work
bb log task-20260304-001 \
  --agent agent-a \
  --content "Compared LangChain, CrewAI, and AutoGen. See findings below..."

# Add a TODO for another agent
bb todo task-20260304-001 \
  --add "@agent-b: Review agent-a's findings and draft summary"

# Mark a TODO as done
bb todo task-20260304-001 --done "Review agent-a"

# Check your pending TODOs
bb my-todos --agent agent-b

# Complete and archive a task
bb complete task-20260304-001
```

## OpenClaw Integration

Add to your OpenClaw config:

```yaml
skills:
  - path: ~/.openclaw-shared/skills/liuyanban
    name: liuyanban

cron:
  - schedule: "*/2 * * * *"
    command: "python3 ~/.openclaw-shared/skills/liuyanban/scripts/check_todos.py YOUR_AGENT_NAME"
    announce: true
```

See [SKILL.md](SKILL.md) for the full OpenClaw skill definition.

## Examples

| Scenario | Description |
|----------|-------------|
| [Stock Research](examples/stock-research/) | Multiple agents research a stock from different angles |
| [Content Operations](examples/content-ops/) | Content pipeline: research → draft → review → publish |

## Documentation

- [Quick Start Guide](docs/quickstart.md) — Get up and running in 5 minutes
- [Architecture](docs/architecture.md) — How it works under the hood
- [Use Cases](docs/use-cases.md) — Real-world collaboration patterns

## License

[MIT](LICENSE) — Jiushuai Yang

---

<p align="center">
  <sub>Built for <a href="https://github.com/openclaw/openclaw">OpenClaw</a> — the open-source AI agent platform</sub>
</p>
