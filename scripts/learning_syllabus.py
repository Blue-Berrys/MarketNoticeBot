"""Curriculum for the Saturday beginner finance-learning letter.

A fixed ~52-week syllabus drives the weekly topic so the letters build a
coherent, non-repeating course from the ground up. When a genuine market
event occurs (an acute weekly drop or a volatility spike), a contextual
"行情插播" lesson is inserted *without* consuming the syllabus pointer, so the
course resumes where it left off the following week.
"""

from __future__ import annotations

from typing import Any

# Each entry: title + angle (a one-line hint steering the LLM) + optional ``tie``
# naming the real asset/macro figure the "用本周真实数据看" section should use.
SYLLABUS: list[dict[str, str]] = [
    {"title": "指数基金到底是什么", "angle": "你买的是一篮子公司，不是一只股票", "tie": "QQQ/SPY"},
    {"title": "复利与72法则", "angle": "时间才是长期投资最大的朋友"},
    {"title": "市盈率 PE：贵还是便宜", "angle": "盈利与价格的比值，估值的第一把尺", "tie": "QQQ"},
    {"title": "回撤与最大回撤", "angle": "跌多少算正常，长期持有要承受什么", "tie": "当周回撤最大的资产"},
    {"title": "波动率与标准差", "angle": "风险如何被量化", "tie": "VIX"},
    {"title": "定投的数学", "angle": "为什么分批买入能摊平成本、微笑曲线"},
    {"title": "股债再平衡", "angle": "组合自动低买高卖的纪律"},
    {"title": "收益率曲线与倒挂", "angle": "经济的体温计", "tie": "美债10Y-2Y利差"},
    {"title": "通胀与实际利率", "angle": "钱为什么会变毛、名义vs实际"},
    {"title": "VIX 恐慌指数", "angle": "市场情绪的温度计", "tie": "VIX"},
    {"title": "估值分位", "angle": "今天处在历史的什么位置"},
    {"title": "美联储与降息周期", "angle": "利率如何影响几乎一切资产"},
    {"title": "黄金的角色", "angle": "它到底对冲什么，不产生现金流意味着什么", "tie": "GLD"},
    {"title": "原油与大宗商品", "angle": "周期性与地缘驱动", "tie": "USO"},
    {"title": "汇率与海外资产", "angle": "人民币/美元波动如何影响你的海外仓位"},
    {"title": "主动 vs 被动", "angle": "费率如何长期侵蚀收益"},
    {"title": "ETF 折溢价与 QDII 限购", "angle": "为什么用指数而非境内场内价"},
    {"title": "市值加权 vs 等权", "angle": "指数是怎么编出来的"},
    {"title": "夏普比率", "angle": "每承担一单位风险换来多少回报"},
    {"title": "贝塔与相关性", "angle": "资产之间是怎么一起动的"},
    {"title": "分散化", "angle": "投资里唯一的免费午餐"},
    {"title": "再投资与分红", "angle": "总回报的真正来源"},
    {"title": "久期与利率风险", "angle": "债券为什么也会跌"},
    {"title": "信用利差", "angle": "市场如何给风险定价"},
    {"title": "损失厌恶", "angle": "为什么亏钱比赚钱的感受强烈得多"},
    {"title": "追涨杀跌与处置效应", "angle": "人为什么总在高点贪、低点怕"},
    {"title": "锚定与近因偏差", "angle": "为什么我们盯着买入价和最近的行情"},
    {"title": "幸存者偏差", "angle": "你只看到赢家，输家已经消失"},
    {"title": "回测陷阱与过度拟合", "angle": "完美的历史曲线为何骗人"},
    {"title": "均值回归 vs 趋势", "angle": "便宜会更便宜，还是会回归"},
    {"title": "泡沫的解剖", "angle": "一个泡沫通常经历的五个阶段"},
    {"title": "2000 互联网泡沫", "angle": "故事、估值与崩塌", "tie": "QQQ"},
    {"title": "2008 金融危机", "angle": "杠杆与信用如何传染"},
    {"title": "2020 疫情闪崩与 V 型反弹", "angle": "最快的熊市与最快的复苏"},
    {"title": "日本失去的三十年", "angle": "单一市场长期不涨的风险", "tie": "恒生科技"},
    {"title": "巴菲特的指数赌约", "angle": "十年里指数如何战胜对冲基金"},
    {"title": "经典资产配置", "angle": "60/40、永久组合与股债商三分法"},
    {"title": "再平衡频率与阈值", "angle": "多久、偏离多少才动手"},
    {"title": "美股长期回报从哪来", "angle": "盈利增长 + 估值变化 + 分红", "tie": "SPY"},
    {"title": "半导体周期", "angle": "你押注的行业是怎么大起大落的", "tie": "中证半导体/MU"},
    {"title": "AI 投资主题", "angle": "主题投资的机会与陷阱", "tie": "QQQ/MU"},
    {"title": "港股与中国互联网", "angle": "低估值与监管的拉锯", "tie": "恒生科技"},
    {"title": "A 股的特点", "angle": "散户主导的市场与高波动"},
    {"title": "集中 vs 分散", "angle": "重押科技的代价与回报"},
    {"title": "税、费与摩擦成本", "angle": "长期收益的隐形杀手"},
    {"title": "通胀对长期投资者的意义", "angle": "为什么现金长期是亏的"},
    {"title": "现金的角色与机会成本", "angle": "留多少子弹、留着等什么"},
    {"title": "何时才该卖", "angle": "极端估值 + 狂热的双重确认"},
    {"title": "黑天鹅与肥尾", "angle": "极端事件为何比正态分布更常见"},
    {"title": "投资 vs 投机", "angle": "划清两者的界限"},
    {"title": "制定并坚持投资纪律", "angle": "写下你自己的投资准则（IPS）"},
    {"title": "年度复盘", "angle": "这一年我们学到了什么、坚持了什么"},
]

# Contextual lessons inserted on a real market event. Kept evergreen so they
# read well whenever the trigger fires.
INSERT_CRASH = {
    "title": "行情插播：大跌时，定投者该怎么想",
    "angle": (
        "本周有大盘资产明显下挫。讲清楚：已实现的下跌对长期定投者意味着什么、"
        "为什么按纪律加码而不是恐慌、越跌越买的边界在哪、以及为什么不该试图抄底逃顶"
    ),
}
INSERT_PANIC = {
    "title": "行情插播：恐慌指数飙升说明了什么",
    "angle": (
        "本周市场波动/恐慌明显升温。讲清楚 VIX 飙升的含义、它并不预测方向、"
        "以及历史上恐慌高点往往与情绪化决策相伴——对机械定投者反而是纪律的考验"
    ),
}

# Thresholds for "行情插播". Event detection prefers a *fresh* weekly move over a
# standing drawdown, so a perpetually depressed index does not hijack the course.
WEEKLY_DROP_TRIGGER = -0.08  # a tracked index fell >=8% week over week
VIX_LEVEL_TRIGGER = 28.0  # acute fear in absolute terms
VIX_JUMP_TRIGGER = 8.0  # VIX spiked >=8 points since last week


def _ok(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in snapshots if not s.get("error")]


def detect_event(
    snapshots: list[dict[str, Any]],
    macro: dict[str, Any],
    prev_prices: dict[str, float],
    prev_vix: float | None,
) -> dict[str, str] | None:
    """Return an insert lesson when a genuine market event is detected."""
    vix = macro.get("vix")
    if vix is not None:
        if vix >= VIX_LEVEL_TRIGGER:
            return INSERT_PANIC
        if prev_vix is not None and vix - prev_vix >= VIX_JUMP_TRIGGER:
            return INSERT_PANIC

    for snap in _ok(snapshots):
        if not snap.get("dca_eligible", True):
            continue
        previous = prev_prices.get(snap["symbol"])
        last = snap.get("last")
        if previous and last and previous > 0:
            weekly_return = last / previous - 1
            if weekly_return <= WEEKLY_DROP_TRIGGER:
                return INSERT_CRASH
    return None


def syllabus_topic(index: int) -> dict[str, str]:
    """Return the syllabus entry for a zero-based week index (wraps around)."""
    return SYLLABUS[index % len(SYLLABUS)]


def choose_lesson(
    progress: dict[str, Any],
    snapshots: list[dict[str, Any]],
    macro: dict[str, Any],
) -> dict[str, Any]:
    """Pick this week's lesson and whether the syllabus pointer should advance.

    Insert lessons (market events) do not advance the pointer, so the course
    resumes from the same place the following week.
    """
    next_index = int(progress.get("next_index", 0))
    event = detect_event(
        snapshots,
        macro,
        progress.get("last_prices") or {},
        progress.get("last_vix"),
    )
    if event is not None:
        return {
            "kind": "insert",
            "title": event["title"],
            "angle": event["angle"],
            "week_no": next_index,  # 0-based pointer not consumed
            "advance": False,
        }
    topic = syllabus_topic(next_index)
    return {
        "kind": "syllabus",
        "title": topic["title"],
        "angle": topic["angle"],
        "tie": topic.get("tie", ""),
        "week_no": (next_index % len(SYLLABUS)) + 1,
        "advance": True,
    }


def current_prices(snapshots: list[dict[str, Any]]) -> dict[str, float]:
    return {
        snap["symbol"]: float(snap["last"])
        for snap in _ok(snapshots)
        if snap.get("last") is not None
    }
