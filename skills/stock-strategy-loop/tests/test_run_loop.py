import base64
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import datetime as dt
from unittest import mock
from pathlib import Path


RUN_LOOP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_loop.py"
SPEC = importlib.util.spec_from_file_location("run_loop", RUN_LOOP_PATH)
run_loop = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = run_loop
SPEC.loader.exec_module(run_loop)


def comprehensive_market_inputs(trade_date="2026-07-15"):
    board_id = run_loop.board_identity("concept", "robotics")
    return {
        "latest_trade_date": trade_date,
        "recent_trade_dates": [trade_date, "2026-07-14", "2026-07-13"],
        "normalized_indices": [
            {
                "code": "000001",
                "name": "上证指数",
                "price": 3500.0,
                "change_pct": 1.2,
                "as_of": trade_date,
            }
        ],
        "breadth": {
            "as_of": trade_date,
            "trade_date": trade_date,
            "advancers": 3200,
            "decliners": 1400,
            "unchanged": 100,
            "turnover_yuan": 1.5e12,
            "median_change_pct": 0.8,
            "complete": True,
            "limit_structure_available": False,
        },
        "board_rankings": {
            "concept": {
                "change_desc": [
                    {
                        "group_key": "robotics",
                        "name": "机器人",
                        "change_pct": 5.2,
                        "turnover_yuan": 1.5e11,
                        "as_of": trade_date,
                        "stale": False,
                    }
                ],
                "turnover_desc": [
                    {
                        "group_key": "robotics",
                        "name": "机器人",
                        "change_pct": 5.2,
                        "turnover_yuan": 1.5e11,
                        "as_of": trade_date,
                        "stale": False,
                    }
                ],
            }
        },
        "board_details": {
            board_id: {
                "as_of": trade_date,
                "stale": False,
                "items": [
                    {
                        "code": "000001",
                        "name": "甲公司",
                        "change_pct": 9.9,
                        "turnover_yuan": 3.0e10,
                        "market_cap_yuan": 1.0e11,
                        "limit_up": True,
                    }
                ],
            }
        },
        "market_history": [
            {
                "trade_date": day,
                "top_change": [board_id],
                "top_turnover": [board_id],
            }
            for day in ("2026-07-13", "2026-07-14", trade_date)
        ],
        "evidence_index": [],
    }


def account_positions(snapshot_time="2026-07-15 15:00:00"):
    return {
        "snapshot_time": snapshot_time,
        "accounts": [
            {
                "account": "demo_primary",
                "cash": 0,
                "stock_value": 100,
                "total_assets": 100,
            }
        ],
        "holdings": [
            {
                "account": "demo_primary",
                "code": "000001",
                "name": "甲公司",
                "shares": 10,
                "cost_price": 10,
                "last_price": 10,
                "market_value": 100,
                "unrealized_pnl": 0,
            }
        ],
        "cash": 0,
        "stock_value": 100,
        "total_assets": 100,
    }


def empty_collected(trade_date="2026-07-15"):
    return run_loop.CollectedData(
        stock_data={},
        board_summaries={},
        board_rankings={},
        board_details={},
        indices=[],
        breadth={},
        market_news={},
        latest_trade_date=trade_date,
        errors=[],
    )


def run_args(workspace, snapshot_date="2026-07-15"):
    return type(
        "Args",
        (),
        {
            "workspace": str(workspace),
            "loop_dir": ".stock-loop",
            "positions_json": None,
            "account": None,
            "a_share_skill": str(workspace),
            "years": 3,
            "start_date": "2023-01-01",
            "end_date": snapshot_date,
            "include_events": False,
        },
    )()


def target_args(workspace, end_date="2026-07-15"):
    return type(
        "Args",
        (),
        {
            "workspace": str(workspace),
            "loop_dir": ".stock-loop",
            "codes": "600000",
            "positions_json": None,
            "account": None,
            "a_share_skill": str(workspace),
            "years": 3,
            "start_date": "2023-01-01",
            "end_date": end_date,
            "include_events": False,
        },
    )()


class RunLoopJsonTests(unittest.TestCase):
    def test_published_positions_sample_is_synthetic_and_valid(self):
        sample_path = RUN_LOOP_PATH.parents[1] / "examples" / "positions.sample.json"
        sample = json.loads(sample_path.read_text(encoding="utf-8"))

        selected, selection_errors = run_loop.select_account_positions(
            sample, None
        )
        self.assertEqual(selection_errors, [])
        valid, errors, _ = run_loop.validate_positions(selected)
        self.assertTrue(valid, errors)

    def test_generate_daily_signal_contains_valid_schema_v2_sections(self):
        positions = {
            "snapshot_time": "2026-07-15 15:00:00",
            "holdings": [],
            "total_assets": 0,
            "stock_value": 0,
        }

        signal = run_loop.generate_daily_signal(
            positions,
            {},
            {"regime": "mixed"},
            {},
            [],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs={
                "latest_trade_date": "2026-07-15",
                "recent_trade_dates": ["2026-07-15"],
                "normalized_indices": [],
                "breadth": {},
                "board_rankings": {},
                "board_details": {},
                "market_history": [],
            },
        )

        self.assertEqual(signal["report_schema_version"], 2)
        for key in (
            "evidence_index",
            "market_snapshot",
            "market_mainlines",
            "market_outlook",
            "portfolio_diagnosis",
            "holding_analyses",
        ):
            with self.subTest(key=key):
                self.assertIn(key, signal)
        self.assertEqual(run_loop.validate_signal_v2(signal), [])

    def test_schema_v2_render_uses_fixture_market_and_holding_evidence(self):
        positions = account_positions()
        inputs = comprehensive_market_inputs()
        market_news = {
            "data": [
                {
                    "title": "机器人订单需求持续",
                    "content": "机器人产业链成交活跃",
                    "published_at": "2026-07-15 10:00:00",
                    "source": "fixture-news",
                }
            ]
        }

        signal = run_loop.generate_daily_signal(
            positions,
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            market_news,
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )
        report = run_loop.render_report(
            positions,
            signal,
            {"scope": "technical_only_diagnostic", "metrics": {}},
            {},
            [],
        )

        self.assertEqual(run_loop.validate_signal_v2(signal), [])
        self.assertEqual(
            [line for line in report.splitlines() if line.startswith("## ")],
            [
                "## 核心结论",
                "## 数据覆盖与时效",
                "## 今日市场发生了什么",
                "## 近期主线与今日主线",
                "## 事实—逻辑—推演",
                "## 双周期市场预判",
                "## 组合诊断",
                "## 持仓逐股分析与操作建议",
                "## 回测与参数证据",
                "## 闭环复盘与下一次检查清单",
            ],
        )
        for text in ("上证指数", "机器人", "000001 甲公司"):
            with self.subTest(text=text):
                self.assertIn(text, report)
        self.assertEqual(signal["portfolio_actions"][0]["action"], "watch")
        self.assertEqual(signal["portfolio_actions"][0]["target_weight"], 0.0)

    def test_mismatched_board_detail_cannot_be_current_leader_evidence(self):
        inputs = comprehensive_market_inputs()
        board_id = run_loop.board_identity("concept", "robotics")
        inputs["board_details"][board_id]["as_of"] = "2026-07-14"

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        line = signal["market_mainlines"][0]
        self.assertEqual(line["classification"], "insufficient_evidence")
        self.assertEqual(line["leaders"], [])
        self.assertEqual(line["score_components"]["breadth"], 0.0)
        self.assertEqual(line["score_components"]["leader_structure"], 0.0)
        self.assertFalse(
            any(
                row["category"] == "constituent"
                and row["reliability"] == "high"
                for row in signal["evidence_index"]
            )
        )

    def test_evidence_uses_each_source_date_and_stale_state(self):
        inputs = comprehensive_market_inputs()
        ranking = inputs["board_rankings"]["concept"]
        for row in ranking["change_desc"] + ranking["turnover_desc"]:
            row["as_of"] = "2026-07-14"
            row["stale"] = True
        board_id = run_loop.board_identity("concept", "robotics")
        inputs["board_details"][board_id]["as_of"] = "2026-07-14"

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        evidence = next(
            row
            for row in signal["evidence_index"]
            if row["evidence_id"] == f"board:{board_id}"
        )
        self.assertEqual(evidence["as_of"], "2026-07-14")
        self.assertEqual(evidence["freshness"], "stale")
        self.assertEqual(evidence["reliability"], "low")

    def test_stale_news_cannot_verify_a_current_session_catalyst(self):
        inputs = comprehensive_market_inputs()
        market_news = {
            "meta": {"stale": True},
            "data": [
                {
                    "title": "机器人订单需求持续",
                    "content": "机器人产业链成交活跃",
                    "published_at": "2026-07-15 10:00:00",
                    "source": "stale-fixture-news",
                }
            ],
        }

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            market_news,
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        news_evidence = next(
            row
            for row in signal["evidence_index"]
            if row["category"] == "news"
        )
        self.assertEqual(news_evidence["freshness"], "stale")
        self.assertEqual(news_evidence["reliability"], "low")
        self.assertFalse(signal["market_mainlines"][0]["catalyst_verified"])

    def test_board_evidence_requires_exact_false_provider_stale_flag(self):
        cases = (
            ("missing", None),
            ("none", None),
            ("false-string", "false"),
            ("true-string", "true"),
            ("zero", 0),
            ("one", 1),
            ("true", True),
            ("exact-false", False),
        )
        board_id = run_loop.board_identity("concept", "robotics")
        for label, stale in cases:
            with self.subTest(label=label):
                inputs = comprehensive_market_inputs()
                ranking = inputs["board_rankings"]["concept"]
                for row in ranking["change_desc"] + ranking["turnover_desc"]:
                    if label == "missing":
                        row.pop("stale", None)
                    else:
                        row["stale"] = stale
                signal = run_loop.generate_daily_signal(
                    account_positions(),
                    {},
                    {"regime": "risk_on"},
                    {},
                    inputs["normalized_indices"],
                    {},
                    [],
                    run_loop.DEFAULT_PARAMS,
                    market_inputs=inputs,
                )
                evidence = next(
                    row
                    for row in signal["evidence_index"]
                    if row["evidence_id"] == f"board:{board_id}"
                )
                if stale is False and label == "exact-false":
                    self.assertEqual(evidence["freshness"], "current-session")
                    self.assertEqual(evidence["reliability"], "high")
                elif stale is True:
                    self.assertEqual(evidence["freshness"], "stale")
                    self.assertEqual(evidence["reliability"], "low")
                else:
                    self.assertEqual(evidence["freshness"], "unknown")
                    self.assertEqual(evidence["reliability"], "low")

    def test_news_scoring_requires_exact_false_provider_stale_flag(self):
        cases = (
            ("missing", None),
            ("none", None),
            ("false-string", "false"),
            ("true-string", "true"),
            ("zero", 0),
            ("one", 1),
            ("true", True),
            ("exact-false", False),
        )
        for label, stale in cases:
            with self.subTest(label=label):
                inputs = comprehensive_market_inputs()
                meta = {} if label == "missing" else {"stale": stale}
                market_news = {
                    "meta": meta,
                    "data": [
                        {
                            "title": "机器人订单需求持续",
                            "content": "机器人产业链成交活跃",
                            "published_at": "2026-07-15 10:00:00",
                            "source": "fixture-news",
                        }
                    ],
                }
                signal = run_loop.generate_daily_signal(
                    account_positions(),
                    {},
                    {"regime": "risk_on"},
                    {},
                    inputs["normalized_indices"],
                    market_news,
                    [],
                    run_loop.DEFAULT_PARAMS,
                    market_inputs=inputs,
                )
                evidence = next(
                    row
                    for row in signal["evidence_index"]
                    if row["category"] == "news"
                )
                line = signal["market_mainlines"][0]
                if stale is False and label == "exact-false":
                    self.assertEqual(evidence["freshness"], "current-session")
                    self.assertEqual(evidence["reliability"], "medium")
                    self.assertTrue(line["catalyst_verified"])
                elif stale is True:
                    self.assertEqual(evidence["freshness"], "stale")
                    self.assertEqual(evidence["reliability"], "low")
                    self.assertFalse(line["catalyst_verified"])
                else:
                    self.assertEqual(evidence["freshness"], "unknown")
                    self.assertEqual(evidence["reliability"], "low")
                    self.assertFalse(line["catalyst_verified"])

    def test_initial_evidence_collision_reaches_duplicate_id_validation(self):
        inputs = comprehensive_market_inputs()
        board_id = run_loop.board_identity("concept", "robotics")
        collision_id = f"board:{board_id}"
        inputs["evidence_index"] = [
            {
                "evidence_id": collision_id,
                "category": "board",
                "statement": "外部碰撞证据",
                "source": "fixture",
                "as_of": "2026-07-15",
                "trading_session": "2026-07-15",
                "freshness": "current-session",
                "reliability": "high",
                "scope": board_id,
            }
        ]

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        self.assertEqual(
            sum(
                row.get("evidence_id") == collision_id
                for row in signal["evidence_index"]
                if isinstance(row, dict)
            ),
            2,
        )
        self.assertIn(
            f"duplicate evidence_id {collision_id}",
            run_loop.validate_signal_v2(signal),
        )

    def test_malformed_initial_evidence_reaches_validator_without_logic_crash(self):
        inputs = comprehensive_market_inputs()
        inputs["evidence_index"] = [
            None,
            7,
            [],
            {"evidence_id": []},
            {"evidence_id": ""},
        ]

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        errors = run_loop.validate_signal_v2(signal)
        self.assertIn("evidence_index[0] must be an object", errors)
        self.assertIn(
            "evidence_index[3] evidence_id must be a non-empty string",
            errors,
        )

    def test_schema_assembly_skips_malformed_rankings_and_indices(self):
        signal = run_loop.generate_daily_signal(
            {
                "snapshot_time": "2026-07-15 15:00:00",
                "holdings": [],
                "total_assets": 0,
                "stock_value": 0,
            },
            {},
            {"regime": "mixed"},
            {},
            [],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs={
                "latest_trade_date": "2026-07-15",
                "recent_trade_dates": ["2026-07-15"],
                "normalized_indices": [
                    None,
                    7,
                    [],
                    {"change_pct": [], "as_of": "2026-07-15"},
                ],
                "breadth": {},
                "board_rankings": {
                    "concept": {
                        "change_desc": [None, 7, [], {"group_key": []}],
                        "turnover_desc": "bad",
                    },
                    "major": None,
                },
                "board_details": {},
                "market_history": [],
                "evidence_index": [],
            },
        )

        self.assertEqual(run_loop.validate_signal_v2(signal), [])
        self.assertEqual(signal["market_snapshot"]["indices"], [])

    def test_schema_assembly_skips_malformed_board_detail_items(self):
        board_id = run_loop.board_identity("concept", "robotics")
        for items in (None, 7, {}, "bad", [None, 7, [], {"code": []}]):
            with self.subTest(items=items):
                inputs = comprehensive_market_inputs()
                inputs["board_details"][board_id]["items"] = items

                signal = run_loop.generate_daily_signal(
                    account_positions(),
                    {},
                    {"regime": "risk_on"},
                    {},
                    inputs["normalized_indices"],
                    {},
                    [],
                    run_loop.DEFAULT_PARAMS,
                    market_inputs=inputs,
                )

                self.assertEqual(run_loop.validate_signal_v2(signal), [])
                self.assertEqual(
                    signal["market_mainlines"][0]["leaders"], []
                )

    def test_read_json_accepts_utf8_bom_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.json"
            path.write_text('{"status": "ok"}', encoding="utf-8-sig")

            self.assertEqual(run_loop.read_json(path), {"status": "ok"})

    def test_run_subprocess_json_reads_unicode_keys_from_python_child(self):
        code = (
            "import json; "
            "print(json.dumps({'\\u4ee3\\u7801': '000302'}, ensure_ascii=False))"
        )

        data, err = run_loop.run_subprocess_json([sys.executable, "-c", code])

        self.assertIsNone(err)
        self.assertEqual(data[run_loop.K_CODE], "000302")

    def test_run_subprocess_json_summarizes_json_errors_on_nonzero_exit(self):
        code = (
            "import json, sys; "
            "print(json.dumps({'data': ["
            "{'code': '300101', 'error': 'first failure'}, "
            "{'code': '000302', 'error': 'second failure'}, "
            "{'code': '000303', 'error': 'third failure'}, "
            "{'code': '000301', 'error': 'fourth failure'}"
            "]}, ensure_ascii=False)); "
            "sys.exit(1)"
        )

        data, err = run_loop.run_subprocess_json([sys.executable, "-c", code])

        self.assertIsInstance(data, dict)
        self.assertIn("300101: first failure", err)
        self.assertIn("+1 more", err)

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
            signal = run_loop.generate_daily_signal(
                {**positions, "holdings": []},
                {},
                {"regime": "mixed"},
                {},
                [],
                {},
                [],
                run_loop.DEFAULT_PARAMS,
                market_inputs={
                    "latest_trade_date": "2026-07-03",
                    "recent_trade_dates": ["2026-07-03"],
                    "normalized_indices": [],
                    "breadth": {},
                    "board_rankings": {},
                    "board_details": {},
                    "market_history": [],
                },
            )
            signal["data_coverage"].update(
                {
                    "holdings": 3,
                    "quotes": 2,
                    "history": 3,
                    "fund_flow": 1,
                    "events": 2,
                    "market_news": 80,
                    "holding_count": 3,
                    "quote_count": 2,
                    "history_count": 3,
                    "fund_flow_count": 1,
                    "event_count": 2,
                    "market_news_count": 80,
                }
            )

            run_loop.write_report(path, positions, signal, {"metrics": {}}, {}, [])

            report = path.read_text(encoding="utf-8")
            self.assertIn("| holdings | 3 |", report)
            self.assertIn("| quotes | 2 |", report)
            self.assertIn("| history | 3 |", report)
            self.assertIn("| fund_flow | 1 |", report)
            self.assertIn("| events | 2 |", report)
            self.assertIn("| market_news | 80 |", report)
            self.assertEqual(
                len([line for line in report.splitlines() if line.startswith("## ")]),
                10,
            )

    def test_build_industry_panorama_classifies_value_chain_prompt(self):
        panorama = run_loop.build_industry_panorama(
            [{"code": "300101", "name": "示例新能源", "industry": "电力设备"}]
        )

        self.assertEqual(panorama[0]["code"], "300101")
        self.assertIn("新能源", panorama[0]["segment_focus"])
        self.assertIn("上游", panorama[0]["value_chain_position"])
        self.assertIn("独角兽", panorama[0]["scarce_capability_check"])

    def test_panorama_exposes_upstream_and_downstream_checks(self):
        panorama = run_loop.build_industry_panorama(
            [{"code": "300101", "name": "示例新能源", "industry": "电力设备"}]
        )

        self.assertIn("upstream_dependency_check", panorama[0])
        self.assertIn("downstream_customer_check", panorama[0])

    def test_fetch_quotes_accepts_unicode_code_key(self):
        original_run = run_loop.run_subprocess_json
        original_direct = run_loop.fetch_quotes_direct
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: ([{run_loop.K_CODE: "000302"}], None)
            run_loop.fetch_quotes_direct = lambda codes: ({}, None)

            quotes, errors = run_loop.fetch_quotes(["000302"], Path("."))

            self.assertEqual(errors, [])
            self.assertIn("000302", quotes)
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

            rows, err = run_loop.fetch_fund_flow("600101", Path("."))

            self.assertIsNone(err)
            self.assertEqual(rows, fallback_rows)
        finally:
            run_loop.run_subprocess_json = original_run
            run_loop.fetch_fund_flow_direct = original_direct

    def test_fetch_fund_flow_direct_retries_http_after_https_disconnect(self):
        class FakeResponse:
            def __init__(self, payload=None):
                self.payload = payload or {
                    "data": {
                        "klines": [
                            "2026-07-06,10000,0,0,5000,5000,1.0,0,0,0,0,10.5,2.0,0,0"
                        ]
                    }
                }

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            calls = []

            def __init__(self):
                self.trust_env = True

            def get(self, url, headers=None, timeout=None):
                self.calls.append((url, self.trust_env))
                if url.startswith("https://"):
                    raise ConnectionError("remote closed")
                return FakeResponse()

        fake_requests = type("FakeRequests", (), {"Session": FakeSession})
        with mock.patch.object(run_loop, "require_requests", return_value=fake_requests):
            rows, err = run_loop.fetch_fund_flow_direct("300101")

            self.assertIsNone(err)
            self.assertEqual(rows[0]["date"], "2026-07-06")
            self.assertEqual(rows[0]["main_net_wan"], 1.0)
            self.assertTrue(FakeSession.calls[0][0].startswith("https://"))
            self.assertTrue(FakeSession.calls[1][0].startswith("http://"))
            self.assertFalse(FakeSession.calls[1][1])

    def test_fetch_fund_flow_direct_retries_http_after_empty_https_payload(self):
        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            calls = []

            def __init__(self):
                self.trust_env = True

            def get(self, url, headers=None, timeout=None):
                self.calls.append(url)
                if url.startswith("https://"):
                    return FakeResponse({"data": None})
                return FakeResponse(
                    {
                        "data": {
                            "klines": [
                                "2026-07-06,20000,0,0,10000,10000,2.0,0,0,0,0,11.5,3.0,0,0"
                            ]
                        }
                    }
                )

        fake_requests = type("FakeRequests", (), {"Session": FakeSession})
        with mock.patch.object(run_loop, "require_requests", return_value=fake_requests):
            rows, err = run_loop.fetch_fund_flow_direct("300101")

            self.assertIsNone(err)
            self.assertEqual(rows[0]["main_net_wan"], 2.0)
            self.assertTrue(FakeSession.calls[0].startswith("https://"))
            self.assertTrue(FakeSession.calls[1].startswith("http://"))

    def test_fetch_fund_flow_direct_uses_snapshot_fallback_when_daykline_fails(self):
        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            def __init__(self):
                self.trust_env = True

            def get(self, url, headers=None, timeout=None):
                if "fflow/daykline" in url:
                    raise ConnectionError("daykline unavailable")
                return FakeResponse(
                    {
                        "data": {
                            "diff": [
                                {
                                    "f2": 10.5,
                                    "f3": 2.0,
                                    "f62": 30000.0,
                                    "f184": 6.0,
                                    "f165": 4.0,
                                    "f175": 3.0,
                                    "f124": 1783323264,
                                }
                            ]
                        }
                    }
                )

        fake_requests = type("FakeRequests", (), {"Session": FakeSession})
        with mock.patch.object(run_loop, "require_requests", return_value=fake_requests):
            rows, err = run_loop.fetch_fund_flow_direct("300101")

            self.assertIsNone(err)
            self.assertEqual(rows[0]["source"], "eastmoney-ulist-snapshot")
            self.assertEqual(rows[0]["main_net_wan"], 3.0)
            self.assertEqual(rows[0]["main_ratio_pct"], 6.0)
            self.assertEqual(rows[0]["five_day_ratio_pct"], 4.0)

    def test_score_from_row_uses_snapshot_fund_flow_ratios(self):
        params = {"weights": {"trend": 0.42, "macd": 0.24, "fund_flow": 0.16, "sector": 0.10, "event": 0.08}}
        row = {
            "close": 10,
            "ma_short": 9,
            "ma_long": 8,
            "dif": 1,
            "dea": 0.5,
            "macd_hist": 1,
            "ret20": 1,
        }
        prev = {"ma_long": 7.9, "macd_hist": 0.5}

        score = run_loop.score_from_row(
            row,
            prev,
            [{"main_ratio_pct": 6.0, "five_day_ratio_pct": 4.0, "ten_day_ratio_pct": 3.0}],
            0,
            0,
            params,
        )

        self.assertEqual(score["fund_flow_score"], 85.0)

    def test_missing_fund_flow_is_null_with_explicit_neutral_total_imputation(self):
        params = {
            "weights": {
                "trend": 0.42,
                "macd": 0.24,
                "fund_flow": 0.16,
                "sector": 0.10,
                "event": 0.08,
            }
        }
        row = {
            "close": 10,
            "ma_short": 9,
            "ma_long": 8,
            "dif": 1,
            "dea": 0.5,
            "macd_hist": 1,
            "ret20": 1,
        }
        prev = {"ma_long": 7.9, "macd_hist": 0.5}

        missing = run_loop.score_from_row(row, prev, [], 0, 0, params)
        real_zero = run_loop.score_from_row(
            row, prev, [{"main_net_wan": 0.0}], 0, 0, params
        )

        self.assertIsNone(missing["fund_flow_score"])
        self.assertEqual(missing.get("score_imputations"), {"fund_flow": 50.0})
        self.assertEqual(missing["total_score"], real_zero["total_score"])
        self.assertEqual(real_zero["fund_flow_score"], 50.0)
        self.assertNotIn("fund_flow", real_zero.get("score_imputations", {}))

    def test_malformed_or_nonfinite_fund_flow_rows_are_missing(self):
        params = {
            "weights": {
                "trend": 0.42,
                "macd": 0.24,
                "fund_flow": 0.16,
                "sector": 0.10,
                "event": 0.08,
            }
        }
        malformed = [
            {"date": "2026-07-15"},
            {"main_net_wan": "bad"},
            {"main_net_wan": float("nan")},
            {"main_ratio_pct": float("inf")},
            {"main_net_wan": True},
        ]

        score = run_loop.score_from_row({}, None, malformed, 0, 0, params)

        self.assertIsNone(score["fund_flow_score"])
        self.assertEqual(score.get("score_imputations"), {"fund_flow": 50.0})
        self.assertEqual(run_loop.normalize_fund_flow_rows(malformed), [])

    def test_empty_failed_fund_flow_stays_null_through_signal_holding_and_report(self):
        positions = account_positions()
        history = [
            {"date": f"2026-06-{day:02d}", "close": 10 + day / 100}
            for day in range(1, 26)
        ]
        stock = run_loop.StockData(
            code="000001",
            name="甲公司",
            history=history,
            quote={run_loop.K_PRICE: 10.25},
            industry="电子",
            fund_flow=[],
            events={},
        )
        signal = run_loop.generate_daily_signal(
            positions,
            {"000001": stock},
            {"regime": "mixed"},
            {},
            [],
            {},
            ["fund_flow 000001: request failed"],
            run_loop.DEFAULT_PARAMS,
            market_inputs={"latest_trade_date": "2026-07-15"},
        )

        score = signal["stock_scores"][0]["scores"]
        factors = signal["holding_analyses"][0]["factor_evidence"]
        report = run_loop.render_report(
            positions,
            signal,
            {"metrics": {}},
            {},
            ["fund_flow 000001: request failed"],
        )
        self.assertEqual(signal["data_coverage"]["fund_flow"], 0)
        self.assertIsNone(score["fund_flow_score"])
        self.assertIsNone(score["raw"]["fund_flow_5d_net_wan"])
        self.assertEqual(score.get("score_imputations"), {"fund_flow": 50.0})
        self.assertIsNone(factors["fund_flow_score"])
        self.assertEqual(factors.get("score_imputations"), {"fund_flow": 50.0})
        self.assertEqual(run_loop.validate_signal_v2(signal), [])
        self.assertIn("资金 证据不足（总分按中性 50 插补）", report)
        self.assertNotIn("资金 50.0", report)

    def test_valid_fund_flow_preserves_public_score_and_raw_net_amount(self):
        positions = account_positions()
        history = [
            {"date": f"2026-06-{day:02d}", "close": 10 + day / 100}
            for day in range(1, 26)
        ]
        stock = run_loop.StockData(
            code="000001",
            name="甲公司",
            history=history,
            quote={run_loop.K_PRICE: 10.25},
            industry="电子",
            fund_flow=[{"main_net_wan": 120.0, "main_ratio_pct": 6.0}],
            events={},
        )

        signal = run_loop.generate_daily_signal(
            positions,
            {"000001": stock},
            {"regime": "mixed"},
            {},
            [],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs={"latest_trade_date": "2026-07-15"},
        )

        score = signal["stock_scores"][0]["scores"]
        factors = signal["holding_analyses"][0]["factor_evidence"]
        self.assertIsNotNone(score["fund_flow_score"])
        self.assertEqual(score["raw"]["fund_flow_5d_net_wan"], 120.0)
        self.assertNotIn("fund_flow", score.get("score_imputations", {}))
        self.assertEqual(factors["fund_flow_score"], score["fund_flow_score"])

    def test_trim_incomplete_daily_rows_drops_today_before_close(self):
        rows = [{"date": "2026-07-03"}, {"date": "2026-07-06"}]

        trimmed = run_loop.trim_incomplete_daily_rows(rows, dt.datetime(2026, 7, 6, 9, 45))

        self.assertEqual(trimmed, [{"date": "2026-07-03"}])

    def test_trim_incomplete_daily_rows_keeps_today_after_close_buffer(self):
        rows = [{"date": "2026-07-03"}, {"date": "2026-07-06"}]

        trimmed = run_loop.trim_incomplete_daily_rows(rows, dt.datetime(2026, 7, 6, 15, 45))

        self.assertEqual(trimmed, rows)

    def test_fetch_sector_info_keeps_partial_rows_when_command_fails(self):
        original_run = run_loop.run_subprocess_json
        try:
            run_loop.run_subprocess_json = lambda command, timeout=35: (
                {
                    "data": [
                        {"code": "000001", "industry": "银行"},
                        {"code": "000002", "industry": None, "error": "network failure"},
                    ]
                },
                "row errors: 000002: network failure",
            )

            sectors, note = run_loop.fetch_sector_info(["000001", "000002"], Path("."))

            self.assertEqual(sectors["000001"]["industry"], "银行")
            self.assertIn("row errors", note)
            self.assertIn("quote fallback", note)
        finally:
            run_loop.run_subprocess_json = original_run

    def test_select_account_positions_requires_explicit_account_for_multiple_accounts(self):
        selected, errors = run_loop.select_account_positions(
            {
                "accounts": [{"account": "**demo_primary"}, {"account": "demo_secondary"}],
                "holdings": [{"account": "**demo_primary"}, {"account": "demo_secondary"}],
            },
            None,
        )

        self.assertIsNone(selected)
        self.assertIn("multiple accounts", errors[0])

    def test_select_account_positions_uses_selected_account_assets(self):
        data = {
            "accounts": [{"account": "**demo_primary", "cash": 10, "stock_value": 90, "total_assets": 100}],
            "holdings": [{"account": "**demo_primary", "code": "000001", "market_value": 90}],
        }

        selected, errors = run_loop.select_account_positions(data, "demo_primary")

        self.assertEqual(errors, [])
        self.assertEqual(selected["accounts"][0]["account"], "demo_primary")
        self.assertEqual(selected["cash"], 10.0)
        self.assertEqual(len(selected["holdings"]), 1)

    def test_single_account_metadata_assigns_holdings_with_omitted_account(self):
        data = json.loads(json.dumps(account_positions()))
        data["holdings"][0].pop("account")

        selected, errors = run_loop.select_account_positions(data, None)

        self.assertEqual(errors, [])
        self.assertEqual(selected["holdings"][0]["account"], "demo_primary")
        valid, validation_errors, _ = run_loop.validate_positions(selected)
        self.assertTrue(valid, validation_errors)

    def test_unmarked_holdings_are_rejected_when_account_assignment_is_ambiguous(self):
        mixed = json.loads(json.dumps(account_positions()))
        unmarked = json.loads(json.dumps(mixed["holdings"][0]))
        unmarked.pop("account")
        unmarked["code"] = "000002"
        mixed["holdings"].append(unmarked)

        multiple = json.loads(json.dumps(account_positions()))
        multiple["holdings"][0].pop("account")
        multiple["accounts"].append(
            {
                "account": "demo_secondary",
                "cash": 0,
                "stock_value": 0,
                "total_assets": 0,
            }
        )

        for label, data in (("mixed", mixed), ("multiple", multiple)):
            with self.subTest(label=label):
                selected, errors = run_loop.select_account_positions(data, None)
                self.assertIsNone(selected)
                self.assertTrue(errors)
                self.assertIn("ambiguous", errors[0])

    def test_validate_command_rejects_non_object_positions_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.json"
            path.write_text("[]", encoding="utf-8")
            args = type(
                "Args",
                (),
                {"positions_json": str(path), "account": None},
            )()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = run_loop.cmd_validate(args)

            payload = json.loads(output.getvalue())
            self.assertNotEqual(result, 0)
            self.assertEqual(payload["status"], "invalid_positions")
            self.assertTrue(payload["errors"])

    def test_commands_report_malformed_positions_json_without_traceback(self):
        for command in ("validate", "target", "account"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths = run_loop.loop_paths(workspace)
                path = paths["positions"] / "positions.json"
                path.write_text("{malformed", encoding="utf-8")
                if command == "account":
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                        b"image"
                    )
                args = (
                    type(
                        "Args",
                        (),
                        {"positions_json": str(path), "account": None},
                    )()
                    if command == "validate"
                    else target_args(workspace)
                    if command == "target"
                    else run_args(workspace)
                )
                output = io.StringIO()

                with contextlib.redirect_stdout(output):
                    result = (
                        run_loop.cmd_validate(args)
                        if command == "validate"
                        else run_loop.cmd_analyze_targets(args)
                        if command == "target"
                        else run_loop.run_loop(args)
                    )

                payload = json.loads(output.getvalue())
                self.assertNotEqual(result, 0)
                self.assertEqual(payload["status"], "invalid_positions")
                self.assertTrue(payload["errors"])

    def test_validate_positions_cli_imports_without_third_party_site_packages(self):
        sample = RUN_LOOP_PATH.parents[1] / "examples" / "positions.sample.json"
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(RUN_LOOP_PATH),
                "validate-positions",
                "--positions-json",
                str(sample),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "ok")

    def test_network_fallback_reports_missing_requests_dependency(self):
        real_import = __import__

        def import_without_requests(name, *args, **kwargs):
            if name == "requests":
                raise ImportError("requests intentionally unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_requests):
            quotes, error = run_loop.fetch_quotes_direct(["000001"])

        self.assertEqual(quotes, {})
        self.assertIn("requests>=2.31,<3", error)

    def test_selected_account_row_authoritatively_propagates_coverage_flags(self):
        for flag in ("cash_unreadable", "total_assets_lower_bound"):
            for marker in (True, False):
                with self.subTest(flag=flag, marker=marker):
                    data = json.loads(json.dumps(account_positions()))
                    account_row = data["accounts"][0]
                    account_row.update({
                        "cash": 50,
                        "stock_value": 100,
                        "total_assets": 150,
                        flag: marker,
                    })
                    data.update({
                        "cash": 999,
                        "stock_value": 100,
                        "total_assets": 1099,
                        flag: not marker,
                    })

                    selected, errors = run_loop.select_account_positions(
                        data, None
                    )

                    self.assertEqual(errors, [])
                    self.assertIs(selected[flag], marker)
                    valid, validation_errors, _ = run_loop.validate_positions(
                        selected
                    )
                    self.assertTrue(valid, validation_errors)

    def test_selected_complete_account_row_clears_stale_top_level_flags(self):
        data = json.loads(json.dumps(account_positions()))
        data["accounts"][0].update({
            "cash": 50,
            "stock_value": 100,
            "total_assets": 150,
        })
        data.update({
            "cash": "stale",
            "stock_value": 100,
            "total_assets": "stale",
            "cash_unreadable": True,
            "total_assets_lower_bound": True,
        })

        selected, errors = run_loop.select_account_positions(data, None)

        self.assertEqual(errors, [])
        self.assertNotIn("cash_unreadable", selected)
        self.assertNotIn("total_assets_lower_bound", selected)
        self.assertEqual(selected["cash"], 50)
        self.assertEqual(selected["total_assets"], 150)
        valid, validation_errors, _ = run_loop.validate_positions(selected)
        self.assertTrue(valid, validation_errors)

    def test_parser_accepts_account_for_validation_and_run(self):
        parser = run_loop.build_parser()

        validate_args = parser.parse_args(
            ["validate-positions", "--positions-json", "positions.json", "--account", "demo_primary"]
        )
        run_args = parser.parse_args(["run", "--account", "demo_secondary"])

        self.assertEqual(validate_args.account, "demo_primary")
        self.assertEqual(run_args.account, "demo_secondary")

    def test_validate_positions_rejects_nonfinite_non_numeric_holding_fields(self):
        invalid_values = ("bad", True, [], {}, float("nan"), float("inf"))
        fields = (
            "shares",
            "cost_price",
            "last_price",
            "market_value",
            "unrealized_pnl",
        )
        for field in fields:
            for value in invalid_values:
                with self.subTest(field=field, value=repr(value)):
                    data = json.loads(json.dumps(account_positions()))
                    data["holdings"][0][field] = value

                    valid, errors, _ = run_loop.validate_positions(data)

                    self.assertFalse(valid, errors)

        all_bool = json.loads(json.dumps(account_positions()))
        for field in fields:
            all_bool["holdings"][0][field] = True
        all_bool["stock_value"] = 1
        all_bool["total_assets"] = 1
        valid, errors, _ = run_loop.validate_positions(all_bool)
        self.assertFalse(valid, errors)

    def test_validate_positions_accepts_only_strict_json_numbers(self):
        for field in (
            "shares",
            "cost_price",
            "last_price",
            "market_value",
            "unrealized_pnl",
        ):
            with self.subTest(scope="holding", field=field):
                data = json.loads(json.dumps(account_positions()))
                data["holdings"][0][field] = str(
                    data["holdings"][0][field]
                )
                valid, _, _ = run_loop.validate_positions(data)
                self.assertFalse(valid)

        for field in ("stock_value", "cash", "total_assets"):
            with self.subTest(scope="top-level", field=field):
                data = json.loads(json.dumps(account_positions()))
                data[field] = str(data[field])
                valid, _, _ = run_loop.validate_positions(data)
                self.assertFalse(valid)

        for number_type in (int, float):
            with self.subTest(valid_type=number_type.__name__):
                data = json.loads(json.dumps(account_positions()))
                values = {
                    "shares": number_type(10),
                    "cost_price": number_type(10),
                    "last_price": number_type(10),
                    "market_value": number_type(100),
                    "unrealized_pnl": number_type(0),
                }
                data["holdings"][0].update(values)
                data["stock_value"] = number_type(100)
                data["cash"] = number_type(1)
                data["total_assets"] = number_type(101)
                valid, errors, _ = run_loop.validate_positions(data)
                self.assertTrue(valid, errors)

        unreadable = json.loads(json.dumps(account_positions()))
        unreadable["cash"] = "not-a-number"
        unreadable["cash_unreadable"] = True
        valid, errors, _ = run_loop.validate_positions(unreadable)
        self.assertTrue(valid, errors)

        lower_bound = json.loads(json.dumps(account_positions()))
        lower_bound["total_assets"] = "not-a-number"
        lower_bound["total_assets_lower_bound"] = True
        valid, errors, _ = run_loop.validate_positions(lower_bound)
        self.assertTrue(valid, errors)

    def test_market_value_derivation_requires_exact_true_and_valid_inputs(self):
        derived = json.loads(json.dumps(account_positions()))
        derived["holdings"][0].pop("market_value")
        derived["holdings"][0]["market_value_derived"] = True
        valid, errors, normalized = run_loop.validate_positions(derived)
        self.assertTrue(valid, errors)
        self.assertEqual(normalized["holdings"][0]["market_value"], 100.0)

        for marker in (None, "true", 1, 1.0):
            with self.subTest(marker=marker):
                data = json.loads(json.dumps(account_positions()))
                data["holdings"][0].pop("market_value")
                if marker is not None:
                    data["holdings"][0]["market_value_derived"] = marker
                valid, _, _ = run_loop.validate_positions(data)
                self.assertFalse(valid)

        invalid_source = json.loads(json.dumps(account_positions()))
        invalid_source["holdings"][0]["market_value"] = "bad"
        invalid_source["holdings"][0]["market_value_derived"] = True
        invalid_source["holdings"][0]["shares"] = "bad"
        valid, _, _ = run_loop.validate_positions(invalid_source)
        self.assertFalse(valid)

        malformed_value = json.loads(json.dumps(account_positions()))
        malformed_value["holdings"][0]["market_value"] = "bad"
        malformed_value["holdings"][0]["market_value_derived"] = True
        valid, _, _ = run_loop.validate_positions(malformed_value)
        self.assertFalse(valid)

    def test_validate_positions_enforces_top_level_asset_semantics(self):
        for field, value in (
            ("stock_value", "bad"),
            ("stock_value", True),
            ("cash", "bad"),
            ("cash", -1),
            ("cash", True),
            ("total_assets", "bad"),
            ("total_assets", True),
            ("total_assets", 0),
        ):
            with self.subTest(field=field, value=repr(value)):
                data = json.loads(json.dumps(account_positions()))
                data[field] = value
                valid, _, _ = run_loop.validate_positions(data)
                self.assertFalse(valid)

        for field, marker, value in (
            ("cash", "cash_unreadable", "bad"),
            ("total_assets", "total_assets_lower_bound", "bad"),
        ):
            for lookalike in ("true", 1, 1.0):
                with self.subTest(field=field, lookalike=lookalike):
                    data = json.loads(json.dumps(account_positions()))
                    data[field] = value
                    data[marker] = lookalike
                    valid, _, _ = run_loop.validate_positions(data)
                    self.assertFalse(valid)

        unreadable = json.loads(json.dumps(account_positions()))
        unreadable["cash"] = "bad"
        unreadable["cash_unreadable"] = True
        valid, errors, normalized = run_loop.validate_positions(unreadable)
        self.assertTrue(valid, errors)
        self.assertEqual(normalized["cash"], 0.0)

        lower_bound = json.loads(json.dumps(account_positions()))
        lower_bound["total_assets"] = "bad"
        lower_bound["total_assets_lower_bound"] = True
        valid, errors, normalized = run_loop.validate_positions(lower_bound)
        self.assertTrue(valid, errors)
        self.assertEqual(normalized["total_assets"], 100.0)

        mismatch = json.loads(json.dumps(account_positions()))
        mismatch["total_assets"] = 200
        valid, _, _ = run_loop.validate_positions(mismatch)
        self.assertFalse(valid)

        account_assets = json.loads(json.dumps(account_positions()))
        account_assets["accounts"][0]["cash"] = True
        account_assets["accounts"][0]["total_assets"] = 101
        selected, selection_errors = run_loop.select_account_positions(
            account_assets, "demo_primary"
        )
        self.assertEqual(selection_errors, [])
        valid, _, _ = run_loop.validate_positions(selected)
        self.assertFalse(valid)

    def test_invalid_positions_stop_before_market_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                b"image"
            )
            paths = run_loop.loop_paths(workspace)
            data = account_positions()
            data["holdings"][0]["unrealized_pnl"] = True
            (paths["positions"] / "positions.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            original_collect = run_loop.collect_data
            calls = []
            try:
                run_loop.collect_data = lambda *args, **kwargs: (
                    calls.append(args) or empty_collected()
                )

                result = run_loop.run_loop(run_args(workspace))

                self.assertEqual(result, 3)
                self.assertEqual(calls, [])
            finally:
                run_loop.collect_data = original_collect

    def test_scan_screenshots_ignores_nested_runtime_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Screenshot_2026-07-13-09-00-00.png").write_bytes(b"root")
            nested = root / ".stock-loop" / "cache"
            nested.mkdir(parents=True)
            (nested / "Screenshot_2026-07-14-09-00-00.png").write_bytes(b"nested")

            manifest = run_loop.scan_screenshots(root)

            self.assertEqual(
                [row["name"] for row in manifest["all_screenshots"]],
                ["Screenshot_2026-07-13-09-00-00.png"],
            )

    def test_validate_snapshot_freshness_rejects_stale_positions(self):
        errors = run_loop.validate_snapshot_freshness(
            {"snapshot_time": "2026-07-12 09:25:12"},
            {"latest_snapshot_time": "2026-07-13 09:25:12"},
        )

        self.assertEqual(
            errors,
            ["positions snapshot_time does not match latest screenshot: 2026-07-13 09:25:12"],
        )

    def test_portfolio_value_uses_last_close_when_a_held_stock_has_no_bar(self):
        value = run_loop.portfolio_value(
            100.0,
            {"000001": 10.0},
            {},
            {"000001": 12.5},
            "close",
        )

        self.assertEqual(value, 225.0)

    def test_run_backtest_preserves_equity_when_a_held_stock_bar_is_missing(self):
        def make_history(code):
            start = dt.date(2025, 1, 1)
            return [
                {
                    "date": (start + dt.timedelta(days=day)).isoformat(),
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 10000.0,
                    "code": code,
                }
                for day in range(145)
            ]

        missing_date = (dt.date(2025, 1, 1) + dt.timedelta(days=130)).isoformat()
        histories = {
            "000001": [row for row in make_history("000001") if row["date"] != missing_date],
            "000002": make_history("000002"),
        }
        params = {**run_loop.DEFAULT_PARAMS, "entry_score": 0.0, "hold_score": 0.0}

        result = run_loop.run_backtest(histories, params)
        equity = {row["date"]: row["equity"] for row in result["equity_curve"]}
        previous_date = (dt.date(2025, 1, 1) + dt.timedelta(days=129)).isoformat()

        self.assertEqual(equity[missing_date], equity[previous_date])

    def test_optimize_params_skips_when_history_cannot_reproduce_live_five_factor_score(self):
        result = run_loop.optimize_params(
            {"000001": []},
            run_loop.DEFAULT_PARAMS,
            comparable_live_inputs=False,
        )

        self.assertEqual(result["status"], "skipped")
        self.assertIn("five-factor", result["reason"])
        self.assertEqual(result["selected_params"], run_loop.DEFAULT_PARAMS)

    def test_board_change_for_industry_preserves_negative_board_signal(self):
        change = run_loop.board_change_for_industry(
            "电力设备",
            {"industry": {"data": [{"groupLabel": "电力设备", "changePct": -3.5}]}},
        )

        self.assertEqual(change, -3.5)

    def test_candidate_params_uses_absolute_risk_threshold_variations(self):
        candidates = run_loop.candidate_params(run_loop.DEFAULT_PARAMS)
        risk_pairs = {
            (item["stop_loss_pct"], item["take_profit_pct"])
            for item in candidates
        }

        self.assertIn((-6.0, 16.0), risk_pairs)
        self.assertIn((-10.0, 22.0), risk_pairs)

    def test_strategy_params_require_complete_strict_bounded_schema(self):
        self.assertEqual(
            run_loop.validate_strategy_params(run_loop.DEFAULT_PARAMS), []
        )

        malformed_values = (True, "1", [], {}, float("nan"), float("inf"))
        numeric_fields = tuple(
            key for key in run_loop.DEFAULT_PARAMS if key != "weights"
        )
        for field in numeric_fields:
            for value in malformed_values:
                with self.subTest(field=field, value=repr(value)):
                    params = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                    params[field] = value
                    self.assertTrue(run_loop.validate_strategy_params(params))

        for field in run_loop.DEFAULT_PARAMS["weights"]:
            for value in malformed_values:
                with self.subTest(weight=field, value=repr(value)):
                    params = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                    params["weights"][field] = value
                    self.assertTrue(run_loop.validate_strategy_params(params))

        for label, mutate in (
            ("missing", lambda value: value.pop("entry_score")),
            ("ma_order", lambda value: value.update(ma_short=60, ma_long=20)),
            ("macd_order", lambda value: value.update(macd_fast=30, macd_slow=12)),
            ("holdings_bound", lambda value: value.update(max_holdings=9)),
            ("weight_bound", lambda value: value.update(max_single_weight=0.16)),
        ):
            with self.subTest(label=label):
                params = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                mutate(params)
                self.assertTrue(run_loop.validate_strategy_params(params))

    def test_commands_return_structured_invalid_params_before_collection(self):
        for case in ("target_corrupt", "account_unsafe"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths = run_loop.loop_paths(workspace)
                params_path = paths["params"] / "strategy_params.json"
                if case == "target_corrupt":
                    params_path.write_text("{corrupt", encoding="utf-8")
                    command_args = target_args(workspace)
                else:
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                        b"image"
                    )
                    (paths["positions"] / "positions.json").write_text(
                        json.dumps(account_positions()), encoding="utf-8"
                    )
                    params = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                    params["max_single_weight"] = 5.0
                    params_path.write_text(json.dumps(params), encoding="utf-8")
                    command_args = run_args(workspace)
                calls = []
                original_collect = run_loop.collect_data
                try:
                    run_loop.collect_data = lambda *args, **kwargs: (
                        calls.append(args) or empty_collected()
                    )
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        result = (
                            run_loop.cmd_analyze_targets(command_args)
                            if case == "target_corrupt"
                            else run_loop.run_loop(command_args)
                        )
                    payload = json.loads(output.getvalue())

                    self.assertEqual(result, 10)
                    self.assertEqual(payload["status"], "invalid_params")
                    self.assertTrue(payload["errors"])
                    self.assertEqual(calls, [])
                    self.assertFalse(
                        (paths["state"] / "loop_state.json").exists()
                    )
                finally:
                    run_loop.collect_data = original_collect

    def test_build_loop_review_marks_first_snapshot_initial(self):
        review = run_loop.build_loop_review(
            None,
            {"snapshot_time": "2026-07-13 09:00:00", "holdings": []},
        )

        self.assertEqual(review["status"], "initial")
        self.assertEqual(review["holding_changes"], [])

    def test_build_loop_review_reconciles_share_decrease_without_claiming_execution(self):
        previous = {
            "snapshot_time": "2026-07-12 09:00:00",
            "holdings": [{"code": "000001", "name": "甲", "shares": 1000}],
            "portfolio_actions": [{"code": "000001", "action": "reduce"}],
        }
        current = {
            "snapshot_time": "2026-07-13 09:00:00",
            "holdings": [{"code": "000001", "name": "甲", "shares": 700}],
        }

        review = run_loop.build_loop_review(previous, current)

        self.assertEqual(review["status"], "reconciled")
        self.assertEqual(review["holding_changes"][0]["kind"], "decreased")
        self.assertEqual(review["action_observations"][0]["observation"], "decrease_observed")
        self.assertNotIn("executed", str(review).lower())

    def test_build_loop_review_marks_matching_snapshot_unchanged(self):
        review = run_loop.build_loop_review(
            {"snapshot_time": "2026-07-13 09:00:00"},
            {"snapshot_time": "2026-07-13 09:00:00", "holdings": []},
        )

        self.assertEqual(review["status"], "unchanged_snapshot")

    def test_build_loop_review_rejects_older_snapshot(self):
        review = run_loop.build_loop_review(
            {"snapshot_time": "2026-07-13 09:00:00"},
            {"snapshot_time": "2026-07-12 09:00:00", "holdings": []},
        )

        self.assertEqual(review["status"], "stale_snapshot")

    def test_run_loop_skips_data_collection_for_an_unchanged_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            screenshot = workspace / "Screenshot_2026-07-13-09-00-00.png"
            screenshot.write_bytes(b"image")
            positions_dir = workspace / ".stock-loop" / "positions"
            positions_dir.mkdir(parents=True)
            positions = {
                "snapshot_time": "2026-07-13 09:00:00",
                "accounts": [{"account": "demo_primary", "cash": 0, "stock_value": 100, "total_assets": 100}],
                "holdings": [
                    {
                        "account": "demo_primary",
                        "code": "000001",
                        "name": "甲",
                        "shares": 10,
                        "cost_price": 10,
                        "last_price": 10,
                        "market_value": 100,
                        "unrealized_pnl": 0,
                    }
                ],
                "cash": 0,
                "stock_value": 100,
                "total_assets": 100,
            }
            (positions_dir / "positions.json").write_text(json.dumps(positions), encoding="utf-8")
            calls = []
            original_collect = run_loop.collect_data
            try:
                empty_collected = run_loop.CollectedData(
                    stock_data={},
                    board_summaries={},
                    board_rankings={},
                    board_details={},
                    indices=[],
                    breadth={},
                    market_news={},
                    latest_trade_date="2026-07-13",
                    errors=[],
                )
                run_loop.collect_data = lambda *args, **kwargs: (calls.append(args) or empty_collected)
                args = type(
                    "Args",
                    (),
                    {
                        "workspace": str(workspace),
                        "loop_dir": ".stock-loop",
                        "positions_json": None,
                        "account": None,
                        "a_share_skill": str(workspace),
                        "years": 3,
                        "start_date": "2023-01-01",
                        "end_date": "2026-07-13",
                        "include_events": False,
                    },
                )()

                self.assertEqual(run_loop.run_loop(args), 0)
                paths = run_loop.loop_paths(workspace)
                state_path = paths["state"] / "loop_state.json"
                history_path = paths["market_history"] / "market_snapshots.jsonl"
                run_dir = paths["runs"] / "2026-07-13-09-00-00"
                self.assertTrue(state_path.exists())
                self.assertTrue(history_path.exists())
                history_before = history_path.read_text(encoding="utf-8")
                state_before = state_path.read_text(encoding="utf-8")
                signal = json.loads(
                    (run_dir / "daily_signal.json").read_text(encoding="utf-8")
                )
                report = (run_dir / "report.md").read_text(encoding="utf-8")
                self.assertEqual(run_loop.validate_signal_v2(signal), [])
                self.assertEqual(
                    len(
                        [
                            line
                            for line in report.splitlines()
                            if line.startswith("## ")
                        ]
                    ),
                    10,
                )
                self.assertEqual(run_loop.run_loop(args), 0)
                self.assertEqual(
                    history_path.read_text(encoding="utf-8"), history_before
                )
                self.assertEqual(
                    state_path.read_text(encoding="utf-8"), state_before
                )
                input_paths = (
                    paths["positions"] / "positions.json",
                    paths["positions"] / "latest_screenshots.json",
                )
                input_bytes = {path: path.read_bytes() for path in input_paths}
                self.assertEqual(run_loop.run_loop(args), 0)
                self.assertEqual(
                    {path: path.read_bytes() for path in input_paths}, input_bytes
                )
                self.assertEqual(len(calls), 1)
            finally:
                run_loop.collect_data = original_collect

    def test_two_account_workspaces_publish_only_inside_their_own_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            workspaces = (parent / "account-one", parent / "account-two")
            accounts = ("demo_one", "demo_two")
            codes = ("000001", "000002")
            original_collect = run_loop.collect_data
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                for workspace, account, code in zip(workspaces, accounts, codes):
                    workspace.mkdir()
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                        b"image"
                    )
                    paths = run_loop.loop_paths(workspace)
                    positions = account_positions()
                    positions["accounts"][0]["account"] = account
                    positions["holdings"][0].update(
                        {"account": account, "code": code}
                    )
                    (paths["positions"] / "positions.json").write_text(
                        json.dumps(positions), encoding="utf-8"
                    )

                    self.assertEqual(run_loop.run_loop(run_args(workspace)), 0)

                self.assertFalse((parent / ".stock-loop").exists())
                for workspace, account, code in zip(workspaces, accounts, codes):
                    paths = run_loop.loop_paths(workspace)
                    state = run_loop.read_json(paths["state"] / "loop_state.json")
                    published = run_loop.read_json(
                        paths["runs"]
                        / "2026-07-15-15-00-00"
                        / "positions.json"
                    )
                    self.assertEqual(state["account"], account)
                    self.assertEqual(state["holdings"][0]["code"], code)
                    self.assertEqual(published["accounts"][0]["account"], account)
                    self.assertEqual(published["holdings"][0]["code"], code)
                    self.assertTrue(
                        Path(state["run_dir"]).resolve().is_relative_to(
                            workspace.resolve()
                        )
                    )
            finally:
                run_loop.collect_data = original_collect

    def test_success_commits_external_inputs_after_report_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
            paths = run_loop.loop_paths(workspace)
            incoming = workspace / "incoming-positions.json"
            incoming.write_text(json.dumps(account_positions()), encoding="utf-8")
            args = run_args(workspace)
            args.positions_json = str(incoming)
            canonical = paths["positions"] / "positions.json"
            manifest = paths["positions"] / "latest_screenshots.json"
            original_report = run_loop.write_report
            observations = []

            def observe_report(*report_args, **report_kwargs):
                observations.append((canonical.exists(), manifest.exists()))
                return original_report(*report_args, **report_kwargs)

            with mock.patch.object(
                run_loop, "collect_data", return_value=empty_collected()
            ), mock.patch.object(run_loop, "write_report", side_effect=observe_report):
                self.assertEqual(run_loop.run_loop(args), 0)

            self.assertEqual(observations, [(False, False)])
            self.assertEqual(
                run_loop.read_json(canonical)["accounts"][0]["account"],
                "demo_primary",
            )
            self.assertEqual(
                run_loop.read_json(manifest)["latest_snapshot_time"],
                "2026-07-15 15:00:00",
            )
            self.assertFalse(run_loop.transaction_journal_path(paths).exists())

    def test_contract_failure_does_not_overwrite_run_history_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            screenshot = workspace / "Screenshot_2026-07-15-15-00-00.png"
            screenshot.write_bytes(b"image")
            paths = run_loop.loop_paths(workspace)
            positions = account_positions()
            (paths["positions"] / "positions.json").write_text(
                json.dumps(positions), encoding="utf-8"
            )
            run_dir = paths["runs"] / "2026-07-15-15-00-00"
            run_dir.mkdir(parents=True)
            report_path = run_dir / "report.md"
            signal_path = run_dir / "daily_signal.json"
            report_path.write_text("sentinel report", encoding="utf-8")
            signal_path.write_text("sentinel signal", encoding="utf-8")
            history_path = paths["market_history"] / "market_snapshots.jsonl"
            history_path.write_text(
                json.dumps(
                    {
                        "trade_date": "2026-07-14",
                        "top_change": [],
                        "top_turnover": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_path = paths["state"] / "loop_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "snapshot_time": "2026-07-14 15:00:00",
                        "holdings": [],
                        "portfolio_actions": [],
                    }
                ),
                encoding="utf-8",
            )
            history_before = history_path.read_bytes()
            state_before = state_path.read_bytes()
            original_collect = run_loop.collect_data
            had_validator = hasattr(run_loop, "validate_signal_v2")
            original_validator = getattr(run_loop, "validate_signal_v2", None)
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.validate_signal_v2 = lambda signal: ["forced contract failure"]

                result = run_loop.run_loop(run_args(workspace))

                self.assertEqual(result, 6)
                self.assertEqual(report_path.read_text(encoding="utf-8"), "sentinel report")
                self.assertEqual(signal_path.read_text(encoding="utf-8"), "sentinel signal")
                self.assertEqual(history_path.read_bytes(), history_before)
                self.assertEqual(state_path.read_bytes(), state_before)
            finally:
                run_loop.collect_data = original_collect
                if had_validator:
                    run_loop.validate_signal_v2 = original_validator
                else:
                    delattr(run_loop, "validate_signal_v2")

    def test_report_write_failure_does_not_mutate_history_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                b"image"
            )
            paths = run_loop.loop_paths(workspace)
            (paths["positions"] / "positions.json").write_text(
                json.dumps(account_positions()), encoding="utf-8"
            )
            history_path = paths["market_history"] / "market_snapshots.jsonl"
            history_path.write_text(
                json.dumps(
                    {
                        "trade_date": "2026-07-14",
                        "top_change": [],
                        "top_turnover": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_path = paths["state"] / "loop_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "snapshot_time": "2026-07-14 15:00:00",
                        "holdings": [],
                        "portfolio_actions": [],
                    }
                ),
                encoding="utf-8",
            )
            current_params_path = paths["params"] / "strategy_params.json"
            current_params_path.write_text(
                json.dumps(run_loop.DEFAULT_PARAMS, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            current_params_before = current_params_path.read_bytes()
            dated_params_path = (
                paths["params"] / "strategy_params_2026-07-15.json"
            )
            history_before = history_path.read_bytes()
            state_before = state_path.read_bytes()
            original_collect = run_loop.collect_data
            original_write_report = run_loop.write_report
            original_optimize = run_loop.optimize_params
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                changed_params = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                changed_params["entry_score"] = 99.0
                run_loop.optimize_params = lambda *args, **kwargs: {
                    "status": "ok",
                    "selected_params": changed_params,
                    "selected_reason": "forced changed params",
                }

                def fail_report(*args, **kwargs):
                    raise OSError("forced report write failure")

                run_loop.write_report = fail_report

                result = run_loop.run_loop(run_args(workspace))

                self.assertEqual(result, 7)
                self.assertEqual(history_path.read_bytes(), history_before)
                self.assertEqual(state_path.read_bytes(), state_before)
                self.assertEqual(
                    current_params_path.read_bytes(), current_params_before
                )
                self.assertFalse(dated_params_path.exists())
                self.assertEqual(list(paths["runs"].iterdir()), [])
                self.assertEqual(list(paths["backtests"].iterdir()), [])
            finally:
                run_loop.collect_data = original_collect
                run_loop.write_report = original_write_report
                run_loop.optimize_params = original_optimize

    def test_precommit_failures_preserve_existing_or_absent_account_inputs(self):
        expected_results = {
            "contract": 6,
            "report": 7,
            "run_json": 11,
            "rename": 11,
            "backtest": 11,
        }
        for input_state in ("existing", "absent"):
            for phase in (*expected_results, "unexpected"):
                with self.subTest(input_state=input_state, phase=phase), tempfile.TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                    paths = run_loop.loop_paths(workspace)
                    canonical_positions = paths["positions"] / "positions.json"
                    manifest_path = paths["positions"] / "latest_screenshots.json"
                    args = run_args(workspace)
                    compact_positions = json.dumps(
                        account_positions(), separators=(",", ":")
                    ).encode("utf-8")
                    if input_state == "existing":
                        canonical_positions.write_bytes(compact_positions)
                        manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                    else:
                        incoming = workspace / "incoming-positions.json"
                        incoming.write_bytes(compact_positions)
                        args.positions_json = str(incoming)
                    before = {
                        path: path.read_bytes() if path.exists() else None
                        for path in (canonical_positions, manifest_path)
                    }
                    original_write_json = run_loop.write_json

                    def fail_selected_json(path, data):
                        original_write_json(path, data)
                        name = Path(path).name
                        if phase == "run_json" and name == "daily_signal.json":
                            raise OSError("forced run JSON failure")
                        if phase == "backtest" and name == "backtest_result_2026-07-15.json":
                            raise OSError("forced backtest failure")

                    with contextlib.ExitStack() as stack:
                        stack.enter_context(
                            mock.patch.object(
                                run_loop,
                                "collect_data",
                                return_value=empty_collected(),
                            )
                        )
                        if phase == "contract":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop,
                                    "validate_signal_v2",
                                    return_value=["forced contract failure"],
                                )
                            )
                        elif phase == "report":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop,
                                    "write_report",
                                    side_effect=OSError("forced report failure"),
                                )
                            )
                        elif phase in ("run_json", "backtest"):
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop,
                                    "write_json",
                                    side_effect=fail_selected_json,
                                )
                            )
                        elif phase == "rename":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop.os,
                                    "rename",
                                    side_effect=OSError("forced final rename failure"),
                                )
                            )
                        elif phase == "unexpected":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop,
                                    "optimize_params",
                                    side_effect=RuntimeError("forced unexpected failure"),
                                )
                            )

                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            if phase == "unexpected":
                                with self.assertRaisesRegex(
                                    RuntimeError, "forced unexpected failure"
                                ):
                                    run_loop.run_loop(args)
                            else:
                                self.assertEqual(
                                    run_loop.run_loop(args), expected_results[phase]
                                )

                    for path, original_bytes in before.items():
                        if original_bytes is None:
                            self.assertFalse(path.exists(), path)
                        else:
                            self.assertEqual(path.read_bytes(), original_bytes)
                    self.assertEqual(list(paths["runs"].iterdir()), [])
                    self.assertEqual(list(paths["backtests"].iterdir()), [])
                    self.assertFalse(run_loop.transaction_journal_path(paths).exists())

    def test_account_input_artifact_failures_roll_back_after_collection(self):
        for input_state in ("existing", "absent"):
            for failed_name in ("latest_screenshots.json", "positions.json"):
                with self.subTest(input_state=input_state, failed_name=failed_name), tempfile.TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                    paths = run_loop.loop_paths(workspace)
                    positions_path = paths["positions"] / "positions.json"
                    manifest_path = paths["positions"] / "latest_screenshots.json"
                    args = run_args(workspace)
                    compact_positions = json.dumps(
                        account_positions(), separators=(",", ":")
                    ).encode("utf-8")
                    if input_state == "existing":
                        positions_path.write_bytes(compact_positions)
                        manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                    else:
                        incoming = workspace / "incoming-positions.json"
                        incoming.write_bytes(compact_positions)
                        args.positions_json = str(incoming)
                    before = {
                        path: path.read_bytes() if path.exists() else None
                        for path in (positions_path, manifest_path)
                    }
                    original_write_json = run_loop.write_json
                    original_collect = run_loop.collect_data
                    collect_calls = []

                    def fail_after_write(path, data):
                        original_write_json(path, data)
                        if Path(path) == paths["positions"] / failed_name:
                            raise OSError(f"forced {failed_name} failure")

                    try:
                        run_loop.write_json = fail_after_write
                        run_loop.collect_data = lambda *args, **kwargs: (
                            collect_calls.append(args) or empty_collected()
                        )
                        output = io.StringIO()

                        with contextlib.redirect_stdout(output):
                            result = run_loop.run_loop(args)

                        payload = json.loads(output.getvalue())
                        self.assertEqual(result, 11)
                        self.assertEqual(payload["status"], "artifact_write_failed")
                        self.assertEqual(payload["rollback_errors"], [])
                        self.assertEqual(len(collect_calls), 1)
                        for path, original_bytes in before.items():
                            if original_bytes is None:
                                self.assertFalse(path.exists(), path)
                            else:
                                self.assertEqual(path.read_bytes(), original_bytes)
                        self.assertEqual(list(paths["runs"].iterdir()), [])
                        self.assertEqual(list(paths["backtests"].iterdir()), [])
                        self.assertFalse(run_loop.transaction_journal_path(paths).exists())
                    finally:
                        run_loop.write_json = original_write_json
                        run_loop.collect_data = original_collect

    def test_account_output_artifact_failures_publish_no_partial_run(self):
        for failed_name in ("daily_signal.json", "backtest_result_2026-07-15.json"):
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                paths = run_loop.loop_paths(workspace)
                positions_path = paths["positions"] / "positions.json"
                positions_path.write_text(
                    json.dumps(account_positions()), encoding="utf-8"
                )
                original_write_json = run_loop.write_json
                original_collect = run_loop.collect_data

                def fail_after_write(path, data):
                    original_write_json(path, data)
                    if Path(path).name == failed_name:
                        raise OSError(f"forced {failed_name} failure")

                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    run_loop.write_json = fail_after_write
                    output = io.StringIO()

                    with contextlib.redirect_stdout(output):
                        result = run_loop.run_loop(run_args(workspace))

                    payload = json.loads(output.getvalue())
                    self.assertEqual(result, 11)
                    self.assertEqual(payload["status"], "artifact_write_failed")
                    self.assertEqual(payload["cleanup_errors"], [])
                    self.assertEqual(list(paths["runs"].iterdir()), [])
                    self.assertEqual(list(paths["backtests"].iterdir()), [])
                    self.assertFalse((paths["state"] / "loop_state.json").exists())
                finally:
                    run_loop.write_json = original_write_json
                    run_loop.collect_data = original_collect

    def test_keyboard_interrupt_during_staged_signal_write_cleans_everything(self):
        for input_state in ("existing", "absent"):
            with self.subTest(input_state=input_state), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                paths = run_loop.loop_paths(workspace)
                positions_path = paths["positions"] / "positions.json"
                manifest_path = paths["positions"] / "latest_screenshots.json"
                args = run_args(workspace)
                if input_state == "existing":
                    positions_path.write_bytes(
                        json.dumps(account_positions(), separators=(",", ":")).encode("utf-8")
                    )
                    manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                else:
                    incoming = workspace / "incoming-positions.json"
                    incoming.write_text(json.dumps(account_positions()), encoding="utf-8")
                    args.positions_json = str(incoming)
                before = {
                    path: path.read_bytes() if path.exists() else None
                    for path in (positions_path, manifest_path)
                }
                original_write_json = run_loop.write_json

                def interrupt_after_signal_write(path, data):
                    original_write_json(path, data)
                    if Path(path).name == "daily_signal.json":
                        raise KeyboardInterrupt("forced staged signal interrupt")

                caught = None
                output = io.StringIO()
                with mock.patch.object(run_loop, "collect_data", return_value=empty_collected()), mock.patch.object(
                    run_loop, "write_json", side_effect=interrupt_after_signal_write
                ), contextlib.redirect_stdout(output):
                    try:
                        result = run_loop.run_loop(args)
                    except BaseException as exc:
                        caught = exc
                        result = None

                self.assertIsNone(caught)
                self.assertEqual(result, 11)
                self.assertEqual(json.loads(output.getvalue())["status"], "artifact_write_failed")
                self.assertEqual(list(paths["runs"].iterdir()), [])
                self.assertEqual(list(paths["backtests"].iterdir()), [])
                self.assertFalse(run_loop.transaction_journal_path(paths).exists())
                for path, original_bytes in before.items():
                    if original_bytes is None:
                        self.assertFalse(path.exists(), path)
                    else:
                        self.assertEqual(path.read_bytes(), original_bytes)

    def test_keyboard_interrupt_during_backtest_write_cleans_published_run(self):
        for input_state in ("existing", "absent"):
            with self.subTest(input_state=input_state), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                paths = run_loop.loop_paths(workspace)
                positions_path = paths["positions"] / "positions.json"
                manifest_path = paths["positions"] / "latest_screenshots.json"
                args = run_args(workspace)
                if input_state == "existing":
                    positions_path.write_bytes(
                        json.dumps(account_positions(), separators=(",", ":")).encode("utf-8")
                    )
                    manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                else:
                    incoming = workspace / "incoming-positions.json"
                    incoming.write_text(json.dumps(account_positions()), encoding="utf-8")
                    args.positions_json = str(incoming)
                before = {
                    path: path.read_bytes() if path.exists() else None
                    for path in (positions_path, manifest_path)
                }
                backtest_path = paths["backtests"] / "backtest_result_2026-07-15.json"
                original_write_json = run_loop.write_json

                def interrupt_after_backtest_write(path, data):
                    original_write_json(path, data)
                    if Path(path) == backtest_path:
                        raise KeyboardInterrupt("forced backtest interrupt")

                caught = None
                output = io.StringIO()
                with mock.patch.object(run_loop, "collect_data", return_value=empty_collected()), mock.patch.object(
                    run_loop, "write_json", side_effect=interrupt_after_backtest_write
                ), contextlib.redirect_stdout(output):
                    try:
                        result = run_loop.run_loop(args)
                    except BaseException as exc:
                        caught = exc
                        result = None

                self.assertIsNone(caught)
                self.assertEqual(result, 11)
                self.assertEqual(json.loads(output.getvalue())["status"], "artifact_write_failed")
                self.assertEqual(list(paths["runs"].iterdir()), [])
                self.assertEqual(list(paths["backtests"].iterdir()), [])
                self.assertFalse(run_loop.transaction_journal_path(paths).exists())
                for path, original_bytes in before.items():
                    if original_bytes is None:
                        self.assertFalse(path.exists(), path)
                    else:
                        self.assertEqual(path.read_bytes(), original_bytes)

    def test_keyboard_interrupt_prejournal_boundary_matrix_cleans_all_artifacts(self):
        phases = (
            "allocate_staging",
            "write_report",
            "publish_rename",
            "publish_fsync",
            "optimization_write",
            "cleanup_staging",
            "restore_backtests",
        )
        for input_state in ("existing", "absent"):
            for phase in phases:
                with self.subTest(input_state=input_state, phase=phase), tempfile.TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                    paths = run_loop.loop_paths(workspace)
                    positions_path = paths["positions"] / "positions.json"
                    manifest_path = paths["positions"] / "latest_screenshots.json"
                    args = run_args(workspace)
                    if input_state == "existing":
                        positions_path.write_bytes(
                            json.dumps(account_positions(), separators=(",", ":")).encode("utf-8")
                        )
                        manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                    else:
                        incoming = workspace / "incoming-positions.json"
                        incoming.write_text(json.dumps(account_positions()), encoding="utf-8")
                        args.positions_json = str(incoming)
                    before = {
                        path: path.read_bytes() if path.exists() else None
                        for path in (positions_path, manifest_path)
                    }
                    optimization_path = paths["backtests"] / "optimization_2026-07-15.json"
                    original_mkdir = Path.mkdir
                    original_write_json = run_loop.write_json
                    original_rename = run_loop.os.rename
                    original_fsync = run_loop.fsync_directory
                    original_cleanup = run_loop.cleanup_output_entry
                    original_restore = run_loop.restore_file_bytes
                    cleanup_interrupts = 0
                    restore_interrupts = 0
                    fsync_interrupts = 0

                    def interrupt_after_staging_mkdir(path, *positional, **keywords):
                        result = original_mkdir(path, *positional, **keywords)
                        candidate = Path(path)
                        if candidate.parent == paths["runs"] and ".staging" in candidate.name:
                            raise KeyboardInterrupt("forced staging allocation interrupt")
                        return result

                    def interrupt_selected_json(path, data):
                        original_write_json(path, data)
                        target = Path(path)
                        if phase == "optimization_write" and target == optimization_path:
                            raise KeyboardInterrupt("forced optimization interrupt")
                        if phase == "cleanup_staging" and target.name == "daily_signal.json":
                            raise OSError("forced staging write failure")
                        if phase == "restore_backtests" and target == optimization_path:
                            raise KeyboardInterrupt("forced restore-path interrupt")

                    def interrupt_after_publish_rename(source, destination):
                        original_rename(source, destination)
                        if Path(source).parent == paths["runs"]:
                            raise KeyboardInterrupt("forced publish rename interrupt")

                    def interrupt_publish_fsync_once(path):
                        nonlocal fsync_interrupts
                        if Path(path) == paths["runs"] and fsync_interrupts == 0:
                            fsync_interrupts += 1
                            raise KeyboardInterrupt("forced publish fsync interrupt")
                        return original_fsync(path)

                    def interrupt_cleanup_once(path):
                        nonlocal cleanup_interrupts
                        if cleanup_interrupts == 0:
                            cleanup_interrupts += 1
                            raise KeyboardInterrupt("forced cleanup interrupt")
                        return original_cleanup(path)

                    def interrupt_restore_once(path, original):
                        nonlocal restore_interrupts
                        if restore_interrupts == 0:
                            restore_interrupts += 1
                            raise KeyboardInterrupt("forced restore interrupt")
                        return original_restore(path, original)

                    output = io.StringIO()
                    caught = None
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(
                            mock.patch.object(run_loop, "collect_data", return_value=empty_collected())
                        )
                        if phase == "allocate_staging":
                            stack.enter_context(mock.patch.object(Path, "mkdir", new=interrupt_after_staging_mkdir))
                        elif phase == "write_report":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop,
                                    "write_report",
                                    side_effect=KeyboardInterrupt("forced report interrupt"),
                                )
                            )
                        elif phase == "publish_rename":
                            stack.enter_context(
                                mock.patch.object(run_loop.os, "rename", new=interrupt_after_publish_rename)
                            )
                        elif phase == "publish_fsync":
                            stack.enter_context(
                                mock.patch.object(run_loop, "fsync_directory", new=interrupt_publish_fsync_once)
                            )
                        elif phase in (
                            "optimization_write",
                            "cleanup_staging",
                            "restore_backtests",
                        ):
                            stack.enter_context(
                                mock.patch.object(run_loop, "write_json", side_effect=interrupt_selected_json)
                            )
                        if phase == "cleanup_staging":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop, "cleanup_output_entry", side_effect=interrupt_cleanup_once
                                )
                            )
                        elif phase == "restore_backtests":
                            stack.enter_context(
                                mock.patch.object(
                                    run_loop, "restore_file_bytes", side_effect=interrupt_restore_once
                                )
                            )

                        with contextlib.redirect_stdout(output):
                            try:
                                result = run_loop.run_loop(args)
                            except BaseException as exc:
                                caught = exc
                                result = None

                    self.assertIsNone(caught)
                    expected_result = 7 if phase == "write_report" else 11
                    expected_status = (
                        "report_write_failed" if phase == "write_report" else "artifact_write_failed"
                    )
                    self.assertEqual(result, expected_result)
                    self.assertEqual(json.loads(output.getvalue())["status"], expected_status)
                    self.assertEqual(list(paths["runs"].iterdir()), [])
                    self.assertEqual(list(paths["backtests"].iterdir()), [])
                    self.assertFalse(run_loop.transaction_journal_path(paths).exists())
                    for path, original_bytes in before.items():
                        if original_bytes is None:
                            self.assertFalse(path.exists(), path)
                        else:
                            self.assertEqual(path.read_bytes(), original_bytes)

    def test_final_directory_rename_failures_are_structured_and_leave_no_staging(self):
        for command in ("target", "account"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths = run_loop.loop_paths(workspace)
                if command == "account":
                    (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(
                        b"image"
                    )
                    (paths["positions"] / "positions.json").write_text(
                        json.dumps(account_positions()), encoding="utf-8"
                    )
                original_collect = run_loop.collect_data
                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    output = io.StringIO()
                    with mock.patch.object(
                        run_loop.os,
                        "rename",
                        side_effect=OSError("forced final rename failure"),
                    ), contextlib.redirect_stdout(output):
                        result = (
                            run_loop.cmd_analyze_targets(target_args(workspace))
                            if command == "target"
                            else run_loop.run_loop(run_args(workspace))
                        )

                    payload = json.loads(output.getvalue())
                    self.assertEqual(result, 11)
                    self.assertEqual(payload["status"], "artifact_write_failed")
                    output_parent = (
                        paths["analyses"] if command == "target" else paths["runs"]
                    )
                    self.assertEqual(list(output_parent.iterdir()), [])
                finally:
                    run_loop.collect_data = original_collect

    def test_parse_target_codes_normalizes_and_deduplicates(self):
        self.assertEqual(
            run_loop.parse_target_codes("sz000001，600000,000001"),
            ["000001", "600000"],
        )

    def test_parse_target_codes_rejects_non_six_digit_input(self):
        with self.assertRaisesRegex(ValueError, "invalid A-share code"):
            run_loop.parse_target_codes("1")

    def test_build_target_positions_preserves_held_target_and_marks_missing_code_research_only(self):
        source = {
            "snapshot_time": "2026-07-13 09:00:00",
            "total_assets": 1000,
            "holdings": [
                {
                    "account": "demo_primary",
                    "code": "000001",
                    "name": "甲",
                    "shares": 100,
                    "market_value": 100,
                }
            ],
        }

        targets = run_loop.build_target_positions(["000001", "600000"], source)

        self.assertEqual(targets["total_assets"], 1000)
        self.assertEqual(targets["holdings"][0]["shares"], 100)
        self.assertEqual(targets["research_only_codes"], ["600000"])

    def test_build_target_positions_preserves_only_exact_boolean_asset_coverage_flags(self):
        source = {
            "cash_unreadable": True,
            "total_assets_lower_bound": False,
            "holdings": [],
        }

        targets = run_loop.build_target_positions(["600000"], source)

        self.assertIs(targets.get("cash_unreadable"), True)
        self.assertIs(targets.get("total_assets_lower_bound"), False)
        for field in ("cash_unreadable", "total_assets_lower_bound"):
            for value in ("true", 1, 1.0):
                with self.subTest(field=field, value=value):
                    non_boolean = run_loop.build_target_positions(
                        ["600000"], {field: value, "holdings": []}
                    )
                    self.assertNotIn(field, non_boolean)

    def test_incomplete_account_target_subsets_use_full_visible_account_denominator(self):
        values = {
            "000101": 2614,
            "000001": 1500,
            "000002": 1400,
            "000003": 1300,
            "000004": 1100,
            "000005": 900,
            "000006": 700,
            "000007": 486,
        }
        source = {
            "cash_unreadable": True,
            "total_assets": 10000,
            "stock_value": 10000,
            "holdings": [
                {"code": code, "name": code, "market_value": market_value}
                for code, market_value in values.items()
            ],
        }

        single = run_loop.build_target_positions(["000101"], source)
        partial = run_loop.build_target_positions(
            ["000101", "000001"], source
        )
        full = run_loop.build_target_positions(list(values), source)

        self.assertEqual(single.get("visible_account_stock_value"), 10000.0)
        single_diagnosis = run_loop.build_portfolio_diagnosis(
            single, [], [], []
        )
        partial_diagnosis = run_loop.build_portfolio_diagnosis(
            partial, [], [], []
        )
        full_diagnosis = run_loop.build_portfolio_diagnosis(full, [], [], [])
        self.assertEqual(
            single_diagnosis["single_stock_concentration"][0]["weight"],
            0.2614,
        )
        self.assertEqual(
            [row["weight"] for row in partial_diagnosis["single_stock_concentration"]],
            [0.2614, 0.15],
        )
        self.assertAlmostEqual(
            sum(row["weight"] for row in full_diagnosis["single_stock_concentration"]),
            1.0,
        )
        self.assertIn(
            "完整可见账户持仓市值",
            single_diagnosis["asset_coverage_note"],
        )

        complete_source = {**source, "cash_unreadable": False}
        complete = run_loop.build_target_positions(["000101"], complete_source)
        self.assertNotIn("visible_account_stock_value", complete)
        complete_diagnosis = run_loop.build_portfolio_diagnosis(
            complete,
            [],
            [{"code": "000101", "current_weight": 0.2614}],
            [],
        )
        self.assertEqual(complete_diagnosis["stock_exposure"], 0.2614)
        self.assertEqual(complete_diagnosis["cash_weight"], 0.7386)
        self.assertNotIn("asset_coverage_note", complete_diagnosis)

    def test_parser_accepts_analyze_targets(self):
        args = run_loop.build_parser().parse_args(["analyze-targets", "--codes", "000001,600000"])

        self.assertEqual(args.codes, "000001,600000")

    def test_research_action_for_target_is_watch_with_zero_weight(self):
        action = run_loop.research_action_for_target(
            {"code": "600000", "name": "600000"},
            {"ma_short": 10, "ma_long": 9},
            run_loop.DEFAULT_PARAMS,
        )

        self.assertEqual(action["action"], "watch")
        self.assertEqual(action["target_weight"], 0.0)

    def test_analyze_targets_writes_isolated_research_output_without_loop_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []
            original_collect = run_loop.collect_data
            try:
                empty_collected = run_loop.CollectedData(
                    stock_data={},
                    board_summaries={},
                    board_rankings={},
                    board_details={},
                    indices=[],
                    breadth={},
                    market_news={},
                    latest_trade_date="2026-07-13",
                    errors=[],
                )
                run_loop.collect_data = lambda *args, **kwargs: (calls.append(args) or empty_collected)
                args = type(
                    "Args",
                    (),
                    {
                        "workspace": str(workspace),
                        "loop_dir": ".stock-loop",
                        "codes": "600000",
                        "positions_json": None,
                        "account": None,
                        "a_share_skill": str(workspace),
                        "years": 3,
                        "start_date": "2023-01-01",
                        "end_date": "2026-07-13",
                        "include_events": False,
                    },
                )()

                self.assertEqual(run_loop.cmd_analyze_targets(args), 0)
                analyses = list((workspace / ".stock-loop" / "analyses").iterdir())
                self.assertEqual(len(analyses), 1)
                self.assertTrue((analyses[0] / "analysis.md").exists())
                signal = json.loads(
                    (analyses[0] / "signal.json").read_text(encoding="utf-8")
                )
                report = (analyses[0] / "analysis.md").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(run_loop.validate_signal_v2(signal), [])
                self.assertEqual(signal["report_schema_version"], 2)
                self.assertEqual(
                    len(
                        [
                            line
                            for line in report.splitlines()
                            if line.startswith("## ")
                        ]
                    ),
                    10,
                )
                self.assertTrue(
                    all(
                        action["action"] == "watch"
                        and action["target_weight"] == 0
                        for action in signal["portfolio_actions"]
                    )
                )
                self.assertFalse((workspace / ".stock-loop" / "state" / "loop_state.json").exists())
                self.assertFalse(
                    (
                        workspace
                        / ".stock-loop"
                        / "params"
                        / "strategy_params.json"
                    ).exists()
                )
                self.assertEqual(
                    list((workspace / ".stock-loop" / "market-history").glob("*")),
                    [],
                )
                self.assertEqual(len(calls), 1)
            finally:
                run_loop.collect_data = original_collect

    def test_target_research_does_not_modify_existing_params_state_or_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = run_loop.loop_paths(workspace)
            tracked = (
                paths["params"] / "strategy_params.json",
                paths["state"] / "loop_state.json",
                paths["market_history"] / "market_snapshots.jsonl",
            )
            tracked[0].write_text(
                json.dumps(run_loop.DEFAULT_PARAMS), encoding="utf-8"
            )
            tracked[1].write_text(
                json.dumps({"snapshot_time": "2026-01-01 15:00:00"}),
                encoding="utf-8",
            )
            tracked[2].write_text(
                json.dumps({
                    "trade_date": "2026-01-01",
                    "top_change": [],
                    "top_turnover": [],
                }) + "\n",
                encoding="utf-8",
            )
            before = {path: path.read_bytes() for path in tracked}
            original_collect = run_loop.collect_data
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()

                self.assertEqual(
                    run_loop.cmd_analyze_targets(target_args(workspace)), 0
                )

                self.assertEqual(
                    {path: path.read_bytes() for path in tracked}, before
                )
            finally:
                run_loop.collect_data = original_collect

    def test_target_contract_failure_writes_no_analysis_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original_collect = run_loop.collect_data
            had_validator = hasattr(run_loop, "validate_signal_v2")
            original_validator = getattr(run_loop, "validate_signal_v2", None)
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.validate_signal_v2 = lambda signal: ["forced contract failure"]
                args = type(
                    "Args",
                    (),
                    {
                        "workspace": str(workspace),
                        "loop_dir": ".stock-loop",
                        "codes": "600000",
                        "positions_json": None,
                        "account": None,
                        "a_share_skill": str(workspace),
                        "years": 3,
                        "start_date": "2023-01-01",
                        "end_date": "2026-07-15",
                        "include_events": False,
                    },
                )()

                result = run_loop.cmd_analyze_targets(args)

                paths = run_loop.loop_paths(workspace)
                self.assertEqual(result, 6)
                self.assertEqual(list(paths["analyses"].iterdir()), [])
                self.assertFalse(
                    (paths["market_history"] / "market_snapshots.jsonl").exists()
                )
                self.assertFalse((paths["state"] / "loop_state.json").exists())
            finally:
                run_loop.collect_data = original_collect
                if had_validator:
                    run_loop.validate_signal_v2 = original_validator
                else:
                    delattr(run_loop, "validate_signal_v2")

    def test_target_report_failure_returns_seven_and_cleans_partial_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original_collect = run_loop.collect_data
            original_write_report = run_loop.write_report
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()

                def fail_report(path, *args, **kwargs):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("partial report", encoding="utf-8")
                    raise OSError("forced target report failure")

                run_loop.write_report = fail_report
                args = type(
                    "Args",
                    (),
                    {
                        "workspace": str(workspace),
                        "loop_dir": ".stock-loop",
                        "codes": "600000",
                        "positions_json": None,
                        "account": None,
                        "a_share_skill": str(workspace),
                        "years": 3,
                        "start_date": "2023-01-01",
                        "end_date": "2026-07-15",
                        "include_events": False,
                    },
                )()

                result = run_loop.cmd_analyze_targets(args)

                paths = run_loop.loop_paths(workspace)
                self.assertEqual(result, 7)
                self.assertEqual(list(paths["analyses"].iterdir()), [])
                self.assertFalse(
                    (paths["market_history"] / "market_snapshots.jsonl").exists()
                )
                self.assertFalse((paths["state"] / "loop_state.json").exists())
            finally:
                run_loop.collect_data = original_collect
                run_loop.write_report = original_write_report

    def test_target_json_failures_return_artifact_error_and_publish_nothing(self):
        for failed_name in ("signal.json", "analysis_manifest.json"):
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                original_collect = run_loop.collect_data
                original_write_json = run_loop.write_json

                def fail_after_write(path, data):
                    original_write_json(path, data)
                    if Path(path).name == failed_name:
                        raise OSError(f"forced {failed_name} failure")

                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    run_loop.write_json = fail_after_write
                    output = io.StringIO()

                    with contextlib.redirect_stdout(output):
                        result = run_loop.cmd_analyze_targets(target_args(workspace))

                    paths = run_loop.loop_paths(workspace)
                    payload = json.loads(output.getvalue())
                    self.assertEqual(result, 11)
                    self.assertEqual(payload["status"], "artifact_write_failed")
                    self.assertEqual(payload["cleanup_errors"], [])
                    self.assertEqual(list(paths["analyses"].iterdir()), [])
                finally:
                    run_loop.collect_data = original_collect
                    run_loop.write_json = original_write_json

    def test_target_fixed_clock_second_success_uses_new_directory_without_modifying_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original_collect = run_loop.collect_data
            original_datetime = run_loop.dt.datetime

            class FixedDateTime(original_datetime):
                @classmethod
                def now(cls, tz=None):
                    value = cls(2026, 7, 15, 12, 34, 56)
                    return value if tz is None else value.replace(tzinfo=tz)

            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.dt.datetime = FixedDateTime

                self.assertEqual(run_loop.cmd_analyze_targets(target_args(workspace)), 0)
                paths = run_loop.loop_paths(workspace)
                base = paths["analyses"] / "2026-07-15-12-34-56-600000"
                first_report = (base / "analysis.md").read_bytes()

                self.assertEqual(run_loop.cmd_analyze_targets(target_args(workspace)), 0)

                self.assertEqual((base / "analysis.md").read_bytes(), first_report)
                self.assertTrue(
                    (paths["analyses"] / "2026-07-15-12-34-56-600000-2" / "analysis.md").is_file()
                )
            finally:
                run_loop.collect_data = original_collect
                run_loop.dt.datetime = original_datetime

    def test_target_base_path_file_is_preserved_and_suffix_directory_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = run_loop.loop_paths(workspace)
            base = paths["analyses"] / "2026-07-15-12-34-56-600000"
            base.write_bytes(b"existing-base-file")
            original_collect = run_loop.collect_data
            original_datetime = run_loop.dt.datetime

            class FixedDateTime(original_datetime):
                @classmethod
                def now(cls, tz=None):
                    value = cls(2026, 7, 15, 12, 34, 56)
                    return value if tz is None else value.replace(tzinfo=tz)

            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.dt.datetime = FixedDateTime

                result = run_loop.cmd_analyze_targets(target_args(workspace))

                self.assertEqual(result, 0)
                self.assertEqual(base.read_bytes(), b"existing-base-file")
                self.assertTrue(
                    (paths["analyses"] / "2026-07-15-12-34-56-600000-2" / "analysis.md").is_file()
                )
            finally:
                run_loop.collect_data = original_collect
                run_loop.dt.datetime = original_datetime

    def test_target_allocator_retries_past_multiple_existing_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = run_loop.loop_paths(workspace)
            base_name = "2026-07-15-12-34-56-600000"
            old_files = {}
            for name in (base_name, f"{base_name}-2"):
                directory = paths["analyses"] / name
                directory.mkdir()
                report = directory / "analysis.md"
                report.write_bytes(name.encode("ascii"))
                old_files[report] = report.read_bytes()
            original_collect = run_loop.collect_data
            original_datetime = run_loop.dt.datetime

            class FixedDateTime(original_datetime):
                @classmethod
                def now(cls, tz=None):
                    value = cls(2026, 7, 15, 12, 34, 56)
                    return value if tz is None else value.replace(tzinfo=tz)

            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.dt.datetime = FixedDateTime

                result = run_loop.cmd_analyze_targets(target_args(workspace))

                self.assertEqual(result, 0)
                for report, original_bytes in old_files.items():
                    self.assertEqual(report.read_bytes(), original_bytes)
                self.assertTrue(
                    (paths["analyses"] / f"{base_name}-3" / "analysis.md").is_file()
                )
            finally:
                run_loop.collect_data = original_collect
                run_loop.dt.datetime = original_datetime

    def test_target_report_failure_cleans_analysis_md_directory_without_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            original_collect = run_loop.collect_data
            original_write_report = run_loop.write_report
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()

                def fail_with_report_directory(path, *args, **kwargs):
                    path.mkdir()
                    (path / "partial.txt").write_text("partial", encoding="utf-8")
                    raise OSError("forced directory-shaped target report failure")

                run_loop.write_report = fail_with_report_directory

                result = run_loop.cmd_analyze_targets(target_args(workspace))

                paths = run_loop.loop_paths(workspace)
                self.assertEqual(result, 7)
                self.assertEqual(list(paths["analyses"].iterdir()), [])
            finally:
                run_loop.collect_data = original_collect
                run_loop.write_report = original_write_report

    @unittest.skipUnless(os.name == "nt", "Windows junction semantics")
    def test_target_report_failure_removes_junction_without_touching_external_target(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                external = workspace / "external-target"
                external.mkdir()
                sentinel = external / "sentinel.bin"
                if not dangling:
                    sentinel.write_bytes(b"external-bytes")
                original_collect = run_loop.collect_data
                original_write_report = run_loop.write_report
                junction_path = None
                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()

                    def fail_with_junction(path, *args, **kwargs):
                        nonlocal junction_path
                        junction_path = path.parent
                        junction_path.rmdir()
                        created = subprocess.run(
                            [
                                "cmd",
                                "/d",
                                "/c",
                                "mklink",
                                "/J",
                                str(junction_path),
                                str(external),
                            ],
                            capture_output=True,
                            text=True,
                        )
                        if created.returncode != 0:
                            raise RuntimeError(
                                f"unable to create junction: {created.stdout} {created.stderr}"
                            )
                        if dangling:
                            external.rmdir()
                        raise OSError("forced target report failure with junction")

                    run_loop.write_report = fail_with_junction
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = run_loop.cmd_analyze_targets(target_args(workspace))

                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(result, 7)
                    self.assertEqual(payload["status"], "report_write_failed")
                    self.assertEqual(payload["cleanup_errors"], [])
                    self.assertIsNotNone(junction_path)
                    with self.assertRaises(FileNotFoundError):
                        os.lstat(str(junction_path))
                    if not dangling:
                        self.assertEqual(sentinel.read_bytes(), b"external-bytes")
                finally:
                    run_loop.collect_data = original_collect
                    run_loop.write_report = original_write_report

    def test_direct_market_history_filters_future_malformed_and_missing_latest_date(self):
        inputs = comprehensive_market_inputs()
        identity = run_loop.board_identity("concept", "robotics")
        inputs["market_history"] = [
            None,
            7,
            {"trade_date": "2026-07-12", "top_change": identity, "top_turnover": []},
            {"trade_date": "2026-07-13", "top_change": ["not-canonical"], "top_turnover": []},
            {"trade_date": "2026-07-16", "top_change": [identity], "top_turnover": []},
            {"trade_date": "2026-07-17", "top_change": [identity], "top_turnover": []},
            {"trade_date": "2026-07-18", "top_change": [identity], "top_turnover": []},
        ]

        signal = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        line = signal["market_mainlines"][0]
        self.assertFalse(line["continuity"]["known"])
        self.assertEqual(line["continuity"]["hits"], 0)
        self.assertNotEqual(line["classification"], "confirmed_mainline")
        self.assertEqual(signal["data_coverage"]["mainline_history_sessions"], 0)

        inputs["latest_trade_date"] = ""
        inputs["market_history"] = [
            {
                "trade_date": date,
                "top_change": [identity],
                "top_turnover": [],
            }
            for date in ("2026-07-12", "2026-07-13", "2026-07-14")
        ]
        no_latest = run_loop.generate_daily_signal(
            account_positions(),
            {},
            {"regime": "risk_on"},
            {},
            inputs["normalized_indices"],
            {},
            [],
            run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )
        line = no_latest["market_mainlines"][0]
        self.assertFalse(line["continuity"]["known"])
        self.assertEqual(line["continuity"]["hits"], 0)
        self.assertNotEqual(line["classification"], "confirmed_mainline")
        self.assertEqual(no_latest["data_coverage"]["mainline_history_sessions"], 0)

    def test_persistence_failures_roll_back_all_files_then_retry_from_original_inputs(self):
        phases = (
            ("dated_params", True),
            ("current_params", True),
            ("history", True),
            ("state_after_history", True),
            ("state_same_params", False),
        )
        for phase, change_params in phases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                paths = run_loop.loop_paths(workspace)
                positions_path = paths["positions"] / "positions.json"
                positions_path.write_text(
                    json.dumps(account_positions()), encoding="utf-8"
                )
                manifest_path = paths["positions"] / "latest_screenshots.json"
                manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                current_params_path = paths["params"] / "strategy_params.json"
                current_params_path.write_text(
                    json.dumps(run_loop.DEFAULT_PARAMS, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                dated_params_path = paths["params"] / "strategy_params_2026-07-15.json"
                history_path = paths["market_history"] / "market_snapshots.jsonl"
                history_path.write_text(
                    json.dumps(
                        {
                            "trade_date": "2026-07-14",
                            "top_change": [],
                            "top_turnover": [],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                state_path = paths["state"] / "loop_state.json"
                state_path.write_text(
                    json.dumps(
                        {
                            "snapshot_time": "2026-07-14 15:00:00",
                            "holdings": [],
                            "portfolio_actions": [],
                        }
                    ),
                    encoding="utf-8",
                )
                tracked = (
                    dated_params_path,
                    current_params_path,
                    history_path,
                    state_path,
                    positions_path,
                    manifest_path,
                )
                before = {
                    path: path.read_bytes() if path.exists() else None
                    for path in tracked
                }
                original_collect = run_loop.collect_data
                original_optimize = run_loop.optimize_params
                original_write_json = run_loop.write_json
                original_append = run_loop.append_market_snapshot
                seen_params = []
                changed = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                changed["entry_score"] = 99.0

                def optimize(histories, params, **kwargs):
                    seen_params.append(json.loads(json.dumps(params)))
                    return {
                        "status": "ok",
                        "selected_params": changed if change_params else params,
                        "selected_reason": "fixture",
                    }

                def failing_write(path, data):
                    path = Path(path)
                    if phase == "dated_params" and path == dated_params_path:
                        original_write_json(path, data)
                        raise OSError("forced dated params failure")
                    if phase == "current_params" and path == current_params_path:
                        original_write_json(path, data)
                        raise OSError("forced current params failure")
                    if phase.startswith("state_") and path == state_path:
                        original_write_json(path, data)
                        raise OSError("forced state failure after write")
                    return original_write_json(path, data)

                def failing_append(path, row):
                    original_append(path, row)
                    raise OSError("forced history failure after write")

                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    run_loop.optimize_params = optimize
                    run_loop.write_json = failing_write
                    if phase == "history":
                        run_loop.append_market_snapshot = failing_append

                    self.assertEqual(run_loop.run_loop(run_args(workspace)), 8)

                    for path, original_bytes in before.items():
                        if original_bytes is None:
                            self.assertFalse(path.exists())
                        else:
                            self.assertEqual(path.read_bytes(), original_bytes)

                    run_loop.write_json = original_write_json
                    run_loop.append_market_snapshot = original_append

                    self.assertEqual(run_loop.run_loop(run_args(workspace)), 0)
                    self.assertEqual(seen_params, [run_loop.DEFAULT_PARAMS, run_loop.DEFAULT_PARAMS])
                    stored_history = run_loop.load_market_history(history_path)
                    self.assertEqual(
                        sum(row["trade_date"] == "2026-07-15" for row in stored_history),
                        1,
                    )
                    if change_params:
                        self.assertEqual(run_loop.read_json(current_params_path), changed)
                        self.assertEqual(run_loop.read_json(dated_params_path), changed)
                    else:
                        self.assertEqual(run_loop.read_json(current_params_path), run_loop.DEFAULT_PARAMS)
                        self.assertFalse(dated_params_path.exists())
                finally:
                    run_loop.collect_data = original_collect
                    run_loop.optimize_params = original_optimize
                    run_loop.write_json = original_write_json
                    run_loop.append_market_snapshot = original_append

    def test_persistence_failures_keep_external_account_inputs_absent(self):
        for phase in ("dated_params", "current_params", "history", "state"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
                paths = run_loop.loop_paths(workspace)
                incoming = workspace / "incoming-positions.json"
                incoming.write_text(json.dumps(account_positions()), encoding="utf-8")
                args = run_args(workspace)
                args.positions_json = str(incoming)
                canonical_positions = paths["positions"] / "positions.json"
                manifest_path = paths["positions"] / "latest_screenshots.json"
                current_params = paths["params"] / "strategy_params.json"
                current_params.write_text(
                    json.dumps(run_loop.DEFAULT_PARAMS), encoding="utf-8"
                )
                history = paths["market_history"] / "market_snapshots.jsonl"
                history.write_text(
                    json.dumps({"trade_date": "2026-07-14", "top_change": [], "top_turnover": []}) + "\n",
                    encoding="utf-8",
                )
                state = paths["state"] / "loop_state.json"
                state.write_text(
                    json.dumps({"snapshot_time": "2026-07-14 15:00:00", "holdings": [], "portfolio_actions": []}),
                    encoding="utf-8",
                )
                changed = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
                changed["entry_score"] = 99.0
                original_write_json = run_loop.write_json
                original_append = run_loop.append_market_snapshot

                def fail_selected_write(path, data):
                    original_write_json(path, data)
                    path = Path(path)
                    if phase == "dated_params" and path.name == "strategy_params_2026-07-15.json":
                        raise OSError("forced dated params failure")
                    if phase == "current_params" and path == current_params:
                        raise OSError("forced current params failure")
                    if phase == "state" and path == state:
                        raise RuntimeError("forced unexpected state failure")

                def fail_history(path, row):
                    original_append(path, row)
                    raise OSError("forced history failure")

                with contextlib.ExitStack() as stack:
                    stack.enter_context(mock.patch.object(run_loop, "collect_data", return_value=empty_collected()))
                    stack.enter_context(
                        mock.patch.object(
                            run_loop,
                            "optimize_params",
                            return_value={"status": "ok", "selected_params": changed, "selected_reason": "fixture"},
                        )
                    )
                    stack.enter_context(mock.patch.object(run_loop, "write_json", side_effect=fail_selected_write))
                    if phase == "history":
                        stack.enter_context(
                            mock.patch.object(run_loop, "append_market_snapshot", side_effect=fail_history)
                        )
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(run_loop.run_loop(args), 8)

                self.assertFalse(canonical_positions.exists())
                self.assertFalse(manifest_path.exists())
                self.assertEqual(list(paths["runs"].iterdir()), [])
                self.assertEqual(list(paths["backtests"].iterdir()), [])
                self.assertFalse(run_loop.transaction_journal_path(paths).exists())

    def _seed_recovery_workspace(self, workspace):
        (workspace / "Screenshot_2026-07-15-15-00-00.png").write_bytes(b"image")
        paths = run_loop.loop_paths(workspace)
        (paths["positions"] / "positions.json").write_text(
            json.dumps(account_positions()), encoding="utf-8"
        )
        current_params = paths["params"] / "strategy_params.json"
        current_params.write_text(
            json.dumps(run_loop.DEFAULT_PARAMS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        dated_params = paths["params"] / "strategy_params_2026-07-15.json"
        history = paths["market_history"] / "market_snapshots.jsonl"
        history.write_text(
            json.dumps(
                {
                    "trade_date": "2026-07-14",
                    "top_change": [],
                    "top_turnover": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        state = paths["state"] / "loop_state.json"
        state.write_text(
            json.dumps(
                {
                    "snapshot_time": "2026-07-14 15:00:00",
                    "holdings": [],
                    "portfolio_actions": [],
                }
            ),
            encoding="utf-8",
        )
        tracked = (dated_params, current_params, history, state)
        before = {
            path: path.read_bytes() if path.exists() else None for path in tracked
        }
        return paths, tracked, before

    def _crash_persistence_subprocess(self, workspace, phase):
        code = r'''
import importlib.util
import json
import os
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
workspace = Path(sys.argv[2])
phase = sys.argv[3]
spec = importlib.util.spec_from_file_location("crash_run_loop", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
paths = module.loop_paths(workspace)
params = module.read_json(paths["params"] / "strategy_params.json")
selected = json.loads(json.dumps(params))
selected["entry_score"] = 99.0
history_path = paths["market_history"] / "market_snapshots.jsonl"
state_path = paths["state"] / "loop_state.json"
original_write = module.write_json

def crashing_write(path, data):
    path = Path(path)
    original_write(path, data)
    if phase == "current" and path == paths["params"] / "strategy_params.json":
        os._exit(91)
    if phase == "state" and path == state_path:
        os._exit(92)

module.write_json = crashing_write
module.persist_loop_progress(
    paths,
    "2026-07-15",
    params,
    selected,
    history_path,
    {"trade_date": "2026-07-15", "top_change": [], "top_turnover": []},
    state_path,
    {
        "snapshot_time": "2026-07-15 15:00:00",
        "holdings": [],
        "portfolio_actions": [],
    },
)
'''
        return subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(RUN_LOOP_PATH),
                str(workspace),
                phase,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _assert_subprocess_crash_recovers(self, phase, expected_code):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths, tracked, before = self._seed_recovery_workspace(workspace)

            crashed = self._crash_persistence_subprocess(workspace, phase)

            self.assertEqual(
                crashed.returncode,
                expected_code,
                msg=f"stdout={crashed.stdout}\nstderr={crashed.stderr}",
            )
            journal = run_loop.transaction_journal_path(paths)
            self.assertTrue(journal.is_file())

            original_collect = run_loop.collect_data
            original_validator = run_loop.validate_signal_v2
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                run_loop.validate_signal_v2 = lambda signal: ["stop after recovery"]

                self.assertEqual(run_loop.run_loop(run_args(workspace)), 6)

                self.assertFalse(journal.exists())
                for path, original_bytes in before.items():
                    if original_bytes is None:
                        self.assertFalse(path.exists())
                    else:
                        self.assertEqual(path.read_bytes(), original_bytes)

                run_loop.validate_signal_v2 = original_validator
                self.assertEqual(run_loop.run_loop(run_args(workspace)), 0)
                stored = run_loop.load_market_history(
                    paths["market_history"] / "market_snapshots.jsonl"
                )
                self.assertEqual(
                    sum(row["trade_date"] == "2026-07-15" for row in stored),
                    1,
                )
            finally:
                run_loop.collect_data = original_collect
                run_loop.validate_signal_v2 = original_validator

    def test_subprocess_crash_after_current_params_is_recovered_on_next_run(self):
        self._assert_subprocess_crash_recovers("current", 91)

    def test_subprocess_crash_after_state_write_is_recovered_on_next_run(self):
        self._assert_subprocess_crash_recovers("state", 92)

    def test_keyboard_interrupt_before_first_target_write_leaves_recoverable_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths, tracked, before = self._seed_recovery_workspace(workspace)
            original_write = run_loop.write_json
            dated_params = paths["params"] / "strategy_params_2026-07-15.json"
            current_params = paths["params"] / "strategy_params.json"
            history = paths["market_history"] / "market_snapshots.jsonl"
            state = paths["state"] / "loop_state.json"
            selected = json.loads(json.dumps(run_loop.DEFAULT_PARAMS))
            selected["entry_score"] = 99.0

            def interrupt_before_first_write(path, data):
                if Path(path) == dated_params:
                    raise KeyboardInterrupt("forced crash before first target write")
                return original_write(path, data)

            try:
                run_loop.write_json = interrupt_before_first_write
                with self.assertRaises(KeyboardInterrupt):
                    run_loop.persist_loop_progress(
                        paths,
                        "2026-07-15",
                        run_loop.DEFAULT_PARAMS,
                        selected,
                        history,
                        {"trade_date": "2026-07-15", "top_change": [], "top_turnover": []},
                        state,
                        {"snapshot_time": "2026-07-15 15:00:00"},
                    )
            finally:
                run_loop.write_json = original_write

            journal = run_loop.transaction_journal_path(paths)
            self.assertTrue(journal.is_file())
            payload = run_loop.read_json(journal)
            self.assertTrue(
                all(
                    not Path(entry["path"]).is_absolute()
                    and ".." not in Path(entry["path"]).parts
                    for entry in payload["entries"]
                )
            )
            recovered, errors = run_loop.recover_pending_transaction(paths)
            self.assertTrue(recovered, errors)
            self.assertFalse(journal.exists())
            for path, original_bytes in before.items():
                if original_bytes is None:
                    self.assertFalse(path.exists())
                else:
                    self.assertEqual(path.read_bytes(), original_bytes)

    def test_keyboard_interrupt_after_account_input_write_recovers_both_inputs(self):
        for input_state in ("existing", "absent"):
            with self.subTest(input_state=input_state), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths = run_loop.loop_paths(workspace)
                manifest_path = paths["positions"] / "latest_screenshots.json"
                positions_path = paths["positions"] / "positions.json"
                if input_state == "existing":
                    manifest_path.write_bytes(b'{"sentinel":"old-manifest"}')
                    positions_path.write_bytes(b'{"sentinel":"old-positions"}')
                tracked = (manifest_path, positions_path)
                before = {
                    path: path.read_bytes() if path.exists() else None
                    for path in tracked
                }
                original_write = run_loop.write_json

                def interrupt_after_positions(path, data):
                    original_write(path, data)
                    if Path(path) == positions_path:
                        raise KeyboardInterrupt("forced crash after positions write")

                with mock.patch.object(
                    run_loop, "write_json", side_effect=interrupt_after_positions
                ):
                    with self.assertRaisesRegex(
                        KeyboardInterrupt, "forced crash after positions write"
                    ):
                        run_loop.persist_loop_progress(
                            paths,
                            "2026-07-15",
                            run_loop.DEFAULT_PARAMS,
                            run_loop.DEFAULT_PARAMS,
                            paths["market_history"] / "market_snapshots.jsonl",
                            None,
                            paths["state"] / "loop_state.json",
                            {"snapshot_time": "2026-07-15 15:00:00"},
                            {"latest_snapshot_time": "2026-07-15 15:00:00"},
                            account_positions(),
                        )

                journal = run_loop.transaction_journal_path(paths)
                self.assertTrue(journal.is_file())
                relative_targets = {
                    entry["path"] for entry in run_loop.read_json(journal)["entries"]
                }
                self.assertIn("positions/latest_screenshots.json", relative_targets)
                self.assertIn("positions/positions.json", relative_targets)
                recovered, errors = run_loop.recover_pending_transaction(paths)
                self.assertTrue(recovered, errors)
                self.assertFalse(journal.exists())
                for path, original_bytes in before.items():
                    if original_bytes is None:
                        self.assertFalse(path.exists())
                    else:
                        self.assertEqual(path.read_bytes(), original_bytes)

    def test_account_input_journal_allowlist_rejects_other_position_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_loop.loop_paths(Path(tmp))

            self.assertEqual(
                run_loop._validated_transaction_target(
                    paths, "positions/positions.json"
                ),
                paths["positions"] / "positions.json",
            )
            self.assertEqual(
                run_loop._validated_transaction_target(
                    paths, "positions/latest_screenshots.json"
                ),
                paths["positions"] / "latest_screenshots.json",
            )
            with self.assertRaisesRegex(ValueError, "outside the persistence allowlist"):
                run_loop._validated_transaction_target(
                    paths, "positions/unreviewed.json"
                )

    @unittest.skipUnless(os.name == "nt", "Windows junction semantics")
    def test_account_input_transaction_rejects_positions_junction_outside_loop_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = run_loop.loop_paths(workspace)
            external = workspace / "external-position-target"
            external.mkdir()
            sentinel = external / "sentinel.bin"
            sentinel.write_bytes(b"external-bytes")
            paths["positions"].rmdir()
            created = subprocess.run(
                [
                    "cmd",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(paths["positions"]),
                    str(external),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                created.returncode,
                0,
                msg=f"stdout={created.stdout}\nstderr={created.stderr}",
            )
            try:
                persisted, errors, rollback_errors = run_loop.persist_loop_progress(
                    paths,
                    "2026-07-15",
                    run_loop.DEFAULT_PARAMS,
                    run_loop.DEFAULT_PARAMS,
                    paths["market_history"] / "market_snapshots.jsonl",
                    None,
                    paths["state"] / "loop_state.json",
                    {"snapshot_time": "2026-07-15 15:00:00"},
                    {"latest_snapshot_time": "2026-07-15 15:00:00"},
                    account_positions(),
                )

                self.assertFalse(persisted)
                self.assertTrue(errors)
                self.assertEqual(rollback_errors, [])
                self.assertEqual(sentinel.read_bytes(), b"external-bytes")
                self.assertFalse(run_loop.transaction_journal_path(paths).exists())
            finally:
                os.rmdir(str(paths["positions"]))

    def test_target_startup_recovers_prepared_journal_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths, tracked, before = self._seed_recovery_workspace(workspace)
            journal = run_loop.prepare_persistence_journal(paths, list(tracked))
            for path in tracked[1:]:
                path.write_bytes(b"not-json")
            original_collect = run_loop.collect_data
            try:
                run_loop.collect_data = lambda *args, **kwargs: empty_collected()

                result = run_loop.cmd_analyze_targets(target_args(workspace))

                self.assertEqual(result, 0)
                self.assertFalse(journal.exists())
                for path, original_bytes in before.items():
                    if original_bytes is None:
                        self.assertFalse(path.exists())
                    else:
                        self.assertEqual(path.read_bytes(), original_bytes)
            finally:
                run_loop.collect_data = original_collect

    def test_corrupt_journal_returns_recovery_failed_before_account_or_target_reads(self):
        for command in ("account", "target"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths, _, _ = self._seed_recovery_workspace(workspace)
                journal = paths["state"] / "persistence_transaction.json"
                journal.write_text("{corrupt", encoding="utf-8")
                (paths["params"] / "strategy_params.json").write_text(
                    "{also-corrupt", encoding="utf-8"
                )
                (paths["state"] / "loop_state.json").write_text(
                    "{also-corrupt", encoding="utf-8"
                )

                result = (
                    run_loop.run_loop(run_args(workspace))
                    if command == "account"
                    else run_loop.cmd_analyze_targets(target_args(workspace))
                )

                self.assertEqual(result, 9)
                self.assertTrue(journal.exists())

    @unittest.skipIf(os.name == "nt", "POSIX dangling symlink semantics")
    def test_dangling_symlink_journal_fails_closed_for_both_commands_and_prepare(self):
        for command in ("account", "target"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths, tracked, _ = self._seed_recovery_workspace(workspace)
                journal = run_loop.transaction_journal_path(paths)
                journal.symlink_to(workspace / "missing-journal-target")
                original_collect = run_loop.collect_data
                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = (
                            run_loop.run_loop(run_args(workspace))
                            if command == "account"
                            else run_loop.cmd_analyze_targets(target_args(workspace))
                        )

                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(result, 9)
                    self.assertEqual(payload["status"], "recovery_failed")
                    self.assertTrue(payload["errors"])
                    os.lstat(str(journal))
                finally:
                    run_loop.collect_data = original_collect

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths, tracked, _ = self._seed_recovery_workspace(workspace)
            journal = run_loop.transaction_journal_path(paths)
            journal.symlink_to(workspace / "missing-journal-target")
            captured = None
            try:
                run_loop.prepare_persistence_journal(paths, list(tracked))
            except Exception as exc:
                captured = exc
            self.assertIsInstance(captured, FileExistsError)
            os.lstat(str(journal))

    @unittest.skipUnless(os.name == "nt", "Windows junction semantics")
    def test_dangling_junction_journal_fails_closed_for_both_commands_and_prepare(self):
        def make_dangling_junction(journal, target):
            target.mkdir()
            created = subprocess.run(
                [
                    "cmd",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(journal),
                    str(target),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                created.returncode,
                0,
                msg=f"stdout={created.stdout}\nstderr={created.stderr}",
            )
            target.rmdir()
            os.lstat(str(journal))

        for command in ("account", "target"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                paths, tracked, _ = self._seed_recovery_workspace(workspace)
                journal = run_loop.transaction_journal_path(paths)
                make_dangling_junction(journal, workspace / "missing-journal-target")
                original_collect = run_loop.collect_data
                try:
                    run_loop.collect_data = lambda *args, **kwargs: empty_collected()
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = (
                            run_loop.run_loop(run_args(workspace))
                            if command == "account"
                            else run_loop.cmd_analyze_targets(target_args(workspace))
                        )

                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(result, 9)
                    self.assertEqual(payload["status"], "recovery_failed")
                    self.assertTrue(payload["errors"])
                    os.lstat(str(journal))
                finally:
                    run_loop.collect_data = original_collect

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths, tracked, _ = self._seed_recovery_workspace(workspace)
            journal = run_loop.transaction_journal_path(paths)
            make_dangling_junction(journal, workspace / "missing-journal-target")
            captured = None
            try:
                run_loop.prepare_persistence_journal(paths, list(tracked))
            except Exception as exc:
                captured = exc
            self.assertIsInstance(captured, FileExistsError)
            os.lstat(str(journal))

    def test_journal_rejects_path_traversal_and_keeps_journal_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = run_loop.loop_paths(workspace)
            outside = workspace / "outside.txt"
            outside.write_bytes(b"outside")
            journal = paths["state"] / "persistence_transaction.json"
            journal.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "path": "../outside.txt",
                                "existed": True,
                                "content_b64": base64.b64encode(b"changed").decode("ascii"),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            recovered, errors = run_loop.recover_pending_transaction(paths)

            self.assertFalse(recovered)
            self.assertTrue(errors)
            self.assertEqual(outside.read_bytes(), b"outside")
            self.assertTrue(journal.exists())

    def test_journal_rejects_boolean_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_loop.loop_paths(Path(tmp))
            journal = paths["state"] / "persistence_transaction.json"
            journal.write_text(
                json.dumps(
                    {
                        "version": True,
                        "entries": [
                            {
                                "path": "state/loop_state.json",
                                "existed": False,
                                "content_b64": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            recovered, errors = run_loop.recover_pending_transaction(paths)

            self.assertFalse(recovered)
            self.assertTrue(errors)
            self.assertTrue(journal.exists())

    def test_write_json_replace_failure_preserves_old_bytes_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_bytes(b"old-bytes")
            original_replace = run_loop.os.replace
            try:
                def fail_replace(source, destination):
                    if Path(destination) == path:
                        raise OSError("forced atomic JSON replace failure")
                    return original_replace(source, destination)

                run_loop.os.replace = fail_replace
                with self.assertRaises(OSError):
                    run_loop.write_json(path, {"new": True})
            finally:
                run_loop.os.replace = original_replace

            self.assertEqual(path.read_bytes(), b"old-bytes")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_future_ranking_is_unknown_low_even_if_recent_dates_include_future(self):
        inputs = comprehensive_market_inputs()
        inputs["recent_trade_dates"] = ["2026-07-16", "2026-07-15"]
        for row in (
            inputs["board_rankings"]["concept"]["change_desc"]
            + inputs["board_rankings"]["concept"]["turnover_desc"]
        ):
            row["as_of"] = "2026-07-16"

        signal = run_loop.generate_daily_signal(
            account_positions(), {}, {"regime": "risk_on"}, {},
            inputs["normalized_indices"], {}, [], run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        evidence = next(
            row for row in signal["evidence_index"] if row["category"] == "board"
        )
        self.assertEqual(evidence["freshness"], "unknown")
        self.assertEqual(evidence["reliability"], "low")

    def test_future_news_is_unknown_low_and_cannot_verify_catalyst(self):
        inputs = comprehensive_market_inputs()
        inputs["recent_trade_dates"] = ["2026-07-16", "2026-07-15"]
        news = {
            "meta": {"stale": False},
            "data": [
                {
                    "title": "机器人未来订单",
                    "content": "机器人产业链",
                    "published_at": "2026-07-16 10:00:00",
                    "source": "future-fixture",
                }
            ],
        }

        signal = run_loop.generate_daily_signal(
            account_positions(), {}, {"regime": "risk_on"}, {},
            inputs["normalized_indices"], news, [], run_loop.DEFAULT_PARAMS,
            market_inputs=inputs,
        )

        evidence = next(
            row for row in signal["evidence_index"] if row["category"] == "news"
        )
        self.assertEqual(evidence["freshness"], "unknown")
        self.assertEqual(evidence["reliability"], "low")
        self.assertFalse(signal["market_mainlines"][0]["catalyst_verified"])

    def test_invalid_numeric_market_evidence_never_fabricates_numbers_or_high_reliability(self):
        invalid_values = (True, [], {}, float("nan"), float("inf"))
        for value in invalid_values:
            with self.subTest(value=value):
                inputs = comprehensive_market_inputs()
                board_id = run_loop.board_identity("concept", "robotics")
                for row in (
                    inputs["board_rankings"]["concept"]["change_desc"]
                    + inputs["board_rankings"]["concept"]["turnover_desc"]
                ):
                    row["change_pct"] = value
                    row["turnover_yuan"] = value
                item = inputs["board_details"][board_id]["items"][0]
                for field in ("change_pct", "turnover_yuan", "ret20", "market_cap_yuan"):
                    item[field] = value
                inputs["normalized_indices"][0]["change_pct"] = value
                for field in ("advancers", "decliners", "turnover_yuan"):
                    inputs["breadth"][field] = value

                signal = run_loop.generate_daily_signal(
                    account_positions(), {}, {"regime": "risk_on"}, {},
                    inputs["normalized_indices"], {}, [], run_loop.DEFAULT_PARAMS,
                    market_inputs=inputs,
                )
                report = run_loop.render_report(
                    account_positions(), signal,
                    {"scope": "technical_only_diagnostic", "metrics": {}}, {}, []
                )

                evidence = [
                    row for row in signal["evidence_index"]
                    if row.get("category") in {"board", "constituent", "breadth"}
                ]
                self.assertEqual({row["category"] for row in evidence}, {"board", "constituent", "breadth"})
                self.assertTrue(all(row["reliability"] == "low" for row in evidence))
                self.assertTrue(all("证据不足" in row["statement"] for row in evidence))
                joined = " ".join(row["statement"] for row in evidence)
                self.assertNotIn(str(value), joined)
                self.assertNotIn(str(value), report)
                self.assertFalse(
                    any(row.get("category") == "index" for row in signal["evidence_index"])
                )
                self.assertEqual(run_loop.validate_signal_v2(signal), [])
                self.assertEqual(
                    sum(line.startswith("## ") for line in report.splitlines()), 10
                )

    def test_fetch_board_summaries_requests_modes_concurrently(self):
        original_run = run_loop.run_subprocess_json
        lock = threading.Lock()
        release = threading.Event()
        active = 0
        max_active = 0

        def delayed_run(command, timeout=30):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
                if active >= 2:
                    release.set()
            release.wait(0.2)
            with lock:
                active -= 1
            return {"data": []}, None

        try:
            run_loop.run_subprocess_json = delayed_run

            summaries, errors = run_loop.fetch_board_summaries(Path("."))

            self.assertEqual(errors, [])
            self.assertEqual(set(summaries), {"major", "sub", "concept"})
            self.assertGreaterEqual(max_active, 2)
        finally:
            run_loop.run_subprocess_json = original_run

    def test_fetch_board_rankings_requests_six_rankings_with_six_worker_cap(self):
        calls = []
        original_run = run_loop.run_subprocess_json
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                calls.append(command)
                or ({"meta": {"tradeDate": "2026-07-15"}, "data": []}, None)
            )

            rankings, trade_date, errors = run_loop.fetch_board_rankings(Path("."))

            self.assertEqual(errors, [])
            self.assertEqual(trade_date, "2026-07-15")
            self.assertEqual(len(calls), 6)
            self.assertEqual(set(rankings), {"major", "sub", "concept"})
            self.assertTrue(
                all(
                    set(value) == {"change_desc", "turnover_desc"}
                    for value in rankings.values()
                )
            )
            self.assertTrue(all("--sort" in command for command in calls))
        finally:
            run_loop.run_subprocess_json = original_run

    def test_fetch_board_rankings_does_not_fabricate_a_trade_date(self):
        original_run = run_loop.run_subprocess_json
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                {"meta": {}, "data": []},
                None,
            )

            _, trade_date, errors = run_loop.fetch_board_rankings(Path("."))

            self.assertEqual(trade_date, "")
            self.assertTrue(any("authoritative trade date" in error for error in errors))
        finally:
            run_loop.run_subprocess_json = original_run

    def test_fetch_board_rankings_reports_mixed_valid_sessions(self):
        original_run = run_loop.run_subprocess_json
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                {
                    "meta": {
                        "tradeDate": (
                            "2026-07-14" if command[command.index("--mode") + 1] == "major"
                            else "2026-07-15"
                        )
                    },
                    "data": [],
                },
                None,
            )

            _, trade_date, errors = run_loop.fetch_board_rankings(Path("."))

            self.assertEqual(trade_date, "2026-07-15")
            self.assertTrue(any("mixed" in error and "2026-07-14" in error for error in errors))
        finally:
            run_loop.run_subprocess_json = original_run

    def test_fetch_board_rankings_rejects_malformed_success_payloads(self):
        original_run = run_loop.run_subprocess_json
        try:
            for payload in (None, {"meta": {"tradeDate": "2026-07-15"}, "data": None}):
                with self.subTest(payload=payload):
                    run_loop.run_subprocess_json = lambda command, timeout=30: (payload, None)

                    rankings, trade_date, errors = run_loop.fetch_board_rankings(Path("."))

                    self.assertEqual(trade_date, "")
                    self.assertTrue(errors)
                    self.assertTrue(
                        all(
                            rows == []
                            for mode in rankings.values()
                            for rows in mode.values()
                        )
                    )
        finally:
            run_loop.run_subprocess_json = original_run

    def test_normalize_board_rows_rejects_rows_without_a_valid_group_key(self):
        payload = {
            "meta": {"tradeDate": "2026-07-15"},
            "data": [
                {"groupKey": "N:robotics", "groupLabel": "Robotics", "changePct": 2.5},
                {"groupKey": "   ", "groupLabel": "Missing"},
                {"groupLabel": "Label is not an API key"},
                {"groupKey": {"bad": "shape"}, "groupLabel": "Malformed"},
            ],
        }

        rows = run_loop.normalize_board_rows(payload)

        self.assertEqual([row["group_key"] for row in rows], ["N:robotics"])
        self.assertEqual(rows[0]["as_of"], "2026-07-15")

    def test_fetch_board_details_bounds_deduplicates_and_skips_invalid_candidates(self):
        calls = []
        original_run = run_loop.run_subprocess_json
        candidates = [
            {"mode": "major", "group_key": ""},
            {"mode": "invalid", "group_key": "N:invalid"},
            {"mode": "major", "group_key": "N:duplicate"},
            {"mode": "major", "group_key": "N:duplicate"},
        ] + [
            {"mode": "concept", "group_key": f"N:{index}"}
            for index in range(20)
        ]
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                calls.append(command) or {"data": {"items": []}},
                None,
            )

            details, errors = run_loop.fetch_board_details(candidates, Path("."))

            self.assertEqual(errors, [])
            self.assertEqual(len(calls), 12)
            self.assertEqual(len(details), 12)
            called_keys = [command[command.index("--group-key") + 1] for command in calls]
            self.assertEqual(len(called_keys), len(set(called_keys)))
            self.assertNotIn("", called_keys)
            self.assertNotIn("N:invalid", called_keys)
            self.assertTrue(
                all(
                    command[command.index("--items-limit") + 1] == "100"
                    for command in calls
                )
            )
        finally:
            run_loop.run_subprocess_json = original_run

    def test_board_details_keep_same_group_key_distinct_across_modes(self):
        original_run = run_loop.run_subprocess_json
        candidates = [
            {"mode": "major", "group_key": "N:shared"},
            {"mode": "concept", "group_key": "N:shared"},
        ]
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                {"meta": {"tradeDate": "2026-07-15", "stale": False}, "data": {"items": []}},
                None,
            )

            details, errors = run_loop.fetch_board_details(candidates, Path("."))

            self.assertEqual(errors, [])
            self.assertEqual(
                set(details),
                {
                    run_loop.board_identity("major", "N:shared"),
                    run_loop.board_identity("concept", "N:shared"),
                },
            )
        finally:
            run_loop.run_subprocess_json = original_run

    def test_normalize_board_detail_preserves_freshness_filters_codes_and_caps_items(self):
        items = [
            {"code": "123", "name": "short"},
            {"code": "garbage600000", "name": "embedded"},
            {"code": "", "name": "empty"},
            {"code": "sh600000", "name": "Shanghai"},
            {"code": "SZ000001", "name": "Shenzhen"},
            {"code": "bj430001", "name": "Beijing"},
        ] + [
            {"code": str(100000 + index), "name": f"Stock {index}"}
            for index in range(120)
        ]

        detail = run_loop.normalize_board_detail(
            {
                "meta": {"tradeDate": "2026-07-15", "stale": True},
                "data": {"summary": {"count": 126}, "items": items},
            }
        )

        self.assertEqual(detail["as_of"], "2026-07-15")
        self.assertIs(detail["stale"], True)
        self.assertEqual(len(detail["items"]), 100)
        codes = {row["code"] for row in detail["items"]}
        self.assertIn("600000", codes)
        self.assertIn("000001", codes)
        self.assertIn("430001", codes)
        self.assertNotIn("000123", codes)

    def test_provider_stock_code_rejects_exchange_prefix_mismatches(self):
        self.assertEqual(run_loop.normalize_provider_stock_code("sh600000"), "600000")
        self.assertEqual(run_loop.normalize_provider_stock_code("SZ.000001"), "000001")
        self.assertEqual(run_loop.normalize_provider_stock_code("bj:430001"), "430001")
        for value in ("123", "garbage600000", "sh000001", "sz600000", "bj000001"):
            with self.subTest(value=value):
                self.assertEqual(run_loop.normalize_provider_stock_code(value), "")

    def test_fetch_board_details_rejects_malformed_success_payloads(self):
        original_run = run_loop.run_subprocess_json
        candidate = [{"mode": "concept", "group_key": "N:robotics"}]
        try:
            for payload in (
                None,
                {"data": None},
                {"data": {"items": None}},
            ):
                with self.subTest(payload=payload):
                    run_loop.run_subprocess_json = lambda command, timeout=30: (payload, None)

                    details, errors = run_loop.fetch_board_details(candidate, Path("."))

                    self.assertEqual(details, {})
                    self.assertTrue(errors)
        finally:
            run_loop.run_subprocess_json = original_run

    def test_market_breadth_normalizes_advancers_turnover_and_session(self):
        payload = [
            {run_loop.K_CHANGE_PCT: 1.0, "\u6210\u4ea4\u989d": 100},
            {run_loop.K_CHANGE_PCT: -2.0, "\u6210\u4ea4\u989d": 200},
        ]

        result = run_loop.normalize_market_breadth(payload, "2026-07-15")

        self.assertEqual(result["advancers"], 1)
        self.assertEqual(result["decliners"], 1)
        self.assertEqual(result["turnover_yuan"], 300.0)
        self.assertEqual(result["trade_date"], "2026-07-15")
        self.assertEqual(result["as_of"], "2026-07-15")
        self.assertFalse(result["limit_structure_available"])
        self.assertEqual(result["sample_size"], 2)
        self.assertFalse(result["complete"])

    def test_market_breadth_skips_malformed_changes_instead_of_counting_them_unchanged(self):
        result = run_loop.normalize_market_breadth(
            [
                {"change_pct": 1.0, "amount": 100},
                {"change_pct": "bad", "amount": 200},
                {"change_pct": None, "amount": 300},
                {"change_pct": float("nan"), "amount": 400},
                {"change_pct": -1.0, "amount": 500},
                {"change_pct": 0.0, "amount": 600},
            ],
            "2026-07-15",
        )

        self.assertEqual(result["sample_size"], 3)
        self.assertEqual(result["advancers"], 1)
        self.assertEqual(result["decliners"], 1)
        self.assertEqual(result["unchanged"], 1)
        self.assertFalse(result["complete"])

    def test_market_breadth_marks_a_plausible_full_market_sample_complete(self):
        rows = [
            {"change_pct": 1.0 if index % 2 else -1.0, "amount": 100}
            for index in range(1000)
        ]

        result = run_loop.normalize_market_breadth(rows, "2026-07-15")

        self.assertEqual(result["sample_size"], 1000)
        self.assertTrue(result["complete"])
        self.assertEqual(result["completeness_threshold"], 1000)
        self.assertEqual(result["turnover_valid_count"], 1000)
        self.assertEqual(result["turnover_coverage_ratio"], 1.0)

    def test_market_breadth_requires_turnover_coverage_not_just_valid_changes(self):
        rows = [
            {
                "change_pct": 1.0 if index % 2 else -1.0,
                **({"amount": 100} if index == 0 else {}),
            }
            for index in range(1000)
        ]
        rows[1]["amount"] = "bad"
        rows[2]["amount"] = -10
        rows[3]["amount"] = float("inf")

        result = run_loop.normalize_market_breadth(rows, "2026-07-15")

        self.assertEqual(result["sample_size"], 1000)
        self.assertEqual(result["turnover_valid_count"], 1)
        self.assertEqual(result["turnover_coverage_ratio"], 0.001)
        self.assertFalse(result["turnover_complete"])
        self.assertFalse(result["complete"])

    def test_fetch_market_breadth_requests_the_full_market_not_default_top_twenty(self):
        calls = []
        original_run = run_loop.run_subprocess_json
        try:
            run_loop.run_subprocess_json = lambda command, timeout=30: (
                calls.append(command)
                or {
                    "data": [
                        {"change_pct": 1.0, "amount": 100},
                        {"change_pct": -1.0, "amount": 200},
                    ]
                },
                None,
            )

            breadth, error = run_loop.fetch_market_breadth(
                Path("."), "2026-07-15"
            )

            self.assertIsNone(error)
            self.assertEqual(breadth["advancers"], 1)
            self.assertIn("--top", calls[0])
            self.assertGreaterEqual(int(calls[0][calls[0].index("--top") + 1]), 6000)
        finally:
            run_loop.run_subprocess_json = original_run

    def test_normalize_indices_exposes_current_session_as_of(self):
        rows = run_loop.normalize_indices(
            [
                {
                    run_loop.K_CODE: "000001",
                    run_loop.K_NAME: "Index",
                    run_loop.K_PRICE: 3210,
                    run_loop.K_CHANGE_PCT: 1.25,
                }
            ],
            "2026-07-15",
        )

        self.assertEqual(rows[0]["change_pct"], 1.25)
        self.assertEqual(rows[0]["as_of"], "2026-07-15")
        self.assertEqual(
            run_loop.classify_market(rows, {})["avg_index_change_pct"],
            1.25,
        )

    def test_normalize_indices_marks_invalid_or_nonpositive_prices_unknown(self):
        invalid_prices = (None, "bad", True, [], {}, float("nan"), float("inf"), 0, -1)
        for price in invalid_prices:
            with self.subTest(price=repr(price)):
                rows = run_loop.normalize_indices(
                    [
                        {
                            run_loop.K_CODE: "000001",
                            run_loop.K_NAME: "Index",
                            run_loop.K_PRICE: price,
                            run_loop.K_CHANGE_PCT: 1.25,
                        }
                    ],
                    "2026-07-15",
                )
                self.assertIsNone(rows[0]["price"])

        valid = run_loop.normalize_indices(
            [{run_loop.K_PRICE: "3,210.5", run_loop.K_CHANGE_PCT: 0}],
            "2026-07-15",
        )
        self.assertEqual(valid[0]["price"], 3210.5)

    def test_market_history_appends_once_per_trade_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"
            row = {
                "trade_date": "2026-07-15",
                "top_change": [run_loop.board_identity("concept", "N:robotics")],
                "top_turnover": [],
            }

            run_loop.append_market_snapshot(path, row)
            run_loop.append_market_snapshot(path, row)

            self.assertEqual(run_loop.load_market_history(path), [row])

    def test_market_history_skips_malformed_scalar_and_undated_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"
            valid = {
                "trade_date": "2026-07-15",
                "top_change": [run_loop.board_identity("concept", "N:shared")],
                "top_turnover": [],
            }
            path.write_text(
                "\n".join(
                    [
                        json.dumps(valid),
                        "42",
                        json.dumps(["not", "an", "object"]),
                        json.dumps({"trade_date": "not-a-date"}),
                        '{"trade_date": "2026-07-16"',
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(run_loop.load_market_history(path), [valid])

    def test_market_history_rejects_malformed_identity_collections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"
            valid = {
                "trade_date": "2026-07-15",
                "top_change": [],
                "top_turnover": [],
            }
            malformed = [
                {"trade_date": "2026-07-10", "top_change": "not-a-list", "top_turnover": []},
                {"trade_date": "2026-07-11", "top_change": [], "top_turnover": None},
                {"trade_date": "2026-07-12", "top_change": [""], "top_turnover": []},
                {"trade_date": "2026-07-13", "top_change": [{"nested": True}], "top_turnover": []},
                {"trade_date": "2026-07-14", "top_change": ["N:legacy-raw"], "top_turnover": []},
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in [*malformed, valid]),
                encoding="utf-8",
            )

            self.assertEqual(run_loop.load_market_history(path), [valid])

    def test_market_history_tolerates_a_truncated_utf8_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"
            valid = {
                "trade_date": "2026-07-15",
                "top_change": [],
                "top_turnover": [],
            }
            path.write_bytes(
                (json.dumps(valid) + "\n").encode("utf-8")
                + b'{"trade_date":"2026-07-16","name":"\xe6\x9c'
            )

            self.assertEqual(run_loop.load_market_history(path), [valid])

    def test_market_history_retains_only_the_latest_sixty_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"
            rows = [
                {
                    "trade_date": (dt.date(2026, 1, 1) + dt.timedelta(days=index)).isoformat(),
                    "top_change": [],
                    "top_turnover": [],
                }
                for index in range(65)
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            newest = {
                "trade_date": "2026-07-15",
                "top_change": [],
                "top_turnover": [],
            }

            run_loop.append_market_snapshot(path, newest)

            stored = run_loop.load_market_history(path)
            self.assertEqual(len(stored), 60)
            self.assertEqual(stored[-1], newest)
            self.assertEqual(stored[0], rows[6])

    def test_market_history_atomic_replace_failure_preserves_live_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "market_snapshots.jsonl"
            old_row = {
                "trade_date": "2026-07-14",
                "top_change": [],
                "top_turnover": [],
            }
            old_text = json.dumps(old_row) + "\n"
            path.write_text(old_text, encoding="utf-8")
            original_replace = run_loop.os.replace
            try:
                run_loop.os.replace = lambda source, target: (_ for _ in ()).throw(
                    OSError("simulated replace failure")
                )

                with self.assertRaisesRegex(OSError, "simulated replace failure"):
                    run_loop.append_market_snapshot(
                        path,
                        {
                            "trade_date": "2026-07-15",
                            "top_change": [],
                            "top_turnover": [],
                        },
                    )
            finally:
                run_loop.os.replace = original_replace

            self.assertEqual(path.read_text(encoding="utf-8"), old_text)
            self.assertEqual(
                [item for item in root.iterdir() if item.name != path.name],
                [],
            )

    def test_market_history_preserves_cross_mode_board_identity(self):
        row = run_loop.market_history_row(
            {
                "major": {
                    "change_desc": [
                        {
                            "group_key": "N:shared",
                            "board_id": "forged-id",
                            "as_of": "2026-07-15",
                            "stale": False,
                        }
                    ],
                    "turnover_desc": [],
                },
                "concept": {
                    "change_desc": [
                        {
                            "group_key": "N:shared",
                            "as_of": "2026-07-15",
                            "stale": False,
                        }
                    ],
                    "turnover_desc": [],
                },
            },
            "2026-07-15",
        )

        self.assertEqual(
            row["top_change"],
            [
                run_loop.board_identity("major", "N:shared"),
                run_loop.board_identity("concept", "N:shared"),
            ],
        )

    def test_market_history_row_only_includes_verified_current_rankings(self):
        rows = [
            {
                "group_key": "current",
                "as_of": "2026-07-15",
                "stale": False,
            },
            {
                "group_key": "stale",
                "as_of": "2026-07-15",
                "stale": True,
            },
            {
                "group_key": "malformed",
                "as_of": "2026-07-15",
                "stale": "false",
            },
            {
                "group_key": "previous",
                "as_of": "2026-07-14",
                "stale": False,
            },
            {"group_key": "missing", "as_of": "2026-07-15"},
        ]

        row = run_loop.market_history_row(
            {
                "concept": {
                    "change_desc": rows,
                    "turnover_desc": list(reversed(rows)),
                }
            },
            "2026-07-15",
        )

        current_id = run_loop.board_identity("concept", "current")
        self.assertEqual(row["top_change"], [current_id])
        self.assertEqual(row["top_turnover"], [current_id])

    def test_prepare_market_inputs_excludes_future_history_and_false_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "market_snapshots.jsonl"
            inputs = comprehensive_market_inputs()
            board_id = run_loop.board_identity("concept", "robotics")
            history_path.write_text(
                "".join(
                    json.dumps(row) + "\n"
                    for row in (
                        {
                            "trade_date": "2026-07-14",
                            "top_change": [],
                            "top_turnover": [],
                        },
                        {
                            "trade_date": "2026-07-15",
                            "top_change": [],
                            "top_turnover": [],
                        },
                        {
                            "trade_date": "2026-07-16",
                            "top_change": [board_id],
                            "top_turnover": [board_id],
                        },
                        {
                            "trade_date": "2026-07-17",
                            "top_change": [board_id],
                            "top_turnover": [board_id],
                        },
                    )
                ),
                encoding="utf-8",
            )
            collected = run_loop.CollectedData(
                stock_data={},
                board_summaries={},
                board_rankings=inputs["board_rankings"],
                board_details=inputs["board_details"],
                indices=inputs["normalized_indices"],
                breadth=inputs["breadth"],
                market_news={},
                latest_trade_date="2026-07-15",
                errors=[],
            )

            market_inputs, current_row = run_loop.prepare_market_inputs(
                collected, history_path
            )
            signal = run_loop.generate_daily_signal(
                account_positions(),
                {},
                {"regime": "risk_on"},
                {},
                collected.indices,
                {},
                [],
                run_loop.DEFAULT_PARAMS,
                market_inputs=market_inputs,
            )

            self.assertEqual(
                [row["trade_date"] for row in market_inputs["market_history"]],
                ["2026-07-14", "2026-07-15"],
            )
            self.assertEqual(current_row["top_change"], [board_id])
            self.assertEqual(
                signal["market_mainlines"][0]["continuity"]["hits"], 0
            )
            self.assertEqual(
                signal["market_mainlines"][0]["continuity"]["sessions"], 2
            )
            self.assertNotEqual(
                signal["market_mainlines"][0]["classification"],
                "confirmed_mainline",
            )

    def test_market_history_ignores_snapshot_without_trade_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "market_snapshots.jsonl"

            run_loop.append_market_snapshot(path, {"trade_date": "", "top_change": []})

            self.assertFalse(path.exists())

    def test_market_inputs_without_authoritative_date_add_no_current_history_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "market_snapshots.jsonl"
            history_path.write_text(
                json.dumps(
                    {
                        "trade_date": "2026-07-14",
                        "top_change": [],
                        "top_turnover": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            collected = empty_collected("")
            collected.indices = [
                {
                    "code": "000001",
                    "name": "上证指数",
                    "change_pct": 1.0,
                    "as_of": "2026-07-14",
                }
            ]

            market_inputs, current_row = run_loop.prepare_market_inputs(
                collected, history_path
            )

            self.assertIsNone(current_row)
            self.assertEqual(
                market_inputs["market_history"],
                [
                    {
                        "trade_date": "2026-07-14",
                        "top_change": [],
                        "top_turnover": [],
                    }
                ],
            )
            self.assertEqual(
                market_inputs["normalized_indices"][0]["as_of"],
                "2026-07-14",
            )
            self.assertNotIn("", market_inputs["recent_trade_dates"])

    def test_loop_paths_include_market_history_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_loop.loop_paths(Path(tmp))

            self.assertEqual(paths["market_history"].name, "market-history")
            self.assertTrue(paths["market_history"].is_dir())

    def test_collect_data_fetches_independent_holdings_concurrently(self):
        originals = {
            "fetch_quotes": run_loop.fetch_quotes,
            "fetch_sector_info": run_loop.fetch_sector_info,
            "fetch_danginvest_industry_fallback": run_loop.fetch_danginvest_industry_fallback,
            "fetch_board_rankings": run_loop.fetch_board_rankings,
            "fetch_board_details": run_loop.fetch_board_details,
            "fetch_market_breadth": run_loop.fetch_market_breadth,
            "fetch_market_news": run_loop.fetch_market_news,
            "fetch_indices": run_loop.fetch_indices,
            "fetch_history": run_loop.fetch_history,
            "fetch_fund_flow": run_loop.fetch_fund_flow,
            "select_board_candidates": run_loop.select_board_candidates,
        }
        lock = threading.Lock()
        release = threading.Event()
        active = 0
        max_active = 0
        selected_for_date = []

        def delayed_history(code, start, end, skill, retries=2):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
                if active >= 2:
                    release.set()
            release.wait(0.2)
            with lock:
                active -= 1
            return [], None

        try:
            run_loop.fetch_quotes = lambda codes, skill: ({}, [])
            run_loop.fetch_sector_info = lambda codes, skill: ({}, None)
            run_loop.fetch_danginvest_industry_fallback = lambda codes: ({}, None)
            run_loop.fetch_board_rankings = lambda skill: (
                {"major": {"change_desc": [], "turnover_desc": []}},
                "2026-07-15",
                [],
            )
            run_loop.fetch_board_details = lambda candidates, skill: ({}, [])
            run_loop.fetch_market_breadth = lambda skill, date: (
                run_loop.normalize_market_breadth([], date),
                None,
            )
            run_loop.fetch_market_news = lambda skill: ({}, None)
            run_loop.fetch_indices = lambda skill: ([], None)
            run_loop.fetch_history = delayed_history
            run_loop.fetch_fund_flow = lambda code, skill: ([], None)
            run_loop.select_board_candidates = (
                lambda rankings, news, limit=12, latest_trade_date=None: (
                    selected_for_date.append(latest_trade_date) or []
                )
            )
            positions = {
                "holdings": [
                    {"code": "000001", "name": "甲"},
                    {"code": "000002", "name": "乙"},
                ]
            }

            collected = run_loop.collect_data(
                positions,
                Path("."),
                "2023-01-01",
                "2026-07-13",
                include_events=False,
            )

            self.assertEqual(collected.errors, [])
            self.assertEqual(set(collected.stock_data), {"000001", "000002"})
            self.assertEqual(collected.latest_trade_date, "2026-07-15")
            self.assertEqual(collected.breadth["as_of"], "2026-07-15")
            self.assertEqual(selected_for_date, ["2026-07-15"])
            self.assertGreaterEqual(max_active, 2)
        finally:
            for name, value in originals.items():
                setattr(run_loop, name, value)


if __name__ == "__main__":
    unittest.main()
