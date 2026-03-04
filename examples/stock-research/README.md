# Example: Stock Research Collaboration

This example shows how three agents can collaboratively analyze a stock.

## Setup

Three agents with different expertise:
- **fundamental-analyst** — Financial statements, valuation metrics
- **technical-analyst** — Price charts, technical indicators
- **sentiment-analyst** — News, social media, institutional activity

## Step 1: Create the Task

```bash
bb create \
  --title "AAPL Q2 2026 investment analysis" \
  --goal "Deliver a buy/hold/sell recommendation with supporting evidence" \
  --context "User is considering a $10k position. Risk tolerance: moderate." \
  --assign fundamental-analyst,technical-analyst,sentiment-analyst \
  --agent user \
  --priority high
```

## Step 2: Assign Specific TODOs

```bash
bb todo task-20260304-001 \
  --add "@fundamental-analyst: Analyze AAPL Q1 earnings, P/E ratio, revenue trend, and FCF"

bb todo task-20260304-001 \
  --add "@technical-analyst: 50/200 DMA crossover, RSI, MACD, support/resistance levels"

bb todo task-20260304-001 \
  --add "@sentiment-analyst: Analyst ratings, news sentiment (last 7 days), insider transactions"
```

## Step 3: Agents Do Their Work

Each agent reads the board, performs analysis, and logs results:

```bash
# fundamental-analyst logs their work
bb log task-20260304-001 \
  --agent fundamental-analyst \
  --content "## Fundamental Analysis

**Revenue:** $124B (Q1 2026), +8% YoY
**P/E Ratio:** 28.5 (slightly above 5-year avg of 26.2)
**Free Cash Flow:** $28B trailing 12 months
**Moat:** Strong ecosystem lock-in, services revenue growing 15% YoY

**Assessment:** Fundamentally sound but priced for growth. Fair value ~$195."

bb todo task-20260304-001 --done "fundamental-analyst"
```

```bash
# technical-analyst logs their work
bb log task-20260304-001 \
  --agent technical-analyst \
  --content "## Technical Analysis

**50 DMA:** $188 (price above — bullish)
**200 DMA:** $175 (price above — bullish)
**RSI:** 62 (neutral, not overbought)
**MACD:** Bullish crossover 3 days ago
**Support:** $182 | **Resistance:** $198

**Assessment:** Bullish setup. Entry zone: $185-190."

bb todo task-20260304-001 --done "technical-analyst"
```

```bash
# sentiment-analyst logs their work
bb log task-20260304-001 \
  --agent sentiment-analyst \
  --content "## Sentiment Analysis

**Analyst Consensus:** 28 Buy, 8 Hold, 2 Sell (avg target $205)
**News Sentiment:** Positive — new product launch well-received
**Insider Activity:** CFO sold $2M (routine scheduled sale)
**Institutional Flow:** Net buying last 2 weeks

**Assessment:** Sentiment is bullish. No red flags."

bb todo task-20260304-001 --done "sentiment-analyst"
```

## Step 4: User Reviews and Completes

```bash
# User reads the complete board
bb read task-20260304-001

# All done — archive it
bb complete task-20260304-001
```

## Result

The user gets a multi-perspective analysis combining fundamental, technical, and sentiment views — all coordinated through a single shared task board, even though the agents cannot directly communicate with each other.
