import copy
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import reporting


def portfolio_diagnosis_fixture():
    return {
        "stock_exposure": None,
        "cash_weight": None,
        "single_stock_concentration": [],
        "industry_concentration": [],
        "theme_concentration": [],
        "mainline_alignment": [],
        "off_mainline_exposure": None,
        "counter_regime_exposure": None,
        "counter_regime_exposure_note": None,
        "shared_catalyst_risks": [],
        "portfolio_posture": None,
        "top_action_priorities": [],
    }


def signal_fixture():
    return {
        "report_schema_version": 2,
        "data_coverage": {}, "evidence_index": [],
        "market_snapshot": {
            "as_of": "2026-07-15", "regime": "structural", "confidence": "high",
            "indices": [], "breadth": {}, "missing_evidence": [],
        },
        "market_mainlines": [], "market_outlook": {
            key: {
                "horizon": horizon, "base_case": "基准", "stronger_case": "更强", "weaker_case": "更弱",
                "key_variables": ["成交"], "portfolio_posture": "条件化", "invalidation": "证据失效", "confidence": "medium",
            }
            for key, horizon in (
                ("short_term", "1-5 trading days"),
                ("medium_term", "1-3 months"),
            )
        },
        "portfolio_diagnosis": portfolio_diagnosis_fixture(),
        "holding_analyses": [], "portfolio_actions": [],
    }


def evidence_fixture(evidence_id="ev-1"):
    return {
        "evidence_id": evidence_id,
        "category": "price",
        "statement": "成交保持活跃",
        "source": "fixture",
        "as_of": "2026-07-15",
        "trading_session": "2026-07-15",
        "freshness": "current-session",
        "reliability": "high",
        "scope": "market",
    }


def mainline_fixture():
    return {
        "name": "机器人",
        "classification": "confirmed_mainline",
        "score": 75,
        "score_components": {"continuity": 20},
        "continuity": {"known": True, "hits": 3},
        "leaders": [{
            "code": "000001",
            "name": "甲",
            "role": "liquidity_anchor",
            "role_evidence": "成交额领先",
            "confidence": "high",
            "risk": "轮动风险",
            "evidence_ids": ["ev-1"],
        }],
        "logic_chain": {
            "facts": ["成交保持活跃"],
            "driver": "资金集中",
            "social_or_industrial_need": "自动化需求",
            "value_chain_transmission": "零部件到整机",
            "earnings_transmission": "订单需验证",
            "price_confirmation": "趋势延续",
            "contradictions": [],
            "unknowns": ["订单兑现"],
        },
        "continuation_conditions": ["成交延续"],
        "invalidation_conditions": ["放量转弱"],
        "risk": "轮动风险",
        "confidence": "high",
        "evidence_ids": ["ev-1"],
        "catalyst_verified": True,
        "contradictions": [],
        "critical_contradiction": False,
    }


def holding_fixture():
    return {
        "code": "000001",
        "name": "甲",
        "account_role": "core",
        "industry_panorama": {
            "segment_focus": "机器人零部件",
            "value_chain_position": "上游",
            "upstream_dependency_check": "材料供应",
            "downstream_customer_check": "整机厂",
            "industry_influence_question": "行业影响待验证",
            "scarce_capability_check": "精密制造",
            "learning_analogy": "卖铲人",
        },
        "mainline_links": [{
            "name": "机器人",
            "relationship": "leader",
            "leader_roles": ["liquidity_anchor"],
        }],
        "factor_evidence": {
            "total_score": 65,
            "trend_score": 15,
            "macd_score": 12,
            "fund_flow_score": 10,
            "sector_score": 14,
            "event_score": 14,
        },
        "bull_evidence": ["趋势向上"],
        "bear_evidence": ["估值待验证"],
        "thesis_status": "supported",
        "data_confidence": "high",
        "evidence_gaps": ["订单待验证"],
        "action": "hold",
        "priority": 4,
        "target_weight": 0.12,
        "reason": "主线关系仍在",
        "trigger": "成交保持",
        "invalidation": "主线转弱",
        "risk_note": "研究结论",
        "evidence_ids": ["ev-1"],
    }


def stock_score_fixture(
    fund_flow_score=10,
    fund_flow_net=100.0,
    score_imputations=None,
    missing_data=None,
):
    return {
        "code": "000001",
        "name": "甲",
        "scores": {
            "total_score": 65,
            "trend_score": 15,
            "macd_score": 12,
            "fund_flow_score": fund_flow_score,
            "sector_score": 14,
            "event_score": 14,
            "score_imputations": (
                {} if score_imputations is None else score_imputations
            ),
            "raw": {"fund_flow_5d_net_wan": fund_flow_net},
        },
        "missing_data": [] if missing_data is None else missing_data,
    }


def portfolio_action_fixture(holding=None):
    holding = holding_fixture() if holding is None else holding
    return {
        key: holding[key]
        for key in (
            "code",
            "name",
            "action",
            "reason",
            "trigger",
            "invalidation",
            "target_weight",
            "risk_note",
        )
    }


def layered_signal_fixture(include_mainline=False, include_stock_score=False):
    signal = signal_fixture()
    signal["evidence_index"] = [evidence_fixture()]
    holding = holding_fixture()
    if include_stock_score:
        holding["factor_evidence"]["score_imputations"] = {}
        holding["factor_evidence"]["raw"] = {
            "fund_flow_5d_net_wan": 100.0
        }
        signal["stock_scores"] = [stock_score_fixture()]
    signal["holding_analyses"] = [holding]
    signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
    if include_mainline:
        signal["market_mainlines"] = [mainline_fixture()]
    return signal


def set_path(row, path, value):
    target = row
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def format_path(path):
    result = ""
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}" if result else part
    return result


class ReportContractTests(unittest.TestCase):
    def assert_validation_error_without_crash(self, signal, expected):
        try:
            errors = reporting.validate_signal_v2(signal)
        except (TypeError, ValueError, OverflowError) as exc:
            self.fail(f"validator raised {type(exc).__name__}: {exc}")
        self.assertIn(expected, errors)

    def test_top_level_containers_fail_closed(self):
        cases = (
            ("data_coverage", []),
            ("evidence_index", {}),
            ("market_snapshot", []),
            ("market_mainlines", {}),
            ("market_outlook", []),
            ("portfolio_diagnosis", []),
            ("holding_analyses", {}),
            ("portfolio_actions", {}),
        )
        for field, value in cases:
            with self.subTest(field=field):
                signal = signal_fixture()
                signal[field] = value
                expected = "must be an object" if field in {
                    "data_coverage",
                    "market_snapshot",
                    "market_outlook",
                    "portfolio_diagnosis",
                } else "must be a list"
                self.assert_validation_error_without_crash(
                    signal, f"{field} {expected}"
                )

    def test_report_schema_version_requires_exact_integer_two(self):
        for value in (True, 2.0, "2", None):
            with self.subTest(value=value):
                signal = signal_fixture()
                signal["report_schema_version"] = value
                self.assertIn(
                    "report_schema_version must equal integer 2",
                    reporting.validate_signal_v2(signal),
                )

    def test_market_regime_requires_exact_string_enum(self):
        invalid = (True, 1, [], {}, "", " ", "mixed", "risk_off", None)
        for value in invalid:
            with self.subTest(value=value):
                signal = signal_fixture()
                signal["market_snapshot"]["regime"] = value
                self.assertIn(
                    "market_snapshot invalid regime",
                    reporting.validate_signal_v2(signal),
                )

    def test_enum_fields_reject_unhashable_pseudo_types_without_crashing(self):
        cases = (
            (
                "freshness",
                ("evidence_index", 0, "freshness"),
                {},
                "evidence_index[0] invalid freshness",
            ),
            (
                "reliability",
                ("evidence_index", 0, "reliability"),
                [],
                "evidence_index[0] invalid reliability",
            ),
            (
                "classification",
                ("market_mainlines", 0, "classification"),
                {},
                "market_mainlines[0] invalid classification",
            ),
            (
                "leader_role",
                ("market_mainlines", 0, "leaders", 0, "role"),
                [],
                "market_mainlines[0].leaders[0] invalid role",
            ),
            (
                "account_role",
                ("holding_analyses", 0, "account_role"),
                {},
                "holding_analyses[0] invalid account_role",
            ),
            (
                "holding_action",
                ("holding_analyses", 0, "action"),
                [],
                "holding_analyses[0] invalid action",
            ),
            (
                "portfolio_action",
                ("portfolio_actions", 0, "action"),
                {},
                "portfolio_actions[0] invalid action",
            ),
        )
        for label, path, value, expected in cases:
            with self.subTest(label=label):
                signal = layered_signal_fixture(include_mainline=True)
                set_path(signal, path, value)
                self.assert_validation_error_without_crash(signal, expected)

    def test_required_contract_strings_reject_blank_and_pseudo_types(self):
        cases = (
            (False, ("market_snapshot", "as_of")),
            (False, ("market_snapshot", "confidence")),
            (False, ("market_outlook", "short_term", "base_case")),
            (False, ("market_outlook", "short_term", "stronger_case")),
            (False, ("market_outlook", "short_term", "weaker_case")),
            (False, ("market_outlook", "short_term", "portfolio_posture")),
            (False, ("market_outlook", "short_term", "invalidation")),
            (False, ("market_outlook", "short_term", "confidence")),
            (True, ("market_mainlines", 0, "name")),
            (True, ("market_mainlines", 0, "risk")),
            (True, ("market_mainlines", 0, "confidence")),
            (True, ("market_mainlines", 0, "leaders", 0, "code")),
            (True, ("market_mainlines", 0, "leaders", 0, "name")),
            (True, ("market_mainlines", 0, "leaders", 0, "role_evidence")),
            (True, ("market_mainlines", 0, "leaders", 0, "confidence")),
            (True, ("market_mainlines", 0, "leaders", 0, "risk")),
            (True, ("market_mainlines", 0, "logic_chain", "driver")),
            (True, ("market_mainlines", 0, "logic_chain", "social_or_industrial_need")),
            (True, ("market_mainlines", 0, "logic_chain", "value_chain_transmission")),
            (True, ("market_mainlines", 0, "logic_chain", "earnings_transmission")),
            (True, ("market_mainlines", 0, "logic_chain", "price_confirmation")),
            (False, ("holding_analyses", 0, "code")),
            (False, ("holding_analyses", 0, "name")),
            (False, ("holding_analyses", 0, "thesis_status")),
            (False, ("holding_analyses", 0, "data_confidence")),
            (False, ("holding_analyses", 0, "reason")),
            (False, ("holding_analyses", 0, "trigger")),
            (False, ("holding_analyses", 0, "invalidation")),
            (False, ("holding_analyses", 0, "risk_note")),
            (False, ("portfolio_actions", 0, "code")),
            (False, ("portfolio_actions", 0, "name")),
            (False, ("portfolio_actions", 0, "reason")),
            (False, ("portfolio_actions", 0, "trigger")),
            (False, ("portfolio_actions", 0, "invalidation")),
            (False, ("portfolio_actions", 0, "risk_note")),
        )
        for include_mainline, path in cases:
            for value in (" ", True, []):
                with self.subTest(path=path, value=value):
                    signal = layered_signal_fixture(
                        include_mainline=include_mainline
                    )
                    set_path(signal, path, value)
                    dotted = format_path(path)
                    self.assertTrue(
                        any(
                            dotted in error
                            and "must be a non-empty string" in error
                            for error in reporting.validate_signal_v2(signal)
                        ),
                        dotted,
                    )

    def test_public_numbers_reject_bool_strings_nan_inf_and_out_of_range(self):
        mainline_cases = (
            (("market_mainlines", 0, "score"), -0.01),
            (("market_mainlines", 0, "score"), 100.01),
            (("market_mainlines", 0, "score_components", "continuity"), 20.01),
            (("market_mainlines", 0, "score_components", "new_component"), 100.01),
        )
        invalid_types = (True, "50", float("nan"), float("inf"), float("-inf"))
        for path in (
            ("market_mainlines", 0, "score"),
            ("market_mainlines", 0, "score_components", "continuity"),
        ):
            for value in invalid_types:
                mainline_cases += ((path, value),)
        for path, value in mainline_cases:
            with self.subTest(path=path, value=value):
                signal = layered_signal_fixture(include_mainline=True)
                set_path(signal, path, value)
                self.assertTrue(reporting.validate_signal_v2(signal))

        for field in (
            "total_score",
            "trend_score",
            "macd_score",
            "fund_flow_score",
            "sector_score",
            "event_score",
        ):
            for value in (*invalid_types, -0.01, 100.01):
                with self.subTest(layer="holding", field=field, value=value):
                    signal = layered_signal_fixture()
                    signal["holding_analyses"][0]["factor_evidence"][field] = value
                    self.assertTrue(
                        any(
                            f"factor_evidence.{field}" in error
                            for error in reporting.validate_signal_v2(signal)
                        )
                    )
                with self.subTest(layer="stock", field=field, value=value):
                    signal = layered_signal_fixture(include_stock_score=True)
                    signal["stock_scores"][0]["scores"][field] = value
                    self.assertTrue(
                        any(
                            f"scores.{field}" in error
                            for error in reporting.validate_signal_v2(signal)
                        )
                    )

    def test_oversized_json_integer_fails_closed_without_crashing(self):
        signal = layered_signal_fixture(include_mainline=True)
        signal["market_mainlines"][0]["score"] = 10**10000
        self.assert_validation_error_without_crash(
            signal,
            "market_mainlines[0].score must be a finite number",
        )

    def test_public_ratio_count_and_priority_numbers_are_strict(self):
        cases = (
            (("data_coverage", "holdings"), float("nan")),
            (("market_snapshot", "indices", 0, "change_pct"), float("inf")),
            (("market_snapshot", "breadth", "advancers"), -1),
            (("portfolio_diagnosis", "stock_exposure"), 1.01),
            (("portfolio_diagnosis", "single_stock_concentration", 0, "weight"), -0.01),
            (("holding_analyses", 0, "priority"), 0),
            (("holding_analyses", 0, "priority"), 6),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                signal = layered_signal_fixture()
                signal["data_coverage"]["holdings"] = 1
                signal["market_snapshot"]["indices"] = [
                    {"name": "指数", "change_pct": 0.0}
                ]
                signal["market_snapshot"]["breadth"] = {"advancers": 1}
                signal["portfolio_diagnosis"]["single_stock_concentration"] = [
                    {"code": "000001", "name": "甲", "weight": 0.1}
                ]
                set_path(signal, path, value)
                self.assertTrue(reporting.validate_signal_v2(signal))

        for path in (
            ("data_coverage", "holdings"),
            ("market_snapshot", "indices", 0, "change_pct"),
            ("market_snapshot", "breadth", "advancers"),
            ("portfolio_diagnosis", "stock_exposure"),
            ("portfolio_diagnosis", "single_stock_concentration", 0, "weight"),
            ("holding_analyses", 0, "priority"),
        ):
            for value in (True, "1", float("nan"), float("inf")):
                with self.subTest(path=path, value=value):
                    signal = layered_signal_fixture()
                    signal["data_coverage"]["holdings"] = 1
                    signal["market_snapshot"]["indices"] = [
                        {"name": "指数", "change_pct": 0.0}
                    ]
                    signal["market_snapshot"]["breadth"] = {"advancers": 1}
                    signal["portfolio_diagnosis"]["single_stock_concentration"] = [
                        {"code": "000001", "name": "甲", "weight": 0.1}
                    ]
                    set_path(signal, path, value)
                    self.assertTrue(reporting.validate_signal_v2(signal))

    def test_optional_public_breadth_and_unknown_date_fields_are_strict(self):
        breadth_cases = (
            ("turnover_valid_count", float("inf")),
            ("completeness_threshold", -1),
            ("turnover_coverage_ratio", 1.01),
            ("turnover_coverage_threshold", -0.01),
            ("limit_up", float("nan")),
        )
        for field, value in breadth_cases:
            with self.subTest(field=field, value=value):
                signal = signal_fixture()
                signal["market_snapshot"]["breadth"] = {field: value}
                self.assertTrue(
                    any(
                        f"market_snapshot.breadth.{field}" in error
                        for error in reporting.validate_signal_v2(signal)
                    )
                )

        for value in (True, [], {}):
            with self.subTest(unknown_as_of=value):
                signal = signal_fixture()
                evidence = evidence_fixture()
                evidence["freshness"] = "unknown"
                evidence["as_of"] = value
                signal["evidence_index"] = [evidence]
                self.assertIn(
                    "evidence_index[0] as_of must be a string or null for "
                    "unknown evidence",
                    reporting.validate_signal_v2(signal),
                )

    def test_boolean_fields_require_exact_bool(self):
        cases = (
            (("market_mainlines", 0, "catalyst_verified"), "false"),
            (("market_mainlines", 0, "continuity", "known"), 1),
            (("market_mainlines", 0, "critical_contradiction"), "false"),
            (("market_snapshot", "breadth", "complete"), "true"),
            (("market_snapshot", "indices", 0, "stale"), 0),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                signal = layered_signal_fixture(include_mainline=True)
                signal["market_snapshot"]["breadth"] = {"complete": True}
                signal["market_snapshot"]["indices"] = [
                    {"name": "指数", "change_pct": 0.0, "stale": False}
                ]
                set_path(signal, path, value)
                self.assertTrue(
                    any(
                        "must be a boolean" in error
                        for error in reporting.validate_signal_v2(signal)
                    )
                )

    def test_portfolio_actions_require_complete_fields_and_bounded_weight(self):
        required = (
            "code",
            "name",
            "action",
            "reason",
            "trigger",
            "invalidation",
            "target_weight",
            "risk_note",
        )
        for field in required:
            with self.subTest(missing=field):
                signal = layered_signal_fixture()
                del signal["portfolio_actions"][0][field]
                self.assertIn(
                    f"portfolio_actions[0] missing {field}",
                    reporting.validate_signal_v2(signal),
                )

        for value in (True, "0.1", float("nan"), float("inf"), -0.01, 0.1501):
            with self.subTest(target_weight=value):
                signal = layered_signal_fixture()
                signal["holding_analyses"][0]["target_weight"] = value
                signal["portfolio_actions"][0]["target_weight"] = value
                errors = reporting.validate_signal_v2(signal)
                self.assertTrue(
                    any(
                        ".target_weight" in error
                        and (
                            "must be a finite number" in error
                            or "must be between 0 and 0.15" in error
                        )
                        for error in errors
                    )
                )

    def test_zero_upper_bound_nullable_and_imputed_values_remain_valid(self):
        for target_weight in (0, 0.15):
            with self.subTest(target_weight=target_weight):
                signal = layered_signal_fixture()
                signal["holding_analyses"][0]["target_weight"] = target_weight
                signal["portfolio_actions"][0]["target_weight"] = target_weight
                signal["portfolio_diagnosis"]["stock_exposure"] = None
                signal["portfolio_diagnosis"]["cash_weight"] = None
                self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_code_sets_and_cross_layer_fields_must_match(self):
        mutators = (
            (
                "action_code",
                lambda signal: signal["portfolio_actions"][0].__setitem__(
                    "code", "999999"
                ),
                "portfolio_actions codes must match holding_analyses codes",
            ),
            (
                "stock_code",
                lambda signal: signal["stock_scores"][0].__setitem__(
                    "code", "999999"
                ),
                "stock_scores codes must match holding_analyses codes",
            ),
            (
                "action_name",
                lambda signal: signal["portfolio_actions"][0].__setitem__(
                    "name", "乙"
                ),
                "portfolio_actions[0].name does not match holding_analyses[0]",
            ),
            (
                "action_value",
                lambda signal: signal["portfolio_actions"][0].__setitem__(
                    "action", "reduce"
                ),
                "portfolio_actions[0].action does not match holding_analyses[0]",
            ),
            (
                "action_target",
                lambda signal: signal["portfolio_actions"][0].__setitem__(
                    "target_weight", 0.1
                ),
                "portfolio_actions[0].target_weight does not match holding_analyses[0]",
            ),
            (
                "stock_name",
                lambda signal: signal["stock_scores"][0].__setitem__(
                    "name", "乙"
                ),
                "stock_scores[0].name does not match holding_analyses[0]",
            ),
        )
        for label, mutate, expected in mutators:
            with self.subTest(label=label):
                signal = layered_signal_fixture(include_stock_score=True)
                signal["stock_scores"][0]["name"] = "甲"
                mutate(signal)
                self.assertIn(expected, reporting.validate_signal_v2(signal))

        for layer in ("holding_analyses", "portfolio_actions"):
            with self.subTest(duplicate=layer):
                signal = layered_signal_fixture()
                signal[layer].append(copy.deepcopy(signal[layer][0]))
                self.assertTrue(
                    any(
                        f"duplicate {layer} code" in error
                        for error in reporting.validate_signal_v2(signal)
                    )
                )

    def test_all_factor_scores_match_between_stock_and_holding_layers(self):
        fields = (
            "total_score",
            "trend_score",
            "macd_score",
            "fund_flow_score",
            "sector_score",
            "event_score",
        )
        for field in fields:
            with self.subTest(field=field):
                signal = layered_signal_fixture(include_stock_score=True)
                signal["holding_analyses"][0]["factor_evidence"][field] += 1
                self.assertIn(
                    "holding_analyses[0].factor_evidence."
                    f"{field} does not match stock_scores[0]",
                    reporting.validate_signal_v2(signal),
                )

    def test_renderer_rejects_invalid_bool_and_non_finite_weight_before_formatting(self):
        cases = (
            (
                "catalyst",
                lambda signal: signal["market_mainlines"][0].__setitem__(
                    "catalyst_verified", "false"
                ),
            ),
            (
                "target_weight",
                lambda signal: (
                    signal["holding_analyses"][0].__setitem__(
                        "target_weight", float("nan")
                    ),
                    signal["portfolio_actions"][0].__setitem__(
                        "target_weight", float("nan")
                    ),
                ),
            ),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                signal = layered_signal_fixture(include_mainline=True)
                mutate(signal)
                with self.assertRaises(ValueError):
                    reporting.render_report({}, signal, {}, {}, [])

    def test_validator_rejects_missing_mainlines(self):
        signal = signal_fixture()
        del signal["market_mainlines"]
        self.assertIn("missing market_mainlines", reporting.validate_signal_v2(signal))

    def test_validator_rejects_incomplete_holding_action(self):
        signal = signal_fixture()
        signal["holding_analyses"] = [{"code": "000001", "name": "甲", "action": "hold"}]
        errors = reporting.validate_signal_v2(signal)
        self.assertIn("holding_analyses[0] missing invalidation", errors)

    def test_validator_rejects_unsupported_leader_shape(self):
        signal = signal_fixture()
        signal["market_mainlines"] = [{
            "name": "机器人", "classification": "today_hotspot", "score": 60,
            "score_components": {}, "leaders": [{"code": "000001", "name": "甲"}],
            "logic_chain": {}, "continuation_conditions": [], "invalidation_conditions": [],
            "risk": "轮动风险", "confidence": "medium", "evidence_ids": [],
            "catalyst_verified": False, "contradictions": [],
        }]
        errors = reporting.validate_signal_v2(signal)
        self.assertIn("market_mainlines[0].leaders[0] missing role", errors)

    def test_renderer_always_emits_ten_sections_in_order(self):
        report = reporting.render_report(
            {"snapshot_time": "2026-07-15 15:00:00", "holdings": []}, signal_fixture(), {"metrics": {}}, {}, []
        )
        headings = [
            "## 核心结论", "## 数据覆盖与时效", "## 今日市场发生了什么", "## 近期主线与今日主线",
            "## 事实—逻辑—推演", "## 双周期市场预判", "## 组合诊断", "## 持仓逐股分析与操作建议",
            "## 回测与参数证据", "## 闭环复盘与下一次检查清单",
        ]
        positions = [report.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            [line for line in report.splitlines() if line.startswith("## ")],
            headings,
        )
        self.assertIn("证据不足", report)

    def test_evidence_registry_requires_fields_unique_ids_and_enums(self):
        required = (
            "evidence_id", "category", "statement", "source", "as_of",
            "trading_session", "freshness", "reliability", "scope",
        )
        for field in required:
            with self.subTest(field=field):
                signal = signal_fixture()
                evidence = evidence_fixture()
                del evidence[field]
                signal["evidence_index"] = [evidence]
                self.assertIn(
                    f"evidence_index[0] missing {field}",
                    reporting.validate_signal_v2(signal),
                )

        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture(), evidence_fixture()]
        errors = reporting.validate_signal_v2(signal)
        self.assertIn("duplicate evidence_id ev-1", errors)

        signal = signal_fixture()
        evidence = evidence_fixture()
        evidence["freshness"] = "live"
        evidence["reliability"] = "certain"
        signal["evidence_index"] = [evidence]
        errors = reporting.validate_signal_v2(signal)
        self.assertIn("evidence_index[0] invalid freshness", errors)
        self.assertIn("evidence_index[0] invalid reliability", errors)

    def test_evidence_ids_and_references_reject_malformed_values_without_crashing(self):
        for value in ([], {}, 7, ""):
            with self.subTest(evidence_id=value):
                signal = signal_fixture()
                signal["evidence_index"] = [evidence_fixture(value)]
                self.assert_validation_error_without_crash(
                    signal,
                    "evidence_index[0] evidence_id must be a non-empty string",
                )

        cases = (
            (
                "mainline",
                {"ev-1": True},
                ["ev-1"],
                ["ev-1"],
                "market_mainlines[0] evidence_ids must be a non-empty list",
            ),
            (
                "leader",
                ["ev-1"],
                [{}],
                ["ev-1"],
                "market_mainlines[0].leaders[0] evidence_ids[0] must be a non-empty string",
            ),
            (
                "leader_non_list",
                ["ev-1"],
                {"ev-1": True},
                ["ev-1"],
                "market_mainlines[0].leaders[0] evidence_ids must be a non-empty list",
            ),
            (
                "holding",
                ["ev-1"],
                ["ev-1"],
                [[]],
                "holding_analyses[0] evidence_ids[0] must be a non-empty string",
            ),
            (
                "holding_non_list",
                ["ev-1"],
                ["ev-1"],
                {"ev-1": True},
                "holding_analyses[0] evidence_ids must be a non-empty list",
            ),
        )
        for name, mainline_refs, leader_refs, holding_refs, expected in cases:
            with self.subTest(reference=name):
                signal = signal_fixture()
                signal["evidence_index"] = [evidence_fixture()]
                mainline = mainline_fixture()
                holding = holding_fixture()
                mainline["evidence_ids"] = mainline_refs
                mainline["leaders"][0]["evidence_ids"] = leader_refs
                holding["evidence_ids"] = holding_refs
                signal["market_mainlines"] = [mainline]
                signal["holding_analyses"] = [holding]
                self.assert_validation_error_without_crash(signal, expected)

    def test_current_session_evidence_requires_auditable_non_empty_strings(self):
        signal = signal_fixture()
        evidence = evidence_fixture("")
        for field in (
            "category", "statement", "source", "as_of",
            "trading_session", "scope",
        ):
            evidence[field] = ""
        signal["evidence_index"] = [evidence]
        errors = reporting.validate_signal_v2(signal)
        for field in (
            "evidence_id", "category", "statement", "source",
            "trading_session", "scope",
        ):
            with self.subTest(field=field):
                self.assertIn(
                    f"evidence_index[0] {field} must be a non-empty string",
                    errors,
                )
        self.assertIn(
            "evidence_index[0] as_of must be a non-empty string for current-session evidence",
            errors,
        )

    def test_unknown_freshness_allows_missing_as_of(self):
        for as_of in (None, ""):
            with self.subTest(as_of=as_of):
                signal = signal_fixture()
                evidence = evidence_fixture()
                evidence["freshness"] = "unknown"
                evidence["as_of"] = as_of
                signal["evidence_index"] = [evidence]
                self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_confirmed_mainline_requires_score_continuity_and_no_critical_contradiction(self):
        cases = (
            ("score", 69, "market_mainlines[0] confirmed_mainline requires score >= 70"),
            ("known", False, "market_mainlines[0] confirmed_mainline requires known continuity"),
            ("hits", 2, "market_mainlines[0] confirmed_mainline requires continuity hits >= 3"),
            ("critical", True, "market_mainlines[0] confirmed_mainline has critical contradiction"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                signal = signal_fixture()
                signal["evidence_index"] = [evidence_fixture()]
                mainline = mainline_fixture()
                if field == "score":
                    mainline["score"] = value
                elif field in {"known", "hits"}:
                    mainline["continuity"][field] = value
                else:
                    mainline["critical_contradiction"] = value
                signal["market_mainlines"] = [mainline]
                self.assertIn(expected, reporting.validate_signal_v2(signal))

    def test_validator_rejects_unsupported_leader_role(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        mainline = mainline_fixture()
        mainline["leaders"][0]["role"] = "fundamental_beneficiary"
        signal["market_mainlines"] = [mainline]
        self.assertIn(
            "market_mainlines[0].leaders[0] invalid role",
            reporting.validate_signal_v2(signal),
        )

    def test_holding_contract_rejects_role_watch_weight_and_action(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["account_role"] = "speculation"
        holding["action"] = "watch"
        holding["target_weight"] = 0.1
        signal["holding_analyses"] = [holding]
        signal["portfolio_actions"] = [{"action": "buy"}]
        errors = reporting.validate_signal_v2(signal)
        self.assertIn("holding_analyses[0] invalid account_role", errors)
        self.assertIn("holding_analyses[0] watch target_weight must equal 0", errors)
        self.assertIn("portfolio_actions[0] invalid action", errors)

    def test_portfolio_watch_action_requires_zero_target_weight(self):
        for action in (
            {"action": "watch"},
            {"action": "watch", "target_weight": 0.1},
        ):
            with self.subTest(action=action):
                signal = signal_fixture()
                signal["portfolio_actions"] = [action]
                self.assertIn(
                    "portfolio_actions[0] watch target_weight must equal 0",
                    reporting.validate_signal_v2(signal),
                )
        signal = layered_signal_fixture()
        holding = signal["holding_analyses"][0]
        holding["action"] = "watch"
        holding["target_weight"] = 0
        signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
        self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_holding_requires_evidence_gaps(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        del holding["evidence_gaps"]
        signal["holding_analyses"] = [holding]
        self.assertIn(
            "holding_analyses[0] missing evidence_gaps",
            reporting.validate_signal_v2(signal),
        )

    def test_outlook_horizons_are_fixed(self):
        signal = signal_fixture()
        signal["market_outlook"]["short_term"]["horizon"] = "5 days"
        signal["market_outlook"]["medium_term"]["horizon"] = "quarter"
        errors = reporting.validate_signal_v2(signal)
        self.assertIn(
            "market_outlook.short_term horizon must equal 1-5 trading days",
            errors,
        )
        self.assertIn(
            "market_outlook.medium_term horizon must equal 1-3 months",
            errors,
        )

    def test_mainline_nested_shape_contract_is_validated(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        mainline = mainline_fixture()
        mainline["score_components"] = []
        mainline["leaders"] = {}
        mainline["logic_chain"] = {
            "facts": "fact",
            "driver": "driver",
            "social_or_industrial_need": "need",
            "value_chain_transmission": "chain",
            "earnings_transmission": "earnings",
            "price_confirmation": "price",
            "contradictions": "none",
            "unknowns": {},
        }
        mainline["continuation_conditions"] = {}
        mainline["invalidation_conditions"] = "invalid"
        mainline["contradictions"] = {}
        signal["market_mainlines"] = [mainline]
        errors = reporting.validate_signal_v2(signal)
        expected = (
            "market_mainlines[0] score_components must be an object",
            "market_mainlines[0].leaders must be a list or null",
            "market_mainlines[0].logic_chain.facts must be a list or null",
            "market_mainlines[0].logic_chain.contradictions must be a list or null",
            "market_mainlines[0].logic_chain.unknowns must be a list or null",
            "market_mainlines[0] continuation_conditions must be a list or null",
            "market_mainlines[0] invalidation_conditions must be a list or null",
            "market_mainlines[0] contradictions must be a list or null",
        )
        for error in expected:
            with self.subTest(error=error):
                self.assertIn(error, errors)

    def test_logic_chain_requires_all_contract_keys(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        mainline = mainline_fixture()
        mainline["logic_chain"] = {}
        signal["market_mainlines"] = [mainline]
        errors = reporting.validate_signal_v2(signal)
        for field in (
            "facts", "driver", "social_or_industrial_need",
            "value_chain_transmission", "earnings_transmission",
            "price_confirmation", "contradictions", "unknowns",
        ):
            with self.subTest(field=field):
                self.assertIn(
                    f"market_mainlines[0].logic_chain missing {field}", errors
                )

    def test_nullable_mainline_collections_remain_valid(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        mainline = mainline_fixture()
        mainline["leaders"] = None
        mainline["continuation_conditions"] = None
        mainline["invalidation_conditions"] = None
        mainline["contradictions"] = None
        mainline["logic_chain"]["facts"] = None
        mainline["logic_chain"]["contradictions"] = None
        mainline["logic_chain"]["unknowns"] = None
        signal["market_mainlines"] = [mainline]
        self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_portfolio_diagnosis_requires_task_five_shape(self):
        signal = signal_fixture()
        signal["portfolio_diagnosis"] = None
        self.assertIn(
            "portfolio_diagnosis must be an object",
            reporting.validate_signal_v2(signal),
        )

        signal = signal_fixture()
        del signal["portfolio_diagnosis"]["portfolio_posture"]
        self.assertIn(
            "portfolio_diagnosis missing portfolio_posture",
            reporting.validate_signal_v2(signal),
        )

        signal = signal_fixture()
        for field in (
            "single_stock_concentration", "industry_concentration",
            "theme_concentration", "mainline_alignment",
            "shared_catalyst_risks", "top_action_priorities",
        ):
            signal["portfolio_diagnosis"][field] = "bad"
        errors = reporting.validate_signal_v2(signal)
        for field in (
            "single_stock_concentration", "industry_concentration",
            "theme_concentration", "mainline_alignment",
            "shared_catalyst_risks", "top_action_priorities",
        ):
            with self.subTest(field=field):
                self.assertIn(
                    f"portfolio_diagnosis.{field} must be a list or null",
                    errors,
                )

    def test_portfolio_diagnosis_rejects_malformed_nested_entries(self):
        signal = signal_fixture()
        diagnosis = signal["portfolio_diagnosis"]
        diagnosis["single_stock_concentration"] = [1]
        diagnosis["industry_concentration"] = [[]]
        diagnosis["theme_concentration"] = ["bad"]
        diagnosis["mainline_alignment"] = [None]
        diagnosis["shared_catalyst_risks"] = [{}]
        diagnosis["top_action_priorities"] = [1]
        errors = reporting.validate_signal_v2(signal)
        expected = (
            "portfolio_diagnosis.single_stock_concentration[0] must be an object",
            "portfolio_diagnosis.industry_concentration[0] must be an object",
            "portfolio_diagnosis.theme_concentration[0] must be an object",
            "portfolio_diagnosis.mainline_alignment[0] must be an object",
            "portfolio_diagnosis.shared_catalyst_risks[0] must be a string",
            "portfolio_diagnosis.top_action_priorities[0] must be an object",
        )
        for error in expected:
            with self.subTest(error=error):
                self.assertIn(error, errors)

    def test_portfolio_diagnosis_nested_objects_require_renderer_keys(self):
        signal = signal_fixture()
        diagnosis = signal["portfolio_diagnosis"]
        for field in (
            "single_stock_concentration", "industry_concentration",
            "theme_concentration", "mainline_alignment",
            "top_action_priorities",
        ):
            diagnosis[field] = [{}]
        errors = reporting.validate_signal_v2(signal)
        expected = (
            "portfolio_diagnosis.single_stock_concentration[0] missing code",
            "portfolio_diagnosis.single_stock_concentration[0] missing name",
            "portfolio_diagnosis.single_stock_concentration[0] missing weight",
            "portfolio_diagnosis.industry_concentration[0] missing industry",
            "portfolio_diagnosis.industry_concentration[0] missing weight",
            "portfolio_diagnosis.theme_concentration[0] missing theme",
            "portfolio_diagnosis.theme_concentration[0] missing weight",
            "portfolio_diagnosis.mainline_alignment[0] missing mainline",
            "portfolio_diagnosis.mainline_alignment[0] missing weight",
            "portfolio_diagnosis.top_action_priorities[0] missing code",
            "portfolio_diagnosis.top_action_priorities[0] missing name",
            "portfolio_diagnosis.top_action_priorities[0] missing action",
        )
        for error in expected:
            with self.subTest(error=error):
                self.assertIn(error, errors)

    def test_portfolio_diagnosis_accepts_and_renders_asset_coverage_note(self):
        signal = signal_fixture()
        note = "现金/总资产未知；单股和行业权重仅按可见持仓市值归一化。"
        signal["portfolio_diagnosis"]["asset_coverage_note"] = note

        self.assertEqual(reporting.validate_signal_v2(signal), [])
        report = reporting.render_report({}, signal, {}, {}, [])
        self.assertIn(f"资产覆盖说明：{note}", report)

    def test_portfolio_diagnosis_rejects_non_string_asset_coverage_note(self):
        signal = signal_fixture()
        signal["portfolio_diagnosis"]["asset_coverage_note"] = 1

        self.assertIn(
            "portfolio_diagnosis.asset_coverage_note must be a string",
            reporting.validate_signal_v2(signal),
        )

    def test_holding_nested_shape_contract_is_validated(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["industry_panorama"] = []
        holding["factor_evidence"] = []
        holding["mainline_links"] = ["bad", {"name": "机器人"}]
        holding["bull_evidence"] = "bad"
        holding["bear_evidence"] = {}
        holding["evidence_gaps"] = "bad"
        signal["holding_analyses"] = [holding]
        errors = reporting.validate_signal_v2(signal)
        expected = (
            "holding_analyses[0] industry_panorama must be an object or null",
            "holding_analyses[0] factor_evidence must be an object or null",
            "holding_analyses[0].mainline_links[0] must be an object",
            "holding_analyses[0].mainline_links[1] missing relationship",
            "holding_analyses[0].mainline_links[1] missing leader_roles",
            "holding_analyses[0] bull_evidence must be a list or null",
            "holding_analyses[0] bear_evidence must be a list or null",
            "holding_analyses[0] evidence_gaps must be a list or null",
        )
        for error in expected:
            with self.subTest(error=error):
                self.assertIn(error, errors)

        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["mainline_links"] = {}
        signal["holding_analyses"] = [holding]
        self.assertIn(
            "holding_analyses[0] mainline_links must be a list or null",
            reporting.validate_signal_v2(signal),
        )

    def test_nullable_holding_nested_values_remain_valid(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["industry_panorama"] = None
        holding["factor_evidence"] = None
        holding["mainline_links"] = None
        holding["bull_evidence"] = None
        holding["bear_evidence"] = None
        holding["evidence_gaps"] = None
        signal["holding_analyses"] = [holding]
        signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
        self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_holding_link_leader_roles_must_be_list_or_null(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["mainline_links"][0]["leader_roles"] = "leader"
        signal["holding_analyses"] = [holding]
        self.assertIn(
            "holding_analyses[0].mainline_links[0] leader_roles must be a list or null",
            reporting.validate_signal_v2(signal),
        )

    def test_holding_nested_objects_require_task_five_child_keys(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["industry_panorama"] = {}
        holding["factor_evidence"] = {}
        signal["holding_analyses"] = [holding]
        errors = reporting.validate_signal_v2(signal)
        panorama_fields = (
            "segment_focus", "value_chain_position",
            "upstream_dependency_check", "downstream_customer_check",
            "industry_influence_question", "scarce_capability_check",
        )
        factor_fields = (
            "total_score", "trend_score", "macd_score",
            "fund_flow_score", "sector_score", "event_score",
        )
        for field in panorama_fields:
            with self.subTest(container="industry_panorama", field=field):
                self.assertIn(
                    f"holding_analyses[0].industry_panorama missing {field}",
                    errors,
                )
        for field in factor_fields:
            with self.subTest(container="factor_evidence", field=field):
                self.assertIn(
                    f"holding_analyses[0].factor_evidence missing {field}",
                    errors,
                )

    def test_holding_factor_evidence_accepts_fund_flow_imputation_metadata(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["factor_evidence"]["fund_flow_score"] = None
        holding["factor_evidence"]["score_imputations"] = {"fund_flow": 50.0}
        holding["factor_evidence"]["raw"] = {
            "fund_flow_5d_net_wan": None
        }
        signal["holding_analyses"] = [holding]
        signal["portfolio_actions"] = [portfolio_action_fixture(holding)]

        self.assertEqual(reporting.validate_signal_v2(signal), [])
        report = reporting.render_report({}, signal, {}, {}, [])
        self.assertIn("资金 证据不足（总分按中性 50 插补）", report)
        self.assertNotIn("资金 50.0", report)

    def test_holding_factor_evidence_rejects_non_object_score_imputations(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["factor_evidence"]["score_imputations"] = []
        signal["holding_analyses"] = [holding]

        self.assertIn(
            "holding_analyses[0].factor_evidence.score_imputations must be an object",
            reporting.validate_signal_v2(signal),
        )

    def test_holding_factor_imputation_requires_exact_neutral_value(self):
        invalid_values = (True, "50", 49.9, float("nan"), float("inf"))
        for value in invalid_values:
            with self.subTest(value=value):
                signal = signal_fixture()
                signal["evidence_index"] = [evidence_fixture()]
                holding = holding_fixture()
                holding["factor_evidence"]["fund_flow_score"] = None
                holding["factor_evidence"]["score_imputations"] = {
                    "fund_flow": value
                }
                signal["holding_analyses"] = [holding]

                self.assertIn(
                    "holding_analyses[0].factor_evidence.score_imputations."
                    "fund_flow must equal finite number 50",
                    reporting.validate_signal_v2(signal),
                )

    def test_holding_factor_imputation_and_public_score_are_mutually_exclusive(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["factor_evidence"]["score_imputations"] = {
            "fund_flow": 50.0
        }
        signal["holding_analyses"] = [holding]

        self.assertIn(
            "holding_analyses[0].factor_evidence fund_flow_score and "
            "score_imputations.fund_flow are mutually exclusive",
            reporting.validate_signal_v2(signal),
        )

    def test_stock_score_fund_flow_missing_shape_requires_neutral_imputation(self):
        def missing_signal():
            signal = signal_fixture()
            signal["evidence_index"] = [evidence_fixture()]
            holding = holding_fixture()
            holding["factor_evidence"]["fund_flow_score"] = None
            holding["factor_evidence"]["score_imputations"] = {
                "fund_flow": 50.0
            }
            holding["factor_evidence"]["raw"] = {
                "fund_flow_5d_net_wan": None
            }
            signal["holding_analyses"] = [holding]
            signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
            signal["stock_scores"] = [stock_score_fixture(
                fund_flow_score=None,
                fund_flow_net=None,
                score_imputations={"fund_flow": 50.0},
                missing_data=["fund_flow"],
            )]
            return signal

        self.assertEqual(reporting.validate_signal_v2(missing_signal()), [])

        cases = (
            ("public_score", lambda row: row["scores"].__setitem__(
                "fund_flow_score", 50.0
            )),
            ("raw_net", lambda row: row["scores"]["raw"].__setitem__(
                "fund_flow_5d_net_wan", 0.0
            )),
            ("imputation", lambda row: row["scores"].__setitem__(
                "score_imputations", {}
            )),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                signal = missing_signal()
                mutate(signal["stock_scores"][0])
                self.assertTrue(
                    any(
                        error.startswith("stock_scores[0] fund_flow missing")
                        for error in reporting.validate_signal_v2(signal)
                    )
                )

    def test_fund_flow_imputation_requires_missing_and_null_public_evidence(self):
        def imputed_signal():
            signal = signal_fixture()
            signal["evidence_index"] = [evidence_fixture()]
            holding = holding_fixture()
            holding["factor_evidence"]["fund_flow_score"] = None
            holding["factor_evidence"]["score_imputations"] = {
                "fund_flow": 50.0
            }
            holding["factor_evidence"]["raw"] = {
                "fund_flow_5d_net_wan": None
            }
            signal["holding_analyses"] = [holding]
            signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
            signal["stock_scores"] = [stock_score_fixture(
                fund_flow_score=None,
                fund_flow_net=None,
                score_imputations={"fund_flow": 50.0},
                missing_data=["fund_flow"],
            )]
            return signal

        missing_marker = imputed_signal()
        missing_marker["stock_scores"][0]["missing_data"] = []

        synced_raw = imputed_signal()
        synced_raw["stock_scores"][0]["missing_data"] = []
        synced_raw["stock_scores"][0]["scores"]["raw"][
            "fund_flow_5d_net_wan"
        ] = 123.0
        synced_raw["holding_analyses"][0]["factor_evidence"]["raw"][
            "fund_flow_5d_net_wan"
        ] = 123.0

        holding_only = imputed_signal()
        del holding_only["stock_scores"]
        holding_only["holding_analyses"][0]["factor_evidence"]["raw"][
            "fund_flow_5d_net_wan"
        ] = 123.0

        cases = (
            (
                "missing_marker",
                missing_marker,
                "stock_scores[0] fund_flow imputation requires missing_data "
                "to contain fund_flow",
            ),
            (
                "synced_stock_raw",
                synced_raw,
                "stock_scores[0] fund_flow imputation requires "
                "fund_flow_5d_net_wan null",
            ),
            (
                "synced_holding_raw",
                synced_raw,
                "holding_analyses[0].factor_evidence fund_flow imputation "
                "requires fund_flow_5d_net_wan null",
            ),
            (
                "holding_only_raw",
                holding_only,
                "holding_analyses[0].factor_evidence fund_flow imputation "
                "requires fund_flow_5d_net_wan null",
            ),
        )
        for label, signal, expected in cases:
            with self.subTest(label=label):
                self.assertIn(expected, reporting.validate_signal_v2(signal))

    def test_stock_score_accepts_zero_ratio_only_and_missing_history_shapes(self):
        cases = (
            (50.0, 0.0, {}, []),
            (65.0, None, {}, []),
            (None, None, {}, ["history"]),
        )
        for fund_score, fund_net, imputations, missing_data in cases:
            with self.subTest(
                fund_score=fund_score,
                fund_net=fund_net,
                missing_data=missing_data,
            ):
                signal = signal_fixture()
                signal["evidence_index"] = [evidence_fixture()]
                holding = holding_fixture()
                holding["factor_evidence"]["fund_flow_score"] = fund_score
                holding["factor_evidence"]["score_imputations"] = imputations
                holding["factor_evidence"]["raw"] = {
                    "fund_flow_5d_net_wan": fund_net
                }
                signal["holding_analyses"] = [holding]
                signal["portfolio_actions"] = [portfolio_action_fixture(holding)]
                signal["stock_scores"] = [stock_score_fixture(
                    fund_score,
                    fund_net,
                    imputations,
                    missing_data,
                )]

                self.assertEqual(reporting.validate_signal_v2(signal), [])

    def test_stock_scores_fail_closed_and_cross_layer_values_must_match(self):
        signal = signal_fixture()
        signal["stock_scores"] = {}
        self.assertIn(
            "stock_scores must be a list",
            reporting.validate_signal_v2(signal),
        )

        signal = signal_fixture()
        signal["stock_scores"] = [stock_score_fixture(), stock_score_fixture()]
        self.assertIn(
            "duplicate stock_scores code 000001",
            reporting.validate_signal_v2(signal),
        )

        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["factor_evidence"]["fund_flow_score"] = 11
        holding["factor_evidence"]["score_imputations"] = {
            "fund_flow": 50.0
        }
        holding["factor_evidence"]["raw"] = {
            "fund_flow_5d_net_wan": 99.0
        }
        signal["holding_analyses"] = [holding]
        signal["stock_scores"] = [stock_score_fixture()]
        errors = reporting.validate_signal_v2(signal)
        for field in (
            "fund_flow_score",
            "score_imputations.fund_flow",
            "raw.fund_flow_5d_net_wan",
        ):
            with self.subTest(field=field):
                self.assertIn(
                    "holding_analyses[0].factor_evidence."
                    f"{field} does not match stock_scores[0]",
                    errors,
                )

    def test_stock_score_cross_layer_raw_value_must_be_explicit(self):
        def ratio_signal():
            signal = signal_fixture()
            signal["evidence_index"] = [evidence_fixture()]
            holding = holding_fixture()
            holding["factor_evidence"]["fund_flow_score"] = 65.0
            holding["factor_evidence"]["score_imputations"] = {}
            holding["factor_evidence"]["raw"] = {
                "fund_flow_5d_net_wan": None
            }
            signal["holding_analyses"] = [holding]
            signal["stock_scores"] = [stock_score_fixture(65.0, None)]
            return signal

        signal = ratio_signal()
        signal["stock_scores"][0]["scores"]["raw"] = {}
        self.assertIn(
            "stock_scores[0].scores.raw missing fund_flow_5d_net_wan",
            reporting.validate_signal_v2(signal),
        )

        signal = ratio_signal()
        signal["holding_analyses"][0]["factor_evidence"].pop("raw")
        self.assertIn(
            "holding_analyses[0].factor_evidence.raw must be an object",
            reporting.validate_signal_v2(signal),
        )

        signal = ratio_signal()
        signal["holding_analyses"][0]["factor_evidence"]["raw"] = []
        self.assertIn(
            "holding_analyses[0].factor_evidence.raw must be an object",
            reporting.validate_signal_v2(signal),
        )

    def test_holding_link_rejects_invalid_leader_role_value(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        holding = holding_fixture()
        holding["mainline_links"][0]["leader_roles"] = [
            "fundamental_beneficiary"
        ]
        signal["holding_analyses"] = [holding]
        self.assertIn(
            "holding_analyses[0].mainline_links[0].leader_roles[0] invalid role",
            reporting.validate_signal_v2(signal),
        )

    def test_renderer_uses_market_as_of_for_title(self):
        signal = signal_fixture()
        signal["market_snapshot"]["as_of"] = "2024-02-03"
        report = reporting.render_report({}, signal, {}, {}, [])
        self.assertTrue(report.startswith("# 股票策略闭环报告 - 2024-02-03\n"))

    def test_renderer_sanitizes_title_to_one_line(self):
        report = reporting.render_report(
            {}, signal_fixture(), {}, {}, [], title="T\n## injected"
        )
        headings = [
            line for line in report.splitlines() if line.startswith("## ")
        ]
        self.assertEqual(len(headings), 10)
        self.assertNotIn("## injected", headings)
        self.assertTrue(report.startswith("# T ## injected - 2026-07-15\n"))

    def test_renderer_sanitizes_lone_carriage_return_in_title(self):
        report = reporting.render_report(
            {}, signal_fixture(), {}, {}, [], title="T\r## injected"
        )
        headings = [
            line for line in report.splitlines() if line.startswith("## ")
        ]
        self.assertEqual(len(headings), 10)
        self.assertNotIn("## injected", headings)
        self.assertTrue(report.startswith("# T ## injected - 2026-07-15\n"))

    def test_renderer_shows_portfolio_and_holding_diagnostics(self):
        signal = signal_fixture()
        signal["evidence_index"] = [evidence_fixture()]
        signal["market_mainlines"] = [mainline_fixture()]
        signal["portfolio_diagnosis"] = {
            "stock_exposure": 0.8,
            "cash_weight": 0.2,
            "single_stock_concentration": [
                {"code": "000001", "name": "甲", "weight": 0.4},
            ],
            "industry_concentration": [{"industry": "机械", "weight": 0.4}],
            "theme_concentration": [{"theme": "机器人", "weight": 0.4}],
            "mainline_alignment": [{"mainline": "机器人", "weight": 0.4}],
            "off_mainline_exposure": 0.4,
            "counter_regime_exposure": None,
            "counter_regime_exposure_note": "风格映射缺失",
            "shared_catalyst_risks": ["机器人"],
            "portfolio_posture": "hold_and_verify",
            "top_action_priorities": [],
        }
        signal["holding_analyses"] = [holding_fixture()]
        signal["portfolio_actions"] = [
            portfolio_action_fixture(signal["holding_analyses"][0])
        ]
        report = reporting.render_report({}, signal, {}, {}, [])
        for text in (
            "主导主线：机器人", "甲(liquidity_anchor)",
            "组合姿态：hold_and_verify", "单股集中度", "主题集中度",
            "主线对齐", "非主线暴露：40.00%", "逆市场状态暴露：证据不足",
            "共享催化风险：机器人", "主线关系：leader",
            "龙头角色：liquidity_anchor", "论点状态：supported",
            "数据可信度：high", "证据缺口：订单待验证", "证据编号：ev-1",
            "上游依赖：材料供应", "下游客户/需求：整机厂",
            "五因子/技术证据", "建议：hold",
        ):
            with self.subTest(text=text):
                self.assertIn(text, report)

    def test_renderer_handles_none_numbers_as_insufficient_evidence(self):
        signal = signal_fixture()
        signal["portfolio_diagnosis"] = {
            "stock_exposure": None,
            "cash_weight": None,
            "single_stock_concentration": [
                {"code": "000001", "name": "甲", "weight": None},
            ],
            "industry_concentration": [
                {"industry": "机械", "weight": None},
            ],
            "theme_concentration": [],
            "mainline_alignment": [],
            "off_mainline_exposure": None,
            "counter_regime_exposure": None,
            "counter_regime_exposure_note": None,
            "shared_catalyst_risks": [],
            "portfolio_posture": None,
            "top_action_priorities": [],
        }
        report = reporting.render_report({}, signal, {}, {}, [])
        self.assertIn("证据不足", report)
        self.assertNotIn("目标点位", report)
        self.assertNotIn("保证收益", report)
        self.assertNotIn("情景概率", report)

    def test_renderer_treats_none_collections_as_insufficient_evidence(self):
        signal = signal_fixture()
        signal["market_snapshot"]["indices"] = None
        signal["market_snapshot"]["breadth"] = None
        for field in (
            "single_stock_concentration", "industry_concentration",
            "theme_concentration", "mainline_alignment",
            "shared_catalyst_risks", "top_action_priorities",
        ):
            signal["portfolio_diagnosis"][field] = None
        for field in (
            "stock_exposure", "cash_weight", "off_mainline_exposure",
            "counter_regime_exposure", "counter_regime_exposure_note",
            "portfolio_posture",
        ):
            signal["portfolio_diagnosis"][field] = None
        report = reporting.render_report({}, signal, {}, {}, None)
        self.assertIn("证据不足", report)


if __name__ == "__main__":
    unittest.main()
