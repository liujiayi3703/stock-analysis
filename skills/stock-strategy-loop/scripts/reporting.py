from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, Dict, List, Sequence


REQUIRED_SIGNAL_FIELDS = (
    "report_schema_version",
    "data_coverage",
    "evidence_index",
    "market_snapshot",
    "market_mainlines",
    "market_outlook",
    "portfolio_diagnosis",
    "holding_analyses",
    "portfolio_actions",
)
REQUIRED_EVIDENCE_FIELDS = (
    "evidence_id",
    "category",
    "statement",
    "source",
    "as_of",
    "trading_session",
    "freshness",
    "reliability",
    "scope",
)
REQUIRED_MAINLINE_FIELDS = (
    "name",
    "classification",
    "score",
    "score_components",
    "leaders",
    "logic_chain",
    "continuation_conditions",
    "invalidation_conditions",
    "risk",
    "confidence",
    "evidence_ids",
    "catalyst_verified",
    "contradictions",
)
REQUIRED_LEADER_FIELDS = (
    "code",
    "name",
    "role",
    "role_evidence",
    "confidence",
    "risk",
    "evidence_ids",
)
REQUIRED_HOLDING_FIELDS = (
    "code",
    "name",
    "account_role",
    "industry_panorama",
    "mainline_links",
    "factor_evidence",
    "bull_evidence",
    "bear_evidence",
    "thesis_status",
    "data_confidence",
    "evidence_gaps",
    "action",
    "priority",
    "target_weight",
    "reason",
    "trigger",
    "invalidation",
    "risk_note",
    "evidence_ids",
)
REQUIRED_MARKET_SNAPSHOT_FIELDS = (
    "as_of",
    "regime",
    "confidence",
    "indices",
    "breadth",
    "missing_evidence",
)
REQUIRED_OUTLOOK_FIELDS = (
    "horizon",
    "base_case",
    "stronger_case",
    "weaker_case",
    "key_variables",
    "portfolio_posture",
    "invalidation",
    "confidence",
)
REQUIRED_LOGIC_CHAIN_FIELDS = (
    "facts",
    "driver",
    "social_or_industrial_need",
    "value_chain_transmission",
    "earnings_transmission",
    "price_confirmation",
    "contradictions",
    "unknowns",
)
REQUIRED_PORTFOLIO_DIAGNOSIS_FIELDS = (
    "stock_exposure",
    "cash_weight",
    "single_stock_concentration",
    "industry_concentration",
    "theme_concentration",
    "mainline_alignment",
    "off_mainline_exposure",
    "counter_regime_exposure",
    "counter_regime_exposure_note",
    "shared_catalyst_risks",
    "portfolio_posture",
    "top_action_priorities",
)
PORTFOLIO_DIAGNOSIS_LIST_FIELDS = (
    "single_stock_concentration",
    "industry_concentration",
    "theme_concentration",
    "mainline_alignment",
    "shared_catalyst_risks",
    "top_action_priorities",
)
PORTFOLIO_DIAGNOSIS_OBJECT_LIST_FIELDS = {
    "single_stock_concentration": ("code", "name", "weight"),
    "industry_concentration": ("industry", "weight"),
    "theme_concentration": ("theme", "weight"),
    "mainline_alignment": ("mainline", "weight"),
    "top_action_priorities": ("code", "name", "action"),
}
REQUIRED_INDUSTRY_PANORAMA_FIELDS = (
    "segment_focus",
    "value_chain_position",
    "upstream_dependency_check",
    "downstream_customer_check",
    "industry_influence_question",
    "scarce_capability_check",
)
REQUIRED_FACTOR_EVIDENCE_FIELDS = (
    "total_score",
    "trend_score",
    "macd_score",
    "fund_flow_score",
    "sector_score",
    "event_score",
)
REQUIRED_ACTION_FIELDS = (
    "code",
    "name",
    "action",
    "reason",
    "trigger",
    "invalidation",
    "target_weight",
    "risk_note",
)
ALLOWED_ACTIONS = {
    "hold",
    "reduce",
    "exit",
    "watch",
    "add_only_if_triggered",
}
ALLOWED_ACCOUNT_ROLES = {
    "core",
    "satellite",
    "trade",
    "hedge",
    "watch",
    "error_position",
}
ALLOWED_MAINLINE_CLASSES = {
    "confirmed_mainline",
    "emerging_mainline",
    "today_hotspot",
    "recent_mainline",
    "one_day_noise",
    "insufficient_evidence",
}
ALLOWED_LEADER_ROLES = {
    "emotion_leader",
    "liquidity_anchor",
    "trend_leader",
    "industry_representative",
    "held_exposure",
}
ALLOWED_FRESHNESS = {"current-session", "recent", "stale", "unknown"}
ALLOWED_RELIABILITY = {"high", "medium", "low"}
ALLOWED_MARKET_REGIMES = {
    "insufficient_evidence",
    "high_volatility",
    "weak",
    "risk_on",
    "structural",
    "defensive",
}
MAINLINE_COMPONENT_MAXIMUMS = {
    "same_day_strength": 20.0,
    "liquidity": 15.0,
    "breadth": 15.0,
    "continuity": 20.0,
    "catalyst_logic": 15.0,
    "leader_structure": 15.0,
}
COVERAGE_COUNT_FIELDS = {
    "holdings",
    "holding_count",
    "quotes",
    "quote_count",
    "history",
    "history_count",
    "history_rows_min",
    "history_rows_max",
    "fund_flow",
    "fund_flow_count",
    "events",
    "event_count",
    "industry",
    "industry_count",
    "board_summaries",
    "board_details",
    "breadth",
    "mainline_history_sessions",
    "indices",
    "index_count",
    "market_news",
    "market_news_count",
    "errors",
    "data_error_count",
}
OUTLOOK_HORIZONS = {
    "short_term": "1-5 trading days",
    "medium_term": "1-3 months",
}


def _missing_fields(
    row: Dict[str, Any], required: Sequence[str], prefix: str
) -> List[str]:
    return [f"{prefix} missing {key}" for key in required if key not in row]


def _number(value: Any) -> float | None:
    return float(value) if _finite_number(value) else None


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _same_nullable_number(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return (
        _finite_number(left)
        and _finite_number(right)
        and float(left) == float(right)
    )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_allowed_string(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def _validate_non_empty_string_fields(
    row: Dict[str, Any],
    fields: Sequence[str],
    prefix: str,
    errors: List[str],
) -> None:
    for field in fields:
        if field in row and not _is_non_empty_string(row.get(field)):
            errors.append(
                f"{prefix}.{field} must be a non-empty string"
            )


def _validate_number(
    value: Any,
    path: str,
    errors: List[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    nullable: bool = False,
    integer: bool = False,
) -> None:
    if value is None and nullable:
        return
    if not _finite_number(value):
        suffix = " or null" if nullable else ""
        errors.append(f"{path} must be a finite number{suffix}")
        return
    number = float(value)
    if integer and (not isinstance(value, int) or number != int(number)):
        errors.append(f"{path} must be an integer")
        return
    if minimum is not None and number < minimum:
        if maximum is None:
            errors.append(f"{path} must be at least {minimum:g}")
        else:
            errors.append(
                f"{path} must be between {minimum:g} and {maximum:g}"
            )
    elif maximum is not None and number > maximum:
        if minimum is None:
            errors.append(f"{path} must be at most {maximum:g}")
        else:
            errors.append(
                f"{path} must be between {minimum:g} and {maximum:g}"
            )


def _validate_boolean(value: Any, path: str, errors: List[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path} must be a boolean")


def _validate_string_list(
    value: Any,
    path: str,
    errors: List[str],
    *,
    nullable: bool = True,
) -> List[Any]:
    if value is None and nullable:
        return []
    if not isinstance(value, list):
        suffix = " or null" if nullable else ""
        errors.append(f"{path} must be a list{suffix}")
        return []
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            errors.append(
                f"{path}[{index}] must be a non-empty string"
            )
    return value


def _list_or_empty(
    value: Any, path: str, errors: List[str]
) -> List[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path} must be a list or null")
        return []
    return value


def _validate_evidence_ids(
    value: Any,
    prefix: str,
    known_evidence: set[str],
    errors: List[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{prefix} evidence_ids must be a non-empty list")
        return
    for index, evidence_id in enumerate(value):
        if not _is_non_empty_string(evidence_id):
            errors.append(
                f"{prefix} evidence_ids[{index}] must be a non-empty string"
            )
        elif evidence_id not in known_evidence:
            errors.append(f"{prefix} unknown evidence {evidence_id}")


def _validate_action(
    row: Dict[str, Any],
    prefix: str,
    errors: List[str],
    *,
    require_fields: bool = False,
) -> None:
    if require_fields:
        errors.extend(_missing_fields(row, REQUIRED_ACTION_FIELDS, prefix))
    _validate_non_empty_string_fields(
        row,
        (
            "code",
            "name",
            "reason",
            "trigger",
            "invalidation",
            "risk_note",
        ),
        prefix,
        errors,
    )
    if not _is_allowed_string(row.get("action"), ALLOWED_ACTIONS):
        errors.append(f"{prefix} invalid action")
    target_weight = row.get("target_weight")
    if "target_weight" in row:
        _validate_number(
            target_weight,
            f"{prefix}.target_weight",
            errors,
            minimum=0.0,
            maximum=0.15,
        )
    if row.get("action") == "watch":
        if not _finite_number(target_weight) or float(target_weight) != 0:
            errors.append(f"{prefix} watch target_weight must equal 0")


def _validate_object_list_entries(
    values: List[Any],
    path: str,
    required: Sequence[str],
    errors: List[str],
) -> None:
    for index, row in enumerate(values):
        prefix = f"{path}[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_missing_fields(row, required, prefix))


def _has_critical_contradiction(line: Dict[str, Any]) -> bool:
    if line.get("critical_contradiction") is True:
        return True
    contradictions = line.get("contradictions")
    if not isinstance(contradictions, list):
        return False
    return any(
        isinstance(row, dict)
        and (
            row.get("critical_contradiction") is True
            or row.get("critical") is True
        )
        for row in contradictions
    )


def validate_signal_v2(signal: Dict[str, Any]) -> List[str]:
    if not isinstance(signal, dict):
        return ["signal must be an object"]

    errors = _missing_fields(signal, REQUIRED_SIGNAL_FIELDS, "")
    errors = [error.lstrip() for error in errors]
    if (
        not isinstance(signal.get("report_schema_version"), int)
        or isinstance(signal.get("report_schema_version"), bool)
        or signal.get("report_schema_version") != 2
    ):
        errors.append("report_schema_version must equal integer 2")

    coverage = signal.get("data_coverage")
    if not isinstance(coverage, dict):
        errors.append("data_coverage must be an object")
    else:
        for field in COVERAGE_COUNT_FIELDS:
            if field in coverage:
                _validate_number(
                    coverage.get(field),
                    f"data_coverage.{field}",
                    errors,
                    minimum=0.0,
                )

    evidence_rows = signal.get("evidence_index", [])
    if not isinstance(evidence_rows, list):
        errors.append("evidence_index must be a list")
        evidence_rows = []
    known_evidence: set[str] = set()
    for index, row in enumerate(evidence_rows):
        prefix = f"evidence_index[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_missing_fields(row, REQUIRED_EVIDENCE_FIELDS, prefix))
        evidence_id = row.get("evidence_id")
        if not _is_non_empty_string(evidence_id):
            errors.append(
                f"{prefix} evidence_id must be a non-empty string"
            )
        elif evidence_id in known_evidence:
            errors.append(f"duplicate evidence_id {evidence_id}")
        else:
            known_evidence.add(evidence_id)
        for field in (
            "category",
            "statement",
            "source",
            "trading_session",
            "scope",
        ):
            if not _is_non_empty_string(row.get(field)):
                errors.append(
                    f"{prefix} {field} must be a non-empty string"
                )
        if "freshness" in row and not _is_allowed_string(
            row.get("freshness"), ALLOWED_FRESHNESS
        ):
            errors.append(f"{prefix} invalid freshness")
        if (
            isinstance(row.get("freshness"), str)
            and row.get("freshness")
            in {"current-session", "recent", "stale"}
            and not _is_non_empty_string(row.get("as_of"))
        ):
            errors.append(
                f"{prefix} as_of must be a non-empty string for "
                f"{row.get('freshness')} evidence"
            )
        if (
            row.get("freshness") == "unknown"
            and row.get("as_of") is not None
            and not isinstance(row.get("as_of"), str)
        ):
            errors.append(
                f"{prefix} as_of must be a string or null for unknown evidence"
            )
        if (
            "reliability" in row
            and not _is_allowed_string(
                row.get("reliability"), ALLOWED_RELIABILITY
            )
        ):
            errors.append(f"{prefix} invalid reliability")

    snapshot = signal.get("market_snapshot", {})
    if not isinstance(snapshot, dict):
        errors.append("market_snapshot must be an object")
        snapshot = {}
    errors.extend(
        _missing_fields(
            snapshot, REQUIRED_MARKET_SNAPSHOT_FIELDS, "market_snapshot"
        )
    )
    _validate_non_empty_string_fields(
        snapshot, ("as_of", "confidence"), "market_snapshot", errors
    )
    if not _is_allowed_string(
        snapshot.get("regime"), ALLOWED_MARKET_REGIMES
    ):
        errors.append("market_snapshot invalid regime")
    for field in (
        "trading_session",
        "style_divergence",
        "risk_appetite",
    ):
        if field in snapshot and snapshot.get(field) is not None:
            _validate_non_empty_string_fields(
                snapshot, (field,), "market_snapshot", errors
            )

    indices = snapshot.get("indices")
    if indices is not None and not isinstance(indices, list):
        errors.append("market_snapshot.indices must be a list or null")
    elif isinstance(indices, list):
        for index, row in enumerate(indices):
            prefix = f"market_snapshot.indices[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("name", "as_of"):
                if field in row and row.get(field) is not None:
                    _validate_non_empty_string_fields(
                        row, (field,), prefix, errors
                    )
            if "price" in row:
                _validate_number(
                    row.get("price"),
                    f"{prefix}.price",
                    errors,
                    minimum=0.0,
                    nullable=True,
                )
            if "change_pct" in row:
                _validate_number(
                    row.get("change_pct"),
                    f"{prefix}.change_pct",
                    errors,
                )
            if "stale" in row:
                _validate_boolean(row.get("stale"), f"{prefix}.stale", errors)

    breadth = snapshot.get("breadth")
    if breadth is not None and not isinstance(breadth, dict):
        errors.append("market_snapshot.breadth must be an object or null")
    elif isinstance(breadth, dict):
        for field in (
            "advancers",
            "decliners",
            "unchanged",
            "sample_size",
            "turnover_yuan",
            "completeness_threshold",
            "turnover_valid_count",
            "limit_up",
            "limit_down",
            "failed_limit_up",
        ):
            if field in breadth:
                _validate_number(
                    breadth.get(field),
                    f"market_snapshot.breadth.{field}",
                    errors,
                    minimum=0.0,
                    nullable=True,
                )
        for field in (
            "median_change_pct",
        ):
            if field in breadth:
                _validate_number(
                    breadth.get(field),
                    f"market_snapshot.breadth.{field}",
                    errors,
                    nullable=True,
                )
        for field in (
            "turnover_coverage_ratio",
            "turnover_coverage_threshold",
        ):
            if field in breadth:
                _validate_number(
                    breadth.get(field),
                    f"market_snapshot.breadth.{field}",
                    errors,
                    minimum=0.0,
                    maximum=1.0,
                    nullable=True,
                )
        for field in (
            "complete",
            "turnover_complete",
            "limit_structure_available",
            "stale",
        ):
            if field in breadth:
                _validate_boolean(
                    breadth.get(field),
                    f"market_snapshot.breadth.{field}",
                    errors,
                )
    if "index_divergence_pct" in snapshot:
        _validate_number(
            snapshot.get("index_divergence_pct"),
            "market_snapshot.index_divergence_pct",
            errors,
            minimum=0.0,
        )
    if "missing_evidence" in snapshot:
        _validate_string_list(
            snapshot.get("missing_evidence"),
            "market_snapshot.missing_evidence",
            errors,
        )

    outlook = signal.get("market_outlook", {})
    if not isinstance(outlook, dict):
        errors.append("market_outlook must be an object")
        outlook = {}
    for key, expected_horizon in OUTLOOK_HORIZONS.items():
        if key not in outlook:
            errors.append(f"missing market_outlook.{key}")
            continue
        row = outlook[key]
        if not isinstance(row, dict):
            errors.append(f"market_outlook.{key} must be an object")
            continue
        errors.extend(
            _missing_fields(row, REQUIRED_OUTLOOK_FIELDS, f"market_outlook.{key}")
        )
        _validate_non_empty_string_fields(
            row,
            (
                "horizon",
                "base_case",
                "stronger_case",
                "weaker_case",
                "portfolio_posture",
                "invalidation",
                "confidence",
            ),
            f"market_outlook.{key}",
            errors,
        )
        if "key_variables" in row:
            _validate_string_list(
                row.get("key_variables"),
                f"market_outlook.{key}.key_variables",
                errors,
                nullable=False,
            )
        if "horizon" in row and row.get("horizon") != expected_horizon:
            errors.append(
                f"market_outlook.{key} horizon must equal {expected_horizon}"
            )

    mainlines = signal.get("market_mainlines", [])
    if not isinstance(mainlines, list):
        errors.append("market_mainlines must be a list")
        mainlines = []
    for index, line in enumerate(mainlines):
        prefix = f"market_mainlines[{index}]"
        if not isinstance(line, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_missing_fields(line, REQUIRED_MAINLINE_FIELDS, prefix))
        _validate_non_empty_string_fields(
            line, ("name", "risk", "confidence"), prefix, errors
        )
        if (
            "classification" in line
            and not _is_allowed_string(
                line.get("classification"), ALLOWED_MAINLINE_CLASSES
            )
        ):
            errors.append(f"{prefix} invalid classification")
        if "score" in line:
            _validate_number(
                line.get("score"),
                f"{prefix}.score",
                errors,
                minimum=0.0,
                maximum=100.0,
            )
        if "catalyst_verified" in line:
            _validate_boolean(
                line.get("catalyst_verified"),
                f"{prefix}.catalyst_verified",
                errors,
            )
        if "critical_contradiction" in line:
            _validate_boolean(
                line.get("critical_contradiction"),
                f"{prefix}.critical_contradiction",
                errors,
            )
        _validate_evidence_ids(
            line.get("evidence_ids"), prefix, known_evidence, errors
        )
        if "score_components" in line and not isinstance(
            line.get("score_components"), dict
        ):
            errors.append(f"{prefix} score_components must be an object")
        elif isinstance(line.get("score_components"), dict):
            for component, value in line["score_components"].items():
                maximum = MAINLINE_COMPONENT_MAXIMUMS.get(component, 100.0)
                _validate_number(
                    value,
                    f"{prefix}.score_components.{component}",
                    errors,
                    minimum=0.0,
                    maximum=maximum,
                )

        continuity = line.get("continuity")
        if "continuity" in line and not isinstance(continuity, dict):
            errors.append(f"{prefix}.continuity must be an object")
            continuity = {}
        if isinstance(continuity, dict):
            if "known" in continuity:
                _validate_boolean(
                    continuity.get("known"),
                    f"{prefix}.continuity.known",
                    errors,
                )
            if "score" in continuity:
                _validate_number(
                    continuity.get("score"),
                    f"{prefix}.continuity.score",
                    errors,
                    minimum=0.0,
                    maximum=20.0,
                )
            for field in ("sessions", "hits"):
                if field in continuity:
                    _validate_number(
                        continuity.get(field),
                        f"{prefix}.continuity.{field}",
                        errors,
                        minimum=0.0,
                    )
        logic_chain = line.get("logic_chain")
        if not isinstance(logic_chain, dict):
            errors.append(f"{prefix} logic_chain must be an object")
        else:
            logic_prefix = f"{prefix}.logic_chain"
            errors.extend(
                _missing_fields(
                    logic_chain, REQUIRED_LOGIC_CHAIN_FIELDS, logic_prefix
                )
            )
            _validate_non_empty_string_fields(
                logic_chain,
                (
                    "driver",
                    "social_or_industrial_need",
                    "value_chain_transmission",
                    "earnings_transmission",
                    "price_confirmation",
                ),
                logic_prefix,
                errors,
            )
            for field in ("facts", "contradictions", "unknowns"):
                if field in logic_chain:
                    values = _list_or_empty(
                        logic_chain.get(field),
                        f"{logic_prefix}.{field}",
                        errors,
                    )
                    if field in {"facts", "unknowns"}:
                        for item_index, item in enumerate(values):
                            if not _is_non_empty_string(item):
                                errors.append(
                                    f"{logic_prefix}.{field}[{item_index}] "
                                    "must be a non-empty string"
                                )
        for field in (
            "continuation_conditions",
            "invalidation_conditions",
            "contradictions",
        ):
            if field in line:
                values = _list_or_empty(
                    line.get(field), f"{prefix} {field}", errors
                )
                if field != "contradictions":
                    for item_index, item in enumerate(values):
                        if not _is_non_empty_string(item):
                            errors.append(
                                f"{prefix}.{field}[{item_index}] must be a "
                                "non-empty string"
                            )
                else:
                    for item_index, item in enumerate(values):
                        if not isinstance(item, dict):
                            continue
                        for bool_field in (
                            "critical_contradiction",
                            "critical",
                        ):
                            if bool_field in item:
                                _validate_boolean(
                                    item.get(bool_field),
                                    f"{prefix}.contradictions[{item_index}]."
                                    f"{bool_field}",
                                    errors,
                                )

        if line.get("classification") == "confirmed_mainline":
            continuity = continuity if isinstance(continuity, dict) else {}
            score = line.get("score")
            hits = continuity.get("hits")
            if not _finite_number(score) or float(score) < 70:
                errors.append(
                    f"{prefix} confirmed_mainline requires score >= 70"
                )
            if continuity.get("known") is not True:
                errors.append(
                    f"{prefix} confirmed_mainline requires known continuity"
                )
            if not _finite_number(hits) or float(hits) < 3:
                errors.append(
                    f"{prefix} confirmed_mainline requires continuity hits >= 3"
                )
            if _has_critical_contradiction(line):
                errors.append(
                    f"{prefix} confirmed_mainline has critical contradiction"
                )

        leaders = _list_or_empty(
            line.get("leaders"), f"{prefix}.leaders", errors
        )
        for leader_index, leader in enumerate(leaders):
            leader_prefix = f"{prefix}.leaders[{leader_index}]"
            if not isinstance(leader, dict):
                errors.append(f"{leader_prefix} must be an object")
                continue
            errors.extend(
                _missing_fields(leader, REQUIRED_LEADER_FIELDS, leader_prefix)
            )
            _validate_non_empty_string_fields(
                leader,
                (
                    "code",
                    "name",
                    "role_evidence",
                    "confidence",
                    "risk",
                ),
                leader_prefix,
                errors,
            )
            if (
                "role" in leader
                and not _is_allowed_string(
                    leader.get("role"), ALLOWED_LEADER_ROLES
                )
            ):
                errors.append(f"{leader_prefix} invalid role")
            _validate_evidence_ids(
                leader.get("evidence_ids"),
                leader_prefix,
                known_evidence,
                errors,
            )

    diagnosis = signal.get("portfolio_diagnosis")
    if not isinstance(diagnosis, dict):
        errors.append("portfolio_diagnosis must be an object")
    else:
        errors.extend(
            _missing_fields(
                diagnosis,
                REQUIRED_PORTFOLIO_DIAGNOSIS_FIELDS,
                "portfolio_diagnosis",
            )
        )
        for field in (
            "stock_exposure",
            "cash_weight",
            "off_mainline_exposure",
            "counter_regime_exposure",
        ):
            if field in diagnosis:
                _validate_number(
                    diagnosis.get(field),
                    f"portfolio_diagnosis.{field}",
                    errors,
                    minimum=0.0,
                    maximum=1.0,
                    nullable=True,
                )
        for field in (
            "counter_regime_exposure_note",
            "portfolio_posture",
        ):
            if field in diagnosis and diagnosis.get(field) is not None:
                _validate_non_empty_string_fields(
                    diagnosis, (field,), "portfolio_diagnosis", errors
                )
        diagnosis_lists: Dict[str, List[Any]] = {}
        for field in PORTFOLIO_DIAGNOSIS_LIST_FIELDS:
            if field in diagnosis:
                diagnosis_lists[field] = _list_or_empty(
                    diagnosis.get(field),
                    f"portfolio_diagnosis.{field}",
                    errors,
                )
        for field, required in PORTFOLIO_DIAGNOSIS_OBJECT_LIST_FIELDS.items():
            _validate_object_list_entries(
                diagnosis_lists.get(field, []),
                f"portfolio_diagnosis.{field}",
                required,
                errors,
            )
        concentration_specs = {
            "single_stock_concentration": ("code", "name"),
            "industry_concentration": ("industry",),
            "theme_concentration": ("theme",),
            "mainline_alignment": ("mainline",),
        }
        for field, string_fields in concentration_specs.items():
            for index, row in enumerate(diagnosis_lists.get(field, [])):
                if not isinstance(row, dict):
                    continue
                prefix = f"portfolio_diagnosis.{field}[{index}]"
                _validate_non_empty_string_fields(
                    row, string_fields, prefix, errors
                )
                if "weight" in row:
                    _validate_number(
                        row.get("weight"),
                        f"{prefix}.weight",
                        errors,
                        minimum=0.0,
                        maximum=1.0,
                        nullable=True,
                    )
        for index, row in enumerate(
            diagnosis_lists.get("top_action_priorities", [])
        ):
            if not isinstance(row, dict):
                continue
            prefix = f"portfolio_diagnosis.top_action_priorities[{index}]"
            _validate_non_empty_string_fields(
                row, ("code", "name"), prefix, errors
            )
            if "action" in row and not _is_allowed_string(
                row.get("action"), ALLOWED_ACTIONS
            ):
                errors.append(f"{prefix} invalid action")
        for index, value in enumerate(
            diagnosis_lists.get("shared_catalyst_risks", [])
        ):
            if not isinstance(value, str):
                errors.append(
                    "portfolio_diagnosis.shared_catalyst_risks"
                    f"[{index}] must be a string"
                )
            elif not value.strip():
                errors.append(
                    "portfolio_diagnosis.shared_catalyst_risks"
                    f"[{index}] must be a non-empty string"
                )
        if (
            "asset_coverage_note" in diagnosis
            and not isinstance(diagnosis.get("asset_coverage_note"), str)
        ):
            errors.append(
                "portfolio_diagnosis.asset_coverage_note must be a string"
            )

    stock_scores_by_code: Dict[str, tuple[int, Dict[str, Any]]] = {}
    if "stock_scores" in signal:
        stock_scores = signal.get("stock_scores")
        if not isinstance(stock_scores, list):
            errors.append("stock_scores must be a list")
            stock_scores = []
        for index, row in enumerate(stock_scores):
            prefix = f"stock_scores[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix} must be an object")
                continue
            code = row.get("code")
            if not _is_non_empty_string(code):
                errors.append(f"{prefix} code must be a non-empty string")
            elif code in stock_scores_by_code:
                errors.append(f"duplicate stock_scores code {code}")
            else:
                stock_scores_by_code[code] = (index, row)
            if "name" in row:
                _validate_non_empty_string_fields(
                    row, ("name",), prefix, errors
                )
            if "current_weight" in row:
                _validate_number(
                    row.get("current_weight"),
                    f"{prefix}.current_weight",
                    errors,
                    minimum=0.0,
                    maximum=1.0,
                )
            if "price" in row:
                _validate_number(
                    row.get("price"),
                    f"{prefix}.price",
                    errors,
                    minimum=0.0,
                    nullable=True,
                )

            scores = row.get("scores")
            if not isinstance(scores, dict):
                errors.append(f"{prefix} scores must be an object")
                continue
            errors.extend(
                _missing_fields(
                    scores,
                    REQUIRED_FACTOR_EVIDENCE_FIELDS,
                    f"{prefix}.scores",
                )
            )
            for field in REQUIRED_FACTOR_EVIDENCE_FIELDS:
                if field not in scores:
                    continue
                _validate_number(
                    scores.get(field),
                    f"{prefix}.scores.{field}",
                    errors,
                    minimum=0.0,
                    maximum=100.0,
                    nullable=field == "fund_flow_score",
                )
            missing_data = row.get("missing_data")
            if not isinstance(missing_data, list):
                errors.append(f"{prefix} missing_data must be a list")
                missing_data = []
            else:
                for missing_index, value in enumerate(missing_data):
                    if not _is_non_empty_string(value):
                        errors.append(
                            f"{prefix}.missing_data[{missing_index}] must be "
                            "a non-empty string"
                        )
            imputations = scores.get("score_imputations", {})
            if not isinstance(imputations, dict):
                errors.append(
                    f"{prefix}.scores.score_imputations must be an object"
                )
                imputations = {}
            has_fund_imputation = "fund_flow" in imputations
            if has_fund_imputation and not (
                _finite_number(imputations.get("fund_flow"))
                and float(imputations["fund_flow"]) == 50.0
            ):
                errors.append(
                    f"{prefix}.scores.score_imputations.fund_flow must equal "
                    "finite number 50"
                )

            fund_score = scores.get("fund_flow_score")
            if fund_score is not None and not _finite_number(fund_score):
                errors.append(
                    f"{prefix}.scores.fund_flow_score must be a finite number "
                    "or null"
                )
            if fund_score is not None and has_fund_imputation:
                errors.append(
                    f"{prefix}.scores fund_flow_score and "
                    "score_imputations.fund_flow are mutually exclusive"
                )

            raw = scores.get("raw")
            if not isinstance(raw, dict):
                errors.append(f"{prefix}.scores.raw must be an object")
                raw = {}
            elif "fund_flow_5d_net_wan" not in raw:
                errors.append(
                    f"{prefix}.scores.raw missing fund_flow_5d_net_wan"
                )
            fund_net = raw.get("fund_flow_5d_net_wan")
            if fund_net is not None and not _finite_number(fund_net):
                errors.append(
                    f"{prefix}.scores.raw.fund_flow_5d_net_wan must be a "
                    "finite number or null"
                )
            if has_fund_imputation:
                if "fund_flow" not in missing_data:
                    errors.append(
                        f"{prefix} fund_flow imputation requires missing_data "
                        "to contain fund_flow"
                    )
                if fund_net is not None:
                    errors.append(
                        f"{prefix} fund_flow imputation requires "
                        "fund_flow_5d_net_wan null"
                    )

            if "fund_flow" in missing_data:
                if fund_score is not None:
                    errors.append(
                        f"{prefix} fund_flow missing requires "
                        "fund_flow_score null"
                    )
                if fund_net is not None:
                    errors.append(
                        f"{prefix} fund_flow missing requires "
                        "fund_flow_5d_net_wan null"
                    )
                if not (
                    has_fund_imputation
                    and _finite_number(imputations.get("fund_flow"))
                    and float(imputations["fund_flow"]) == 50.0
                ):
                    errors.append(
                        f"{prefix} fund_flow missing requires neutral "
                        "fund_flow imputation 50"
                    )

    holdings = signal.get("holding_analyses", [])
    if not isinstance(holdings, list):
        errors.append("holding_analyses must be a list")
        holdings = []
    holdings_by_code: Dict[str, tuple[int, Dict[str, Any]]] = {}
    for index, holding in enumerate(holdings):
        prefix = f"holding_analyses[{index}]"
        if not isinstance(holding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_missing_fields(holding, REQUIRED_HOLDING_FIELDS, prefix))
        _validate_non_empty_string_fields(
            holding,
            (
                "code",
                "name",
                "thesis_status",
                "data_confidence",
                "reason",
                "trigger",
                "invalidation",
                "risk_note",
            ),
            prefix,
            errors,
        )
        code = holding.get("code")
        if _is_non_empty_string(code):
            if code in holdings_by_code:
                errors.append(f"duplicate holding_analyses code {code}")
            else:
                holdings_by_code[code] = (index, holding)
        if (
            "account_role" in holding
            and not _is_allowed_string(
                holding.get("account_role"), ALLOWED_ACCOUNT_ROLES
            )
        ):
            errors.append(f"{prefix} invalid account_role")
        _validate_action(holding, prefix, errors)
        if "priority" in holding:
            _validate_number(
                holding.get("priority"),
                f"{prefix}.priority",
                errors,
                minimum=1.0,
                maximum=5.0,
                integer=True,
            )
        for field in ("industry_panorama", "factor_evidence"):
            value = holding.get(field)
            if field in holding and value is not None and not isinstance(
                value, dict
            ):
                errors.append(f"{prefix} {field} must be an object or null")
        panorama = holding.get("industry_panorama")
        if isinstance(panorama, dict):
            errors.extend(
                _missing_fields(
                    panorama,
                    REQUIRED_INDUSTRY_PANORAMA_FIELDS,
                    f"{prefix}.industry_panorama",
                )
            )
            _validate_non_empty_string_fields(
                panorama,
                REQUIRED_INDUSTRY_PANORAMA_FIELDS,
                f"{prefix}.industry_panorama",
                errors,
            )
        factors = holding.get("factor_evidence")
        if isinstance(factors, dict):
            errors.extend(
                _missing_fields(
                    factors,
                    REQUIRED_FACTOR_EVIDENCE_FIELDS,
                    f"{prefix}.factor_evidence",
                )
            )
            for field in REQUIRED_FACTOR_EVIDENCE_FIELDS:
                if field not in factors:
                    continue
                _validate_number(
                    factors.get(field),
                    f"{prefix}.factor_evidence.{field}",
                    errors,
                    minimum=0.0,
                    maximum=100.0,
                    nullable=field == "fund_flow_score",
                )
            factor_imputations = factors.get("score_imputations", {})
            if not isinstance(factor_imputations, dict):
                errors.append(
                    f"{prefix}.factor_evidence.score_imputations must be an object"
                )
                factor_imputations = {}
            has_fund_imputation = "fund_flow" in factor_imputations
            if has_fund_imputation and not (
                _finite_number(factor_imputations.get("fund_flow"))
                and float(factor_imputations["fund_flow"]) == 50.0
            ):
                errors.append(
                    f"{prefix}.factor_evidence.score_imputations.fund_flow "
                    "must equal finite number 50"
                )
            factor_fund_score = factors.get("fund_flow_score")
            if (
                factor_fund_score is not None
                and not _finite_number(factor_fund_score)
            ):
                errors.append(
                    f"{prefix}.factor_evidence.fund_flow_score must be a "
                    "finite number or null"
                )
            if factor_fund_score is not None and has_fund_imputation:
                errors.append(
                    f"{prefix}.factor_evidence fund_flow_score and "
                    "score_imputations.fund_flow are mutually exclusive"
                )

            factor_raw_value = factors.get("raw")
            if "raw" in factors and not isinstance(factor_raw_value, dict):
                errors.append(
                    f"{prefix}.factor_evidence.raw must be an object"
                )
            factor_raw = (
                factor_raw_value
                if isinstance(factor_raw_value, dict)
                else {}
            )
            if has_fund_imputation:
                if not isinstance(factor_raw_value, dict):
                    if "raw" not in factors:
                        errors.append(
                            f"{prefix}.factor_evidence.raw must be an object"
                        )
                elif "fund_flow_5d_net_wan" not in factor_raw:
                    errors.append(
                        f"{prefix}.factor_evidence.raw missing "
                        "fund_flow_5d_net_wan"
                    )
                elif factor_raw.get("fund_flow_5d_net_wan") is not None:
                    errors.append(
                        f"{prefix}.factor_evidence fund_flow imputation "
                        "requires fund_flow_5d_net_wan null"
                    )

            code = holding.get("code")
            score_match = (
                stock_scores_by_code.get(code)
                if _is_non_empty_string(code)
                else None
            )
            if score_match is not None:
                score_index, score_row = score_match
                if holding.get("name") != score_row.get("name"):
                    errors.append(
                        f"stock_scores[{score_index}].name does not match "
                        f"holding_analyses[{index}]"
                    )
                scores = score_row.get("scores")
                if isinstance(scores, dict):
                    for field in REQUIRED_FACTOR_EVIDENCE_FIELDS:
                        if not _same_nullable_number(
                            factors.get(field), scores.get(field)
                        ):
                            errors.append(
                                f"{prefix}.factor_evidence.{field} does not "
                                f"match stock_scores[{score_index}]"
                            )
                    if not _same_nullable_number(
                        factor_fund_score, scores.get("fund_flow_score")
                    ):
                        expected = (
                            f"{prefix}.factor_evidence.fund_flow_score does "
                            f"not match stock_scores[{score_index}]"
                        )
                        if expected not in errors:
                            errors.append(expected)
                    score_imputations = scores.get("score_imputations", {})
                    score_imputations = (
                        score_imputations
                        if isinstance(score_imputations, dict)
                        else {}
                    )
                    if not _same_nullable_number(
                        factor_imputations.get("fund_flow"),
                        score_imputations.get("fund_flow"),
                    ):
                        errors.append(
                            f"{prefix}.factor_evidence.score_imputations."
                            "fund_flow does not match "
                            f"stock_scores[{score_index}]"
                        )
                    if not isinstance(factor_raw_value, dict):
                        if "raw" not in factors and not has_fund_imputation:
                            errors.append(
                                f"{prefix}.factor_evidence.raw must be an "
                                "object"
                            )
                    elif (
                        "fund_flow_5d_net_wan" not in factor_raw
                        and not has_fund_imputation
                    ):
                        errors.append(
                            f"{prefix}.factor_evidence.raw missing "
                            "fund_flow_5d_net_wan"
                        )
                    score_raw = scores.get("raw", {})
                    score_raw = (
                        score_raw if isinstance(score_raw, dict) else {}
                    )
                    if not _same_nullable_number(
                        factor_raw.get("fund_flow_5d_net_wan"),
                        score_raw.get("fund_flow_5d_net_wan"),
                    ):
                        errors.append(
                            f"{prefix}.factor_evidence.raw."
                            "fund_flow_5d_net_wan does not match "
                            f"stock_scores[{score_index}]"
                        )
        mainline_links = _list_or_empty(
            holding.get("mainline_links"),
            f"{prefix} mainline_links",
            errors,
        )
        for link_index, link in enumerate(mainline_links):
            link_prefix = f"{prefix}.mainline_links[{link_index}]"
            if not isinstance(link, dict):
                errors.append(f"{link_prefix} must be an object")
                continue
            errors.extend(
                _missing_fields(
                    link,
                    ("name", "relationship", "leader_roles"),
                    link_prefix,
                )
            )
            _validate_non_empty_string_fields(
                link, ("name", "relationship"), link_prefix, errors
            )
            if "leader_roles" in link:
                leader_roles = _list_or_empty(
                    link.get("leader_roles"),
                    f"{link_prefix} leader_roles",
                    errors,
                )
                for role_index, role in enumerate(leader_roles):
                    if (
                        not isinstance(role, str)
                        or role not in ALLOWED_LEADER_ROLES
                    ):
                        errors.append(
                            f"{link_prefix}.leader_roles[{role_index}] "
                            "invalid role"
                        )
        for field in ("bull_evidence", "bear_evidence", "evidence_gaps"):
            if field in holding:
                values = _list_or_empty(
                    holding.get(field), f"{prefix} {field}", errors
                )
                for item_index, item in enumerate(values):
                    if not _is_non_empty_string(item):
                        errors.append(
                            f"{prefix}.{field}[{item_index}] must be a "
                            "non-empty string"
                        )
        _validate_evidence_ids(
            holding.get("evidence_ids"), prefix, known_evidence, errors
        )

    actions = signal.get("portfolio_actions", [])
    if not isinstance(actions, list):
        errors.append("portfolio_actions must be a list")
        actions = []
    actions_by_code: Dict[str, tuple[int, Dict[str, Any]]] = {}
    for index, action in enumerate(actions):
        prefix = f"portfolio_actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix} must be an object")
        else:
            _validate_action(action, prefix, errors, require_fields=True)
            code = action.get("code")
            if _is_non_empty_string(code):
                if code in actions_by_code:
                    errors.append(f"duplicate portfolio_actions code {code}")
                else:
                    actions_by_code[code] = (index, action)

    holding_codes = set(holdings_by_code)
    action_codes = set(actions_by_code)
    if action_codes != holding_codes:
        errors.append(
            "portfolio_actions codes must match holding_analyses codes"
        )
    if "stock_scores" in signal and isinstance(signal.get("stock_scores"), list):
        if set(stock_scores_by_code) != holding_codes:
            errors.append(
                "stock_scores codes must match holding_analyses codes"
            )

    for code in holding_codes & action_codes:
        holding_index, holding = holdings_by_code[code]
        action_index, action = actions_by_code[code]
        for field in (
            "name",
            "action",
            "reason",
            "trigger",
            "invalidation",
            "risk_note",
        ):
            if action.get(field) != holding.get(field):
                errors.append(
                    f"portfolio_actions[{action_index}].{field} does not "
                    f"match holding_analyses[{holding_index}]"
                )
        if not _same_nullable_number(
            action.get("target_weight"), holding.get("target_weight")
        ):
            errors.append(
                f"portfolio_actions[{action_index}].target_weight does not "
                f"match holding_analyses[{holding_index}]"
            )

    for code in holding_codes & set(stock_scores_by_code):
        holding_index, holding = holdings_by_code[code]
        score_index, score_row = stock_scores_by_code[code]
        if score_row.get("name") != holding.get("name"):
            expected = (
                f"stock_scores[{score_index}].name does not match "
                f"holding_analyses[{holding_index}]"
            )
            if expected not in errors:
                errors.append(expected)
    return list(dict.fromkeys(errors))


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _value(value: Any) -> str:
    return "证据不足" if _is_missing(value) else str(value)


def _cell(value: Any) -> str:
    return (
        _value(value)
        .replace("|", "\\|")
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _items(values: Any) -> List[Any]:
    if _is_missing(values):
        return []
    if isinstance(values, (str, bytes)):
        return [values]
    if isinstance(values, dict):
        return [values]
    if isinstance(values, Iterable):
        return list(values)
    return [values]


def _join(values: Any) -> str:
    cleaned = [_cell(value) for value in _items(values) if not _is_missing(value)]
    return "；".join(cleaned) if cleaned else "证据不足"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:.2%}" if number is not None else "证据不足"


def _metric(value: Any, suffix: str = "") -> str:
    return f"{_cell(value)}{suffix}" if not _is_missing(value) else "证据不足"


def _leader_text(leaders: Any) -> str:
    return _join(
        f"{row.get('name')}({row.get('role')})"
        for row in _items(leaders)
        if isinstance(row, dict)
    )


def _mainline_link_text(link: Dict[str, Any]) -> str:
    return (
        f"{_cell(link.get('name'))}；"
        f"主线关系：{_cell(link.get('relationship'))}；"
        f"龙头角色：{_join(link.get('leader_roles', []))}"
    )


def _append_outlook(
    lines: List[str], label: str, outlook: Dict[str, Any]
) -> None:
    lines.extend(
        [
            f"### {label}（{_cell(outlook.get('horizon'))}）",
            f"- 基准情景：{_cell(outlook.get('base_case'))}",
            f"- 更强情景：{_cell(outlook.get('stronger_case'))}",
            f"- 更弱情景：{_cell(outlook.get('weaker_case'))}",
            f"- 关键变量：{_join(outlook.get('key_variables', []))}",
            f"- 组合姿态：{_cell(outlook.get('portfolio_posture'))}",
            f"- 失效条件：{_cell(outlook.get('invalidation'))}",
            f"- 可信度：{_cell(outlook.get('confidence'))}",
            "",
        ]
    )


def render_report(
    positions: Dict[str, Any],
    signal: Dict[str, Any],
    backtest: Dict[str, Any],
    optimization: Dict[str, Any],
    data_errors: Sequence[str],
    title: str = "股票策略闭环报告",
) -> str:
    errors = validate_signal_v2(signal)
    if errors:
        raise ValueError("; ".join(errors))

    snapshot = signal["market_snapshot"]
    mainlines = signal["market_mainlines"]
    diagnosis_value = signal["portfolio_diagnosis"]
    diagnosis = diagnosis_value if isinstance(diagnosis_value, dict) else {}
    lines = [
        f"# {_cell(title)} - {_cell(snapshot.get('as_of'))}",
        "",
        "## 核心结论",
        f"- 市场状态：{_cell(snapshot.get('regime'))}；可信度：{_cell(snapshot.get('confidence'))}",
        "- 主导主线："
        + _join(
            row.get("name")
            for row in mainlines
            if row.get("classification")
            in {"confirmed_mainline", "emerging_mainline", "recent_mainline"}
        ),
        f"- 组合姿态：{_cell(diagnosis.get('portfolio_posture'))}",
    ]
    priorities = [
        row
        for row in _items(diagnosis.get("top_action_priorities"))
        if isinstance(row, dict)
    ]
    lines.extend(
        f"- 优先动作：{_cell(row.get('code'))} {_cell(row.get('name'))} {_cell(row.get('action'))}"
        for row in priorities[:3]
    )
    if not priorities:
        lines.append("- 优先动作：证据不足")

    coverage = signal.get("data_coverage", {})
    coverage = coverage if isinstance(coverage, dict) else {}
    lines.extend(
        [
            "",
            "## 数据覆盖与时效",
            f"- 截图时间：{_cell(positions.get('snapshot_time'))}",
            f"- 市场时间：{_cell(snapshot.get('as_of'))}",
            f"- 交易时段：{_cell(snapshot.get('trading_session'))}",
            f"- 总体可信度：{_cell(snapshot.get('confidence'))}",
            f"- 缺失证据：{_join(snapshot.get('missing_evidence', []))}",
            f"- 数据问题：{_join(data_errors)}",
            "",
            "| 数据项 | 覆盖 |",
            "|---|---|",
        ]
    )
    coverage_keys = (
        "holdings",
        "quotes",
        "history",
        "fund_flow",
        "events",
        "industry",
        "board_summaries",
        "board_details",
        "breadth",
        "mainline_history_sessions",
        "indices",
        "market_news",
        "errors",
    )
    lines.extend(f"| {key} | {_cell(coverage.get(key))} |" for key in coverage_keys)

    lines.extend(
        [
            "",
            "## 今日市场发生了什么",
            "",
            "| 指数 | 最新值 | 涨跌幅 |",
            "|---|---:|---:|",
        ]
    )
    indices = [
        row
        for row in _items(snapshot.get("indices"))
        if isinstance(row, dict)
    ]
    for row in indices:
        lines.append(
            f"| {_cell(row.get('name'))} | {_cell(row.get('price'))} | "
            f"{_metric(row.get('change_pct'), '%')} |"
        )
    if not indices:
        lines.append("| 证据不足 | 证据不足 | 证据不足 |")
    breadth = snapshot.get("breadth", {})
    breadth = breadth if isinstance(breadth, dict) else {}
    lines.extend(
        [
            "",
            f"- 市场广度：上涨 {_cell(breadth.get('advancers'))}，下跌 {_cell(breadth.get('decliners'))}，平盘 {_cell(breadth.get('unchanged'))}。",
            f"- 成交与中位数：总成交 {_cell(breadth.get('turnover_yuan'))} 元，中位涨跌 {_metric(breadth.get('median_change_pct'), '%')}。",
            f"- 涨跌停结构：{_cell('可用' if breadth.get('limit_structure_available') is True else None)}。",
            f"- 风格分化：{_cell(snapshot.get('style_divergence'))}",
            f"- 风险偏好：{_cell(snapshot.get('risk_appetite'))}",
        ]
    )

    lines.extend(
        [
            "",
            "## 近期主线与今日主线",
            "",
            "| 主线 | 分类 | 得分 | 催化 | 龙头角色 | 证据 | 延续条件 | 失效条件 | 风险 | 可信度 |",
            "|---|---|---:|---|---|---|---|---|---|---|",
        ]
    )
    for row in mainlines:
        lines.append(
            f"| {_cell(row.get('name'))} | {_cell(row.get('classification'))} | "
            f"{_cell(row.get('score'))} | "
            f"{'已验证' if row.get('catalyst_verified') else '待验证'} | "
            f"{_leader_text(row.get('leaders', []))} | "
            f"{_join(row.get('evidence_ids', []))} | "
            f"{_join(row.get('continuation_conditions', []))} | "
            f"{_join(row.get('invalidation_conditions', []))} | "
            f"{_cell(row.get('risk'))} | {_cell(row.get('confidence'))} |"
        )
    if not mainlines:
        lines.append("| 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 | 证据不足 |")

    lines.extend(["", "## 事实—逻辑—推演"])
    for row in mainlines:
        chain = row.get("logic_chain", {})
        chain = chain if isinstance(chain, dict) else {}
        lines.extend(
            [
                "",
                f"### {_cell(row.get('name'))}",
                f"- 事实：{_join(chain.get('facts', []))}",
                f"- 推断—即时驱动：{_cell(chain.get('driver'))}",
                f"- 推断—社会/产业需求：{_cell(chain.get('social_or_industrial_need'))}",
                f"- 推断—产业链传导：{_cell(chain.get('value_chain_transmission'))}",
                f"- 待验证—盈利传导：{_cell(chain.get('earnings_transmission'))}",
                f"- 价格确认：{_cell(chain.get('price_confirmation'))}",
                f"- 反证：{_join(chain.get('contradictions', []))}",
                f"- 待验证：{_join(chain.get('unknowns', []))}",
                f"- 监测变量：{_join(row.get('continuation_conditions', []))}",
                f"- 失效条件：{_join(row.get('invalidation_conditions', []))}",
            ]
        )
    if not mainlines:
        lines.append("- 证据不足：没有可构造的主线因果链。")

    lines.extend(["", "## 双周期市场预判", ""])
    _append_outlook(lines, "短期", signal["market_outlook"]["short_term"])
    _append_outlook(lines, "中期", signal["market_outlook"]["medium_term"])

    lines.extend(
        [
            "## 组合诊断",
            f"- 组合姿态：{_cell(diagnosis.get('portfolio_posture'))}",
            f"- 股票仓位：{_percent(diagnosis.get('stock_exposure'))}；现金权重：{_percent(diagnosis.get('cash_weight'))}",
            *(
                [f"- 资产覆盖说明：{_cell(diagnosis.get('asset_coverage_note'))}"]
                if diagnosis.get("asset_coverage_note")
                else []
            ),
            f"- 非主线暴露：{_percent(diagnosis.get('off_mainline_exposure'))}",
            f"- 逆市场状态暴露：{_percent(diagnosis.get('counter_regime_exposure'))}",
            f"- 逆市场状态说明：{_cell(diagnosis.get('counter_regime_exposure_note'))}",
            f"- 共享催化风险：{_join(diagnosis.get('shared_catalyst_risks', []))}",
            "",
            "### 单股集中度",
            "| 代码 | 名称 | 权重 |",
            "|---|---|---:|",
        ]
    )
    single_stock = [
        row
        for row in _items(diagnosis.get("single_stock_concentration"))
        if isinstance(row, dict)
    ]
    for row in single_stock:
        lines.append(
            f"| {_cell(row.get('code'))} | {_cell(row.get('name'))} | "
            f"{_percent(row.get('weight'))} |"
        )
    if not single_stock:
        lines.append("| 证据不足 | 证据不足 | 证据不足 |")

    lines.extend(["", "### 行业集中度", "| 行业 | 权重 |", "|---|---:|"])
    industries = [
        row
        for row in _items(diagnosis.get("industry_concentration"))
        if isinstance(row, dict)
    ]
    for row in industries:
        lines.append(
            f"| {_cell(row.get('industry'))} | {_percent(row.get('weight'))} |"
        )
    if not industries:
        lines.append("| 证据不足 | 证据不足 |")

    lines.extend(["", "### 主题集中度", "| 主题 | 权重 |", "|---|---:|"])
    themes = [
        row
        for row in _items(diagnosis.get("theme_concentration"))
        if isinstance(row, dict)
    ]
    for row in themes:
        lines.append(
            f"| {_cell(row.get('theme'))} | {_percent(row.get('weight'))} |"
        )
    if not themes:
        lines.append("| 证据不足 | 证据不足 |")

    lines.extend(["", "### 主线对齐", "| 主线 | 权重 |", "|---|---:|"])
    alignment = [
        row
        for row in _items(diagnosis.get("mainline_alignment"))
        if isinstance(row, dict)
    ]
    for row in alignment:
        lines.append(
            f"| {_cell(row.get('mainline'))} | {_percent(row.get('weight'))} |"
        )
    if not alignment:
        lines.append("| 证据不足 | 证据不足 |")

    lines.extend(["", "## 持仓逐股分析与操作建议"])
    holdings = signal["holding_analyses"]
    for row in holdings:
        panorama = row.get("industry_panorama", {})
        panorama = panorama if isinstance(panorama, dict) else {}
        factors = row.get("factor_evidence", {})
        factors = factors if isinstance(factors, dict) else {}
        score_imputations = factors.get("score_imputations", {})
        score_imputations = (
            score_imputations if isinstance(score_imputations, dict) else {}
        )
        fund_flow_evidence = _cell(factors.get("fund_flow_score"))
        if (
            factors.get("fund_flow_score") is None
            and score_imputations.get("fund_flow") == 50.0
        ):
            fund_flow_evidence = "证据不足（总分按中性 50 插补）"
        links = row.get("mainline_links", [])
        lines.extend(
            [
                "",
                f"### {_cell(row.get('code'))} {_cell(row.get('name'))}",
                f"- 账户角色/行业位置：{_cell(row.get('account_role'))}；{_cell(panorama.get('segment_focus'))}；{_cell(panorama.get('value_chain_position'))}。",
                f"- 上游依赖：{_cell(panorama.get('upstream_dependency_check'))}",
                f"- 下游客户/需求：{_cell(panorama.get('downstream_customer_check'))}",
                f"- 行业影响与稀缺能力：{_cell(panorama.get('industry_influence_question'))}；{_cell(panorama.get('scarce_capability_check'))}",
                f"- 类比理解：{_cell(panorama.get('learning_analogy'))}",
            ]
        )
        if links:
            lines.extend(
                f"- 主线映射：{_mainline_link_text(link)}"
                for link in links
                if isinstance(link, dict)
            )
        else:
            lines.append("- 主线映射：证据不足；主线关系：证据不足；龙头角色：证据不足")
        lines.extend(
            [
                f"- 五因子/技术证据：总分 {_cell(factors.get('total_score'))}，趋势 {_cell(factors.get('trend_score'))}，MACD {_cell(factors.get('macd_score'))}，资金 {fund_flow_evidence}，板块 {_cell(factors.get('sector_score'))}，事件 {_cell(factors.get('event_score'))}。",
                f"- 多头证据：{_join(row.get('bull_evidence', []))}",
                f"- 空头/反证：{_join(row.get('bear_evidence', []))}",
                f"- 论点状态：{_cell(row.get('thesis_status'))}",
                f"- 数据可信度：{_cell(row.get('data_confidence'))}",
                f"- 证据缺口：{_join(row.get('evidence_gaps', []))}",
                f"- 证据编号：{_join(row.get('evidence_ids', []))}",
                f"- 建议：{_cell(row.get('action'))}；优先级 {_cell(row.get('priority'))}；目标权重 {_percent(row.get('target_weight'))}。",
                f"- 原因：{_cell(row.get('reason'))}",
                f"- 触发：{_cell(row.get('trigger'))}",
                f"- 失效：{_cell(row.get('invalidation'))}",
                f"- 风险：{_cell(row.get('risk_note'))}",
            ]
        )
    if not holdings:
        lines.append("- 证据不足：当前没有持仓分析对象。")

    metrics = backtest.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    lines.extend(
        [
            "",
            "## 回测与参数证据",
            f"- 回测范围：{_cell(backtest.get('scope'))}",
            f"- 年化收益：{_metric(metrics.get('annualized_return_pct'), '%')}；最大回撤：{_metric(metrics.get('max_drawdown_pct'), '%')}；Sharpe：{_cell(metrics.get('sharpe'))}。",
            f"- 胜率：{_metric(metrics.get('win_rate_pct'), '%')}；交易次数：{_cell(metrics.get('trade_count'))}；换手：{_cell(metrics.get('turnover'))}。",
            f"- 优化资格：{_cell(optimization.get('eligible'))}",
            f"- 参数结论：{_cell(optimization.get('selected_reason') or optimization.get('reason'))}",
            f"- 局限：{_cell(backtest.get('limitations') or optimization.get('limitations'))}",
        ]
    )

    review = signal.get("loop_review", {})
    review = review if isinstance(review, dict) else {}
    lines.extend(
        [
            "",
            "## 闭环复盘与下一次检查清单",
            f"- 闭环状态：{_cell(review.get('status'))}",
            f"- 上次/本次截图：{_cell(review.get('previous_snapshot_time'))} → {_cell(review.get('current_snapshot_time'))}",
            f"- 持仓变化：{_join(review.get('observed_share_changes', []))}",
            f"- 上次动作对照：{_join(review.get('prior_action_comparison', []))}",
            f"- 下次检查：{_join(review.get('next_session_checks', []))}",
            "- 下一次手动触发：加入新截图后运行；复核广度、成交、主线龙头和每只持仓失效条件。",
            f"- 数据问题：{_join(data_errors)}",
            "- 本报告仅用于研究与模拟，不自动下单。",
        ]
    )
    return "\n".join(lines) + "\n"
