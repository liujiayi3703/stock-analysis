import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import market_context


class EvidenceAndMarketSnapshotTests(unittest.TestCase):
    def test_future_evidence_is_unknown_even_when_recent_dates_include_it(self):
        self.assertEqual(
            market_context.classify_freshness(
                "2026-07-16", "2026-07-15", ["2026-07-16"]
            ),
            "unknown",
        )
        evidence = market_context.make_evidence(
            "future",
            "news",
            "future event",
            "fixture",
            "2026-07-16",
            "2026-07-15",
            ["2026-07-16"],
            "market",
            "high",
        )
        self.assertEqual(evidence["freshness"], "unknown")
        self.assertEqual(evidence["reliability"], "low")

    def test_stale_evidence_cannot_be_high_reliability(self):
        item = market_context.make_evidence(
            "ev-1", "news", "旧催化", "fixture", "2026-06-01",
            "2026-07-15", ["2026-07-15", "2026-07-14", "2026-07-13"], "market", "high"
        )
        self.assertEqual(item["freshness"], "stale")
        self.assertEqual(item["reliability"], "low")

    def test_index_only_snapshot_is_not_high_confidence(self):
        snapshot = market_context.build_market_snapshot(
            indices=[{"name": "上证指数", "change_pct": 1.2}],
            breadth={},
            latest_trade_date="2026-07-15",
        )
        self.assertEqual(snapshot["confidence"], "low")
        self.assertIn("breadth", snapshot["missing_evidence"])
        self.assertIn("turnover", snapshot["missing_evidence"])

    def test_breadth_and_turnover_support_structural_regime(self):
        snapshot = market_context.build_market_snapshot(
            indices=[
                {"name": "上证指数", "change_pct": 0.4, "as_of": "2026-07-15"},
                {"name": "创业板指", "change_pct": -0.8, "as_of": "2026-07-15"},
            ],
            breadth={
                "advancers": 1800,
                "decliners": 3200,
                "unchanged": 100,
                "turnover_yuan": 1.4e12,
                "as_of": "2026-07-15",
                "sample_size": 5100,
                "complete": True,
            },
            latest_trade_date="2026-07-15",
        )
        self.assertEqual(snapshot["regime"], "structural")
        self.assertEqual(snapshot["confidence"], "high")

    def test_extreme_index_divergence_is_high_volatility(self):
        snapshot = market_context.build_market_snapshot(
            indices=[
                {"name": "上证指数", "change_pct": 1.0, "as_of": "2026-07-15"},
                {"name": "创业板指", "change_pct": -3.0, "as_of": "2026-07-15"},
            ],
            breadth={
                "advancers": 2200,
                "decliners": 2800,
                "turnover_yuan": 1.6e12,
                "as_of": "2026-07-15",
                "sample_size": 5000,
                "complete": True,
            },
            latest_trade_date="2026-07-15",
        )
        self.assertEqual(snapshot["regime"], "high_volatility")

    def test_stale_market_sources_cannot_support_current_session_conclusion(self):
        snapshot = market_context.build_market_snapshot(
            indices=[
                {"name": "上证指数", "change_pct": 1.0, "as_of": "2026-06-01"},
                {"name": "创业板指", "change_pct": -3.0, "as_of": "2026-06-01"},
            ],
            breadth={
                "advancers": 2200,
                "decliners": 2800,
                "turnover_yuan": 1.6e12,
                "as_of": "2026-06-01",
                "sample_size": 5000,
                "complete": True,
            },
            latest_trade_date="2026-07-15",
        )
        self.assertEqual(snapshot["regime"], "insufficient_evidence")
        self.assertEqual(snapshot["confidence"], "low")
        self.assertIn("indices_as_of", snapshot["missing_evidence"])
        self.assertIn("breadth_as_of", snapshot["missing_evidence"])

    def test_partial_breadth_fields_are_missing_evidence(self):
        for partial_breadth in ({"advancers": 2200}, {"decliners": 2800}):
            with self.subTest(partial_breadth=partial_breadth):
                snapshot = market_context.build_market_snapshot(
                    indices=[
                        {"name": "上证指数", "change_pct": 0.4, "as_of": "2026-07-15"},
                    ],
                    breadth={
                        **partial_breadth,
                        "turnover_yuan": 1.6e12,
                        "as_of": "2026-07-15",
                        "sample_size": 5000,
                        "complete": True,
                    },
                    latest_trade_date="2026-07-15",
                )
                self.assertEqual(snapshot["regime"], "insufficient_evidence")
                self.assertEqual(snapshot["confidence"], "low")
                self.assertIn("breadth", snapshot["missing_evidence"])

    def test_partial_breadth_sample_cannot_support_high_confidence(self):
        snapshot = market_context.build_market_snapshot(
            indices=[
                {"name": "Index A", "change_pct": 1.0, "as_of": "2026-07-15"},
                {"name": "Index B", "change_pct": -1.0, "as_of": "2026-07-15"},
            ],
            breadth={
                "advancers": 20,
                "decliners": 20,
                "turnover_yuan": 1.6e12,
                "as_of": "2026-07-15",
                "sample_size": 40,
                "complete": False,
            },
            latest_trade_date="2026-07-15",
        )

        self.assertEqual(snapshot["confidence"], "low")
        self.assertEqual(snapshot["regime"], "insufficient_evidence")
        self.assertIn("breadth_completeness", snapshot["missing_evidence"])

    def test_present_non_false_market_stale_flags_fail_closed(self):
        base_indices = [
            {
                "name": "Index A",
                "change_pct": 1.0,
                "as_of": "2026-07-15",
            },
            {
                "name": "Index B",
                "change_pct": 0.5,
                "as_of": "2026-07-15",
            },
        ]
        base_breadth = {
            "advancers": 3200,
            "decliners": 1400,
            "turnover_yuan": 1.6e12,
            "as_of": "2026-07-15",
            "complete": True,
        }
        for source in ("index", "breadth"):
            for stale in (True, None, "false", "true", 0, 1):
                with self.subTest(source=source, stale=stale):
                    indices = [dict(row) for row in base_indices]
                    breadth = dict(base_breadth)
                    if source == "index":
                        indices[0]["stale"] = stale
                    else:
                        breadth["stale"] = stale
                    snapshot = market_context.build_market_snapshot(
                        indices, breadth, "2026-07-15"
                    )
                    outlook = market_context.build_market_outlook(snapshot, [])
                    self.assertEqual(
                        snapshot["regime"], "insufficient_evidence"
                    )
                    self.assertEqual(snapshot["confidence"], "low")
                    self.assertEqual(
                        outlook["short_term"]["confidence"], "low"
                    )
                    self.assertEqual(
                        outlook["medium_term"]["confidence"], "low"
                    )

        for row in base_indices:
            row["stale"] = False
        base_breadth["stale"] = False
        snapshot = market_context.build_market_snapshot(
            base_indices, base_breadth, "2026-07-15"
        )
        self.assertEqual(snapshot["confidence"], "high")

    def test_snapshot_skips_malformed_index_rows_without_crashing(self):
        snapshot = market_context.build_market_snapshot(
            [None, 7, [], {"change_pct": [], "as_of": "2026-07-15"}],
            None,
            "2026-07-15",
        )

        self.assertEqual(snapshot["regime"], "insufficient_evidence")
        self.assertEqual(snapshot["confidence"], "low")
        self.assertEqual(snapshot["indices"], [])

    def test_snapshot_malformed_breadth_numbers_fail_closed_without_crashing(self):
        malformed_values = ([], {}, True, False, float("nan"), float("inf"), "bad")
        for field in ("advancers", "decliners", "turnover_yuan"):
            for value in malformed_values:
                with self.subTest(field=field, value=value):
                    breadth = {
                        "advancers": 3200,
                        "decliners": 1400,
                        "turnover_yuan": 1.6e12,
                        "as_of": "2026-07-15",
                        "complete": True,
                    }
                    breadth[field] = value

                    snapshot = market_context.build_market_snapshot(
                        [{"name": "Index A", "change_pct": 1.0, "as_of": "2026-07-15"}],
                        breadth,
                        "2026-07-15",
                    )

                    self.assertEqual(snapshot["regime"], "insufficient_evidence")
                    self.assertEqual(snapshot["confidence"], "low")
                    self.assertIn(
                        "turnover" if field == "turnover_yuan" else "breadth",
                        snapshot["missing_evidence"],
                    )


class MainlineCandidateTests(unittest.TestCase):
    def test_candidate_selection_skips_malformed_modes_rows_and_keys(self):
        rankings = {
            "concept": {
                "change_desc": [None, 7, [], {"group_key": []}],
                "turnover_desc": "not-a-list",
            },
            "major": None,
            "invalid-mode": {
                "change_desc": [
                    {"group_key": "x", "name": "invalid"}
                ],
                "turnover_desc": [],
            },
        }

        self.assertEqual(
            market_context.select_board_candidates(rankings, []), []
        )
    def test_candidate_selection_is_deduplicated_and_bounded(self):
        rows = [
            {
                "group_key": f"N:{i}",
                "name": f"Theme {i}",
                "change_pct": 10 - i,
                "turnover_yuan": 1000 - i,
            }
            for i in range(20)
        ]
        rankings = {
            mode: {"change_desc": rows, "turnover_desc": list(reversed(rows))}
            for mode in ("major", "sub", "concept")
        }

        candidates = market_context.select_board_candidates(rankings, [], limit=12)

        self.assertLessEqual(len(candidates), 12)
        self.assertEqual(
            len({row["board_id"] for row in candidates}), len(candidates)
        )

    def test_same_group_key_in_different_modes_keeps_distinct_identity(self):
        row = {
            "group_key": "N:shared",
            "name": "Shared label",
            "change_pct": 2.0,
            "turnover_yuan": 1e10,
        }
        rankings = {
            "major": {"change_desc": [row], "turnover_desc": []},
            "concept": {"change_desc": [row], "turnover_desc": []},
        }

        candidates = market_context.select_board_candidates(rankings, [])

        self.assertEqual(len(candidates), 2)
        self.assertEqual({row["mode"] for row in candidates}, {"major", "concept"})
        self.assertEqual(len({row["board_id"] for row in candidates}), 2)

    def test_board_evidence_is_current_only_when_ranking_and_detail_sessions_match(self):
        candidate = {
            "mode": "concept",
            "group_key": "N:robotics",
            "as_of": "2026-07-15",
            "stale": False,
        }
        current_detail = {"as_of": "2026-07-15", "stale": False, "items": []}

        self.assertTrue(
            market_context.board_evidence_is_current(
                candidate, current_detail, "2026-07-15"
            )
        )
        for changed_candidate, changed_detail in (
            ({**candidate, "as_of": "2026-07-14"}, current_detail),
            (candidate, {**current_detail, "as_of": "2026-07-14"}),
            ({**candidate, "stale": True}, current_detail),
            (candidate, {**current_detail, "stale": True}),
            (candidate, {**current_detail, "as_of": ""}),
            ({key: value for key, value in candidate.items() if key != "stale"}, current_detail),
            (candidate, {key: value for key, value in current_detail.items() if key != "stale"}),
            ({**candidate, "stale": None}, current_detail),
            (candidate, {**current_detail, "stale": None}),
            ({**candidate, "stale": "false"}, current_detail),
            (candidate, {**current_detail, "stale": "true"}),
            ({**candidate, "stale": 0}, current_detail),
        ):
            with self.subTest(candidate=changed_candidate, detail=changed_detail):
                self.assertFalse(
                    market_context.board_evidence_is_current(
                        changed_candidate, changed_detail, "2026-07-15"
                    )
                )

    def test_malformed_history_collections_do_not_crash_continuity(self):
        identity = market_context.board_identity("concept", "N:robotics")
        malformed = [
            {"trade_date": "2026-07-13", "top_change": None, "top_turnover": []},
            {"trade_date": "2026-07-14", "top_change": [{"bad": "shape"}], "top_turnover": []},
            {"trade_date": "2026-07-15", "top_change": identity, "top_turnover": 42},
        ]

        result = market_context.continuity_score(
            identity, malformed, latest_trade_date="2026-07-15"
        )

        self.assertFalse(result["known"])
        self.assertEqual(result["hits"], 0)

    def test_continuity_ignores_non_dict_rows_and_invalid_trade_dates(self):
        identity = market_context.board_identity("concept", "N:robotics")
        history = [
            None,
            [],
            "not-a-row",
            {"trade_date": "not-a-date", "top_change": [identity], "top_turnover": []},
            {"trade_date": "2026-02-30", "top_change": [identity], "top_turnover": []},
            {"trade_date": "2026-07-14junk", "top_change": [identity], "top_turnover": []},
            {"trade_date": "2026-07-15", "top_change": [identity], "top_turnover": []},
        ]

        result = market_context.continuity_score(
            identity, history, latest_trade_date="2026-07-15"
        )

        self.assertEqual(result["sessions"], 1)
        self.assertEqual(result["hits"], 0)
        self.assertFalse(result["known"])

    def test_composite_candidates_never_fall_back_to_a_shared_legacy_detail(self):
        raw_key = "N:shared"
        candidates = [
            {
                "mode": mode,
                "group_key": raw_key,
                "board_id": market_context.board_identity(mode, raw_key),
                "name": mode,
                "turnover_yuan": 0.0,
                "base_score": 80.0,
                "continuity": {"known": True, "score": 20.0},
            }
            for mode in ("major", "concept")
        ]
        legacy_details = {
            raw_key: {
                "items": [
                    {
                        "code": "600000",
                        "name": "Legacy only",
                        "change_pct": 5.0,
                        "turnover_yuan": 1e10,
                    }
                ]
            }
        }

        scored = market_context.score_mainline_candidates(
            candidates, legacy_details, [], []
        )
        finalized = market_context.finalize_mainlines(
            scored, legacy_details, set()
        )

        self.assertEqual([row["score_components"]["breadth"] for row in scored], [0.0, 0.0])
        self.assertEqual(
            [row["classification"] for row in finalized],
            ["insufficient_evidence", "insufficient_evidence"],
        )

    def test_forged_cross_mode_or_malformed_explicit_identity_fails_closed(self):
        raw_key = "N:shared"
        canonical_major = market_context.board_identity("major", raw_key)
        forged_concept = market_context.board_identity("concept", raw_key)
        candidates = [
            {
                "mode": "major",
                "group_key": raw_key,
                "board_id": forged_concept,
                "name": "Forged cross-mode",
                "turnover_yuan": 0.0,
            },
            {
                "board_id": "malformed-explicit-id",
                "name": "Malformed identity only",
                "turnover_yuan": 0.0,
            },
            {
                "mode": "invalid-mode",
                "group_key": raw_key,
                "name": "Invalid mode is not legacy",
                "turnover_yuan": 0.0,
            },
        ]
        leaked_item = {
            "code": "600000",
            "name": "Must not leak",
            "change_pct": 5.0,
            "turnover_yuan": 1e10,
        }
        details = {
            forged_concept: {"items": [leaked_item]},
            "malformed-explicit-id": {"items": [leaked_item]},
            canonical_major: {"items": [leaked_item]},
            raw_key: {"items": [leaked_item]},
        }
        history = [
            {
                "trade_date": date,
                "top_change": [forged_concept, "malformed-explicit-id", raw_key],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]

        scored = market_context.score_mainline_candidates(
            candidates, details, [], history
        )
        finalized = market_context.finalize_mainlines(scored, details, set())

        self.assertEqual([row["score_components"]["breadth"] for row in scored], [0.0, 0.0, 0.0])
        self.assertEqual([row["continuity"]["hits"] for row in scored], [0, 0, 0])
        self.assertEqual(
            [row["classification"] for row in finalized],
            ["insufficient_evidence", "insufficient_evidence", "insufficient_evidence"],
        )

    def test_identity_resolver_distinguishes_absent_fields_from_falsey_invalid_values(self):
        raw_key = "N:shared"
        explicit = market_context.board_identity("concept", raw_key)
        item = {
            "code": "600000",
            "name": "Evidence",
            "change_pct": 5.0,
            "turnover_yuan": 1e10,
        }
        details = {
            raw_key: {"items": [item]},
            explicit: {"items": [item]},
        }
        history = [
            {
                "trade_date": date,
                "top_change": [raw_key, explicit],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]
        invalid_candidates = [
            {"mode": 0, "group_key": raw_key},
            {"mode": False, "group_key": raw_key},
            {"board_id": 0, "group_key": raw_key},
            {"board_id": False, "group_key": raw_key},
            {"board_id": None, "group_key": raw_key},
            {"board_id": "", "group_key": raw_key},
            {"board_id": explicit, "group_key": "N:different"},
        ]
        invalid_candidates = [
            {**candidate, "name": f"invalid-{index}", "turnover_yuan": 0.0}
            for index, candidate in enumerate(invalid_candidates)
        ]

        invalid_scored = market_context.score_mainline_candidates(
            invalid_candidates, details, [], history
        )
        invalid_final = market_context.finalize_mainlines(
            invalid_scored, details, set()
        )

        self.assertEqual(
            [row["score_components"]["breadth"] for row in invalid_scored],
            [0.0] * len(invalid_candidates),
        )
        self.assertEqual(
            [row["continuity"]["hits"] for row in invalid_scored],
            [0] * len(invalid_candidates),
        )
        self.assertTrue(
            all(row["classification"] == "insufficient_evidence" for row in invalid_final)
        )

        valid_candidates = [
            {"group_key": raw_key, "name": "raw legacy", "turnover_yuan": 0.0},
            {"board_id": explicit, "name": "identity only", "turnover_yuan": 0.0},
            {
                "board_id": explicit,
                "group_key": raw_key,
                "name": "identity with matching key",
                "turnover_yuan": 0.0,
            },
        ]

        valid_scored = market_context.score_mainline_candidates(
            valid_candidates,
            details,
            [],
            history,
            latest_trade_date="2026-07-15",
        )
        valid_final = market_context.finalize_mainlines(valid_scored, details, set())

        self.assertEqual(market_context.parse_board_identity(explicit), ("concept", raw_key))
        self.assertEqual(
            [row["score_components"]["breadth"] for row in valid_scored],
            [15.0, 15.0, 15.0],
        )
        self.assertEqual([row["continuity"]["hits"] for row in valid_scored], [3, 3, 3])
        self.assertTrue(
            all(row["classification"] != "insufficient_evidence" for row in valid_final)
        )

    def test_candidate_selection_matches_board_name_in_news(self):
        rankings = {
            "concept": {
                "change_desc": [
                    {
                        "group_key": "N:robotics",
                        "name": "Robotics",
                        "change_pct": 3.0,
                        "turnover_yuan": 1e10,
                    }
                ],
                "turnover_desc": [],
            }
        }

        candidates = market_context.select_board_candidates(
            rankings,
            [
                {
                    "title": "Robotics demand expands",
                    "content": "",
                    "published_at": "2026-07-15 09:30:00",
                }
            ],
            latest_trade_date="2026-07-15",
        )

        self.assertEqual(candidates[0]["preliminary_score"], 8.0)

    def test_candidate_selection_does_not_reward_an_empty_name(self):
        rankings = {
            "concept": {
                "change_desc": [
                    {
                        "group_key": "N:unnamed",
                        "name": "",
                        "change_pct": 3.0,
                        "turnover_yuan": 1e10,
                    }
                ],
                "turnover_desc": [],
            }
        }

        candidates = market_context.select_board_candidates(rankings, [])

        self.assertEqual(candidates[0]["preliminary_score"], 5.0)

    def test_candidate_selection_requires_current_session_news(self):
        rankings = {
            "concept": {
                "change_desc": [
                    {
                        "group_key": "N:robotics",
                        "name": "Robotics",
                        "change_pct": 3.0,
                        "turnover_yuan": 1e10,
                    }
                ],
                "turnover_desc": [],
            }
        }
        cases = (
            (
                "latest_trade_date_not_provided",
                [{"title": "Robotics demand", "published_at": "2026-07-15"}],
                None,
            ),
            (
                "news_date_missing",
                [{"title": "Robotics demand"}],
                "2026-07-15",
            ),
            (
                "news_is_stale",
                [{"title": "Robotics demand", "published_at": "2026-07-14"}],
                "2026-07-15",
            ),
        )

        for label, news_items, latest_trade_date in cases:
            with self.subTest(label=label):
                candidates = market_context.select_board_candidates(
                    rankings,
                    news_items,
                    latest_trade_date=latest_trade_date,
                )
                self.assertEqual(candidates[0]["preliminary_score"], 5.0)

    def test_candidate_news_reward_is_added_once_after_deduplication(self):
        row = {
            "group_key": "N:robotics",
            "name": "Robotics",
            "change_pct": 3.0,
            "turnover_yuan": 1e10,
        }
        rankings = {
            "concept": {
                "change_desc": [row],
                "turnover_desc": [row],
            }
        }

        candidates = market_context.select_board_candidates(
            rankings,
            [{"title": "Robotics demand", "published_at": "2026-07-15"}],
            latest_trade_date="2026-07-15",
        )

        self.assertEqual(candidates[0]["preliminary_score"], 13.0)

    def test_continuity_needs_three_sessions(self):
        result = market_context.continuity_score(
            "N:robotics",
            [
                {
                    "trade_date": "2026-07-15",
                    "top_change": ["N:robotics"],
                    "top_turnover": [],
                }
            ],
            latest_trade_date="2026-07-15",
        )

        self.assertFalse(result["known"])
        self.assertEqual(result["score"], 0.0)

    def test_repeated_board_gets_positive_continuity(self):
        history = [
            {
                "trade_date": date,
                "top_change": ["N:robotics"],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]

        result = market_context.continuity_score(
            "N:robotics", history, latest_trade_date="2026-07-15"
        )

        self.assertTrue(result["known"])
        self.assertGreater(result["score"], 0.0)

    def test_continuity_uses_observed_sessions_across_long_exchange_holidays(self):
        key = market_context.board_identity("concept", "N:holiday")
        cases = (
            (
                "spring_festival",
                "2026-02-23",
                ("2026-02-04", "2026-02-05", "2026-02-06", "2026-02-23"),
            ),
            (
                "national_day",
                "2026-10-09",
                ("2026-09-18", "2026-09-21", "2026-09-22", "2026-10-09"),
            ),
        )

        for label, latest_trade_date, dates in cases:
            with self.subTest(label=label):
                history = [
                    {
                        "trade_date": date,
                        "top_change": [key],
                        "top_turnover": [],
                    }
                    for date in dates
                ]

                result = market_context.continuity_score(
                    key, history, latest_trade_date=latest_trade_date
                )

                self.assertTrue(result["known"])
                self.assertEqual(result["sessions"], 4)
                self.assertEqual(result["hits"], 4)
                self.assertEqual(result["score"], 20.0)

    def test_continuity_rejects_weekend_or_invalid_latest_trade_date(self):
        history = [
            {
                "trade_date": date,
                "top_change": ["N:robotics"],
                "top_turnover": [],
            }
            for date in ("2026-07-16", "2026-07-17", "2026-07-18")
        ]
        for latest_trade_date in (
            "2026-07-18",
            "2026-07-19",
            "not-a-date",
            "2026-02-30",
        ):
            with self.subTest(latest_trade_date=latest_trade_date):
                result = market_context.continuity_score(
                    "N:robotics",
                    history,
                    latest_trade_date=latest_trade_date,
                )

                self.assertEqual(
                    result,
                    {"known": False, "score": 0.0, "sessions": 0, "hits": 0},
                )

        weekday_latest = market_context.continuity_score(
            "N:robotics", history, latest_trade_date="2026-07-20"
        )
        self.assertFalse(weekday_latest["known"])
        self.assertEqual(weekday_latest["sessions"], 2)

    def test_continuity_deduplicates_dates_and_caps_observed_sessions_at_ten(self):
        dates = (
            "2026-06-30",
            "2026-07-01",
            "2026-07-02",
            "2026-07-03",
            "2026-07-06",
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
            "2026-07-13",
            "2026-07-14",
            "2026-07-15",
            "2026-07-15",
        )
        history = [
            {
                "trade_date": date,
                "top_change": ["N:robotics"],
                "top_turnover": [],
            }
            for date in dates
        ]

        result = market_context.continuity_score(
            "N:robotics", history, latest_trade_date="2026-07-15"
        )

        self.assertTrue(result["known"])
        self.assertEqual(result["sessions"], 10)
        self.assertEqual(result["hits"], 10)
        self.assertEqual(result["score"], 20.0)

    def test_one_hit_across_three_sessions_is_not_known_continuity(self):
        history = [
            {
                "trade_date": date,
                "top_change": ["N:robotics"] if date == "2026-07-15" else [],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]

        result = market_context.continuity_score(
            "N:robotics", history, latest_trade_date="2026-07-15"
        )

        self.assertFalse(result["known"])
        self.assertEqual(result["hits"], 1)
        self.assertGreater(result["score"], 0.0)

    def test_score_mainline_candidates_exposes_score_components(self):
        candidates = [
            {
                "group_key": "N:robotics",
                "name": "Robotics",
                "turnover_yuan": 1e10,
            }
        ]
        details = {
            "N:robotics": {
                "items": [{"change_pct": 2.0}, {"change_pct": -1.0}]
            }
        }
        history = [
            {
                "trade_date": date,
                "top_change": ["N:robotics"],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]

        scored = market_context.score_mainline_candidates(
            candidates,
            details,
            [
                {
                    "title": "Robotics policy support",
                    "content": "",
                    "published_at": "2026-07-15 10:00:00",
                }
            ],
            history,
            latest_trade_date="2026-07-15",
        )

        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0]["score_components"]["breadth"], 7.5)
        self.assertTrue(scored[0]["catalyst_verified"])
        self.assertGreater(scored[0]["continuity"]["score"], 0.0)

    def test_non_positive_board_or_all_decliners_have_no_same_day_strength(self):
        key = market_context.board_identity("concept", "N:falling")
        history = [
            {
                "trade_date": date,
                "top_change": [key],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]
        news = [
            {
                "title": "Falling policy",
                "content": "",
                "published_at": "2026-07-15",
            }
        ]
        cases = (
            ("non_positive_board", -5.0, 3.0),
            ("all_decliners", 5.0, -8.0),
        )

        for label, board_change, item_change in cases:
            with self.subTest(label=label):
                candidate = {
                    "mode": "concept",
                    "group_key": "N:falling",
                    "board_id": key,
                    "name": "Falling",
                    "change_pct": board_change,
                    "turnover_yuan": 1.5e11,
                }
                details = {
                    key: {
                        "items": [
                            {
                                "code": "000001",
                                "name": "A",
                                "change_pct": item_change,
                                "turnover_yuan": 5e10,
                                "evidence_ids": ["constituent-a"],
                            },
                            {
                                "code": "000002",
                                "name": "B",
                                "change_pct": item_change,
                                "turnover_yuan": 4e10,
                                "evidence_ids": ["constituent-b"],
                            },
                        ]
                    }
                }

                scored = market_context.score_mainline_candidates(
                    [candidate],
                    details,
                    news,
                    history,
                    latest_trade_date="2026-07-15",
                )
                final = market_context.finalize_mainlines(scored, details, set())[0]

                self.assertEqual(
                    scored[0]["score_components"]["same_day_strength"], 0.0
                )
                self.assertNotIn(
                    final["classification"],
                    {"confirmed_mainline", "emerging_mainline"},
                )

    def test_continuity_excludes_sparse_sessions_outside_recent_window(self):
        key = market_context.board_identity("concept", "N:sparse")
        history = [
            {
                "trade_date": date,
                "top_change": [key],
                "top_turnover": [],
            }
            for date in (
                "2024-01-02",
                "2025-01-02",
                "2026-06-14",
                "2026-07-15",
            )
        ]

        result = market_context.continuity_score(
            key, history, latest_trade_date="2026-07-15"
        )

        self.assertFalse(result["known"])
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["sessions"], 1)

    def test_positive_recent_candidate_with_valid_leader_remains_confirmed(self):
        key = market_context.board_identity("concept", "N:rising")
        candidate = {
            "mode": "concept",
            "group_key": "N:rising",
            "board_id": key,
            "name": "Rising",
            "change_pct": 5.0,
            "turnover_yuan": 1.5e11,
        }
        details = {
            key: {
                "items": [
                    {
                        "code": "000001",
                        "name": "Leader",
                        "change_pct": 8.0,
                        "turnover_yuan": 5e10,
                        "ret20": 12.0,
                        "market_cap_yuan": 1e11,
                        "evidence_ids": ["constituent-leader"],
                    },
                    {
                        "code": "000002",
                        "name": "Follower",
                        "change_pct": 3.0,
                        "turnover_yuan": 4e10,
                        "evidence_ids": ["constituent-follower"],
                    },
                ]
            }
        }
        history = [
            {
                "trade_date": date,
                "top_change": [key],
                "top_turnover": [],
            }
            for date in ("2026-07-13", "2026-07-14", "2026-07-15")
        ]

        scored = market_context.score_mainline_candidates(
            [candidate],
            details,
            [{"title": "Rising demand", "published_at": "2026-07-15"}],
            history,
            latest_trade_date="2026-07-15",
        )
        final = market_context.finalize_mainlines(scored, details, set())[0]

        self.assertEqual(final["classification"], "confirmed_mainline")
        self.assertTrue(final["leaders"])

    def test_invalid_board_or_constituent_changes_cannot_create_strength(self):
        invalid_values = (
            float("nan"),
            float("inf"),
            float("-inf"),
            "5.0",
            True,
        )
        for value in invalid_values:
            for field in ("board", "constituent"):
                with self.subTest(field=field, value=value):
                    board_change = value if field == "board" else 5.0
                    item_change = 5.0 if field == "board" else value
                    candidate = {
                        "group_key": "N:invalid",
                        "name": "Invalid",
                        "change_pct": board_change,
                        "turnover_yuan": 0.0,
                    }
                    details = {
                        "N:invalid": {
                            "items": [
                                {
                                    "code": "000001",
                                    "name": "Invalid item",
                                    "change_pct": item_change,
                                    "turnover_yuan": 1e9,
                                    "evidence_ids": ["constituent-invalid"],
                                }
                            ]
                        }
                    }

                    scored = market_context.score_mainline_candidates(
                        [candidate],
                        details,
                        [],
                        [],
                        latest_trade_date="2026-07-15",
                    )

                    self.assertEqual(
                        scored[0]["score_components"]["same_day_strength"], 0.0
                    )
                    if field == "constituent":
                        self.assertEqual(
                            scored[0]["score_components"]["breadth"], 0.0
                        )

    def test_mainline_score_does_not_verify_an_empty_name(self):
        scored = market_context.score_mainline_candidates(
            [{"group_key": "N:unnamed", "name": "", "turnover_yuan": 0.0}],
            {},
            [],
            [],
        )

        self.assertFalse(scored[0]["catalyst_verified"])
        self.assertEqual(scored[0]["score_components"]["catalyst_logic"], 0.0)

    def test_mainline_score_requires_current_session_news(self):
        candidate = {
            "group_key": "N:robotics",
            "name": "Robotics",
            "turnover_yuan": 0.0,
        }
        cases = (
            (
                "latest_trade_date_not_provided",
                [{"title": "Robotics demand", "published_at": "2026-07-15"}],
                None,
            ),
            (
                "news_date_missing",
                [{"title": "Robotics demand"}],
                "2026-07-15",
            ),
            (
                "news_is_stale",
                [{"title": "Robotics demand", "published_at": "2026-07-14"}],
                "2026-07-15",
            ),
        )

        for label, news_items, latest_trade_date in cases:
            with self.subTest(label=label):
                scored = market_context.score_mainline_candidates(
                    [candidate],
                    {},
                    news_items,
                    [],
                    latest_trade_date=latest_trade_date,
                )
                self.assertFalse(scored[0]["catalyst_verified"])
                self.assertEqual(
                    scored[0]["score_components"]["catalyst_logic"], 0.0
                )

    def test_malformed_candidate_turnover_and_detail_shapes_contribute_zero(self):
        malformed_values = ([], {}, True, float("nan"), float("inf"), "bad")
        for value in malformed_values:
            with self.subTest(value=value):
                scored = market_context.score_mainline_candidates(
                    [{"group_key": "N:robotics", "name": "Robotics", "turnover_yuan": value}],
                    {"N:robotics": {"items": value}},
                    [],
                    [],
                )
                finalized = market_context.finalize_mainlines(
                    scored, {"N:robotics": {"items": value}}, set()
                )

                self.assertEqual(scored[0]["score_components"]["liquidity"], 0.0)
                self.assertEqual(scored[0]["score_components"]["breadth"], 0.0)
                self.assertEqual(finalized[0]["classification"], "insufficient_evidence")


class LeaderAndClassificationTests(unittest.TestCase):
    def test_emotion_and_liquidity_roles_require_strictly_positive_turnover(self):
        invalid_turnovers = (
            0,
            -1,
            [],
            {},
            True,
            float("nan"),
            float("inf"),
            "bad",
        )
        for turnover in invalid_turnovers:
            with self.subTest(turnover=turnover):
                leaders = market_context.classify_leader_roles(
                    [
                        {
                            "code": "000001",
                            "name": "Evidence",
                            "change_pct": 10.0,
                            "turnover_yuan": turnover,
                            "limit_up": True,
                            "ret20": 8.0,
                            "market_cap_yuan": 1e10,
                        }
                    ],
                    set(),
                )
                roles = {row["role"] for row in leaders}
                self.assertNotIn("emotion_leader", roles)
                self.assertNotIn("liquidity_anchor", roles)
                self.assertIn("trend_leader", roles)
                self.assertIn("industry_representative", roles)

        positive = market_context.classify_leader_roles(
            [
                {
                    "code": "000001",
                    "name": "Evidence",
                    "change_pct": 10.0,
                    "turnover_yuan": 1.0,
                    "limit_up": True,
                }
            ],
            set(),
        )
        positive_roles = {row["role"] for row in positive}
        self.assertIn("emotion_leader", positive_roles)
        self.assertIn("liquidity_anchor", positive_roles)

    def test_leader_roles_are_evidence_specific(self):
        items = [
            {
                "code": "000001",
                "name": "甲",
                "change_pct": 10.0,
                "turnover_yuan": 3e9,
                "market_cap_yuan": 9e10,
                "limit_up": True,
                "ret20": 8.0,
                "evidence_ids": ["ev-1"],
            },
            {
                "code": "000002",
                "name": "乙",
                "change_pct": 4.0,
                "turnover_yuan": 5e9,
                "market_cap_yuan": 7e10,
                "limit_up": False,
                "ret20": 15.0,
                "evidence_ids": ["ev-2"],
            },
        ]

        leaders = market_context.classify_leader_roles(items, {"000002"})

        roles = {(row["code"], row["role"]) for row in leaders}
        allowed_roles = {
            "emotion_leader",
            "liquidity_anchor",
            "trend_leader",
            "industry_representative",
            "held_exposure",
        }
        self.assertLessEqual({row["role"] for row in leaders}, allowed_roles)
        self.assertIn(("000001", "emotion_leader"), roles)
        self.assertIn(("000002", "liquidity_anchor"), roles)
        self.assertIn(("000002", "trend_leader"), roles)
        self.assertIn(("000001", "industry_representative"), roles)
        self.assertIn(("000002", "held_exposure"), roles)
        industry_representative = next(
            row
            for row in leaders
            if row["role"] == "industry_representative"
        )
        self.assertIn("市值", industry_representative["role_evidence"])
        for leader in leaders:
            self.assertTrue(leader["role_evidence"])
            self.assertIn("evidence_ids", leader)
            self.assertIn(leader["confidence"], {"low", "medium", "high"})
            self.assertTrue(leader["risk"])

    def test_one_session_cannot_be_confirmed_mainline(self):
        candidate = {
            "group_key": "N:机器人",
            "name": "机器人",
            "base_score": 85.0,
            "continuity": {"known": False, "score": 0.0},
            "catalyst_verified": True,
        }

        result = market_context.finalize_mainlines(
            [candidate],
            {
                "N:机器人": {
                    "items": [
                        {
                            "code": "000001",
                            "name": "甲",
                            "change_pct": 1.0,
                            "turnover_yuan": 1e9,
                        }
                    ]
                }
            },
            set(),
        )

        self.assertNotEqual(result[0]["classification"], "confirmed_mainline")

    def test_complete_evidence_can_confirm_mainline_with_high_confidence(self):
        candidate = {
            "group_key": "N:机器人",
            "name": "机器人",
            "base_score": 70.0,
            "score_components": {
                "same_day_strength": 20.0,
                "breadth": 15.0,
            },
            "continuity": {"known": True, "score": 20.0},
            "catalyst_verified": False,
            "critical_contradiction": False,
        }

        result = market_context.finalize_mainlines(
            [candidate],
            {
                "N:机器人": {
                    "items": [
                        {
                            "code": "000001",
                            "name": "甲",
                            "change_pct": 1.0,
                            "turnover_yuan": 1e9,
                            "evidence_ids": ["constituent-000001"],
                        }
                    ]
                }
            },
            set(),
        )

        self.assertEqual(result[0]["classification"], "confirmed_mainline")
        self.assertEqual(result[0]["confidence"], "high")

    def test_confirmed_mainline_rejects_forged_strength_without_valid_structure(self):
        candidate = {
            "group_key": "N:forged",
            "name": "Forged",
            "base_score": 70.0,
            "score_components": {
                "same_day_strength": 20.0,
                "breadth": 0.0,
            },
            "continuity": {"known": True, "score": 20.0},
            "catalyst_verified": False,
            "critical_contradiction": False,
        }
        details = {
            "N:forged": {
                "items": [
                    {
                        "code": "",
                        "name": "",
                        "change_pct": 5.0,
                        "turnover_yuan": 1e9,
                    }
                ]
            }
        }

        result = market_context.finalize_mainlines(
            [candidate], details, set()
        )[0]

        self.assertNotEqual(result["classification"], "confirmed_mainline")

    def test_missing_constituents_force_low_confidence_insufficient_evidence(self):
        candidate = {
            "group_key": "N:机器人",
            "name": "机器人",
            "base_score": 85.0,
            "continuity": {"known": True, "score": 20.0},
            "catalyst_verified": True,
        }

        result = market_context.finalize_mainlines(
            [candidate], {"N:机器人": {}}, set()
        )

        self.assertEqual(result[0]["classification"], "insufficient_evidence")
        self.assertEqual(result[0]["confidence"], "low")

    def test_malformed_constituent_numbers_do_not_create_positive_leader_roles(self):
        malformed_values = ([], {}, True, float("nan"), float("inf"), "bad")
        for value in malformed_values:
            with self.subTest(field="change_pct", value=value):
                leaders = market_context.classify_leader_roles(
                    [None, 7, {"code": "000001", "change_pct": value}], set()
                )
                self.assertEqual(leaders, [])

            with self.subTest(field="turnover_yuan", value=value):
                leaders = market_context.classify_leader_roles(
                    [
                        {
                            "code": "000001",
                            "change_pct": 1.0,
                            "turnover_yuan": value,
                        }
                    ],
                    set(),
                )
                self.assertNotIn("liquidity_anchor", {row["role"] for row in leaders})

            with self.subTest(field="ret20", value=value):
                leaders = market_context.classify_leader_roles(
                    [
                        {
                            "code": "000001",
                            "change_pct": 1.0,
                            "turnover_yuan": 1e9,
                            "ret20": value,
                        }
                    ],
                    set(),
                )
                self.assertNotIn("trend_leader", {row["role"] for row in leaders})

            with self.subTest(field="market_cap_yuan", value=value):
                leaders = market_context.classify_leader_roles(
                    [
                        {
                            "code": "000001",
                            "change_pct": 1.0,
                            "turnover_yuan": 1e9,
                            "market_cap_yuan": value,
                        }
                    ],
                    set(),
                )
                self.assertNotIn(
                    "industry_representative", {row["role"] for row in leaders}
                )

    def test_malformed_base_and_component_scores_cannot_confirm_mainline(self):
        malformed_values = ([], {}, True, float("nan"), float("inf"), "bad")
        details = {
            "N:robotics": {
                "items": [
                    {
                        "code": "000001",
                        "name": "Evidence",
                        "change_pct": 1.0,
                        "turnover_yuan": 1e9,
                    }
                ]
            }
        }
        for value in malformed_values:
            with self.subTest(value=value):
                result = market_context.finalize_mainlines(
                    [
                        {
                            "group_key": "N:robotics",
                            "name": "Robotics",
                            "base_score": value,
                            "score_components": {"same_day_strength": value},
                            "continuity": {"known": True, "score": 20.0},
                            "catalyst_verified": True,
                        }
                    ],
                    details,
                    set(),
                )

                self.assertNotIn(
                    result[0]["classification"],
                    {"confirmed_mainline", "emerging_mainline", "today_hotspot"},
                )
                self.assertLessEqual(result[0]["score"], 15.0)


class LogicAndOutlookTests(unittest.TestCase):
    def test_logic_chain_ignores_malformed_rows_ids_and_references(self):
        chain = market_context.build_fact_logic_chain(
            {
                "name": "机器人",
                "classification": "insufficient_evidence",
                "evidence_ids": [None, [], {}, "", "valid"],
            },
            [
                None,
                7,
                [],
                {"evidence_id": []},
                {
                    "evidence_id": "valid",
                    "statement": "有效事实",
                    "freshness": "current-session",
                    "reliability": "high",
                },
            ],
        )

        self.assertEqual(chain["facts"], ["有效事实"])

    def test_logic_chain_separates_fact_inference_and_unknown(self):
        line = {
            "name": "机器人",
            "classification": "emerging_mainline",
            "evidence_ids": ["ev-board-1"],
        }
        chain = market_context.build_fact_logic_chain(
            line,
            [
                {
                    "evidence_id": "ev-board-1",
                    "statement": "机器人板块成交额上升",
                    "freshness": "current-session",
                    "reliability": "high",
                }
            ],
        )

        self.assertEqual(chain["facts"], ["机器人板块成交额上升"])
        self.assertIn("social_or_industrial_need", chain)
        self.assertIn("unknowns", chain)
        self.assertTrue(chain["invalidation_conditions"])

    def test_recent_evidence_is_labeled_without_current_session_confirmation(self):
        chain = market_context.build_fact_logic_chain(
            {
                "name": "机器人",
                "classification": "recent_mainline",
                "score": 60,
                "catalyst_verified": True,
                "evidence_ids": ["ev-board-1"],
            },
            [
                {
                    "evidence_id": "ev-board-1",
                    "statement": "机器人板块连续活跃",
                    "freshness": "recent",
                    "reliability": "medium",
                }
            ],
        )

        self.assertEqual(chain["facts"], ["近期事实：机器人板块连续活跃"])
        self.assertIn("当日证据不足", chain["driver"])
        self.assertNotIn("已观察", chain["driver"])
        self.assertNotIn("催化共振", chain["driver"])
        self.assertIn("当日证据不足", chain["price_confirmation"])
        self.assertTrue(
            any("当日证据不足" in item for item in chain["unknowns"])
        )

    def test_logic_chain_rejects_stale_unknown_or_low_reliability_evidence(self):
        line = {
            "name": "机器人",
            "classification": "confirmed_mainline",
            "catalyst_verified": True,
            "evidence_ids": ["ev-board-1"],
        }
        rejected_evidence = (
            {"freshness": "stale", "reliability": "high"},
            {"freshness": "unknown", "reliability": "high"},
            {"freshness": "current-session", "reliability": "low"},
            {"freshness": "current-session"},
            {"freshness": "current-session", "reliability": "unknown"},
            {"freshness": "current-session", "reliability": "trusted"},
        )

        for evidence_gate in rejected_evidence:
            with self.subTest(evidence_gate=evidence_gate):
                chain = market_context.build_fact_logic_chain(
                    line,
                    [
                        {
                            "evidence_id": "ev-board-1",
                            "statement": "机器人价格上涨且催化落地",
                            **evidence_gate,
                        }
                    ],
                )
                self.assertEqual(chain["facts"], [])
                self.assertIn("证据不足", chain["driver"])
                self.assertNotIn("已观察", chain["driver"])
                self.assertNotIn("催化共振", chain["driver"])
                self.assertIn("证据不足", chain["price_confirmation"])
                self.assertTrue(chain["unknowns"])

    def test_outlook_has_both_horizons_and_three_cases(self):
        outlook = market_context.build_market_outlook(
            {"regime": "structural", "confidence": "high"},
            [
                {
                    "name": "机器人",
                    "classification": "confirmed_mainline",
                    "confidence": "high",
                }
            ],
        )

        self.assertEqual(set(outlook), {"short_term", "medium_term"})
        self.assertEqual(outlook["short_term"]["horizon"], "1-5 trading days")
        self.assertEqual(outlook["medium_term"]["horizon"], "1-3 months")
        for horizon in outlook.values():
            self.assertTrue(horizon["base_case"])
            self.assertTrue(horizon["stronger_case"])
            self.assertTrue(horizon["weaker_case"])
            self.assertTrue(horizon["key_variables"])
            self.assertTrue(horizon["portfolio_posture"])
            self.assertTrue(horizon["invalidation"])

    def test_low_confidence_outlook_requires_evidence_before_continuation(self):
        cases = (
            {"regime": "structural", "confidence": "low"},
            {"regime": "insufficient_evidence", "confidence": "high"},
        )

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                outlook = market_context.build_market_outlook(
                    snapshot,
                    [
                        {
                            "name": "机器人",
                            "classification": "confirmed_mainline",
                            "confidence": "high",
                        }
                    ],
                )
                short_term = outlook["short_term"]
                medium_term = outlook["medium_term"]
                self.assertEqual(short_term["confidence"], "low")
                self.assertTrue(
                    "证据不足" in short_term["base_case"]
                    or "补齐证据" in short_term["base_case"]
                )
                self.assertNotIn("环境延续", short_term["base_case"])
                self.assertEqual(medium_term["confidence"], "low")
                self.assertTrue(
                    "证据不足" in medium_term["base_case"]
                    or "补齐证据" in medium_term["base_case"]
                )


class PortfolioAndHoldingTests(unittest.TestCase):
    def test_portfolio_diagnosis_finds_industry_concentration(self):
        positions = {
            "total_assets": 1000,
            "holdings": [
                {"code": "000001", "name": "甲", "market_value": 400},
                {"code": "000002", "name": "乙", "market_value": 300},
            ],
        }
        scores = [
            {
                "code": "000001",
                "industry": "电子",
                "current_weight": 0.4,
            },
            {
                "code": "000002",
                "industry": "电子",
                "current_weight": 0.3,
            },
        ]

        diagnosis = market_context.build_portfolio_diagnosis(
            positions, [], scores, []
        )

        self.assertEqual(
            diagnosis["industry_concentration"][0]["industry"], "电子"
        )
        self.assertAlmostEqual(
            diagnosis["industry_concentration"][0]["weight"], 0.7
        )

    def test_portfolio_diagnosis_exposes_required_concentration_contract(self):
        positions = {
            "total_assets": 1000,
            "holdings": [
                {"code": "000001", "name": "甲"},
                {"code": "000002", "name": "乙"},
                {"code": "000003", "name": "丙"},
                {"code": "000004", "name": "丁"},
            ],
        }
        scores = [
            {"code": "000001", "industry": "电子", "current_weight": 0.4},
            {"code": "000002", "industry": "电力", "current_weight": 0.2},
            {"code": "000003", "industry": "汽车", "current_weight": 0.1},
            {"code": "000004", "industry": "传媒", "current_weight": 0.1},
        ]
        mainlines = [
            {
                "name": "确认主题",
                "classification": "confirmed_mainline",
                "constituent_codes": ["000001"],
            },
            {
                "name": "近期主题",
                "classification": "recent_mainline",
                "constituent_codes": ["000002"],
            },
            {
                "name": "新兴主题",
                "classification": "emerging_mainline",
                "constituent_codes": ["000003"],
            },
            {
                "name": "当日噪声",
                "classification": "one_day_noise",
                "constituent_codes": ["000004"],
            },
        ]

        diagnosis = market_context.build_portfolio_diagnosis(
            positions, mainlines, scores, []
        )

        self.assertEqual(
            diagnosis["single_stock_concentration"][0],
            {"code": "000001", "name": "甲", "weight": 0.4},
        )
        aligned = {row["mainline"] for row in diagnosis["mainline_alignment"]}
        self.assertEqual(aligned, {"确认主题", "近期主题", "新兴主题"})
        self.assertNotIn(
            "当日噪声", {row["theme"] for row in diagnosis["theme_concentration"]}
        )
        self.assertAlmostEqual(diagnosis["off_mainline_exposure"], 0.1)
        self.assertIsNone(diagnosis["counter_regime_exposure"])
        self.assertTrue(diagnosis["counter_regime_exposure_note"])
        self.assertTrue(diagnosis["portfolio_posture"])

    def test_single_stock_weight_does_not_create_shared_catalyst_risk(self):
        diagnosis = market_context.build_portfolio_diagnosis(
            {"holdings": [{"code": "000001", "name": "甲"}]},
            [
                {
                    "name": "机器人",
                    "classification": "confirmed_mainline",
                    "constituent_codes": ["000001"],
                }
            ],
            [{"code": "000001", "current_weight": 0.4}],
            [],
        )

        self.assertEqual(diagnosis["shared_catalyst_risks"], [])

    def test_two_positive_weight_holdings_create_shared_catalyst_risk(self):
        diagnosis = market_context.build_portfolio_diagnosis(
            {
                "holdings": [
                    {"code": "000001", "name": "甲"},
                    {"code": "000002", "name": "乙"},
                ]
            },
            [
                {
                    "name": "机器人",
                    "classification": "confirmed_mainline",
                    "constituent_codes": ["000001", "000002"],
                }
            ],
            [
                {"code": "000001", "current_weight": 0.2},
                {"code": "000002", "current_weight": 0.1},
            ],
            [],
        )

        self.assertEqual(diagnosis["shared_catalyst_risks"], ["机器人"])

    def test_market_value_fills_only_missing_current_weights(self):
        diagnosis = market_context.build_portfolio_diagnosis(
            {
                "total_assets": 1000,
                "holdings": [
                    {"code": "000001", "name": "无评分行", "market_value": 300},
                    {"code": "000002", "name": "评分缺权重", "market_value": 200},
                    {"code": "000003", "name": "显式权重", "market_value": 400},
                ],
            },
            [],
            [
                {"code": "000002", "industry": "电子"},
                {
                    "code": "000003",
                    "industry": "汽车",
                    "current_weight": 0.1,
                },
            ],
            [],
        )

        self.assertAlmostEqual(diagnosis["stock_exposure"], 0.6)
        self.assertEqual(
            diagnosis["single_stock_concentration"],
            [
                {"code": "000001", "name": "无评分行", "weight": 0.3},
                {"code": "000002", "name": "评分缺权重", "weight": 0.2},
                {"code": "000003", "name": "显式权重", "weight": 0.1},
            ],
        )
        self.assertAlmostEqual(diagnosis["cash_weight"], 0.4)

    def test_incomplete_assets_use_visible_market_value_for_concentration(self):
        for coverage_flag in ("cash_unreadable", "total_assets_lower_bound"):
            with self.subTest(coverage_flag=coverage_flag):
                diagnosis = market_context.build_portfolio_diagnosis(
                    {
                        "total_assets": 1000,
                        coverage_flag: True,
                        "holdings": [
                            {
                                "code": "000001",
                                "name": "甲",
                                "market_value": 300,
                            },
                            {
                                "code": "000002",
                                "name": "乙",
                                "market_value": 100,
                            },
                        ],
                    },
                    [],
                    [
                        {
                            "code": "000001",
                            "industry": "电子",
                            "current_weight": 0.9,
                        },
                        {
                            "code": "000002",
                            "industry": "机械",
                            "current_weight": 0.05,
                        },
                    ],
                    [],
                )

                self.assertIsNone(diagnosis["stock_exposure"])
                self.assertIsNone(diagnosis["cash_weight"])
                self.assertEqual(
                    diagnosis["single_stock_concentration"],
                    [
                        {"code": "000001", "name": "甲", "weight": 0.75},
                        {"code": "000002", "name": "乙", "weight": 0.25},
                    ],
                )
                self.assertEqual(
                    diagnosis["industry_concentration"],
                    [
                        {"industry": "电子", "weight": 0.75},
                        {"industry": "机械", "weight": 0.25},
                    ],
                )
                self.assertIn("现金/总资产未知", diagnosis["asset_coverage_note"])
                self.assertIn("可见持仓市值", diagnosis["asset_coverage_note"])

    def test_non_boolean_asset_coverage_flags_keep_complete_asset_behavior(self):
        for coverage_flag in ("cash_unreadable", "total_assets_lower_bound"):
            for value in ("true", 1, 1.0):
                with self.subTest(coverage_flag=coverage_flag, value=value):
                    diagnosis = market_context.build_portfolio_diagnosis(
                        {
                            "total_assets": 1000,
                            coverage_flag: value,
                            "holdings": [
                                {
                                    "code": "000001",
                                    "name": "甲",
                                    "market_value": 200,
                                }
                            ],
                        },
                        [],
                        [{"code": "000001", "current_weight": 0.4}],
                        [],
                    )

                    self.assertEqual(diagnosis["stock_exposure"], 0.4)
                    self.assertEqual(diagnosis["cash_weight"], 0.6)
                    self.assertNotIn("asset_coverage_note", diagnosis)

    def test_holding_analysis_preserves_action_contract(self):
        actions = [
            {
                "code": "000001",
                "name": "甲",
                "action": "hold",
                "reason": "结构未破坏",
                "trigger": "站稳20日线",
                "invalidation": "跌破60日线",
                "target_weight": 0.1,
                "risk_note": "条件化信号",
            }
        ]

        rows = market_context.build_holding_analyses(
            {"holdings": [{"code": "000001", "name": "甲"}]},
            [],
            [
                {
                    "code": "000001",
                    "industry": "电子",
                    "scores": {"total_score": 60},
                    "data_confidence": "high",
                }
            ],
            [
                {
                    "code": "000001",
                    "segment_focus": "电子制造",
                    "value_chain_position": "中游",
                    "upstream_dependency_check": "核验原材料与设备",
                    "downstream_customer_check": "核验客户与需求",
                    "industry_influence_question": "核验行业影响",
                    "scarce_capability_check": "核验稀缺能力",
                }
            ],
            actions,
        )

        self.assertEqual(rows[0]["action"], "hold")
        self.assertEqual(rows[0]["invalidation"], "跌破60日线")
        self.assertIn("industry_panorama", rows[0])
        self.assertIn("bull_evidence", rows[0])
        self.assertIn("bear_evidence", rows[0])
        self.assertEqual(rows[0]["factor_evidence"]["total_score"], 60)
        self.assertEqual(rows[0]["evidence_gaps"], [])

    def test_partial_panorama_names_each_missing_evidence_field(self):
        complete_panorama = {
            "code": "000001",
            "segment_focus": "电子制造",
            "value_chain_position": "中游",
            "upstream_dependency_check": "核验原材料与设备",
            "downstream_customer_check": "核验客户与需求",
            "industry_influence_question": "核验行业影响",
            "scarce_capability_check": "核验稀缺能力",
        }
        required_fields = (
            "segment_focus",
            "value_chain_position",
            "upstream_dependency_check",
            "downstream_customer_check",
            "industry_influence_question",
            "scarce_capability_check",
        )

        for missing_field in required_fields:
            with self.subTest(missing_field=missing_field):
                panorama = dict(complete_panorama)
                panorama.pop(missing_field)
                rows = market_context.build_holding_analyses(
                    {"holdings": [{"code": "000001", "name": "甲"}]},
                    [],
                    [
                        {
                            "code": "000001",
                            "scores": {"total_score": 60},
                            "data_confidence": "high",
                        }
                    ],
                    [panorama],
                    [{"code": "000001", "action": "hold"}],
                )

                self.assertIn(
                    missing_field, " ".join(rows[0]["evidence_gaps"])
                )

    def test_holding_links_distinguish_leader_and_follower_and_flag_gaps(self):
        rows = market_context.build_holding_analyses(
            {
                "holdings": [
                    {"code": "000001", "name": "甲"},
                    {"code": "000002", "name": "乙"},
                ]
            },
            [
                {
                    "name": "机器人",
                    "classification": "confirmed_mainline",
                    "constituent_codes": ["000001", "000002"],
                    "leaders": [
                        {"code": "000001", "role": "liquidity_anchor"},
                        {"code": "000002", "role": "held_exposure"},
                    ],
                }
            ],
            [
                {
                    "code": "000001",
                    "industry": "机械",
                    "scores": {"total_score": 60},
                    "data_confidence": "high",
                },
                {
                    "code": "000002",
                    "industry": "机械",
                    "scores": {"total_score": 50},
                    "data_confidence": "low",
                },
            ],
            [{"code": "000001", "segment_focus": "机器人零部件"}],
            [],
        )

        self.assertEqual(rows[0]["mainline_links"][0]["relationship"], "leader")
        self.assertEqual(
            rows[0]["mainline_links"][0]["leader_roles"],
            ["liquidity_anchor"],
        )
        self.assertEqual(
            rows[1]["mainline_links"][0]["relationship"],
            "follower_or_constituent",
        )
        gaps = " ".join(rows[1]["evidence_gaps"])
        self.assertIn("data_confidence", gaps)
        self.assertIn("industry_panorama", gaps)

    def test_holding_link_can_be_label_only(self):
        rows = market_context.build_holding_analyses(
            {"holdings": [{"code": "000001", "name": "甲"}]},
            [
                {
                    "name": "机器人",
                    "classification": "emerging_mainline",
                    "constituent_codes": ["000002"],
                }
            ],
            [
                {
                    "code": "000001",
                    "industry": "机器人",
                    "scores": {"total_score": 60},
                    "data_confidence": "high",
                }
            ],
            [],
            [],
        )

        self.assertEqual(rows[0]["mainline_links"][0]["relationship"], "label_only")
        self.assertEqual(rows[0]["mainline_links"][0]["link_type"], "label")

    def test_existing_allowed_actions_keep_priority_target_and_role(self):
        cases = (
            ("reduce", 2, 0.12, "core"),
            ("exit", 1, 0.0, "error_position"),
            ("add_only_if_triggered", 3, 0.15, "trade"),
        )

        for action_name, priority, target_weight, account_role in cases:
            with self.subTest(action=action_name):
                rows = market_context.build_holding_analyses(
                    {"holdings": [{"code": "000001", "name": "甲"}]},
                    [],
                    [
                        {
                            "code": "000001",
                            "current_weight": 0.2,
                            "scores": {"total_score": 60},
                            "data_confidence": "high",
                        }
                    ],
                    [],
                    [
                        {
                            "code": "000001",
                            "action": action_name,
                            "target_weight": target_weight,
                        }
                    ],
                )

                self.assertEqual(rows[0]["action"], action_name)
                self.assertEqual(rows[0]["priority"], priority)
                self.assertEqual(rows[0]["target_weight"], target_weight)
                self.assertEqual(rows[0]["account_role"], account_role)

    def test_watch_action_stays_watch_with_zero_target_weight(self):
        rows = market_context.build_holding_analyses(
            {"holdings": [{"code": "research-1", "name": "研究标的"}]},
            [],
            [
                {
                    "code": "research-1",
                    "scores": {"total_score": 80},
                    "data_confidence": "high",
                }
            ],
            [],
            [
                {
                    "code": "research-1",
                    "action": "watch",
                    "target_weight": 0,
                }
            ],
        )

        self.assertEqual(rows[0]["action"], "watch")
        self.assertEqual(rows[0]["account_role"], "watch")
        self.assertEqual(rows[0]["target_weight"], 0)

    def test_malformed_portfolio_numbers_fail_closed_without_crashing(self):
        malformed_values = ([], {}, True, float("nan"), float("inf"), "bad")
        for value in malformed_values:
            with self.subTest(value=value):
                positions = {
                    "total_assets": value,
                    "holdings": [
                        {
                            "code": "000001",
                            "name": "Malformed",
                            "market_value": value,
                        }
                    ],
                }
                scores = [
                    {
                        "code": "000001",
                        "current_weight": value,
                        "scores": {"total_score": value},
                        "data_confidence": "low",
                    }
                ]
                actions = [
                    {
                        "code": "000001",
                        "action": "hold",
                        "target_weight": value,
                    }
                ]

                diagnosis = market_context.build_portfolio_diagnosis(
                    positions, [], scores, actions
                )
                holdings = market_context.build_holding_analyses(
                    positions, [], scores, [], actions
                )

                self.assertEqual(diagnosis["stock_exposure"], 0.0)
                self.assertEqual(holdings[0]["target_weight"], 0.0)
                self.assertEqual(holdings[0]["bull_evidence"], [])


if __name__ == "__main__":
    unittest.main()
