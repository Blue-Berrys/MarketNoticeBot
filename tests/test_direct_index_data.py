from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest

from tradingagents.dataflows import direct_index_data, stockstats_utils, y_finance
from tradingagents.dataflows.config import set_config


def _response(payload: dict) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


@pytest.mark.unit
def test_fetches_hang_seng_tech_history_from_tencent(monkeypatch):
    payload = {
        "data": {
            "hkHSTECH": {
                "day": [
                    ["2026-06-17", "5200.0", "5250.0", "5280.0", "5180.0", "1000"],
                    ["2026-06-18", "5260.0", "5300.0", "5320.0", "5240.0", "1200"],
                ]
            }
        }
    }
    monkeypatch.setattr(
        direct_index_data.requests, "get", lambda *args, **kwargs: _response(payload)
    )

    result = direct_index_data.fetch_direct_index_ohlcv(
        "HSTECH.HK", "2026-06-01", "2026-06-18"
    )

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.index.name == "Date"
    assert result.loc[pd.Timestamp("2026-06-18"), "Close"] == 5300.0


@pytest.mark.unit
def test_fetches_semiconductor_history_from_csindex(monkeypatch):
    payload = {
        "code": "200",
        "data": [
            {
                # The API prepends the requested start date using the next
                # session's OHLCV. It must not become a fake trading row.
                "tradeDate": "20260601",
                "open": 3100,
                "high": 3150,
                "low": 3080,
                "close": 3140,
                "tradingVol": 200,
            },
            {
                "tradeDate": "20260617",
                "open": 3100,
                "high": 3150,
                "low": 3080,
                "close": 3140,
                "tradingVol": 200,
            },
            {
                "tradeDate": "20260618",
                "open": 3140,
                "high": 3200,
                "low": 3120,
                "close": 3190,
                "tradingVol": 300,
            },
        ],
    }
    monkeypatch.setattr(
        direct_index_data.requests, "get", lambda *args, **kwargs: _response(payload)
    )

    result = direct_index_data.fetch_direct_index_ohlcv(
        "931865.SS", "2026-06-01", "2026-06-18"
    )

    assert len(result) == 2
    assert result.index.min() == pd.Timestamp("2026-06-17")
    assert result.iloc[-1]["Close"] == 3190


@pytest.mark.unit
def test_load_ohlcv_bypasses_yahoo_for_direct_indices(monkeypatch, tmp_path):
    dates = pd.bdate_range("2025-01-01", "2026-06-18")
    direct = pd.DataFrame(
        {
            "Open": range(len(dates)),
            "High": range(len(dates)),
            "Low": range(len(dates)),
            "Close": range(len(dates)),
            "Volume": [1000] * len(dates),
        },
        index=dates,
    )
    direct.index.name = "Date"
    fetch = Mock(return_value=direct)
    monkeypatch.setattr(stockstats_utils, "fetch_direct_index_ohlcv", fetch)
    yahoo = Mock(side_effect=AssertionError("Yahoo must not be called"))
    monkeypatch.setattr(stockstats_utils.yf, "download", yahoo)
    set_config({"data_cache_dir": str(tmp_path)})

    result = stockstats_utils.load_ohlcv("000688.SS", "2026-06-18")

    assert len(result) > 200
    assert result["Date"].max() == pd.Timestamp("2026-06-18")
    assert fetch.called
    yahoo.assert_not_called()


@pytest.mark.unit
def test_stock_data_tool_uses_direct_index_history(monkeypatch):
    dates = pd.bdate_range("2026-01-01", "2026-06-18")
    direct = pd.DataFrame(
        {
            "Open": range(len(dates)),
            "High": range(len(dates)),
            "Low": range(len(dates)),
            "Close": range(len(dates)),
            "Volume": [1000] * len(dates),
        },
        index=dates,
    )
    direct.index.name = "Date"
    monkeypatch.setattr(y_finance, "fetch_direct_index_ohlcv", lambda *args: direct)
    monkeypatch.setattr(
        y_finance.yf,
        "Ticker",
        Mock(side_effect=AssertionError("Yahoo must not be called")),
    )

    result = y_finance.get_YFin_data_online(
        "HSTECH.HK", "2026-01-01", "2026-06-18"
    )

    assert "# Total records: 121" in result
    assert "2026-06-18" in result
