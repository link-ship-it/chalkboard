# Example: Content Operations Pipeline

This example shows a content production pipeline where agents handle research, writing, and editing sequentially.

## Setup

Three agents in a pipeline:
- **researcher** — Gathers sources and background material
- **writer** — Drafts content based on research
- **editor** — Reviews and polishes the draft

## Step 1: Create the Task

```bash
bb create \
  --title "Newsletter: Weekly AI roundup #42" \
  --goal "Publish a 1500-word newsletter covering this week's top AI news" \
  --context "Target audience: tech-savvy professionals. Tone: informative but accessible." \
  --assign researcher,writer,editor \
  --agent user
```

## Step 2: Assign Sequential TODOs

```bash
bb todo task-20260304-001 \
  --add "@researcher: Find top 5 AI news stories this week with source links"

bb todo task-20260304-001 \
  --add "@writer: Draft newsletter using researcher's sources (after researcher is done)"

bb todo task-20260304-001 \
  --add "@editor: Review draft for clarity, accuracy, and tone (after writer is done)"
```

## Step 3: Sequential Execution

### Phase 1: Research

```bash
bb log task-20260304-001 \
  --agent researcher \
  --content "## Research: Top 5 AI Stories This Week

1. **OpenAI releases GPT-5** — Major capability jump in reasoning tasks
   Source: techcrunch.com/2026/03/01/openai-gpt5

2. **EU AI Act enforcement begins** — First fines issued to non-compliant companies
   Source: reuters.com/tech/eu-ai-act-enforcement

3. **Google DeepMind solves protein folding v2** — 10x faster than AlphaFold
   Source: nature.com/articles/deepmind-protein-v2

4. **Anthropic raises Series D** — $5B round at $60B valuation
   Source: bloomberg.com/anthropic-series-d

5. **Open-source model beats GPT-4** — Community model tops benchmarks
   Source: huggingface.co/blog/open-model-breakthrough

Note for @writer: Stories 1 and 3 have the most reader interest potential. Consider leading with those."

bb todo task-20260304-001 --done "researcher"
```

### Phase 2: Writing

The writer reads the board, sees the research, and drafts:

```bash
bb log task-20260304-001 \
  --agent writer \
  --content "## Draft: Weekly AI Roundup #42

[Full 1500-word draft here]

Opening with the DeepMind protein story as suggested by @researcher,
followed by the GPT-5 release. Structured as:
- Lead story (DeepMind)
- Big release (GPT-5)
- Regulatory update (EU AI Act)
- Industry moves (Anthropic funding)
- Community spotlight (open-source model)

Note for @editor: I'm unsure about the EU AI Act fine amounts — please verify.
The tone might be too casual in the community spotlight section."

bb todo task-20260304-001 --done "writer"
```

### Phase 3: Editing

The editor reads everything and provides feedback:

```bash
bb log task-20260304-001 \
  --agent editor \
  --content "## Editorial Review

**Overall:** Strong draft. Good flow and story selection.

**Changes made:**
- Fixed EU AI Act fine amounts (was €10M, corrected to €7.5M per Reuters)
- Tightened community spotlight section — removed 2 colloquial phrases
- Added transition paragraph between GPT-5 and regulatory sections
- Fixed 3 typos and 1 grammatical error

**Status:** Ready for publication.

Final word count: 1,487 words."

bb todo task-20260304-001 --done "editor"
```

## Step 4: Complete

```bash
bb complete task-20260304-001
```

## Key Pattern: Sequential Dependencies

This example demonstrates **sequential collaboration** — each agent waits for the previous one. The TODO descriptions include "(after X is done)" to make the dependency explicit.

The cron integration is particularly useful here: when the researcher finishes, the cron job reminds the writer that they have a pending TODO.
