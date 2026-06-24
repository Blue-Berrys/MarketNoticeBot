#!/usr/bin/env python3
"""Compile TradingAgents outputs into a long-horizon learning report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from scripts.weekly_market_snapshot import load_env_file, send_feishu
except ModuleNotFoundError:
    # When executed as ``python scripts/compile_weekly_learning_report.py``,
    # Python places ``scripts/`` rather than the repository root on sys.path.
    from weekly_market_snapshot import load_env_file, send_feishu


def collect_report_material(summary: list[dict]) -> dict[str, str]:
    materials = {}
    for item in summary:
        if item.get("status") != "ok" or not item.get("report"):
            continue
        path = Path(item["report"])
        if path.exists():
            materials[item["label"]] = path.read_text(encoding="utf-8")
    return materials


def _trim_report(text: str, limit: int = 10000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[为控制汇总长度已截断]"


def build_synthesis_prompt(
    snapshot: str,
    materials: dict[str, str],
    analysis_date: str,
) -> str:
    sources = "\n\n".join(
        f"===== {label} =====\n{_trim_report(text)}"
        for label, text in materials.items()
    )
    return f"""
你是一名面向十年持续定投者的金融学习报告编辑。分析日期为
{analysis_date}。用户每周投入约500元，采用股债商三分法，主动提高科技
权重，并接受大幅波动。

严格规则：
1. 不得把 BUY/HOLD/SELL、短线目标价或止损位直接转换为用户操作。
2. 只有轻量核验快照中的已实现回撤和长期均线可用于 1x/2x/3x 提醒。
3. MU、SNDK 是存储产业观察项，不给定投倍数，不建议越跌越买。
4. 不预测金融危机；只解释已观察到的信用、波动、利率和趋势信号。
5. 明确区分事实数据、模型推断和数据缺失。
6. 不使用境内 QDII 场内 ETF 的溢价价格代表海外底层资产。
7. 宏观与风险温度中的每一个指标都必须逐项写清：
   - 指标是什么（面向完全没有金融基础的新手）；
   - 当前值；
   - 通常影响股票、债券、黄金或商品中的哪些资产，以及常见影响方向；
   - 本周这个数值应如何理解，但不得据此预测必然涨跌；
   - 数据来源类型：官方经济数据、预测市场概率或模型推断。
8. 概率数据不得写成已经发生的事实；必须明确它只是市场定价或调查概率。
9. 中文社区帖子只能作为散户观点与叙事信号，不能当成事实新闻。
10. 输出中文，控制在5000字以内。

请按以下固定标题输出：
# 每周金融学习日报 · {analysis_date}
## 一、本周结论
## 二、三分法组合
## 三、美国科技与大盘
## 四、恒生市场
## 五、中国科技与半导体
## 六、黄金与原油
## 七、存储产业
## 八、宏观与风险温度
## 九、本周学习
## 十、数据质量与限制

轻量核验快照：
{snapshot}

TradingAgents 多智能体原始材料：
{sources}
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
    parser.add_argument("--date", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--feishu-config")
    parser.add_argument("--no-push", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    snapshot = Path(args.snapshot).read_text(encoding="utf-8")
    materials = collect_report_material(summary)
    report = synthesize(build_synthesis_prompt(snapshot, materials, args.date))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report + "\n", encoding="utf-8")
    print(report)
    if not args.no_push:
        config = load_env_file(args.feishu_config)
        send_feishu(report, config["FEISHU_WEBHOOK"], config["FEISHU_SECRET"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
