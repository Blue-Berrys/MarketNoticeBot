"""S&P 500 valuation percentile (Shiller CAPE and trailing P/E) from multpl.com.

multpl publishes the full monthly history with no authentication, which makes it
the most robust free source for a long-horizon US-equity valuation read — the
Shiller CAPE is the canonical metric for "are stocks expensive versus history".

No reliable free *historical*-PE source was found for the Nasdaq-100, Hong Kong,
or CSI indices (danjuan/xueqiu are login-walled; CSIndex exposes no public PE
history endpoint). Valuation percentile therefore covers the S&P 500 only; other
instruments keep their price/drawdown read. Everything degrades to ``None`` on
any transport or parse failure so the weekly snapshot never breaks.
"""

from __future__ import annotations

import bisect
import json
import re
import urllib.request

_MULTPL = "https://www.multpl.com/{slug}/table/by-month"
_UA = "Mozilla/5.0 (X11; Linux x86_64) weekly-market-snapshot/1.0"
# Rows look like: <td>Jun 1, 2026</td><td>\n&#x2002;\n 41.32 \n</td>
_ROW = re.compile(
    r">\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*</td>\s*<td[^>]*>(.*?)</td>",
    re.DOTALL,
)
_NUM = re.compile(r"-?\d+\.?\d*")
_MONTHS_10Y = 120


def _fetch(slug: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        _MULTPL.format(slug=slug), headers={"User-Agent": _UA}
    )
    return urllib.request.urlopen(request, timeout=timeout).read().decode(
        "utf-8", "replace"
    )


def parse_multpl_table(html: str) -> list[tuple[str, float]]:
    """Parse a multpl ``by-month`` table into (date, value), latest first."""
    rows: list[tuple[str, float]] = []
    for label, cell in _ROW.findall(html):
        # Strip HTML entities first: the value cell is padded with an en-space
        # (``&#x2002;``) whose digits would otherwise be matched as "2002".
        cleaned = re.sub(r"&#?\w+;", " ", cell)
        match = _NUM.search(cleaned)
        if match:
            rows.append((label.strip(), float(match.group())))
    return rows


def percentile_rank(values: list[float], current: float) -> float:
    """Share of history at or below ``current`` (higher = more expensive)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return bisect.bisect_right(ordered, current) / len(ordered) * 100


def valuation_temperature(percentile_10y: float) -> str:
    if percentile_10y >= 90:
        return "极高"
    if percentile_10y >= 75:
        return "偏高"
    if percentile_10y <= 25:
        return "偏低"
    return "中性"


def sp500_valuation(timeout: int = 20) -> dict | None:
    """Return current S&P 500 Shiller CAPE / PE with historical percentiles."""
    try:
        cape_rows = parse_multpl_table(_fetch("shiller-pe", timeout))
    except Exception:
        return None
    if not cape_rows:
        return None

    cape_values = [value for _, value in cape_rows]
    current_cape = cape_values[0]
    result = {
        "asof": cape_rows[0][0],
        "cape": current_cape,
        "cape_pct_all": percentile_rank(cape_values, current_cape),
        "cape_pct_10y": percentile_rank(cape_values[:_MONTHS_10Y], current_cape),
    }
    result["temperature"] = valuation_temperature(result["cape_pct_10y"])

    try:
        pe_rows = parse_multpl_table(_fetch("s-p-500-pe-ratio", timeout))
    except Exception:
        pe_rows = []
    if pe_rows:
        pe_values = [value for _, value in pe_rows]
        result["pe_ttm"] = pe_values[0]
        result["pe_pct_10y"] = percentile_rank(pe_values[:_MONTHS_10Y], pe_values[0])
    return result


# --- Per-index PE percentile (韭圈儿/funddb) --------------------------------
# funddb exposes a current PE plus a precomputed historical percentile for a
# broad list of indices, including overseas ones that danjuan/xueqiu wall off.
# It needs no login (unlike danjuan). Maps snapshot symbols -> funddb gu_code;
# 中证全指半导体 (h30184) is the valuation proxy for the 931865 exposure.
_FUNDDB_URL = "https://api.jiucaishuo.com/v2/guzhi/showcategory"
INDEX_FUNDDB_CODES: dict[str, str] = {
    "QQQ": "NDX.GI",
    "SPY": "SPX.GI",
    "HSI": "HSI.HI",
    "HSTECH": "HSTECH.HI",
    "STAR50": "000688.SH",
    "SEMICONDUCTOR": "h30184.CSI",
}


def fetch_funddb_index_valuations(timeout: int = 15) -> dict[str, dict]:
    """Return {snapshot_symbol: {name, pe, pe_pct}} from funddb; {} on failure."""
    try:
        request = urllib.request.Request(
            _FUNDDB_URL,
            data=b"{}",
            headers={"Content-Type": "application/json", "User-Agent": _UA},
        )
        payload = json.loads(urllib.request.urlopen(request, timeout=timeout).read())
    except Exception:
        return {}

    rows = (((payload or {}).get("data") or {}).get("right_list")) or []
    by_code = {row.get("gu_code"): row for row in rows if isinstance(row, dict)}

    out: dict[str, dict] = {}
    for symbol, code in INDEX_FUNDDB_CODES.items():
        row = by_code.get(code)
        if not row:
            continue
        try:
            out[symbol] = {
                "name": row.get("gu_name"),
                "pe": float(row["gu_pe"]),
                "pe_pct": float(row["gu_pe_current_perent"]),
            }
        except (TypeError, ValueError, KeyError):
            continue
    return out
