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


class FunddbValuationTests(unittest.TestCase):
    _PAYLOAD = {
        "data": {
            "right_list": [
                {"gu_code": "NDX.GI", "gu_name": "纳斯达克100",
                 "gu_pe": "34.80", "gu_pe_current_perent": "71.99",
                 "gu_pb": "7.36", "gu_pb_current_perent": "51.82",
                 "gu_xilv": "0.44"},
                {"gu_code": "HSTECH.HI", "gu_name": "恒生科技指数",
                 "gu_pe": "21.70", "gu_pe_current_perent": "21.25"},
                {"gu_code": "h30184.CSI", "gu_name": "中证全指半导体",
                 "gu_pe": "165.95", "gu_pe_current_perent": "99.96"},
                {"gu_code": "UNRELATED", "gu_name": "无关",
                 "gu_pe": "1", "gu_pe_current_perent": "1"},
            ]
        }
    }

    def test_maps_codes_to_snapshot_symbols(self):
        class _Resp:
            def read(self_inner):
                import json as _json
                return _json.dumps(FunddbValuationTests._PAYLOAD).encode()

        with patch("urllib.request.urlopen", return_value=_Resp()):
            result = valuation.fetch_funddb_index_valuations()

        self.assertEqual(result["QQQ"]["pe_pct"], 71.99)
        self.assertEqual(result["QQQ"]["pb_pct"], 51.82)
        self.assertEqual(result["QQQ"]["dividend"], 0.44)
        self.assertEqual(result["HSTECH"]["pe"], 21.70)
        self.assertNotIn("pb_pct", result["HSTECH"])  # PB absent -> field skipped
        self.assertEqual(result["SEMICONDUCTOR"]["pe_pct"], 99.96)
        self.assertNotIn("SPY", result)  # SPX.GI absent from this payload

    def test_returns_empty_dict_on_failure(self):
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertEqual(valuation.fetch_funddb_index_valuations(), {})


if __name__ == "__main__":
    unittest.main()
