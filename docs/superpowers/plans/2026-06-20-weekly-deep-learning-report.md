# Weekly Deep Learning Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a weekly two-layer report that combines verified market data with TradingAgents multi-agent analysis, then pushes a long-horizon learning summary to Feishu.

**Architecture:** Keep `weekly_market_snapshot.py` as the deterministic data-verification layer. Add a separate non-interactive deep-analysis runner that invokes `TradingAgentsGraph` for supported instruments, uses DeepSeek for every market while GLM quota is unavailable, and compiles reports without treating short-term ratings as user actions.

**Tech Stack:** Python 3.12, TradingAgents/LangGraph, DeepSeek, Sina/Tencent/FRED market data, Feishu webhook, cron.

## Global Constraints

- Use US-listed `QQQ`, `SPY`, `GLD`, and `USO`; never substitute mainland QDII exchange funds.
- Use Hang Seng Index and Hang Seng Tech Index directly.
- Track China technology with STAR 50 and a semiconductor index, not exchange-traded proxy funds.
- `MU` and `SNDK` are observation-only single stocks and receive no DCA multiplier.
- BUY/HOLD/SELL outputs are source material, not user actions.
- Keep concurrency at three or below to control upstream data/API pressure.

---

### Task 1: Expand deterministic asset coverage

**Files:**
- Modify: `scripts/weekly_market_snapshot.py`
- Modify: `tests/test_weekly_market_snapshot.py`

- [ ] Write failing tests for SPY/QQQ/GLD/USO, HSI/HSTECH, STAR50/semiconductor, and MU/SNDK observation-only classification.
- [ ] Run `.venv/bin/python -m unittest tests.test_weekly_market_snapshot -v` and verify failure.
- [ ] Add source mappings and separate DCA-eligible assets from observation-only assets.
- [ ] Run tests and verify all pass.

### Task 2: Add non-interactive TradingAgents batch runner

**Files:**
- Create: `scripts/run_weekly_deep_analysis.py`
- Create: `tests/test_weekly_deep_analysis.py`

- [ ] Write failing tests for all-DeepSeek configuration, concurrency cap, report persistence, and rating filtering.
- [ ] Run the focused tests and verify failure.
- [ ] Implement `TradingAgentsGraph` invocation with DeepSeek V4 Pro/Flash.
- [ ] Run focused tests and verify pass.

### Task 3: Compile the long-horizon learning report

**Files:**
- Create: `scripts/compile_weekly_learning_report.py`
- Create: `tests/test_compile_weekly_learning_report.py`

- [ ] Write failing tests for sections: portfolio temperature, macro cycle, stock/bond/commodity buckets, technology/semiconductor/storage observations, and source-data caveats.
- [ ] Implement deterministic compilation from snapshot plus saved TradingAgents reports.
- [ ] Verify ratings are excluded from action recommendations.

### Task 4: Run one complete analysis

- [ ] Verify local proxy and all required API keys without printing secrets.
- [ ] Run the deterministic snapshot.
- [ ] Run the full multi-agent batch for the latest common trading date, `2026-06-18`.
- [ ] Compile and push the resulting learning report to Feishu.
- [ ] Record failures per instrument without discarding successful reports.

### Task 5: Schedule and verify

**Files:**
- Modify: `scripts/run_weekly_market_snapshot.sh`

- [ ] Extend the weekly wrapper to run snapshot, deep analysis, compile, and Feishu delivery with `flock`.
- [ ] Keep logs and latest report under `~/weekly-snapshot`.
- [ ] Install the Wednesday 08:00 cron entry.
- [ ] Manually execute the wrapper and verify exit code, reports, and Feishu delivery.
