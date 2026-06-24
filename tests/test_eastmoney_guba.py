from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import HTTPError

from tradingagents.dataflows.eastmoney_guba import (
    VERIFIED_BARS,
    fetch_eastmoney_guba_posts,
)


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode()


def test_fetches_verified_dedicated_bar_posts():
    payload = {
        "re": [
            {
                "stockbar_name": "科创50吧",
                "post_title": "对科创50上涨保持警觉",
                "post_content": "短期上涨较快，关注成交量。",
                "post_publish_time": "2026-06-20 16:46:49",
                "post_click_count": 120,
                "post_comment_count": 8,
            }
        ]
    }
    with patch(
        "tradingagents.dataflows.eastmoney_guba.urlopen",
        return_value=_Response(payload),
    ):
        result = fetch_eastmoney_guba_posts("000688.SS")

    assert "科创50吧" in result
    assert "120 reads" in result
    assert "8 comments" in result
    assert "对科创50上涨保持警觉" in result


def test_unmapped_symbol_does_not_fall_back_to_generic_bar():
    result = fetch_eastmoney_guba_posts("HSTECH.HK")

    assert "no verified dedicated Eastmoney bar mapping" in result
    assert "股市实战吧" not in result


def test_verified_bars_cover_gap_assets_with_wellformed_entries():
    # The HK index and the semiconductor index previously had no sentiment
    # source at all; they must now resolve to a dedicated bar.
    for symbol in ("^HSI", "931865.SS", "000688.SS"):
        assert symbol in VERIFIED_BARS
    for code, name in VERIFIED_BARS.values():
        assert code and name
        assert name.endswith("吧")
        assert name != "股市实战吧"  # never the generic fallback


def test_verified_bar_filters_out_foreign_posts_in_mixed_feed():
    # 板块/ETF feeds can interleave other bars; only the expected bar is kept.
    payload = {
        "re": [
            {
                "stockbar_name": "半导体吧",
                "post_title": "半导体板块今日走强",
                "post_content": "关注国产替代进度。",
                "post_publish_time": "2026-06-24 10:00:00",
                "post_click_count": 88,
                "post_comment_count": 5,
            },
            {
                "stockbar_name": "光伏设备吧",
                "post_title": "无关帖子",
                "post_content": "应被过滤。",
                "post_publish_time": "2026-06-24 10:01:00",
                "post_click_count": 10,
                "post_comment_count": 1,
            },
        ]
    }
    with patch(
        "tradingagents.dataflows.eastmoney_guba.urlopen",
        return_value=_Response(payload),
    ):
        result = fetch_eastmoney_guba_posts("931865.SS")

    assert "半导体板块今日走强" in result
    assert "无关帖子" not in result


def test_transport_error_degrades_without_raising():
    error = HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch(
        "tradingagents.dataflows.eastmoney_guba.urlopen", side_effect=error
    ):
        result = fetch_eastmoney_guba_posts("000688.SS")

    assert "eastmoney guba unavailable" in result
