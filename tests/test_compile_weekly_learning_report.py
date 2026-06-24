import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.compile_weekly_learning_report import (
    build_sentiment_section,
    build_synthesis_prompt,
    collect_report_material,
    extract_sentiment,
)


class CompileWeeklyLearningReportTests(unittest.TestCase):
    def test_cli_entrypoint_can_load_sibling_snapshot_module(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "compile_weekly_learning_report.py"),
                "--help",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prompt_enforces_long_horizon_sections(self):
        prompt = build_synthesis_prompt(
            "snapshot",
            {"美国科技": "report"},
            "2026-06-18",
        )
        for heading in (
            "三分法组合",
            "美国科技与大盘",
            "恒生市场",
            "中国科技与半导体",
            "黄金与原油",
            "存储产业",
            "本周学习",
        ):
            self.assertIn(heading, prompt)
        self.assertIn("不得把 BUY/HOLD/SELL", prompt)
        self.assertIn("MU、SNDK", prompt)
        self.assertIn("指标是什么", prompt)
        self.assertIn("通常影响股票、债券、黄金或商品", prompt)
        self.assertIn("数据来源类型", prompt)
        self.assertIn("概率数据不得写成已经发生的事实", prompt)

    def test_material_collection_reads_successful_reports_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "qqq.md"
            report.write_text("QQQ report", encoding="utf-8")
            summary = [
                {"label": "美国科技", "status": "ok", "report": str(report)},
                {"label": "黄金", "status": "failed", "error": "timeout"},
            ]

            materials = collect_report_material(summary)

        self.assertEqual(materials, {"美国科技": "QQQ report"})


    def test_extract_sentiment_parses_structured_header(self):
        report = (
            "# QQQ — 2026-06-18\n\n"
            "## market_report\n\nsome text\n\n"
            "## sentiment_report\n\n"
            "**Overall Sentiment:** **Mixed** (Score: 5.2/10)\n"
            "**Confidence:** Medium\n\n"
            "## news_report\n\nmore\n"
        )
        self.assertEqual(
            extract_sentiment(report),
            "Mixed（评分 5.2/10，可信度 Medium）",
        )

    def test_extract_sentiment_returns_none_without_header(self):
        self.assertIsNone(extract_sentiment("## sentiment_report\n\n(empty)\n"))

    def test_sentiment_section_lists_only_ok_reports_with_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qqq = root / "qqq.md"
            qqq.write_text(
                "## sentiment_report\n**Overall Sentiment:** Bullish "
                "(Score: 7.0/10)\n**Confidence:** High\n",
                encoding="utf-8",
            )
            gld = root / "gld.md"
            gld.write_text("## sentiment_report\n(no header)\n", encoding="utf-8")
            summary = [
                {"label": "美国科技", "ticker": "QQQ", "status": "ok",
                 "report": str(qqq)},
                {"label": "黄金", "ticker": "GLD", "status": "ok",
                 "report": str(gld)},
                {"label": "原油", "ticker": "USO", "status": "failed",
                 "error": "timeout"},
            ]

            section = build_sentiment_section(summary)

        self.assertIn("## 十一、情绪面速览（多智能体）", section)
        self.assertIn("美国科技（QQQ）", section)
        self.assertIn("Bullish（评分 7.0/10，可信度 High）", section)
        self.assertNotIn("黄金（GLD）", section)
        self.assertNotIn("原油", section)

    def test_sentiment_section_empty_when_no_material(self):
        self.assertEqual(build_sentiment_section([]), "")


if __name__ == "__main__":
    unittest.main()
