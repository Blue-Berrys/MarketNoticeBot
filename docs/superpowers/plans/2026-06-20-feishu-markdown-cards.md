# Feishu Markdown Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send weekly reports as readable Feishu interactive Markdown cards instead of plain text.

**Architecture:** Add pure formatting and card-building helpers beside the existing Feishu sender. The sender signs and submits each generated card independently, preserving the existing webhook configuration and callers.

**Tech Stack:** Python standard library, Feishu custom-bot interactive cards, unittest.

## Global Constraints

- Do not change report-generation content or investment rules.
- Do not expose webhook or signing secret.
- Convert Markdown tables to readable lines.
- Split long reports by section and size.

---

### Task 1: Card formatting and payload construction

**Files:**
- Modify: `scripts/weekly_market_snapshot.py`
- Test: `tests/test_weekly_market_snapshot.py`

**Interfaces:**
- Produces: `build_feishu_cards(text: str, max_chars: int = 3500) -> list[dict]`
- Produces: `send_feishu(text: str, webhook: str, secret: str) -> list[dict]`

- [ ] Write failing tests asserting `interactive`, `lark_md`, section splitting, and table conversion.
- [ ] Run the focused tests and confirm they fail because cards are not implemented.
- [ ] Implement Markdown normalization, section/chunk splitting, and card payload generation.
- [ ] Update `send_feishu` to sign and submit each card.
- [ ] Run focused and complete weekly-report tests.

### Task 2: Deploy and verify

**Files:**
- Deploy: `scripts/weekly_market_snapshot.py`

- [ ] Sync the script to `tx`.
- [ ] Re-send `latest-learning-report.md`.
- [ ] Verify every Feishu response has success code zero.
- [ ] Run repository tests and update the Obsidian project note.
