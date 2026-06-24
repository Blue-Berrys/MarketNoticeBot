import datetime
import json
import unittest
from unittest.mock import Mock, patch

import scripts.weekly_market_snapshot as snapshot_module
from scripts.weekly_market_snapshot import (
    ASSETS,
    build_asset_snapshot,
    build_feishu_cards,
    build_report,
    choose_dca_multiplier,
    collect_macro,
    parse_sina_jsonp,
    parse_fred_csv,
    parse_tencent_kline,
)


class WeeklyMarketSnapshotTests(unittest.TestCase):
    def test_feishu_cards_use_interactive_lark_markdown(self):
        cards = build_feishu_cards(
            "# 每周金融学习日报 · 2026-06-18\n\n"
            "## 一、本周结论\n\n**重点**：继续执行纪律。\n\n"
            "## 二、三分法组合\n\n- 股票\n- 债券\n- 商品"
        )

        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["msg_type"], "interactive")
        self.assertEqual(
            cards[0]["card"]["elements"][0]["text"]["tag"], "lark_md"
        )
        self.assertIn("一、本周结论", cards[0]["card"]["header"]["title"]["content"])
        self.assertIn("**重点**", cards[0]["card"]["elements"][0]["text"]["content"])

    def test_feishu_cards_convert_markdown_tables_to_readable_lines(self):
        cards = build_feishu_cards(
            "# 日报\n\n## 组合\n\n"
            "| 资产 | 倍数 | 依据 |\n"
            "|:--|:--:|:--|\n"
            "| 恒生科技 | 3x | 明显回撤 |\n"
            "| 黄金 | 2x | 回撤 |\n"
        )
        content = cards[0]["card"]["elements"][0]["text"]["content"]

        self.assertNotIn("|:--", content)
        self.assertNotIn("| 恒生科技 |", content)
        self.assertIn("**恒生科技**", content)
        self.assertIn("倍数：3x", content)

    def test_feishu_cards_convert_unsupported_subheadings_to_bold_text(self):
        cards = build_feishu_cards(
            "# 日报\n\n## 本周学习\n\n"
            "### 学习点一：当股价远超200日线时，要看什么？\n\n正文"
        )
        content = cards[0]["card"]["elements"][0]["text"]["content"]

        self.assertNotIn("###", content)
        self.assertIn(
            "**学习点一：当股价远超200日线时，要看什么？**", content
        )

    def test_feishu_cards_split_oversized_sections(self):
        cards = build_feishu_cards(
            "# 日报\n\n## 长章节\n\n" + "\n\n".join(["段落" * 120] * 8),
            max_chars=500,
        )

        self.assertGreater(len(cards), 1)
        for card in cards:
            content = card["card"]["elements"][0]["text"]["content"]
            self.assertLessEqual(len(content), 500)

    def test_send_feishu_submits_each_interactive_card(self):
        response = Mock()
        response.read.return_value = b'{"code":0,"msg":"success"}'
        with patch.object(
            snapshot_module.urllib.request, "urlopen", return_value=response
        ) as urlopen:
            results = snapshot_module.send_feishu(
                "# 日报\n\n## 第一章\n\n内容\n\n## 第二章\n\n内容",
                "https://example.invalid/hook",
                "secret",
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(urlopen.call_count, 2)
        for call in urlopen.call_args_list:
            request = call.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload["msg_type"], "interactive")
            self.assertEqual(
                payload["card"]["elements"][0]["text"]["tag"], "lark_md"
            )

    def test_assets_use_underlying_us_etfs_and_hk_index_not_cn_proxy_funds(self):
        self.assertEqual(ASSETS["QQQ"]["source_symbol"], "QQQ")
        self.assertEqual(ASSETS["SPY"]["source_symbol"], "SPY")
        self.assertEqual(ASSETS["GLD"]["source_symbol"], "GLD")
        self.assertEqual(ASSETS["USO"]["source_symbol"], "USO")
        self.assertEqual(ASSETS["HSI"]["source_symbol"], "hkHSI")
        self.assertEqual(ASSETS["HSTECH"]["source_symbol"], "hkHSTECH")
        self.assertEqual(ASSETS["STAR50"]["source_symbol"], "sh000688")
        self.assertEqual(ASSETS["SEMICONDUCTOR"]["provider"], "direct")
        self.assertEqual(ASSETS["SEMICONDUCTOR"]["source_symbol"], "931865.SS")
        self.assertFalse(ASSETS["MU"]["dca_eligible"])
        self.assertFalse(ASSETS["SNDK"]["dca_eligible"])
        self.assertFalse(
            any(
                value["source_symbol"].startswith(("159", "513"))
                for value in ASSETS.values()
            )
        )

    def test_parse_sina_jsonp_extracts_daily_rows(self):
        payload = '/*redirect*/\nvar x=([{"d":"2026-06-17","c":"100.0"},{"d":"2026-06-18","c":"90.0"}]);'

        rows = parse_sina_jsonp(payload)

        self.assertEqual(rows[-1], {"date": "2026-06-18", "close": 90.0})

    def test_parse_tencent_kline_extracts_daily_rows(self):
        payload = {
            "code": 0,
            "data": {
                "hkHSTECH": {
                    "day": [
                        ["2026-06-17", "100", "98", "101", "97", "1000"],
                        ["2026-06-18", "98", "95", "99", "94", "1100"],
                    ]
                }
            },
        }

        rows = parse_tencent_kline(json.dumps(payload), "hkHSTECH")

        self.assertEqual(rows[-1], {"date": "2026-06-18", "close": 95.0})

    def test_parse_fred_csv_skips_missing_values(self):
        payload = "DATE,DGS10\n2026-06-16,.\n2026-06-17,4.49\n"

        self.assertEqual(parse_fred_csv(payload), 4.49)

    def test_parse_fred_csv_accepts_observation_date_header(self):
        payload = (
            "observation_date,VIXCLS\n"
            "2026-06-16,16.41\n"
            "2026-06-17,18.44\n"
        )

        self.assertEqual(parse_fred_csv(payload), 18.44)

    def test_macro_failure_degrades_without_blocking_report(self):
        def failing_fetcher(series_id):
            if series_id == "DGS10":
                raise TimeoutError("FRED unavailable")
            return {"DGS2": 4.2, "VIXCLS": 18.4}[series_id]

        self.assertEqual(
            collect_macro(failing_fetcher),
            {"vix": 18.4, "yield_spread": None},
        )

    def test_fred_uses_keyless_csv_before_keyed_api(self):
        with patch.object(
            snapshot_module,
            "fetch_fred_latest",
            side_effect=AssertionError("keyed API should not be called"),
        ) as keyed_fetch, patch.object(
            snapshot_module,
            "fetch_fred_keyless",
            side_effect=lambda series_id: {
                "DGS10": 4.49,
                "DGS2": 4.20,
                "VIXCLS": 18.44,
            }[series_id],
        ):
            result = snapshot_module.fetch_macro("configured-key")

        keyed_fetch.assert_not_called()
        self.assertEqual(result["vix"], 18.44)
        self.assertAlmostEqual(result["yield_spread"], 0.29)

    def test_fred_keyless_failure_falls_back_to_keyed_api(self):
        with patch.object(
            snapshot_module,
            "fetch_fred_keyless",
            side_effect=RuntimeError("CSV endpoint timeout"),
        ), patch.object(
            snapshot_module,
            "fetch_fred_latest",
            side_effect=lambda series_id, api_key: {
                "DGS10": 4.49,
                "DGS2": 4.20,
                "VIXCLS": 18.44,
            }[series_id],
        ):
            result = snapshot_module.fetch_macro("configured-key")

        self.assertEqual(result["vix"], 18.44)
        self.assertAlmostEqual(result["yield_spread"], 0.29)

    def test_fred_csv_url_limits_history_window(self):
        from scripts.weekly_market_snapshot import build_fred_csv_url

        url = build_fred_csv_url("DGS10", today=datetime.date(2026, 6, 20))

        self.assertIn("id=DGS10", url)
        self.assertIn("cosd=2024-06-20", url)

    def test_dca_multiplier_requires_a_real_drawdown(self):
        self.assertEqual(choose_dca_multiplier(-0.10, -0.05), 1)
        self.assertEqual(choose_dca_multiplier(-0.22, -0.08), 2)
        self.assertEqual(choose_dca_multiplier(-0.38, -0.20), 3)

    def test_asset_snapshot_uses_52_week_high_and_200_day_average(self):
        closes = [100.0] * 200 + [80.0] * 52
        rows = [
            {"date": f"2026-{i // 28 + 1:02d}-{i % 28 + 1:02d}", "close": close}
            for i, close in enumerate(closes)
        ]

        snapshot = build_asset_snapshot("TEST", "测试", rows)

        self.assertAlmostEqual(snapshot["drawdown_52w"], -0.20)
        self.assertLess(snapshot["vs_sma200"], 0)
        self.assertEqual(snapshot["multiplier"], 2)

    def test_report_never_declares_sell_without_valuation_and_froth_confirmation(self):
        assets = [
            {
                "symbol": "QQQ",
                "name": "纳指100",
                "date": "2026-06-18",
                "last": 100.0,
                "drawdown_52w": -0.01,
                "vs_sma200": 0.30,
                "temperature": "偏热",
                "multiplier": 1,
            }
        ]

        report = build_report(assets, {"vix": 15.0, "yield_spread": 0.25})

        self.assertIn("减仓触发：否", report)
        self.assertIn("缺少“极端估值 + 狂热”双重确认", report)
        self.assertIn("倍数只作用于对应资产", report)

    def test_observation_only_stock_has_no_dca_multiplier(self):
        rows = [
            {"date": f"2025-01-{(i % 28) + 1:02d}", "close": 100 + i}
            for i in range(220)
        ]

        snapshot = build_asset_snapshot(
            "MU", "美光存储", rows, dca_eligible=False
        )
        report = build_report(
            [snapshot], {"vix": None, "yield_spread": None}
        )

        self.assertIsNone(snapshot["multiplier"])
        self.assertIn("观察项，不计算定投倍数", report)


if __name__ == "__main__":
    unittest.main()
