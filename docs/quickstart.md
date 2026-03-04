# Quick Start Guide

Get Liuyanban running in 5 minutes.

## Prerequisites

- Python 3.8+
- [OpenClaw](https://github.com/openclaw/openclaw) (optional, for cron integration)

## 1. Install

```bash
git clone https://github.com/link-ship-it/liuyanban.git
cp -r liuyanban ~/.openclaw-shared/skills/liuyanban
chmod +x ~/.openclaw-shared/skills/liuyanban/bb
```

Add `bb` to your PATH (optional but recommended):

```bash
echo 'export PATH="$HOME/.openclaw-shared/skills/liuyanban:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## 2. Configure

```bash
mkdir -p ~/.liuyanban
cp config.example.yaml ~/.liuyanban/config.yaml
```

Edit `~/.liuyanban/config.yaml` to define your agents and directories.

## 3. Create Your First Task

```bash
bb create \
  --title "Test the bulletin board" \
  --goal "Verify that all agents can read and write to the board" \
  --assign agent-a,agent-b \
  --agent agent-a
```

You'll see output like:

```
Created: /home/user/.liuyanban/boards/task-20260304-001.md
Task ID: task-20260304-001
Assigned to: agent-a, agent-b
```

## 4. Work with the Board

```bash
# List tasks
bb list

# Read the task
bb read task-20260304-001

# Log your work
bb log task-20260304-001 \
  --agent agent-a \
  --content "Board is working correctly. File locking verified."

# Mark TODO as done
bb todo task-20260304-001 --done "agent-a"

# Check remaining TODOs
bb my-todos --agent agent-b
```

## 5. Set Up Cron Reminders (Optional)

In your OpenClaw config:

```yaml
cron:
  - schedule: "*/2 * * * *"
    command: "python3 ~/.openclaw-shared/skills/liuyanban/scripts/check_todos.py agent-a"
    announce: true
```

This checks every 2 minutes and reminds the agent of any pending TODOs.

## 6. Complete and Archive

```bash
bb complete task-20260304-001
```

The task is moved from `~/.liuyanban/boards/` to `~/.liuyanban/archive/`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIUYANBAN_BOARD_DIR` | `~/.liuyanban/boards` | Where active task boards are stored |
| `LIUYANBAN_ARCHIVE_DIR` | `~/.liuyanban/archive` | Where completed tasks are archived |

## Next Steps

- Read [Architecture](architecture.md) to understand how file locking and task lifecycle work
- See [Use Cases](use-cases.md) for real collaboration patterns
- Check out [examples/](../examples/) for complete walkthroughs
