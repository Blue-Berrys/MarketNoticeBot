from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from tradingagents.dataflows import valuation

_CAPE_HTML = """
<table>
<tr class="even"><td>Jun 1, 2026</td><td>\n&#x2002;\n 41.32 \n</td></tr>
<tr class="odd"><td>May 1, 2026</td><td>\n&#x2002;\n 41.10 \n</td></tr>
<tr class="even"><td>Apr 1, 2026</td><td>\n&#x2002;\n 30.00 \n</td></tr>
<tr class="odd"><td>Mar 1, 2026</td><td>\n&#x2002;\n 20.00 \n</td></tr>
</table>
"""

_PE_HTML = """
<tr><td>Jun 1, 2026</td><td>\n&#x2002;\n 30.10 \n</td></tr>
<tr><td>May 1, 2026</td><td>\n&#x2002;\n 18.00 \n</td></tr>
"""


class ParseTests(unittest.TestCase):
    def test_parse_handles_enspace_and_newlines(self):
        rows = valuation.parse_multpl_table(_CAPE_HTML)
        self.assertEqual(rows[0], ("Jun 1, 2026", 41.32))
        self.assertEqual(len(rows), 4)

    def test_percentile_rank_ranks_high_value_near_top(self):
        values = [20.0, 30.0, 41.10, 41.32]
        self.assertEqual(valuation.percentile_rank(values, 41.32), 100.0)
        self.assertEqual(valuation.percentile_rank(values, 20.0), 25.0)

    def test_percentile_rank_empty_is_nan(self):
        self.assertTrue(math.isnan(valuation.percentile_rank([], 1.0)))

    def test_temperature_bands(self):
        self.assertEqual(valuation.valuation_temperature(95), "极高")
        self.assertEqual(valuation.valuation_temperature(80), "偏高")
        self.assertEqual(valuation.valuation_temperature(50), "中性")
        self.assertEqual(valuation.valuation_temperature(10), "偏低")


class Sp500ValuationTests(unittest.TestCase):
    def test_assembles_cape_and_pe_with_percentiles(self):
        def fake_fetch(slug, timeout=20):
            return _CAPE_HTML if slug == "shiller-pe" else _PE_HTML

        with patch.object(valuation, "_fetch", side_effect=fake_fetch):
            result = valuation.sp500_valuation()

        self.assertEqual(result["cape"], 41.32)
        self.assertEqual(result["cape_pct_all"], 100.0)
        self.assertEqual(result["temperature"], "极高")
        self.assertEqual(result["pe_ttm"], 30.10)
        self.assertEqual(result["asof"], "Jun 1, 2026")

    def test_returns_none_on_fetch_failure(self):
        with patch.object(valuation, "_fetch", side_effect=OSError("boom")):
            self.assertIsNone(valuation.sp500_valuation())

    def test_returns_none_on_empty_table(self):
        with patch.object(valuation, "_fetch", return_value="<table></table>"):
            self.assertIsNone(valuation.sp500_valuation())

    def test_degrades_when_pe_table_fails_but_keeps_cape(self):
        def fake_fetch(slug, timeout=20):
            if slug == "shiller-pe":
                return _CAPE_HTML
            raise OSError("pe down")

        with patch.object(valuation, "_fetch", side_effect=fake_fetch):
            result = valuation.sp500_valuation()

        self.assertEqual(result["cape"], 41.32)
        self.assertNotIn("pe_ttm", result)


if __name__ == "__main__":
    unittest.main()
