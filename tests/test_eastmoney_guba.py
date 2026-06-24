from __future__ import annotations

import json
from urllib.error import HTTPError
from unittest.mock import patch

from tradingagents.dataflows.eastmoney_guba import fetch_eastmoney_guba_posts


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


def test_transport_error_degrades_without_raising():
    error = HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch(
        "tradingagents.dataflows.eastmoney_guba.urlopen", side_effect=error
    ):
        result = fetch_eastmoney_guba_posts("000688.SS")

    assert "eastmoney guba unavailable" in result
