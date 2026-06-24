"""Weekly long-horizon market snapshot and Feishu delivery.

Price sources deliberately use underlying US-listed ETFs, direct market
indexes, and observation-only US stocks. Mainland-listed QDII proxy funds are
excluded because their prices can contain subscription-driven premiums.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ASSETS = {
    "QQQ": {
        "name": "纳指100",
        "provider": "sina",
        "source_symbol": "QQQ",
        "dca_eligible": True,
    },
    "SPY": {
        "name": "标普500",
        "provider": "sina",
        "source_symbol": "SPY",
        "dca_eligible": True,
    },
    "HSI": {
        "name": "恒生指数",
        "provider": "tencent",
        "source_symbol": "hkHSI",
        "dca_eligible": True,
    },
    "HSTECH": {
        "name": "恒生科技",
        "provider": "tencent",
        "source_symbol": "hkHSTECH",
        "dca_eligible": True,
    },
    "GLD": {
        "name": "黄金",
        "provider": "sina",
        "source_symbol": "GLD",
        "dca_eligible": True,
    },
    "USO": {
        "name": "原油",
        "provider": "sina",
        "source_symbol": "USO",
        "dca_eligible": True,
    },
    "STAR50": {
        "name": "科创50",
        "provider": "tencent",
        "source_symbol": "sh000688",
        "dca_eligible": True,
    },
    "SEMICONDUCTOR": {
        "name": "中国半导体指数",
        "provider": "direct",
        "source_symbol": "931865.SS",
        "dca_eligible": True,
    },
    "MU": {
        "name": "美光存储",
        "provider": "sina",
        "source_symbol": "MU",
        "dca_eligible": False,
    },
    "SNDK": {
        "name": "闪迪存储",
        "provider": "sina",
        "source_symbol": "SNDK",
        "dca_eligible": False,
    },
}

SINA_URL = (
    "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
    "var%20snapshot=/US_MinKService.getDailyK"
)
TENCENT_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
USER_AGENT = "Mozilla/5.0 weekly-market-snapshot/1.0"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


def _get_text(url: str, timeout: int = 20, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://finance.sina.com.cn/",
                },
            )
            return urllib.request.urlopen(request, timeout=timeout).read().decode(
                "utf-8", "replace"
            )
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"request failed after {attempts} attempts: {url}") from last_error


def parse_sina_jsonp(payload: str) -> list[dict]:
    match = re.search(r"=\s*\((\[.*\])\)\s*;?\s*$", payload, re.DOTALL)
    if not match:
        raise ValueError("Sina response did not contain the expected JSONP array")
    raw_rows = json.loads(match.group(1))
    return [
        {"date": row["d"], "close": float(row["c"])}
        for row in raw_rows
        if row.get("d") and row.get("c") not in (None, "")
    ]


def parse_tencent_kline(payload: str, source_symbol: str) -> list[dict]:
    document = json.loads(payload)
    block = (document.get("data") or {}).get(source_symbol) or {}
    raw_rows = block.get("qfqday") or block.get("day") or []
    return [
        {"date": row[0], "close": float(row[2])}
        for row in raw_rows
        if len(row) >= 3
    ]


def parse_yahoo_chart(payload: str) -> list[dict]:
    document = json.loads(payload)
    result = ((document.get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    rows = []
    for timestamp, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(
                    timestamp, timezone.utc
                ).date().isoformat(),
                "close": float(close),
            }
        )
    return rows


def fetch_asset_rows(asset: dict) -> list[dict]:
    if asset["provider"] == "sina":
        query = urllib.parse.urlencode(
            {"symbol": asset["source_symbol"], "___qn": "3"}
        )
        return parse_sina_jsonp(_get_text(f"{SINA_URL}?{query}"))
    if asset["provider"] == "tencent":
        query = urllib.parse.urlencode(
            {"param": f"{asset['source_symbol']},day,,,320,qfq"}
        )
        return parse_tencent_kline(
            _get_text(f"{TENCENT_URL}?{query}"), asset["source_symbol"]
        )
    if asset["provider"] == "yahoo":
        query = urllib.parse.urlencode(
            {"range": "2y", "interval": "1d", "events": "history"}
        )
        symbol = urllib.parse.quote(asset["source_symbol"], safe="")
        return parse_yahoo_chart(
            _get_text(f"{YAHOO_CHART_URL}/{symbol}?{query}")
        )
    if asset["provider"] == "direct":
        from tradingagents.dataflows.direct_index_data import (
            fetch_direct_index_ohlcv,
        )

        end_date = date.today().isoformat()
        start_date = date(date.today().year - 5, 1, 1).isoformat()
        data = fetch_direct_index_ohlcv(
            asset["source_symbol"], start_date, end_date
        )
        return [
            {"date": index.date().isoformat(), "close": float(row["Close"])}
            for index, row in data.iterrows()
        ]
    raise ValueError(f"unsupported provider: {asset['provider']}")


def choose_dca_multiplier(drawdown_52w: float, vs_sma200: float) -> int:
    """Return a capped multiplier based on an already-realized decline.

    This is intentionally reactive rather than predictive. A multiplier above
    1 requires both a material drawdown and price below its 200-day average.
    """

    if drawdown_52w <= -0.30 and vs_sma200 <= -0.15:
        return 3
    if drawdown_52w <= -0.15 and vs_sma200 < 0:
        return 2
    return 1


def build_asset_snapshot(
    symbol: str,
    name: str,
    rows: list[dict],
    dca_eligible: bool = True,
) -> dict:
    if len(rows) < 200:
        raise ValueError(f"{symbol} has only {len(rows)} daily rows; need >= 200")
    closes = [float(row["close"]) for row in rows]
    last = closes[-1]
    high_52w = max(closes[-252:])
    sma200 = sum(closes[-200:]) / 200
    drawdown = last / high_52w - 1
    vs_sma200 = last / sma200 - 1
    if drawdown <= -0.20:
        temperature = "明显回撤"
    elif drawdown <= -0.10:
        temperature = "回调区"
    elif vs_sma200 >= 0.20:
        temperature = "偏热"
    else:
        temperature = "中性"
    return {
        "symbol": symbol,
        "name": name,
        "date": rows[-1]["date"],
        "last": last,
        "drawdown_52w": drawdown,
        "vs_sma200": vs_sma200,
        "temperature": temperature,
        "multiplier": (
            choose_dca_multiplier(drawdown, vs_sma200)
            if dca_eligible
            else None
        ),
    }


def fetch_fred_latest(series_id: str, api_key: str) -> float | None:
    query = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10,
        }
    )
    document = json.loads(_get_text(f"{FRED_URL}?{query}"))
    for observation in document.get("observations", []):
        value = observation.get("value")
        if value not in (None, ".", ""):
            return float(value)
    return None


def parse_fred_csv(payload: str) -> float | None:
    rows = list(csv.DictReader(io.StringIO(payload)))
    if not rows:
        return None
    date_keys = {"DATE", "observation_date"}
    value_key = next((key for key in rows[0] if key not in date_keys), None)
    if not value_key:
        return None
    for row in reversed(rows):
        value = row.get(value_key)
        if value not in (None, ".", ""):
            return float(value)
    return None


def build_fred_csv_url(series_id: str, today: date | None = None) -> str:
    current = today or date.today()
    start = current.replace(year=current.year - 2).isoformat()
    query = urllib.parse.urlencode({"id": series_id, "cosd": start})
    return f"{FRED_CSV_URL}?{query}"


def fetch_fred_keyless(series_id: str) -> float | None:
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", "15", build_fred_csv_url(series_id)],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return parse_fred_csv(result.stdout)


def collect_macro(fetcher) -> dict:
    values = {}
    for series_id in ("DGS10", "DGS2", "VIXCLS"):
        try:
            values[series_id] = fetcher(series_id)
        except Exception:
            values[series_id] = None
    ten_year = values["DGS10"]
    two_year = values["DGS2"]
    return {
        "vix": values["VIXCLS"],
        "yield_spread": (
            ten_year - two_year
            if ten_year is not None and two_year is not None
            else None
        ),
    }


def fetch_macro(api_key: str | None) -> dict:
    def fetcher(series_id: str) -> float | None:
        try:
            return fetch_fred_keyless(series_id)
        except Exception:
            if api_key:
                return fetch_fred_latest(series_id, api_key)
            raise

    return collect_macro(fetcher)


def build_report(assets: list[dict], macro: dict, valuation: dict | None = None) -> str:
    available = [asset for asset in assets if not asset.get("error")]
    report_date = max(
        (asset["date"] for asset in available),
        default=date.today().isoformat(),
    )
    lines = [f"📊 每周长期定投快照 · {report_date}", ""]
    for asset in assets:
        if asset.get("error"):
            lines.append(
                f"{asset['name']} {asset['symbol']}：数据暂缺｜"
                f"{asset['error']}"
            )
            continue
        suffix = (
            f"本周 {asset['multiplier']}x"
            if asset["multiplier"] is not None
            else "观察项，不计算定投倍数"
        )
        lines.append(
            f"{asset['name']} {asset['symbol']}：距52周高点 "
            f"{asset['drawdown_52w']:+.1%}｜较200日线 "
            f"{asset['vs_sma200']:+.1%}｜{asset['temperature']}｜{suffix}"
        )
    vix = macro.get("vix")
    spread = macro.get("yield_spread")
    lines.extend(["", "🌍 宏观慢变量"])
    lines.append(f"VIX：{vix:.1f}" if vix is not None else "VIX：数据暂缺")
    lines.append(
        f"美债10Y-2Y利差：{spread:+.2f}%"
        if spread is not None
        else "美债10Y-2Y利差：数据暂缺"
    )

    if valuation:
        lines.extend(["", "🌡️ 美股估值（标普500 · Shiller CAPE）"])
        lines.append(
            f"CAPE：{valuation['cape']:.1f}｜近10年分位 "
            f"{valuation['cape_pct_10y']:.0f}%｜全历史分位 "
            f"{valuation['cape_pct_all']:.0f}%｜{valuation['temperature']}"
        )
        if valuation.get("pe_ttm") is not None:
            lines.append(
                f"市盈率TTM：{valuation['pe_ttm']:.1f}｜近10年分位 "
                f"{valuation['pe_pct_10y']:.0f}%"
            )

    multipliers = [
        asset["multiplier"]
        for asset in available
        if asset["multiplier"] is not None
    ]
    maximum = max(multipliers, default=1)

    if valuation:
        sell_line = (
            "🚦 减仓触发：否（机械规则不自动减仓）。美股 Shiller CAPE 近10年分位 "
            f"{valuation['cape_pct_10y']:.0f}%（{valuation['temperature']}）——"
            "即使估值偏高，仍需叠加“狂热”信号才构成“极端估值 + 狂热”双重确认，"
            "单一高估值不触发减仓。"
        )
        gauge_line = (
            "📚 口径：美股估值用标普500 Shiller CAPE（multpl，含历史分位）；"
            "纳指/港股/中国指数暂无可靠免费历史PE源，仍以价格回撤为温度代理。"
            "价格用美国上市 ETF 与官方指数，不使用可能带溢价的境内场内基金。"
        )
    else:
        sell_line = (
            "🚦 减仓触发：否。本周估值分位数据暂缺，"
            "缺少“极端估值 + 狂热”双重确认；价格偏热本身不构成卖出条件。"
        )
        gauge_line = (
            "📚 口径：使用美国上市 QQQ/SPY/GLD/USO、恒生/恒生科技"
            "及中国科技/半导体直接指数；MU/SNDK仅作产业观察，"
            "不使用可能带溢价的境内场内代理基金。"
        )

    lines.extend(
        [
            "",
            f"💰 本周规则：最高加码档 {maximum}x。倍数只作用于对应资产，"
            "不是把整笔 ¥500 全部放大；仍按股债商框架执行，并设置每周总额上限。",
            sell_line,
            gauge_line,
            "仅作长期学习与机械定投参考，不构成投资建议。",
        ]
    )
    return "\n".join(lines)


def fetch_valuation() -> dict | None:
    """Best-effort S&P 500 valuation percentile; never raises."""
    try:
        from tradingagents.dataflows.valuation import sp500_valuation

        return sp500_valuation()
    except Exception:
        return None


def load_env_file(path: str | os.PathLike) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells)


def markdown_tables_to_lines(text: str) -> str:
    """Convert Markdown tables into lark_md-compatible bullet blocks."""
    lines = text.splitlines()
    converted: list[str] = []
    index = 0
    while index < len(lines):
        subheading = re.fullmatch(r"#{3,6}\s+(.+)", lines[index].strip())
        if subheading:
            converted.append(f"**{subheading.group(1).strip()}**")
            index += 1
            continue
        if (
            index + 1 < len(lines)
            and "|" in lines[index]
            and _is_table_separator(lines[index + 1])
        ):
            headers = _table_cells(lines[index])
            index += 2
            while index < len(lines) and "|" in lines[index]:
                values = _table_cells(lines[index])
                if len(values) != len(headers):
                    break
                details = "｜".join(
                    f"{header}：{value}"
                    for header, value in zip(headers[1:], values[1:], strict=False)
                )
                converted.append(f"- **{values[0]}**")
                if details:
                    converted.append(f"  {details}")
                index += 1
            converted.append("")
            continue
        converted.append(lines[index])
        index += 1
    return "\n".join(converted).strip()


def _split_markdown_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.strip().splitlines()
    document_title = "每周金融学习日报"
    if lines and lines[0].startswith("# "):
        document_title = lines.pop(0)[2:].strip()

    sections: list[tuple[str, str]] = []
    current_title = document_title
    current_lines: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if any(part.strip() for part in current_lines):
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if any(part.strip() for part in current_lines):
        sections.append((current_title, "\n".join(current_lines).strip()))
    return document_title, sections or [(document_title, text.strip())]


def _split_card_content(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n{2,}", text.strip()):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [""]


def build_feishu_cards(text: str, max_chars: int = 3500) -> list[dict]:
    """Build sectioned Feishu interactive cards using lark_md content."""
    document_title, sections = _split_markdown_sections(text)
    cards: list[dict] = []
    for section_title, section_body in sections:
        body = markdown_tables_to_lines(section_body)
        chunks = _split_card_content(body, max_chars)
        for position, chunk in enumerate(chunks, start=1):
            suffix = f"（{position}/{len(chunks)}）" if len(chunks) > 1 else ""
            title = section_title
            if section_title != document_title:
                title = f"{document_title} · {section_title}"
            cards.append(
                {
                    "msg_type": "interactive",
                    "card": {
                        "config": {"wide_screen_mode": True},
                        "header": {
                            "template": "blue",
                            "title": {
                                "tag": "plain_text",
                                "content": f"{title}{suffix}"[:120],
                            },
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {"tag": "lark_md", "content": chunk},
                            }
                        ],
                    },
                }
            )
    return cards


def send_feishu(text: str, webhook: str, secret: str) -> list[dict]:
    responses = []
    for card in build_feishu_cards(text):
        timestamp = str(int(time.time()))
        sign = base64.b64encode(
            hmac.new(
                f"{timestamp}\n{secret}".encode(),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode()
        body = {"timestamp": timestamp, "sign": sign, **card}
        request = urllib.request.Request(
            webhook,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = json.loads(
            urllib.request.urlopen(request, timeout=20).read().decode()
        )
        if response.get("code", response.get("StatusCode")) != 0:
            raise RuntimeError(f"Feishu delivery failed: {response}")
        responses.append(response)
    return responses


def generate_report(fred_api_key: str | None = None) -> str:
    snapshots = []
    for symbol, asset in ASSETS.items():
        try:
            snapshots.append(
                build_asset_snapshot(
                    symbol,
                    asset["name"],
                    fetch_asset_rows(asset),
                    dca_eligible=asset["dca_eligible"],
                )
            )
        except Exception as exc:
            snapshots.append(
                {
                    "symbol": symbol,
                    "name": asset["name"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return build_report(snapshots, fetch_macro(fred_api_key), fetch_valuation())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="~/weekly-snapshot/feishu.env")
    parser.add_argument("--print-only", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    config = load_env_file(config_path) if config_path.exists() else {}
    report = generate_report(config.get("FRED_API_KEY") or os.getenv("FRED_API_KEY"))
    if args.output:
        Path(args.output).expanduser().write_text(report + "\n", encoding="utf-8")
    print(report)
    if not args.print_only:
        send_feishu(report, config["FEISHU_WEBHOOK"], config["FEISHU_SECRET"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
