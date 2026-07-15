from __future__ import annotations

import datetime as dt
import math
import statistics
from typing import Any, Dict, List, Optional, Sequence


def _date(value: Any) -> str:
    text = str(value or "")[:10]
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def finite_number(value: Any) -> Optional[float]:
    """Return a finite numeric value while rejecting bools and containers."""
    if value is None or isinstance(value, bool) or isinstance(
        value, (list, tuple, dict, set)
    ):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_market_number(value: Any) -> Optional[float]:
    """Return finite built-in numeric market evidence without coercing strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def classify_freshness(as_of: Any, latest_trade_date: str, recent_trade_dates: Sequence[str]) -> str:
    observed = _date(as_of)
    latest = _date(latest_trade_date)
    if not observed or not latest or observed > latest:
        return "unknown"
    if observed == latest:
        return "current-session"
    if observed in set(recent_trade_dates[:10]):
        return "recent"
    return "stale"


def make_evidence(
    evidence_id: str,
    category: str,
    statement: str,
    source: str,
    as_of: Any,
    latest_trade_date: str,
    recent_trade_dates: Sequence[str],
    scope: str,
    reliability: str,
    url: str | None = None,
) -> Dict[str, Any]:
    freshness = classify_freshness(as_of, latest_trade_date, recent_trade_dates)
    if freshness in {"stale", "unknown"}:
        reliability = "low"
    return {
        "evidence_id": evidence_id,
        "category": category,
        "statement": statement,
        "source": source,
        "url": url,
        "as_of": as_of,
        "trading_session": latest_trade_date,
        "freshness": freshness,
        "reliability": reliability,
        "scope": scope,
    }


def build_market_snapshot(
    indices: List[Dict[str, Any]], breadth: Dict[str, Any], latest_trade_date: str
) -> Dict[str, Any]:
    clean_indices: List[Dict[str, Any]] = []
    changes: List[float] = []
    for row in indices if isinstance(indices, list) else []:
        if not isinstance(row, dict):
            continue
        change = finite_number(row.get("change_pct"))
        if change is None:
            continue
        clean_row = {**row, "change_pct": change}
        if "price" in clean_row:
            price = finite_number(clean_row.get("price"))
            clean_row["price"] = price if price is not None and price >= 0 else None
        clean_indices.append(clean_row)
        changes.append(change)
    breadth = breadth if isinstance(breadth, dict) else {}
    advancers = finite_number(breadth.get("advancers"))
    decliners = finite_number(breadth.get("decliners"))
    turnover = finite_number(breadth.get("turnover_yuan"))
    clean_breadth = dict(breadth)
    for field in ("advancers", "decliners", "unchanged", "sample_size", "turnover_yuan"):
        number = finite_number(clean_breadth.get(field))
        clean_breadth[field] = (
            number if number is not None and number >= 0 else None
        )
    if "median_change_pct" in clean_breadth:
        clean_breadth["median_change_pct"] = finite_number(
            clean_breadth.get("median_change_pct")
        )
    divergence = max(changes) - min(changes) if len(changes) > 1 else 0.0
    missing: List[str] = []
    expected_date = _date(latest_trade_date)
    if not expected_date or not clean_indices or any(
        _date(row.get("as_of")) != expected_date for row in clean_indices
    ):
        missing.append("indices_as_of")
    if any(
        "stale" in row and row.get("stale") is not False
        for row in clean_indices
    ):
        missing.append("indices_stale")
    if not expected_date or _date(breadth.get("as_of")) != expected_date:
        missing.append("breadth_as_of")
    if "stale" in breadth and breadth.get("stale") is not False:
        missing.append("breadth_stale")
    if breadth.get("complete") is not True:
        missing.append("breadth_completeness")
    if (
        advancers is None
        or advancers <= 0
        or decliners is None
        or decliners <= 0
    ):
        missing.append("breadth")
    if turnover is None or turnover <= 0:
        missing.append("turnover")
    if missing:
        regime, confidence = "insufficient_evidence", "low"
    else:
        adv = advancers
        dec = decliners
        average = statistics.mean(changes) if changes else 0.0
        if divergence >= 3.0:
            regime = "high_volatility"
        elif average <= -1.5 and dec > adv * 1.5:
            regime = "weak"
        elif average >= 1.0 and adv > dec * 1.4:
            regime = "risk_on"
        elif divergence >= 1.0:
            regime = "structural"
        elif average < 0:
            regime = "defensive"
        else:
            regime = "structural"
        confidence = "high"
    return {
        "as_of": latest_trade_date,
        "regime": regime,
        "confidence": confidence,
        "indices": clean_indices,
        "breadth": clean_breadth,
        "index_divergence_pct": round(divergence, 2),
        "missing_evidence": missing,
    }


def _matches_current_news(
    name: str,
    news_items: Sequence[Dict[str, Any]],
    latest_trade_date: str | None,
) -> bool:
    if not name or not latest_trade_date:
        return False
    return any(
        _date(item.get("published_at")) == latest_trade_date
        and name in f"{item.get('title', '')} {item.get('content', '')}"
        for item in news_items
        if isinstance(item, dict)
    )


def board_identity(mode: Any, group_key: Any) -> str:
    """Return an unambiguous stable identity for a board within its mode."""
    mode_text = str(mode or "").strip()
    key_text = str(group_key or "").strip()
    if not mode_text or not key_text:
        return ""
    return f"{len(mode_text)}:{mode_text}{len(key_text)}:{key_text}"


def parse_board_identity(value: Any) -> Optional[tuple[str, str]]:
    if not isinstance(value, str) or not value:
        return None
    first_separator = value.find(":")
    if first_separator <= 0 or not value[:first_separator].isdigit():
        return None
    mode_length = int(value[:first_separator])
    mode_start = first_separator + 1
    mode_end = mode_start + mode_length
    if mode_end >= len(value):
        return None
    second_separator = value.find(":", mode_end)
    if second_separator <= mode_end or not value[mode_end:second_separator].isdigit():
        return None
    key_length = int(value[mode_end:second_separator])
    mode = value[mode_start:mode_end]
    key = value[second_separator + 1 :]
    if not (
        mode in {"major", "sub", "concept"}
        and len(key) == key_length
        and board_identity(mode, key) == value
    ):
        return None
    return mode, key


def is_board_identity(value: Any) -> bool:
    return parse_board_identity(value) is not None


def _candidate_board_id(candidate: Dict[str, Any]) -> str:
    mode_present = "mode" in candidate
    board_id_present = "board_id" in candidate
    group_key_present = "group_key" in candidate

    if mode_present:
        mode_value = candidate.get("mode")
        group_key_value = candidate.get("group_key")
        if not isinstance(mode_value, str) or not mode_value.strip():
            return ""
        if not isinstance(group_key_value, str) or not group_key_value.strip():
            return ""
        mode = mode_value.strip()
        group_key = group_key_value.strip()
        if mode not in {"major", "sub", "concept"}:
            return ""
        canonical = board_identity(mode, group_key)
        if board_id_present:
            explicit_value = candidate.get("board_id")
            if not isinstance(explicit_value, str) or explicit_value != canonical:
                return ""
        return canonical

    if board_id_present:
        explicit_value = candidate.get("board_id")
        parsed = parse_board_identity(explicit_value)
        if parsed is None:
            return ""
        if group_key_present:
            group_key_value = candidate.get("group_key")
            if (
                not isinstance(group_key_value, str)
                or not group_key_value
                or group_key_value != parsed[1]
            ):
                return ""
        return explicit_value

    if not group_key_present:
        return ""
    group_key_value = candidate.get("group_key")
    if not isinstance(group_key_value, str) or not group_key_value.strip():
        return ""
    return group_key_value.strip()


def _detail_for_candidate(
    candidate: Dict[str, Any], details: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    identity = _candidate_board_id(candidate)
    if not identity:
        return {}
    value = details.get(identity)
    return value if isinstance(value, dict) else {}


def board_evidence_is_current(
    candidate: Dict[str, Any], detail: Dict[str, Any], latest_trade_date: str
) -> bool:
    expected = _date(latest_trade_date)
    return bool(
        expected
        and _date(candidate.get("as_of")) == expected
        and _date(detail.get("as_of")) == expected
        and candidate.get("stale") is False
        and detail.get("stale") is False
    )


def select_board_candidates(
    rankings: Dict[str, Dict[str, List[Dict[str, Any]]]],
    news_items: Sequence[Dict[str, Any]],
    limit: int = 12,
    latest_trade_date: str | None = None,
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rankings, dict):
        return []
    for mode, mode_rows in rankings.items():
        if mode not in {"major", "sub", "concept"} or not isinstance(
            mode_rows, dict
        ):
            continue
        for rank_name in ("change_desc", "turnover_desc"):
            rows = mode_rows.get(rank_name, [])
            if not isinstance(rows, list):
                continue
            for rank, row in enumerate(rows[:5], start=1):
                if not isinstance(row, dict):
                    continue
                key_value = row.get("group_key") or row.get("name")
                if not isinstance(key_value, str):
                    continue
                key = key_value.strip()
                if not key:
                    continue
                identity = board_identity(mode, key)
                if not identity:
                    continue
                current = merged.setdefault(
                    identity,
                    dict(
                        row,
                        mode=mode,
                        group_key=key,
                        board_id=identity,
                        preliminary_score=0.0,
                    ),
                )
                current["preliminary_score"] += max(0.0, 6.0 - rank)
    for current in merged.values():
        if _matches_current_news(
            str(current.get("name", "")), news_items, latest_trade_date
        ):
            current["preliminary_score"] += 3.0
    return sorted(
        merged.values(),
        key=lambda row: row["preliminary_score"],
        reverse=True,
    )[:limit]


def continuity_score(
    group_key: str,
    history: Sequence[Dict[str, Any]],
    latest_trade_date: str | None = None,
) -> Dict[str, Any]:
    latest = _date(latest_trade_date)
    if not latest:
        return {"known": False, "score": 0.0, "sessions": 0, "hits": 0}
    latest_date = dt.date.fromisoformat(latest)
    if latest_date.weekday() >= 5:
        return {"known": False, "score": 0.0, "sessions": 0, "hits": 0}
    earliest_date = latest_date - dt.timedelta(days=30)

    by_date: Dict[str, Dict[str, Any]] = {}
    for row in history:
        if not isinstance(row, dict):
            continue
        raw_trade_date = row.get("trade_date")
        trade_date = _date(raw_trade_date)
        if not isinstance(raw_trade_date, str) or trade_date != raw_trade_date:
            continue
        observed_date = dt.date.fromisoformat(trade_date)
        if (
            observed_date.weekday() >= 5
            or observed_date < earliest_date
            or observed_date > latest_date
        ):
            continue
        by_date[trade_date] = row
    recent_rows = [by_date[key] for key in sorted(by_date)[-10:]]
    sessions = set(by_date)
    if len(sessions) < 3:
        return {
            "known": False,
            "score": 0.0,
            "sessions": len(sessions),
            "hits": 0,
        }
    hits = 0
    for row in recent_rows:
        identities = set()
        for field in ("top_change", "top_turnover"):
            values = row.get(field)
            if not isinstance(values, list):
                continue
            identities.update(
                value.strip()
                for value in values
                if isinstance(value, str) and value.strip()
            )
        if group_key in identities:
            hits += 1
    return {
        "known": hits >= 3,
        "score": round(min(20.0, hits / len(recent_rows) * 20.0), 2),
        "sessions": len(recent_rows),
        "hits": hits,
    }


def score_mainline_candidates(
    candidates: Sequence[Dict[str, Any]],
    details: Dict[str, Dict[str, Any]],
    news_items: Sequence[Dict[str, Any]],
    history: Sequence[Dict[str, Any]],
    latest_trade_date: str | None = None,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for rank, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        key = _candidate_board_id(candidate)
        detail = _detail_for_candidate(candidate, details)
        raw_items = detail.get("items", [])
        items = (
            [item for item in raw_items if isinstance(item, dict)]
            if isinstance(raw_items, list)
            else []
        )
        advancers = sum(
            1
            for item in items
            if (_finite_market_number(item.get("change_pct")) or 0.0) > 0
        )
        breadth = advancers / len(items) if items else 0.0
        continuity = continuity_score(
            key, history, latest_trade_date=latest_trade_date
        )
        board_change = _finite_market_number(candidate.get("change_pct"))
        turnover = _finite_market_number(candidate.get("turnover_yuan"))
        components = {
            "same_day_strength": (
                round(max(0.0, 21.0 - rank), 2)
                if board_change is not None
                and board_change > 0
                and advancers > 0
                else 0.0
            ),
            "liquidity": round(
                min(15.0, max(0.0, turnover or 0.0) / 1e10),
                2,
            ),
            "breadth": round(breadth * 15.0, 2),
            "continuity": continuity["score"],
            "catalyst_logic": (
                15.0
                if _matches_current_news(
                    str(candidate.get("name", "")),
                    news_items,
                    latest_trade_date,
                )
                else 0.0
            ),
        }
        result.append(
            {
                **candidate,
                "score_components": components,
                "continuity": continuity,
                "catalyst_verified": components["catalyst_logic"] > 0,
                "contradictions": [],
                "base_score": round(sum(components.values()), 2),
            }
        )
    return result


def _leader(
    code_row: Dict[str, Any], role: str, reason: str, confidence: str
) -> Dict[str, Any]:
    evidence_ids = code_row.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        evidence_ids = []
    return {
        "code": str(code_row.get("code", "")),
        "name": str(code_row.get("name", "")),
        "role": role,
        "role_evidence": reason,
        "evidence_ids": list(evidence_ids),
        "confidence": confidence,
        "risk": "角色仅由当前市场证据识别，不代表公司长期质地或确定收益。",
    }


def classify_leader_roles(
    items: Sequence[Dict[str, Any]], held_codes: set[str]
) -> List[Dict[str, Any]]:
    clean_items = (
        [row for row in items if isinstance(row, dict)]
        if isinstance(items, (list, tuple))
        else []
    )
    positive = [
        row
        for row in clean_items
        if (_finite_market_number(row.get("change_pct")) or 0.0) > 0
    ]
    leaders: List[Dict[str, Any]] = []
    limit_rows = [
        row
        for row in positive
        if row.get("limit_up") is True
        and (_finite_market_number(row.get("turnover_yuan")) or 0.0) > 0
    ]
    if limit_rows:
        row = max(
            limit_rows,
            key=lambda value: _finite_market_number(value.get("turnover_yuan")) or 0.0,
        )
        leaders.append(
            _leader(
                row,
                "emotion_leader",
                "当日涨停且在涨停成分中成交额最高",
                "high",
            )
        )
    liquidity_rows = [
        row
        for row in positive
        if (_finite_market_number(row.get("turnover_yuan")) or 0.0) > 0
    ]
    if liquidity_rows:
        row = max(
            liquidity_rows,
            key=lambda value: _finite_market_number(value.get("turnover_yuan")) or 0.0,
        )
        leaders.append(
            _leader(
                row,
                "liquidity_anchor",
                "板块内正收益成分成交额最高",
                "high",
            )
        )
    trend_rows = [
        value
        for value in positive
        if _finite_market_number(value.get("ret20")) is not None
    ]
    if trend_rows:
        row = max(
            trend_rows,
            key=lambda value: _finite_market_number(value.get("ret20")) or 0.0,
        )
        leaders.append(
            _leader(
                row,
                "trend_leader",
                "板块内正收益成分20日收益最高",
                "medium",
            )
        )
    market_cap_rows = [
        value
        for value in positive
        if (_finite_market_number(value.get("market_cap_yuan")) or 0.0) > 0
    ]
    if market_cap_rows:
        row = max(
            market_cap_rows,
            key=lambda value: _finite_market_number(value.get("market_cap_yuan")) or 0.0,
        )
        leaders.append(
            _leader(
                row,
                "industry_representative",
                "板块内正收益成分市值最高，仅代表市值维度",
                "medium",
            )
        )
    for row in clean_items:
        if str(row.get("code", "")) in held_codes:
            leaders.append(
                _leader(
                    row,
                    "held_exposure",
                    "当前账户持仓属于该板块成分",
                    "high",
                )
            )
    unique: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in leaders:
        unique[(row["code"], row["role"])] = row
    return list(unique.values())


def finalize_mainlines(
    candidates: Sequence[Dict[str, Any]],
    details: Dict[str, Dict[str, Any]],
    held_codes: set[str],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        detail = _detail_for_candidate(candidate, details)
        raw_items = detail.get("items")
        items = (
            [row for row in raw_items if isinstance(row, dict)]
            if isinstance(raw_items, list)
            else []
        )
        leaders = classify_leader_roles(items, held_codes)
        valid_structural_leaders = [
            row
            for row in leaders
            if row.get("role") != "held_exposure"
            and str(row.get("code") or "").strip()
            and str(row.get("name") or "").strip()
            and isinstance(row.get("evidence_ids"), list)
            and any(
                isinstance(evidence_id, str) and evidence_id.strip()
                for evidence_id in row["evidence_ids"]
            )
        ]
        structural_roles = {row["role"] for row in valid_structural_leaders}
        leader_score = min(15.0, len(structural_roles) * 5.0)
        total = round(
            (_finite_market_number(candidate.get("base_score")) or 0.0)
            + leader_score,
            2,
        )
        continuity = candidate.get("continuity")
        if not isinstance(continuity, dict):
            continuity = {}
        continuity_known = continuity.get("known") is True
        score_components = candidate.get("score_components")
        if not isinstance(score_components, dict):
            score_components = {}
        same_day_strength = (
            _finite_market_number(score_components.get("same_day_strength")) or 0.0
        )
        breadth_score = (
            _finite_market_number(score_components.get("breadth")) or 0.0
        )
        current_structure = breadth_score > 0 or bool(valid_structural_leaders)
        if not items:
            classification = "insufficient_evidence"
        elif (
            total >= 70.0
            and continuity_known
            and same_day_strength > 0
            and current_structure
            and not candidate.get("critical_contradiction")
        ):
            classification = "confirmed_mainline"
        elif (
            total >= 55.0
            and candidate.get("catalyst_verified") is True
            and same_day_strength > 0
            and current_structure
        ):
            classification = "emerging_mainline"
        elif same_day_strength >= 15.0 and current_structure:
            classification = "today_hotspot"
        elif (
            continuity_known
            and (_finite_market_number(score_components.get("continuity")) or 0.0)
            >= 10.0
        ):
            classification = "recent_mainline"
        else:
            classification = "one_day_noise"
        result.append(
            {
                **candidate,
                "score_components": {
                    **score_components,
                    "leader_structure": leader_score,
                },
                "score": total,
                "classification": classification,
                "leaders": leaders,
                "constituent_codes": [
                    str(row.get("code", ""))
                    for row in items
                    if row.get("code")
                ],
                "confidence": (
                    "high"
                    if classification == "confirmed_mainline"
                    else "medium"
                    if items
                    else "low"
                ),
            }
        )
    return sorted(result, key=lambda row: row["score"], reverse=True)


THEME_LOGIC_RULES = (
    (
        ("AI", "算力", "半导体", "光模块", "PCB"),
        "数字化和算力效率需求",
        "设备/材料→算力基础设施→应用",
        "订单、出货量、利用率与毛利率",
    ),
    (
        ("机器人", "具身智能"),
        "自动化、效率提升与劳动力结构变化",
        "核心零部件→整机→场景应用",
        "订单验证、量产进度、单位成本与客户复购",
    ),
    (
        ("航天", "军工", "卫星"),
        "安全、通信和空间基础设施需求",
        "材料/元件→装备制造→运营服务",
        "型号进度、订单、交付节奏与产能利用率",
    ),
    (
        ("汽车", "新能源车", "热管理"),
        "交通电动化与能效需求",
        "材料/零部件→整车→售后与能源生态",
        "销量、单车价值量、份额与价格竞争",
    ),
    (
        ("医药", "医疗", "DRG", "DIP"),
        "医疗可及性、支付效率和老龄化需求",
        "研发/器械→医疗服务→支付体系",
        "获批、入院、渗透率、价格与现金回款",
    ),
    (
        ("风电", "光伏", "储能", "电力设备"),
        "能源安全、低碳转型和电网调节需求",
        "材料/设备→发电/储能→电网与终端",
        "招标、装机、利用小时、价格与回款",
    ),
)


def _theme_logic(name: str) -> Dict[str, str]:
    for keywords, need, chain, earnings in THEME_LOGIC_RULES:
        if any(keyword in name for keyword in keywords):
            return {
                "social_or_industrial_need": need,
                "value_chain_transmission": chain,
                "earnings_transmission": earnings,
            }
    return {
        "social_or_industrial_need": "待验证：需要行业、政策或终端需求证据",
        "value_chain_transmission": "待验证：需要确认上下游和利润池位置",
        "earnings_transmission": "待验证：需要确认量、价、利用率、订单或现金流渠道",
    }


def build_fact_logic_chain(
    line: Dict[str, Any], evidence_index: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    raw_ids = line.get("evidence_ids", [])
    raw_ids = raw_ids if isinstance(raw_ids, list) else []
    ids = {
        value
        for value in raw_ids
        if isinstance(value, str) and value.strip()
    }
    matched = [
        row
        for row in evidence_index
        if isinstance(row, dict)
        and isinstance(row.get("evidence_id"), str)
        and row.get("evidence_id") in ids
    ]
    accepted = [
        row
        for row in matched
        if row.get("freshness") in {"current-session", "recent"}
        and row.get("reliability") in {"medium", "high"}
    ]
    rejected = [row for row in matched if row not in accepted]
    current = [
        row
        for row in accepted
        if row.get("freshness") == "current-session" and row.get("statement")
    ]
    facts = [
        (
            str(row["statement"])
            if row.get("freshness") == "current-session"
            else f"近期事实：{row['statement']}"
        )
        for row in accepted
        if row.get("statement")
    ]
    logic = _theme_logic(str(line.get("name", "")))
    unknowns = [
        value for value in logic.values() if value.startswith("待验证")
    ]
    unknowns.extend(
        "证据未通过门禁："
        f"{row.get('evidence_id', 'unknown')}（freshness="
        f"{row.get('freshness', 'unknown')}，reliability="
        f"{row.get('reliability', 'unknown')}）"
        for row in rejected
    )
    if not current:
        unknowns.append("当日证据不足，价格与催化状态待验证")
        driver = "当日证据不足：价格与催化均待验证"
    elif line.get("catalyst_verified"):
        driver = "资金与催化共振"
    else:
        driver = "价格驱动已观察，催化仍待验证"
    return {
        "facts": facts,
        "driver": driver,
        **logic,
        "price_confirmation": (
            f"分类={line.get('classification', 'insufficient_evidence')}，"
            f"得分={line.get('score', 0)}"
            if current
            else "当日证据不足：价格确认待验证"
        ),
        "contradictions": (
            list(line.get("contradictions", []))
            if isinstance(line.get("contradictions", []), list)
            else []
        ),
        "unknowns": unknowns,
        "continuation_conditions": [
            "板块广度不显著收缩",
            "成交与龙头结构保持",
            "催化未被事实证伪",
        ],
        "invalidation_conditions": [
            "龙头与板块明显背离",
            "上涨广度快速收窄",
            "核心催化被证伪",
        ],
        "labels": {"facts": "事实", "logic": "推断", "unknowns": "待验证"},
    }


def build_market_outlook(
    market_snapshot: Dict[str, Any], mainlines: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    confirmed = [
        str(row["name"])
        for row in mainlines
        if row.get("classification") == "confirmed_mainline"
        and row.get("name")
    ]
    focus = "、".join(confirmed[:3]) or "尚无确认主线"
    regime = str(market_snapshot.get("regime", "insufficient_evidence"))
    snapshot_confidence = str(market_snapshot.get("confidence", "low"))
    evidence_is_insufficient = (
        snapshot_confidence == "low" or regime == "insufficient_evidence"
    )
    short_base_case = (
        "证据不足，先补齐指数、广度、成交与主线证据后再判断行情结构。"
        if evidence_is_insufficient
        else f"{regime}环境延续，重点验证{focus}的广度与龙头结构。"
    )
    medium_base_case = (
        "证据不足，先补齐市场与产业验证证据后再形成中期判断。"
        if evidence_is_insufficient
        else "产业需求与盈利传导需要订单、价格、利用率或业绩继续验证。"
    )
    return {
        "short_term": {
            "horizon": "1-5 trading days",
            "base_case": short_base_case,
            "stronger_case": "指数、广度和成交同步改善，主线龙头不背离。",
            "weaker_case": "指数反弹但广度/成交不确认，或主线快速轮动。",
            "key_variables": [
                "指数分化",
                "全市场广度",
                "总成交额",
                "主线成交与龙头",
            ],
            "portfolio_posture": (
                "按触发条件处理持仓，避免把候选热点当作确认主线追涨。"
            ),
            "invalidation": "市场数据过期、广度缺失或确认主线失效。",
            "confidence": (
                "low" if evidence_is_insufficient else snapshot_confidence
            ),
        },
        "medium_term": {
            "horizon": "1-3 months",
            "base_case": medium_base_case,
            "stronger_case": (
                "政策/需求事实转化为连续订单、量产、价格或利润改善。"
            ),
            "weaker_case": (
                "主题交易持续但基本面兑现缺失，估值与拥挤度风险上升。"
            ),
            "key_variables": [
                "产业订单",
                "价格与毛利",
                "产能利用率",
                "公司公告与财报",
            ],
            "portfolio_posture": (
                "中期仓位只对已验证产业链和公司证据提高信任。"
            ),
            "invalidation": "产业需求、盈利传导或公司竞争位置被事实证伪。",
            "confidence": (
                "low"
                if evidence_is_insufficient
                else "medium"
                if confirmed
                else "low"
            ),
        },
    }


def _by_code(
    rows: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return {
        str(row.get("code", "")): row
        for row in rows
        if isinstance(row, dict) and row.get("code")
    }


def build_portfolio_diagnosis(
    positions: Dict[str, Any],
    mainlines: Sequence[Dict[str, Any]],
    stock_scores: Sequence[Dict[str, Any]],
    actions: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    score_map = _by_code(stock_scores)
    eligible_classes = {
        "confirmed_mainline",
        "recent_mainline",
        "emerging_mainline",
    }
    eligible_lines = [
        line
        for line in mainlines
        if line.get("classification") in eligible_classes
    ]
    eligible_codes = {
        str(code)
        for line in eligible_lines
        for code in line.get("constituent_codes", [])
    }
    industry_weights: Dict[str, float] = {}
    mainline_weights: Dict[str, float] = {}
    mainline_positive_codes: Dict[str, set[str]] = {}
    single_stock_concentration: List[Dict[str, Any]] = []
    stock_exposure = 0.0
    off_mainline_exposure = 0.0
    total_assets = finite_number(positions.get("total_assets")) or 0.0
    incomplete_asset_coverage = (
        positions.get("cash_unreadable") is True
        or positions.get("total_assets_lower_bound") is True
    )
    visible_stock_value = sum(
        max(0.0, finite_number(holding.get("market_value")) or 0.0)
        for holding in positions.get("holdings", [])
        if isinstance(holding, dict)
    )
    visible_account_stock_value = finite_number(
        positions.get("visible_account_stock_value")
    )
    use_full_visible_account_denominator = (
        incomplete_asset_coverage
        and visible_account_stock_value is not None
        and visible_account_stock_value > 0
    )
    concentration_denominator = (
        visible_account_stock_value
        if use_full_visible_account_denominator
        else visible_stock_value
    )

    for holding in positions.get("holdings", []):
        if not isinstance(holding, dict):
            continue
        code = str(holding.get("code", ""))
        score = score_map.get(code, {})
        score_weight = finite_number(score.get("current_weight"))
        if incomplete_asset_coverage:
            market_value = finite_number(holding.get("market_value")) or 0.0
            weight = (
                max(0.0, market_value) / concentration_denominator
                if concentration_denominator > 0
                else 0.0
            )
        elif "current_weight" in score and score_weight is not None:
            weight = max(0.0, score_weight)
        elif total_assets > 0:
            market_value = finite_number(holding.get("market_value")) or 0.0
            weight = max(0.0, market_value) / total_assets
        else:
            weight = 0.0
        stock_exposure += weight
        single_stock_concentration.append(
            {
                "code": code,
                "name": str(holding.get("name") or score.get("name") or ""),
                "weight": round(weight, 4),
            }
        )
        industry = str(score.get("industry") or "未知")
        industry_weights[industry] = industry_weights.get(industry, 0.0) + weight
        if code not in eligible_codes:
            off_mainline_exposure += weight
        for line in eligible_lines:
            if code not in {
                str(value) for value in line.get("constituent_codes", [])
            }:
                continue
            name = str(line.get("name") or "未命名主线")
            mainline_weights[name] = mainline_weights.get(name, 0.0) + weight
            if weight > 0:
                mainline_positive_codes.setdefault(name, set()).add(code)

    single_stock_concentration.sort(
        key=lambda row: row["weight"], reverse=True
    )
    mainline_alignment = [
        {"mainline": key, "weight": round(value, 4)}
        for key, value in sorted(
            mainline_weights.items(), key=lambda item: item[1], reverse=True
        )
    ]
    priorities = sorted(
        actions,
        key=lambda row: {
            "exit": 0,
            "reduce": 1,
            "add_only_if_triggered": 2,
            "hold": 3,
            "watch": 4,
        }.get(row.get("action"), 5),
    )[:3]
    priority_actions = {row.get("action") for row in priorities}
    if priority_actions & {"exit", "reduce"}:
        portfolio_posture = "risk_reduction_first"
    elif "add_only_if_triggered" in priority_actions:
        portfolio_posture = "conditional_add_only"
    else:
        portfolio_posture = "hold_and_verify"

    return {
        "stock_exposure": (
            None if incomplete_asset_coverage else round(stock_exposure, 4)
        ),
        "cash_weight": (
            round(max(0.0, 1.0 - stock_exposure), 4)
            if total_assets > 0 and not incomplete_asset_coverage
            else None
        ),
        **(
            {
                "asset_coverage_note": (
                    (
                        "现金/总资产未知；单股、行业、主题及主线权重按完整可见账户"
                        "持仓市值归一化，不代表目标子集占完整账户的全部仓位。"
                    )
                    if use_full_visible_account_denominator
                    else (
                        "现金/总资产未知；单股、行业、主题及主线权重仅按可见持仓市值"
                        "归一化，不代表完整账户资产配置。"
                    )
                )
            }
            if incomplete_asset_coverage
            else {}
        ),
        "single_stock_concentration": single_stock_concentration,
        "industry_concentration": [
            {"industry": key, "weight": round(value, 4)}
            for key, value in sorted(
                industry_weights.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ],
        "theme_concentration": [
            {"theme": row["mainline"], "weight": row["weight"]}
            for row in mainline_alignment
        ],
        "mainline_alignment": mainline_alignment,
        "off_mainline_exposure": round(off_mainline_exposure, 4),
        "counter_regime_exposure": None,
        "counter_regime_exposure_note": (
            "证据不足：当前接口未提供可映射到持仓的市场风格暴露。"
        ),
        "shared_catalyst_risks": [
            key
            for key, value in mainline_weights.items()
            if value >= 0.3
            and len(mainline_positive_codes.get(key, set())) >= 2
        ],
        "portfolio_posture": portfolio_posture,
        "top_action_priorities": priorities,
    }


def build_holding_analyses(
    positions: Dict[str, Any],
    mainlines: Sequence[Dict[str, Any]],
    stock_scores: Sequence[Dict[str, Any]],
    panorama: Sequence[Dict[str, Any]],
    actions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    score_map = _by_code(stock_scores)
    panorama_map = _by_code(panorama)
    action_map = _by_code(actions)
    allowed_actions = {
        "hold",
        "reduce",
        "exit",
        "watch",
        "add_only_if_triggered",
    }
    result: List[Dict[str, Any]] = []

    for holding in positions.get("holdings", []):
        if not isinstance(holding, dict):
            continue
        code = str(holding.get("code", ""))
        score = score_map.get(code, {})
        panorama_row = panorama_map.get(code, {})
        action = action_map.get(code, {})
        action_name = str(action.get("action") or "watch")
        if action_name not in allowed_actions:
            action_name = "watch"
        current_weight = finite_number(score.get("current_weight")) or 0.0
        if action_name == "exit":
            account_role = "error_position"
        elif action_name == "watch":
            account_role = "watch"
        elif action_name == "add_only_if_triggered":
            account_role = "trade"
        elif current_weight >= 0.12:
            account_role = "core"
        else:
            account_role = "satellite"

        links: List[Dict[str, Any]] = []
        industry = str(score.get("industry") or "")
        for line in mainlines:
            constituent_codes = {
                str(value) for value in line.get("constituent_codes", [])
            }
            is_constituent = code in constituent_codes
            label_only = bool(
                industry
                and industry == str(line.get("name") or "")
                and not is_constituent
            )
            if not is_constituent and not label_only:
                continue
            leader_roles = [
                str(leader.get("role"))
                for leader in line.get("leaders", [])
                if str(leader.get("code", "")) == code
                and leader.get("role")
                and leader.get("role") != "held_exposure"
            ]
            relationship = (
                "leader"
                if leader_roles
                else "follower_or_constituent"
                if is_constituent
                else "label_only"
            )
            links.append(
                {
                    "name": line.get("name", ""),
                    "classification": line.get(
                        "classification", "insufficient_evidence"
                    ),
                    "link_type": "constituent" if is_constituent else "label",
                    "relationship": relationship,
                    "leader_roles": leader_roles,
                }
            )

        data_confidence = str(score.get("data_confidence") or "low")
        evidence_gaps: List[str] = []
        if data_confidence != "high":
            evidence_gaps.append(
                f"data_confidence={data_confidence}，需补齐行情、资金或事件证据。"
            )
        if not panorama_row:
            evidence_gaps.append(
                "industry_panorama 缺失，需补齐细分行业及上下游证据。"
            )
        else:
            required_panorama_fields = (
                "segment_focus",
                "value_chain_position",
                "upstream_dependency_check",
                "downstream_customer_check",
                "industry_influence_question",
                "scarce_capability_check",
            )
            for field in required_panorama_fields:
                if not panorama_row.get(field):
                    evidence_gaps.append(
                        f"industry_panorama.{field} 缺失，需补齐对应证据。"
                    )

        factor_scores = score.get("scores", {})
        if not isinstance(factor_scores, dict):
            factor_scores = {}
        total_score = finite_number(factor_scores.get("total_score")) or 0.0
        target_weight = (
            0.0
            if action_name == "watch"
            else finite_number(action.get("target_weight")) or 0.0
        )
        result.append(
            {
                "code": code,
                "name": holding.get("name", ""),
                "account_role": account_role,
                "industry_panorama": panorama_row,
                "mainline_links": links,
                "factor_evidence": {
                    "total_score": factor_scores.get("total_score"),
                    "trend_score": factor_scores.get("trend_score"),
                    "macd_score": factor_scores.get("macd_score"),
                    "fund_flow_score": factor_scores.get("fund_flow_score"),
                    "sector_score": factor_scores.get("sector_score"),
                    "event_score": factor_scores.get("event_score"),
                    "score_imputations": factor_scores.get(
                        "score_imputations", {}
                    ),
                    "raw": factor_scores.get("raw", {}),
                },
                "bull_evidence": (
                    [f"综合评分 {total_score:.1f}"]
                    if total_score >= 55
                    else []
                ),
                "bear_evidence": (
                    [f"综合评分 {total_score:.1f}"]
                    if total_score < 55
                    else []
                ),
                "thesis_status": (
                    "supported" if total_score >= 55 else "challenged"
                ),
                "data_confidence": data_confidence,
                "evidence_gaps": evidence_gaps,
                "action": action_name,
                "priority": {
                    "exit": 1,
                    "reduce": 2,
                    "add_only_if_triggered": 3,
                    "hold": 4,
                    "watch": 5,
                }[action_name],
                "target_weight": target_weight,
                "reason": action.get("reason", "证据不足，保持观察"),
                "trigger": action.get("trigger", "补齐关键数据后复核"),
                "invalidation": action.get(
                    "invalidation", "关键数据持续缺失"
                ),
                "risk_note": action.get(
                    "risk_note", "条件化研究结论，不自动下单。"
                ),
                "evidence_ids": list(score.get("evidence_ids", [])),
            }
        )
    return result
