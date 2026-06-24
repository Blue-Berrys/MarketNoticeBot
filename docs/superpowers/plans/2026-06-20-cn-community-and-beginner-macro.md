# Chinese Community Sentiment and Beginner Macro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable Chinese retail-community evidence to sentiment analysis and beginner-friendly macro explanations to the weekly learning report.

**Architecture:** A resilient Eastmoney fetcher returns formatted public posts only for verified dedicated bars. The Sentiment Analyst receives this as a fourth structured source. The synthesis prompt enforces per-indicator beginner explanations without changing deterministic market calculations.

**Tech Stack:** Python standard library, Eastmoney public API, LangChain prompt assembly, pytest.

## Global Constraints

- No personal cookies or login state.
- No WAF bypass.
- No generic-bar posts presented as ticker-specific evidence.
- Community opinions are not factual news.
- Missing Chinese sources lower sentiment confidence.

---

### Task 1: Eastmoney community fetcher

**Files:**
- Create: `tradingagents/dataflows/eastmoney_guba.py`
- Test: `tests/test_eastmoney_guba.py`

- [ ] Write parser, verified-mapping, unavailable-source, and transport-error tests.
- [ ] Run tests and confirm failure.
- [ ] Implement the resilient public fetcher.
- [ ] Run focused tests.

### Task 2: Sentiment Analyst integration

**Files:**
- Modify: `tradingagents/agents/analysts/sentiment_analyst.py`
- Test: `tests/test_structured_agents.py`

- [ ] Write a failing prompt-content test.
- [ ] Inject the Chinese-community block and analysis rules.
- [ ] Run sentiment tests.

### Task 3: Beginner macro explanations

**Files:**
- Modify: `scripts/compile_weekly_learning_report.py`
- Test: `tests/test_compile_weekly_learning_report.py`

- [ ] Write a failing prompt-policy test.
- [ ] Require definition, asset effects, current interpretation, and source type.
- [ ] Run report compiler tests.

### Task 4: Server verification

- [ ] Deploy changed files.
- [ ] Fetch a live 科创50 community block.
- [ ] Re-run 科创50 through the complete multi-agent graph.
- [ ] Generate and push a preview learning report.
- [ ] Run repository tests and update Obsidian.
