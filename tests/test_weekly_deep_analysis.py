import tempfile
import unittest
from pathlib import Path

from scripts.run_weekly_deep_analysis import (
    ASSETS,
    REPORT_SECTIONS,
    build_config,
    render_report,
)


class WeeklyDeepAnalysisTests(unittest.TestCase):
    def test_asset_universe_uses_direct_underlyings(self):
        self.assertEqual(ASSETS["美国科技"]["ticker"], "QQQ")
        self.assertEqual(ASSETS["恒生科技"]["ticker"], "HSTECH.HK")
        self.assertEqual(ASSETS["中国科技"]["ticker"], "000688.SS")
        self.assertEqual(ASSETS["中国半导体"]["ticker"], "931865.SS")
        self.assertNotIn("XLK", {item["ticker"] for item in ASSETS.values()})
        self.assertFalse(ASSETS["美光存储"]["dca_eligible"])
        self.assertFalse(ASSETS["闪迪存储"]["dca_eligible"])

    def test_config_is_all_deepseek(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = build_config("QQQ", Path(tmp))
        self.assertEqual(config["llm_provider"], "deepseek")
        self.assertEqual(config["deep_think_llm"], "deepseek-v4-pro")
        self.assertEqual(config["quick_think_llm"], "deepseek-v4-flash")
        self.assertIsNone(config["backend_url"])
        self.assertEqual(config["output_language"], "Chinese")
        self.assertEqual(config["max_debate_rounds"], 1)
        self.assertEqual(config["max_risk_discuss_rounds"], 1)

    def test_render_report_persists_all_graph_sections(self):
        state = {section: f"{section} content" for section in REPORT_SECTIONS}
        text = render_report("QQQ", "美国科技", "2026-06-18", state, "HOLD")
        for section in REPORT_SECTIONS:
            self.assertIn(f"## {section}", text)
            self.assertIn(f"{section} content", text)
        self.assertIn("短期模型原始结论（仅作学习材料）", text)


if __name__ == "__main__":
    unittest.main()
