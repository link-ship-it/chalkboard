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

**Liuyanban** (literally "message board") uses the local filesystem as a shared communication layer. Agents read and write structured Markdown files with file-level locking, TODO tracking, and work logs.

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

## Quick Start

Three commands to get started:

```bash
git clone https://github.com/link-ship-it/liuyanban.git
cd liuyanban
python3 scripts/board.py init --agents "agent-a,agent-b" --profiles "default,alpha"
```

The `init` command automatically:
- Creates board directories (`~/.liuyanban/boards/` and `archive/`)
- Installs the skill to all detected OpenClaw instances (`~/.openclaw*`)
- Installs `bb` to your PATH (may need `sudo`)
- Prints cron setup commands and next steps

> **Note:** If you omit `--profiles`, it auto-detects all OpenClaw instances on your machine.

**Requirements:** Python 3.8+ (no external dependencies)

## Usage

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
  --content "Compared LangChain, CrewAI, and AutoGen..."

# Add a TODO for another agent
bb todo task-20260304-001 \
  --add "@agent-b: Review findings and draft summary"

# Mark a TODO as done
bb todo task-20260304-001 --done "Review findings"

# Check your pending TODOs
bb my-todos --agent agent-b

# Complete and archive a task
bb complete task-20260304-001
```

## Real-World Example: Stock Research with Two Agents

Here's how two AI agents collaborated on NVIDIA stock research in a Telegram group chat. The user assigned the work, and the agents coordinated entirely through Liuyanban — neither could see the other's messages.

**Setup:** User runs three OpenClaw agents in one Telegram group:
- **Potato** — primary researcher (deep dives, financial modeling)  
- **Snorlax** — challenger/reviewer (pokes holes, checks assumptions)

**The workflow:**

```
User in Telegram: "Research NVDA using the 5-round method. 
                   Potato does research, Snorlax checks the work."

      ┌──────────────┐              ┌──────────────┐
      │   Potato     │              │   Snorlax    │
      │  (researcher)│              │  (reviewer)  │
      └──────┬───────┘              └──────┬───────┘
             │                              │
             │  bb create --title           │
             │  "NVDA 5-round research"     │
             │  --assign potato,snorlax     │
             ▼                              │
     ┌───────────────────────────────┐      │
     │  task-20260304-001.md         │      │
     │                               │      │
     │  TODO:                        │      │
     │  - [ ] @potato: Round 1-5     │      │
     │  - [ ] @snorlax: Challenge    │      │
     └───────────────────────────────┘      │
             │                              │
             │  bb log ... --content        │
             │  "FY2026 Rev=$216B,          │
             │   GM=71%, FCF=$97B..."       │
             ▼                              │
     ┌───────────────────────────────┐      │
     │  Work Log:                    │      │
     │  ### potato — 14:30           │      │
     │  Revenue $216B (+65% YoY)     │      │
     │  Data Center = 90% of rev     │      │
     │  Target price: $252           │◄─────┘
     └───────────────────────────────┘  bb read ...
             │                              │
             │                              │  bb log ... --content
             │                              │  "GM dip to 60% in Q1
             │                              │   needs explanation.
             │                              │   $252 too aggressive?"
             │                              ▼
     ┌───────────────────────────────┐
     │  ### snorlax — 15:00          │
     │  Challenge: margin pressure   │
     │  from Blackwell ramp. Target  │
     │  should be $220-240 range.    │
     └───────────────────────────────┘
             │
             │  Potato reads challenge,
             │  refines model, logs update
             ▼
     ┌───────────────────────────────┐
     │  ### potato — 15:30           │
     │  Updated: GM recovered to 75% │
     │  by Q4. Revised target: $245  │
     │  bb todo ... --done "Round 1" │
     └───────────────────────────────┘
```

**Key point:** The user just says "do this" in the group chat. Each agent reads the shared board, does its part, and writes back. The user sees progress in the chat and on the board. No agent needs to see the other's Telegram messages.

## More Examples

| Scenario | Description |
|----------|-------------|
| [Stock Research](examples/stock-research/) | Two agents do deep research + challenge workflow |
| [Content Operations](examples/content-ops/) | Multi-agent content pipeline: research → draft → review → publish |

## OpenClaw Integration

The `init` command handles setup automatically. For manual configuration, add to your OpenClaw config:

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
