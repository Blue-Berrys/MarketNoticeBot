#!/usr/bin/env python3
"""Run TradingAgents non-interactively for the weekly learning report."""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any


ASSETS = {
    "美国科技": {"ticker": "QQQ", "dca_eligible": True},
    "美国大盘": {"ticker": "SPY", "dca_eligible": True},
    "恒生指数": {"ticker": "^HSI", "dca_eligible": True},
    "恒生科技": {"ticker": "HSTECH.HK", "dca_eligible": True},
    "黄金": {"ticker": "GLD", "dca_eligible": True},
    "原油": {"ticker": "USO", "dca_eligible": True},
    "中国科技": {"ticker": "000688.SS", "dca_eligible": True},
    "中国半导体": {"ticker": "931865.SS", "dca_eligible": True},
    "美光存储": {"ticker": "MU", "dca_eligible": False},
    "闪迪存储": {"ticker": "SNDK", "dca_eligible": False},
}

REPORT_SECTIONS = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
)


def safe_ticker(ticker: str) -> str:
    return ticker.replace("^", "INDEX_").replace("/", "_").replace(".", "_")


def build_config(ticker: str, work_dir: Path) -> dict[str, Any]:
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["data_vendors"] = DEFAULT_CONFIG["data_vendors"].copy()
    config["tool_vendors"] = DEFAULT_CONFIG["tool_vendors"].copy()
    config.update(
        {
            "llm_provider": "deepseek",
            "deep_think_llm": "deepseek-v4-pro",
            "quick_think_llm": "deepseek-v4-flash",
            "backend_url": None,
            "output_language": "Chinese",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "analyst_concurrency_limit": 1,
            "checkpoint_enabled": False,
            "memory_log_path": str(
                work_dir / "memory" / f"{safe_ticker(ticker)}.md"
            ),
            "results_dir": str(work_dir / "graph-logs"),
            "data_cache_dir": str(work_dir / "cache"),
        }
    )
    return config


def render_report(
    ticker: str,
    label: str,
    analysis_date: str,
    state: dict[str, Any],
    decision: Any,
) -> str:
    parts = [
        f"# {label}（{ticker}）— {analysis_date}",
        "",
        "> 本报告来自 TradingAgents 全流程。短期评级只作为金融学习材料，"
        "不直接转换为十年定投操作。",
    ]
    for section in REPORT_SECTIONS:
        parts.extend(["", f"## {section}", "", str(state.get(section) or "(empty)")])
    parts.extend(
        [
            "",
            "## 短期模型原始结论（仅作学习材料）",
            "",
            str(decision),
            "",
        ]
    )
    return "\n".join(parts)


def run_one(job: tuple[str, dict[str, Any], str, str]) -> dict[str, Any]:
    label, asset, analysis_date, output_root_text = job
    ticker = asset["ticker"]
    output_root = Path(output_root_text)
    started = time.time()
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = build_config(ticker, output_root)
        graph = TradingAgentsGraph(debug=False, config=config)
        state, decision = graph.propagate(ticker, analysis_date)
        report_dir = output_root / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{safe_ticker(ticker)}_{analysis_date}.md"
        report_path.write_text(
            render_report(ticker, label, analysis_date, state, decision),
            encoding="utf-8",
        )
        return {
            "label": label,
            "ticker": ticker,
            "status": "ok",
            "report": str(report_path),
            "decision": str(decision),
            "elapsed_seconds": round(time.time() - started, 1),
            "dca_eligible": asset["dca_eligible"],
        }
    except Exception as exc:
        traceback.print_exc()
        return {
            "label": label,
            "ticker": ticker,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(time.time() - started, 1),
            "dca_eligible": asset["dca_eligible"],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-dir", default="weekly-deep-output")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument(
        "--assets",
        nargs="*",
        choices=tuple(ASSETS),
        help="Subset of asset labels; default runs the full universe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    max_workers = max(1, min(args.max_workers, 3))
    output_root = Path(args.output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    labels = args.assets or list(ASSETS)
    jobs = [
        (label, ASSETS[label], args.date, str(output_root))
        for label in labels
    ]
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_one, job): job[0] for job in jobs}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    summary_path = output_root / f"summary_{args.date}.json"
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if all(item["status"] == "ok" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
