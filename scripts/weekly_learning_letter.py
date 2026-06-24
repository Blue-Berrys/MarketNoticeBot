#!/usr/bin/env python3
"""Saturday beginner finance-learning letter.

A light, self-contained companion to the Wednesday market notice. It does NOT
run the multi-agent graph: it reuses the cheap stdlib snapshot for real numbers
and makes a single LLM call to write one structured lesson, driven by a fixed
curriculum (with contextual market-event inserts). Pushes Feishu cards.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

try:
    from scripts.learning_syllabus import (
        SYLLABUS,
        choose_lesson,
        current_prices,
    )
    from scripts.weekly_market_snapshot import (
        ASSETS,
        build_asset_snapshot,
        build_report,
        fetch_asset_rows,
        fetch_macro,
        load_env_file,
        send_feishu,
    )
except ModuleNotFoundError:
    # When executed as ``python scripts/weekly_learning_letter.py`` the
    # ``scripts/`` directory, not the repo root, is on sys.path.
    from learning_syllabus import SYLLABUS, choose_lesson, current_prices
    from weekly_market_snapshot import (
        ASSETS,
        build_asset_snapshot,
        build_report,
        fetch_asset_rows,
        fetch_macro,
        load_env_file,
        send_feishu,
    )

DEFAULT_PROGRESS = "~/weekly-snapshot/learning-progress.json"


def collect_snapshots(fred_api_key: str | None = None) -> tuple[list[dict], dict]:
    snapshots: list[dict] = []
    for symbol, asset in ASSETS.items():
        try:
            snapshot = build_asset_snapshot(
                symbol,
                asset["name"],
                fetch_asset_rows(asset),
                dca_eligible=asset["dca_eligible"],
            )
            snapshot["dca_eligible"] = asset["dca_eligible"]
            snapshots.append(snapshot)
        except Exception as exc:
            snapshots.append(
                {
                    "symbol": symbol,
                    "name": asset["name"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return snapshots, fetch_macro(fred_api_key)


def load_progress(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"next_index": 0, "last_prices": {}, "last_vix": None, "history": []}


def save_progress(
    path: Path,
    progress: dict,
    lesson: dict,
    snapshots: list[dict],
    macro: dict,
    today: str,
) -> None:
    if lesson["advance"]:
        progress["next_index"] = int(progress.get("next_index", 0) + 1) % len(SYLLABUS)
    progress["last_prices"] = current_prices(snapshots)
    progress["last_vix"] = macro.get("vix")
    history = progress.get("history") or []
    history.append({"date": today, "kind": lesson["kind"], "title": lesson["title"]})
    progress["history"] = history[-60:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_prompt(lesson: dict, snapshot_text: str, today: str) -> str:
    kind_note = (
        "本周是一期“行情插播”，围绕刚发生的市场事件展开，但仍要把它当成一堂可长期复用的课。"
        if lesson["kind"] == "insert"
        else f"本周主题来自固定教学大纲，循序渐进。可联系的真实标的：{lesson.get('tie') or '自选最相关者'}。"
    )
    heading = (
        f"# 每周金融学习信 · {today} · {lesson['title']}"
        if lesson["kind"] == "insert"
        else f"# 每周金融学习信 · {today} · 第{lesson['week_no']}课：{lesson['title']}"
    )
    return f"""
你是一位面向“完全零金融基础”的耐心老师，学生是一名打算坚持十年的指数定投者：
采用股债商三分法、主动提高科技权重、明确不怕暴跌、用 TradingAgents 学习而非短炒。
请写一封本周的金融学习信。

本期主题：{lesson['title']}
讲解角度：{lesson['angle']}
{kind_note}

严格规则：
1. 面向新手：每出现一个术语都要用大白话解释，能打比方就打比方。
2. 不得给出任何 BUY/HOLD/SELL、目标价或择时建议；这是学习信，不是操作信。
3. “用本周真实数据看”一节必须引用下面快照里的真实数字，把概念落到当下行情。
4. 不预测涨跌、不预测危机；只解释已经发生或已经观测到的现象。
5. 区分事实数据、推断与数据缺失；概率不得写成既成事实。
6. 输出中文，控制在 3500 字以内，语气平实、鼓励长期纪律。

请严格按以下标题输出（保留一级与二级标题，便于推送切卡片）：
{heading}
## 一、本周核心概念
（把主题概念讲透：是什么、为什么重要、对长期定投者意味着什么）
## 二、用本周真实数据看
（引用快照里的具体数字，用本周行情解释这个概念）
## 三、术语卡
（挑 2–3 个相关高频术语，每个一句话人话翻译）
## 四、常见误区
（破除一个与本主题相关的直觉陷阱，说清为什么错）
## 五、历史小课堂
（一个具体的历史案例或经典常识，给长期视角）
## 六、思考题（文末附答案）
（出 1 道小题，先问，答案放在本节最后用“参考答案：”给出）
## 写给长期定投者
（一句话收尾，回到坚持定投、不被情绪左右的纪律）

本周轻量市场快照（真实数据，供第二节引用）：
{snapshot_text}
""".strip()


def synthesize(prompt: str) -> str:
    from tradingagents.llm_clients import create_llm_client

    llm = create_llm_client(
        provider="deepseek",
        model="deepseek-v4-pro",
        base_url=None,
    ).get_llm()
    response = llm.invoke(prompt)
    return str(response.content).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="~/weekly-snapshot/feishu.env")
    parser.add_argument("--progress", default=DEFAULT_PROGRESS)
    parser.add_argument("--output")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Generate and print, but do not push to Feishu.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pick the topic and print the prompt without calling the LLM.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser()
    config = load_env_file(config_path) if config_path.exists() else {}
    progress_path = Path(args.progress).expanduser()

    snapshots, macro = collect_snapshots(
        config.get("FRED_API_KEY") or os.getenv("FRED_API_KEY")
    )
    progress = load_progress(progress_path)
    lesson = choose_lesson(progress, snapshots, macro)
    snapshot_text = build_report(snapshots, macro)
    prompt = build_prompt(lesson, snapshot_text, args.date)

    print(f"[lesson] kind={lesson['kind']} title={lesson['title']}")
    if args.dry_run:
        print(prompt)
        return 0

    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    letter = synthesize(prompt)
    if args.output:
        Path(args.output).expanduser().write_text(letter + "\n", encoding="utf-8")
    print(letter)
    if not args.print_only:
        # Only a real, pushed run advances the curriculum; --print-only is a
        # side-effect-free preview.
        send_feishu(letter, config["FEISHU_WEBHOOK"], config["FEISHU_SECRET"])
        save_progress(progress_path, progress, lesson, snapshots, macro, args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
