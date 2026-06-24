import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.compile_weekly_learning_report import (
    build_synthesis_prompt,
    collect_report_material,
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


if __name__ == "__main__":
    unittest.main()
