import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


RUN_LOOP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_loop.py"
SPEC = importlib.util.spec_from_file_location("run_loop", RUN_LOOP_PATH)
run_loop = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = run_loop
SPEC.loader.exec_module(run_loop)


class RunLoopJsonTests(unittest.TestCase):
    def test_read_json_accepts_utf8_bom_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.json"
            path.write_text('{"status": "ok"}', encoding="utf-8-sig")

            self.assertEqual(run_loop.read_json(path), {"status": "ok"})

    def test_run_subprocess_json_reads_unicode_keys_from_python_child(self):
        code = (
            "import json; "
            "print(json.dumps({'\\u4ee3\\u7801': '002579'}, ensure_ascii=False))"
        )

        data, err = run_loop.run_subprocess_json([sys.executable, "-c", code])

        self.assertIsNone(err)
        self.assertEqual(data[run_loop.K_CODE], "002579")

    def test_summarize_market_news_exposes_contract_count(self):
        summary = run_loop.summarize_market_news(
            {"data": [{"title": "AI compute demand", "content": ""}, {"title": "macro CPI risk", "content": ""}]}
        )

        self.assertEqual(summary["count"], 2)

    def test_write_report_uses_data_coverage_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            positions = {
                "snapshot_time": "2026-07-03 23:15:02",
                "holdings": [{"code": "000001"}],
                "stock_value": 100.0,
                "total_assets": 120.0,
            }
            signal = {
                "data_coverage": {
                    "holding_count": 3,
                    "quote_count": 2,
                    "history_count": 3,
                    "fund_flow_count": 1,
                    "event_count": 2,
                    "market_news_count": 80,
                },
                "market_regime": {"regime": "mixed"},
                "market_news_context": {"top_topics": [{"topic": "AI/compute", "hits": 8}]},
                "portfolio_actions": [],
                "stock_scores": [],
            }

            run_loop.write_report(path, positions, signal, {"metrics": {}}, {}, [])

            report = path.read_text(encoding="utf-8")
            self.assertIn("quotes 2/3", report)
            self.assertIn("history 3/3", report)
            self.assertIn("fund_flow 1/3", report)
            self.assertIn("events 2/3", report)
            self.assertIn("market_news 80", report)

    def test_fetch_quotes_accepts_unicode_code_key(self):
        original_run = run_loop.run_subprocess_json
        original_direct = run_loop.fetch_quotes_direct
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: ([{run_loop.K_CODE: "002579"}], None)
            run_loop.fetch_quotes_direct = lambda codes: ({}, None)

            quotes, errors = run_loop.fetch_quotes(["002579"], Path("."))

            self.assertEqual(errors, [])
            self.assertIn("002579", quotes)
        finally:
            run_loop.run_subprocess_json = original_run
            run_loop.fetch_quotes_direct = original_direct

    def test_fetch_fund_flow_uses_direct_fallback_when_primary_is_empty(self):
        original_run = run_loop.run_subprocess_json
        original_direct = run_loop.fetch_fund_flow_direct
        try:
            fallback_rows = [{"date": "2026-07-03", "main_net_wan": 12.3}]
            run_loop.run_subprocess_json = lambda command, timeout=30: ([], None)
            run_loop.fetch_fund_flow_direct = lambda code: (fallback_rows, None)

            rows, err = run_loop.fetch_fund_flow("605020", Path("."))

            self.assertIsNone(err)
            self.assertEqual(rows, fallback_rows)
        finally:
            run_loop.run_subprocess_json = original_run
            run_loop.fetch_fund_flow_direct = original_direct


if __name__ == "__main__":
    unittest.main()
