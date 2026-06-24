from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.learning_syllabus import (
    INSERT_CRASH,
    INSERT_PANIC,
    SYLLABUS,
    choose_lesson,
    current_prices,
    detect_event,
    syllabus_topic,
)
from scripts.weekly_learning_letter import build_prompt, save_progress


def _snap(symbol, last, dca=True):
    return {"symbol": symbol, "name": symbol, "last": last, "dca_eligible": dca}


class SyllabusTests(unittest.TestCase):
    def test_syllabus_is_long_and_wellformed(self):
        self.assertGreaterEqual(len(SYLLABUS), 50)
        for entry in SYLLABUS:
            self.assertTrue(entry.get("title"))
            self.assertTrue(entry.get("angle"))

    def test_syllabus_topic_wraps_around(self):
        self.assertEqual(syllabus_topic(0), SYLLABUS[0])
        self.assertEqual(syllabus_topic(len(SYLLABUS)), SYLLABUS[0])

    def test_no_event_returns_syllabus_topic_and_advances(self):
        lesson = choose_lesson(
            {"next_index": 2, "last_prices": {}, "last_vix": None},
            [_snap("QQQ", 100.0)],
            {"vix": 16.0},
        )
        self.assertEqual(lesson["kind"], "syllabus")
        self.assertEqual(lesson["title"], SYLLABUS[2]["title"])
        self.assertEqual(lesson["week_no"], 3)
        self.assertTrue(lesson["advance"])

    def test_weekly_drop_triggers_crash_insert_without_advancing(self):
        lesson = choose_lesson(
            {"next_index": 5, "last_prices": {"HSTECH": 100.0}, "last_vix": 15.0},
            [_snap("HSTECH", 90.0)],  # -10% week over week
            {"vix": 16.0},
        )
        self.assertEqual(lesson["kind"], "insert")
        self.assertEqual(lesson["title"], INSERT_CRASH["title"])
        self.assertFalse(lesson["advance"])

    def test_standing_drawdown_without_prior_price_does_not_trigger(self):
        # No prev price -> cannot infer a fresh weekly move -> stay on syllabus.
        lesson = choose_lesson(
            {"next_index": 0, "last_prices": {}, "last_vix": None},
            [_snap("HSTECH", 50.0)],
            {"vix": 16.0},
        )
        self.assertEqual(lesson["kind"], "syllabus")

    def test_vix_level_and_jump_trigger_panic(self):
        self.assertEqual(detect_event([], {"vix": 30.0}, {}, None), INSERT_PANIC)
        self.assertEqual(detect_event([], {"vix": 26.0}, {}, 15.0), INSERT_PANIC)
        self.assertIsNone(detect_event([], {"vix": 18.0}, {}, 16.0))

    def test_current_prices_skips_errored_assets(self):
        snaps = [_snap("QQQ", 100.0), {"symbol": "X", "error": "boom"}]
        self.assertEqual(current_prices(snaps), {"QQQ": 100.0})


class PromptTests(unittest.TestCase):
    def test_prompt_contains_all_sections_and_guardrails(self):
        lesson = {
            "kind": "syllabus",
            "title": "市盈率 PE：贵还是便宜",
            "angle": "估值的第一把尺",
            "tie": "QQQ",
            "week_no": 3,
            "advance": True,
        }
        prompt = build_prompt(lesson, "QQQ 距52周高点 -0.7%", "2026-06-27")
        for heading in (
            "一、本周核心概念",
            "二、用本周真实数据看",
            "三、术语卡",
            "四、常见误区",
            "五、历史小课堂",
            "六、思考题",
            "写给长期定投者",
        ):
            self.assertIn(heading, prompt)
        self.assertIn("第3课", prompt)
        self.assertIn("QQQ 距52周高点 -0.7%", prompt)
        self.assertIn("不得给出任何 BUY/HOLD/SELL", prompt)

    def test_insert_prompt_omits_lesson_number(self):
        lesson = {
            "kind": "insert",
            "title": INSERT_CRASH["title"],
            "angle": INSERT_CRASH["angle"],
            "week_no": 4,
            "advance": False,
        }
        prompt = build_prompt(lesson, "snapshot", "2026-06-27")
        self.assertIn("行情插播", prompt)
        self.assertNotIn("课：", prompt)


class ProgressTests(unittest.TestCase):
    def test_syllabus_lesson_advances_and_records_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            progress = {"next_index": 0, "last_prices": {}, "last_vix": None}
            lesson = {"kind": "syllabus", "title": "T", "advance": True}
            save_progress(
                path, progress, lesson, [_snap("QQQ", 101.0)],
                {"vix": 17.0}, "2026-06-27",
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["next_index"], 1)
        self.assertEqual(saved["last_prices"], {"QQQ": 101.0})
        self.assertEqual(saved["last_vix"], 17.0)
        self.assertEqual(saved["history"][-1]["title"], "T")

    def test_insert_lesson_does_not_advance_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            progress = {"next_index": 7, "last_prices": {}, "last_vix": None}
            lesson = {"kind": "insert", "title": "E", "advance": False}
            save_progress(
                path, progress, lesson, [_snap("QQQ", 100.0)],
                {"vix": 30.0}, "2026-06-27",
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["next_index"], 7)

    def test_pointer_wraps_at_end_of_syllabus(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            progress = {"next_index": len(SYLLABUS) - 1, "last_prices": {}}
            lesson = {"kind": "syllabus", "title": "last", "advance": True}
            save_progress(
                path, progress, lesson, [], {"vix": None}, "2026-06-27"
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["next_index"], 0)


if __name__ == "__main__":
    unittest.main()
