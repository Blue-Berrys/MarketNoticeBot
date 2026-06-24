"""Direct historical OHLCV sources for indices Yahoo does not serve reliably.

These mappings deliberately point to the underlying indices, not mainland-listed
ETF wrappers whose market prices can include subscription/redemption premiums.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import requests

from .symbol_utils import NoMarketDataError


@dataclass(frozen=True)
class DirectIndexSpec:
    provider: str
    provider_symbol: str


DIRECT_INDEX_SPECS: dict[str, DirectIndexSpec] = {
    "HSTECH.HK": DirectIndexSpec("tencent", "hkHSTECH"),
    "000688.SS": DirectIndexSpec("tencent", "sh000688"),
    "931865.SS": DirectIndexSpec("csindex", "931865"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    ),
}


def get_direct_index_spec(symbol: str) -> DirectIndexSpec | None:
    return DIRECT_INDEX_SPECS.get(symbol.upper())


def _finalize_ohlcv(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if data.empty:
        raise NoMarketDataError(symbol, symbol, "direct index source returned no rows")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").set_index("Date")
    for column in ("Open", "High", "Low", "Close", "Volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["Close"])
    if data.empty:
        raise NoMarketDataError(
            symbol, symbol, "direct index source contained no valid OHLCV rows"
        )
    data.index.name = "Date"
    return data[["Open", "High", "Low", "Close", "Volume"]]


def _fetch_tencent(
    symbol: str, provider_symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{provider_symbol},day,{start_date},{end_date},1600,qfq",
    }
    response = requests.get(url, params=params, headers=_HEADERS, timeout=30)
    response.raise_for_status()
    node = (response.json().get("data") or {}).get(provider_symbol) or {}
    rows = node.get("qfqday") or node.get("day") or []
    parsed = [
        {
            "Date": row[0],
            "Open": row[1],
            "Close": row[2],
            "High": row[3],
            "Low": row[4],
            "Volume": row[5],
        }
        for row in rows
        if len(row) >= 6
    ]
    return _finalize_ohlcv(pd.DataFrame(parsed), symbol)


def _fetch_csindex(
    symbol: str, provider_symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    url = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
    params = {
        "indexCode": provider_symbol,
        "startDate": start_date.replace("-", ""),
        "endDate": end_date.replace("-", ""),
    }
    response = requests.get(
        url,
        params=params,
        headers={**_HEADERS, "Referer": "https://www.csindex.com.cn/"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("code")) != "200":
        raise NoMarketDataError(
            symbol, symbol, f"CSIndex API error: {payload.get('msg', 'unknown')}"
        )

    # CSIndex may prepend a synthetic row whose tradeDate is the requested
    # start date formatted with dashes. Real sessions use compact YYYYMMDD.
    parsed = []
    for row in payload.get("data") or []:
        trade_date = str(row.get("tradeDate", ""))
        if len(trade_date) != 8 or not trade_date.isdigit():
            continue
        parsed.append(
            {
                "Date": datetime.strptime(trade_date, "%Y%m%d"),
                "Open": row.get("open"),
                "High": row.get("high"),
                "Low": row.get("low"),
                "Close": row.get("close"),
                "Volume": row.get("tradingVol"),
            }
        )
    data = pd.DataFrame(parsed)
    if len(data) >= 2:
        requested_start = pd.to_datetime(start_date)
        first_values = data.iloc[0][["Open", "High", "Low", "Close", "Volume"]]
        second_values = data.iloc[1][["Open", "High", "Low", "Close", "Volume"]]
        if data.iloc[0]["Date"] == requested_start and first_values.equals(
            second_values
        ):
            data = data.iloc[1:].copy()
    return _finalize_ohlcv(data, symbol)


def fetch_direct_index_ohlcv(
    symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Return direct-index OHLCV for a supported symbol."""
    spec = get_direct_index_spec(symbol)
    if spec is None:
        raise ValueError(f"No direct index source configured for {symbol}")
    if spec.provider == "tencent":
        return _fetch_tencent(symbol, spec.provider_symbol, start_date, end_date)
    if spec.provider == "csindex":
        return _fetch_csindex(symbol, spec.provider_symbol, start_date, end_date)
    raise ValueError(f"Unsupported direct index provider: {spec.provider}")
