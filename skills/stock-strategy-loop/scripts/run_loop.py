#!/usr/bin/env python3
"""Run a local A-share holding strategy loop.

This script handles deterministic work: locating screenshots, validating a
positions JSON produced by Codex vision, fetching market data, scoring current
holdings, running a no-lookahead backtest, trying bounded parameter candidates,
and writing Markdown/JSON outputs under .stock-loop/.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import datetime as dt
import json
import math
import os
import re
import stat
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from market_context import (
    board_evidence_is_current,
    board_identity,
    build_fact_logic_chain,
    build_holding_analyses,
    build_market_outlook,
    build_market_snapshot,
    build_portfolio_diagnosis,
    finalize_mainlines,
    finite_number,
    is_board_identity,
    make_evidence,
    score_mainline_candidates,
    select_board_candidates,
)
from reporting import render_report, validate_signal_v2


DEFAULT_A_SHARE_SKILL = Path(
    os.environ.get(
        "A_SHARE_SKILL_DIR",
        str(Path.home() / ".codex" / "skills" / "a-share-data"),
    )
)
DEFAULT_LOOP_DIR = ".stock-loop"
SCREENSHOT_RE = re.compile(
    r"(?P<date>20\d{2}[-_]?\d{2}[-_]?\d{2})(?:[-_](?P<h>\d{2})[-_](?P<m>\d{2})[-_](?P<s>\d{2}))?",
    re.IGNORECASE,
)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MIN_BREADTH_SAMPLE_SIZE = 1000
MIN_TURNOVER_COVERAGE_RATIO = 0.90
SOURCE_STALE_UNSET = object()
TRANSACTION_JOURNAL_NAME = "persistence_transaction.json"


def require_requests() -> Any:
    """Load the network fallback dependency only when a fallback is used."""
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "missing optional dependency: install requests>=2.31,<3 to use network fallbacks"
        ) from exc
    return requests


DEFAULT_PARAMS: Dict[str, Any] = {
    "version": 1,
    "ma_short": 20,
    "ma_long": 60,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "weights": {
        "trend": 0.42,
        "macd": 0.24,
        "fund_flow": 0.16,
        "sector": 0.10,
        "event": 0.08,
    },
    "entry_score": 68.0,
    "hold_score": 55.0,
    "reduce_score": 45.0,
    "stop_loss_pct": -8.0,
    "take_profit_pct": 18.0,
    "trailing_profit_pct": 10.0,
    "max_holdings": 8,
    "max_single_weight": 0.15,
    "roundtrip_cost_bps": 45,
    "rebalance_cost_bps": 22.5,
}

DANGINVEST_SUMMARY_URL = "https://dang-invest.com/api/market/boards/summary"
DANGINVEST_DETAIL_URL = "https://dang-invest.com/api/market/boards/detail"
DANGINVEST_NEWS_URL = "https://dang-invest.com/api/market/news"

K_CODE = "\u4ee3\u7801"
K_NAME = "\u540d\u79f0"
K_PRICE = "\u6700\u65b0\u4ef7"
K_CHANGE_PCT = "\u6da8\u8dcc\u5e45(%)"
K_PREV_CLOSE = "\u6628\u6536"
K_MAIN_AMOUNT = "\u4e3b\u529b\u51c0\u989d"
K_INDUSTRY = "\u884c\u4e1a"
K_DATA_SOURCE = "\u6570\u636e\u6e90"
K_DATE = "\u65e5\u671f"
K_CLOSE = "\u6536\u76d8\u4ef7"
K_PCT_CHG = "\u6da8\u8dcc\u5e45"
K_MAIN_NET = "\u4e3b\u529b\u51c0\u6d41\u5165-\u51c0\u989d"
K_MAIN_RATIO = "\u4e3b\u529b\u51c0\u6d41\u5165-\u51c0\u5360\u6bd4"
K_SUPER_NET = "\u8d85\u5927\u5355\u51c0\u6d41\u5165-\u51c0\u989d"
K_BIG_NET = "\u5927\u5355\u51c0\u6d41\u5165-\u51c0\u989d"
K_TITLE = "\u65b0\u95fb\u6807\u9898"
K_CONTENT = "\u65b0\u95fb\u5185\u5bb9"
K_PUBLISHED_AT = "\u53d1\u5e03\u65f6\u95f4"
K_SOURCE = "\u6587\u7ae0\u6765\u6e90"
K_NET_PROFIT_YOY = "\u51c0\u5229\u6da6-\u540c\u6bd4\u589e\u957f"
K_PERF_CHANGE_PCT = "\u4e1a\u7ee9\u53d8\u52a8\u5e45\u5ea6"


@dataclass
class StockData:
    code: str
    name: str
    history: List[Dict[str, Any]]
    quote: Dict[str, Any]
    industry: str = ""
    fund_flow: List[Dict[str, Any]] | None = None
    events: Dict[str, Any] | None = None


@dataclass
class CollectedData:
    stock_data: Dict[str, StockData]
    board_summaries: Dict[str, Any]
    board_rankings: Dict[str, Dict[str, List[Dict[str, Any]]]]
    board_details: Dict[str, Dict[str, Any]]
    indices: List[Dict[str, Any]]
    breadth: Dict[str, Any]
    market_news: Dict[str, Any]
    latest_trade_date: str
    errors: List[str]


def now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return default
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "-", "--", "None", "nan"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def normalize_code(code: Any) -> str:
    digits = re.sub(r"\D", "", str(code or ""))
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6) if digits else ""


def parse_target_codes(value: str) -> List[str]:
    tokens = [token for token in re.split(r"[，,\s]+", str(value or "")) if token]
    codes: List[str] = []
    for token in tokens:
        if len(re.sub(r"\D", "", token)) != 6:
            raise ValueError(f"invalid A-share code: {token}")
        code = normalize_code(token)
        if len(code) != 6:
            raise ValueError(f"invalid A-share code: {token}")
        if code not in codes:
            codes.append(code)
    if not codes:
        raise ValueError("at least one six-digit A-share code is required")
    return codes


INDUSTRY_PANORAMA_RULES: List[Tuple[Tuple[str, ...], str, str, str, str]] = [
    (
        ("半导体", "芯片", "集成电路", "电子元件", "光刻", "封测", "PCB"),
        "半导体/电子产业链",
        "上游材料/设备到中游制造/封测之间，需按公司主营再细分",
        "重点看客户认证、工艺良率、国产替代、周期库存和是否卡住关键环节",
        "像给电子城堡打造砖块、工具或地基，真正值钱的是别人短期造不出的那一环",
    ),
    (
        ("软件", "信息", "云", "AI", "人工智能", "互联网", "数据", "传媒", "游戏"),
        "数字经济/软件应用",
        "多为下游应用或平台基础设施，需区分工具、平台、内容和数据入口",
        "重点看用户粘性、数据闭环、付费能力、交付成本和AI是否削弱原有功能价值",
        "像一座集市或魔法书库，护城河来自人流、规则、数据和离开它的成本",
    ),
    (
        ("锂", "稀土", "有色", "煤炭", "石油", "钢铁", "化工", "材料", "矿"),
        "资源/原材料",
        "通常偏上游，利润受资源价格、供需周期和成本曲线影响",
        "重点看资源品位、产能释放、成本位置、下游需求和价格弹性",
        "像水源或粮仓，水价涨时很舒服，但丰水期和新水源会改变议价权",
    ),
    (
        ("电池", "光伏", "风电", "储能", "电力设备", "新能源", "充电"),
        "新能源设备/材料",
        "多处在上游材料、中游制造或设备环节，需拆到具体产品",
        "重点看技术路线、单位成本、产能过剩、客户结构和政策/装机周期",
        "像给新大陆铺电网和造马车，赛道大不等于每个零件商都能赚钱",
    ),
    (
        ("汽车", "整车", "家电", "消费电子", "食品", "饮料", "服装", "零售"),
        "终端消费/品牌制造",
        "通常偏下游，靠品牌、渠道、产品力和需求周期赚钱",
        "重点看需求弹性、库存、渠道议价、品牌心智和新品成功率",
        "像街口的店铺，位置和招牌重要，但最终要看顾客愿不愿意反复回来",
    ),
    (
        ("医药", "医疗", "创新药", "器械", "CRO", "生物", "疫苗"),
        "医药医疗",
        "覆盖研发上游、制造中游和医院/患者下游，需按产品管线拆分",
        "重点看临床进度、审批、集采、医保、医生/患者采用和商业化兑现",
        "像炼金实验室到药房的长路，魔法配方重要，但通关许可和卖出去同样重要",
    ),
    (
        ("银行", "保险", "证券", "金融"),
        "金融服务",
        "属于资金流通基础设施，不宜机械套上中下游",
        "重点看资产质量、利差/费率、资本充足、风险偏好和宏观信用周期",
        "像城市里的水渠和账房，水流顺畅时大家都方便，坏账堵住时风险会扩散",
    ),
    (
        ("物流", "港口", "机场", "铁路", "公路", "航运", "交通"),
        "交通物流基础设施",
        "通常是产业链中游基础设施，连接供给和需求",
        "重点看吞吐量、价格机制、利用率、区域腹地和周期/油价影响",
        "像商路和渡口，货物流量决定热闹程度，收费权决定利润质量",
    ),
    (
        ("房地产", "建筑", "建材", "水泥", "家居", "装饰"),
        "地产建筑链",
        "从上游建材到中游施工再到下游销售/物业，周期属性较强",
        "重点看地产周期、订单回款、资产负债表、现金流和政策托底边界",
        "像盖房子的队伍，砖、工匠和售楼处都在一条链上，但谁收得到钱最关键",
    ),
    (
        ("军工", "航空", "航天", "船舶", "卫星"),
        "高端装备/军工",
        "多为中上游零部件、整机或系统集成，受订单和型号周期驱动",
        "重点看型号放量、定价机制、交付节奏、资质壁垒和供应链位置",
        "像王国的兵器工坊，订单节奏和关键零件地位比热闹故事更重要",
    ),
]


def infer_industry_panorama(industry: str, name: str = "") -> Dict[str, str]:
    text = f"{industry} {name}"
    for keywords, segment, chain_position, influence, analogy in INDUSTRY_PANORAMA_RULES:
        if any(keyword in text for keyword in keywords):
            return {
                "segment_focus": segment,
                "value_chain_position": chain_position,
                "industry_influence_question": influence,
                "learning_analogy": analogy,
            }
    if not industry:
        return {
            "segment_focus": "行业标签缺失，需先核验主营业务",
            "value_chain_position": "待核验",
            "industry_influence_question": "先确认公司收入结构、核心产品、客户和供应商，再判断行业影响",
            "learning_analogy": "像先拿到地图再出发：没有行业坐标时，不急着判断它在城堡的哪一层",
        }
    return {
        "segment_focus": f"{industry}（需继续拆到具体产品/服务）",
        "value_chain_position": "待核验：需结合主营产品判断上游/中游/下游",
        "industry_influence_question": "重点核验它控制的是成本、技术、渠道、品牌、产能、数据还是牌照",
        "learning_analogy": "像看一座城市里的店铺：先弄清它卖什么、向谁买、卖给谁，再判断它有多重要",
    }


def dependency_prompts(value_chain_position: str) -> Tuple[str, str]:
    if "上游" in value_chain_position:
        return (
            "核验核心资源、原材料、设备、技术或牌照来源及价格敏感性",
            "核验中游制造客户、采购集中度、替代材料和议价权",
        )
    if "下游" in value_chain_position:
        return (
            "核验产品、渠道、流量、品牌和关键供应商依赖",
            "核验终端客户需求、复购、渗透率、支付能力和场景持续性",
        )
    return (
        "核验原材料、设备、技术、数据、牌照和核心供应商依赖",
        "核验终端/企业/政府客户、渠道、认证、需求弹性和回款周期",
    )


def build_industry_panorama(stock_scores: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    panorama: List[Dict[str, str]] = []
    for row in stock_scores:
        industry = str(row.get("industry") or "")
        name = str(row.get("name") or "")
        hint = infer_industry_panorama(industry, name)
        upstream_check, downstream_check = dependency_prompts(
            hint["value_chain_position"]
        )
        panorama.append(
            {
                "code": str(row.get("code") or ""),
                "name": name,
                "industry": industry,
                "segment_focus": hint["segment_focus"],
                "value_chain_position": hint["value_chain_position"],
                "industry_influence_question": hint["industry_influence_question"],
                "scarce_capability_check": "核验是否有难复制的技术/工艺/数据/牌照/客户认证/成本曲线优势；没有证据则不要称为独角兽能力",
                "upstream_dependency_check": upstream_check,
                "downstream_customer_check": downstream_check,
                "learning_analogy": hint["learning_analogy"],
            }
        )
    return panorama


def market_prefix(code: str) -> str:
    return "sh" if code.startswith(("5", "6", "9")) else "sz"


def parse_screenshot_time(path: Path) -> Optional[dt.datetime]:
    match = SCREENSHOT_RE.search(path.name)
    if not match:
        return None
    raw_date = re.sub(r"[-_]", "", match.group("date"))
    hour = int(match.group("h") or "23")
    minute = int(match.group("m") or "59")
    second = int(match.group("s") or "59")
    try:
        return dt.datetime.strptime(raw_date, "%Y%m%d").replace(
            hour=hour, minute=minute, second=second
        )
    except ValueError:
        return None


def scan_screenshots(workspace: Path) -> Dict[str, Any]:
    screenshots: List[Dict[str, Any]] = []
    for path in workspace.iterdir():
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        shot_time = parse_screenshot_time(path)
        if not shot_time:
            continue
        screenshots.append(
            {
                "path": str(path.resolve()),
                "name": path.name,
                "shot_time": shot_time.isoformat(sep=" ") if shot_time else None,
                "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" "),
                "size": path.stat().st_size,
            }
        )
    screenshots.sort(key=lambda x: x.get("shot_time") or x["mtime"], reverse=True)
    latest_time = screenshots[0]["shot_time"] if screenshots else None
    latest_date = latest_time[:10] if latest_time else None
    latest = [
        x for x in screenshots if latest_date and str(x.get("shot_time") or x["mtime"]).startswith(latest_date)
    ]
    if not latest and screenshots:
        latest = [screenshots[0]]
    return {
        "generated_at": now_str(),
        "workspace": str(workspace.resolve()),
        "latest_snapshot_time": latest_time,
        "latest_snapshot_date": latest_date,
        "latest_screenshots": latest,
        "all_screenshots": screenshots,
    }


def validate_snapshot_freshness(positions: Dict[str, Any], manifest: Dict[str, Any]) -> List[str]:
    latest = str(manifest.get("latest_snapshot_time") or "")
    snapshot = str(positions.get("snapshot_time") or "")
    if latest and snapshot != latest:
        return [f"positions snapshot_time does not match latest screenshot: {latest}"]
    return []


def snapshot_run_id(snapshot_time: str) -> str:
    return re.sub(r"[^0-9]+", "-", str(snapshot_time or "")).strip("-") or "unknown"


def snapshot_time_order(left: str, right: str) -> int:
    try:
        left_value = dt.datetime.fromisoformat(left)
        right_value = dt.datetime.fromisoformat(right)
        return (left_value > right_value) - (left_value < right_value)
    except ValueError:
        return (left > right) - (left < right)


def holding_snapshot(positions: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    snapshot: Dict[str, Dict[str, Any]] = {}
    for holding in positions.get("holdings", []):
        if not isinstance(holding, dict):
            continue
        code = normalize_code(holding.get("code"))
        if len(code) != 6:
            continue
        snapshot[code] = {
            "code": code,
            "name": str(holding.get("name") or code),
            "shares": safe_float(holding.get("shares")),
        }
    return snapshot


def build_loop_review(previous_state: Optional[Dict[str, Any]], positions: Dict[str, Any]) -> Dict[str, Any]:
    current_time = str(positions.get("snapshot_time") or "")
    base = {
        "schema_version": 1,
        "current_snapshot_time": current_time,
        "holding_changes": [],
        "action_observations": [],
    }
    if not previous_state:
        return {**base, "status": "initial", "note": "首次快照，等待下一次新截图进行持仓变化复盘。"}

    previous_time = str(previous_state.get("snapshot_time") or "")
    base["previous_snapshot_time"] = previous_time
    order = snapshot_time_order(current_time, previous_time)
    if order == 0:
        return {**base, "status": "unchanged_snapshot", "note": "截图未更新，不重复采集数据或覆盖前一次分析。"}
    if order < 0:
        return {**base, "status": "stale_snapshot", "note": "当前截图早于已保存的闭环状态。"}

    previous_holdings = holding_snapshot(previous_state)
    current_holdings = holding_snapshot(positions)
    prior_actions = {
        normalize_code(action.get("code")): action
        for action in previous_state.get("portfolio_actions", [])
        if isinstance(action, dict) and len(normalize_code(action.get("code"))) == 6
    }
    holding_changes: List[Dict[str, Any]] = []
    action_observations: List[Dict[str, Any]] = []
    for code in sorted(set(previous_holdings) | set(current_holdings)):
        before = previous_holdings.get(code, {})
        after = current_holdings.get(code, {})
        previous_shares = safe_float(before.get("shares"))
        current_shares = safe_float(after.get("shares"))
        delta_shares = round(current_shares - previous_shares, 4)
        if previous_shares <= 0 < current_shares:
            kind = "new"
        elif current_shares <= 0 < previous_shares:
            kind = "closed"
        elif delta_shares > 0:
            kind = "increased"
        elif delta_shares < 0:
            kind = "decreased"
        else:
            kind = "unchanged"
        holding_changes.append(
            {
                "code": code,
                "name": after.get("name") or before.get("name") or code,
                "previous_shares": previous_shares,
                "current_shares": current_shares,
                "delta_shares": delta_shares,
                "kind": kind,
            }
        )
        prior_action = prior_actions.get(code)
        if prior_action:
            observation = (
                "decrease_observed"
                if delta_shares < 0
                else "increase_observed"
                if delta_shares > 0
                else "no_share_change_observed"
            )
            action_observations.append(
                {
                    "code": code,
                    "name": after.get("name") or before.get("name") or code,
                    "previous_action": prior_action.get("action"),
                    "observation": observation,
                }
            )
        else:
            action_observations.append(
                {
                    "code": code,
                    "name": after.get("name") or before.get("name") or code,
                    "previous_action": None,
                    "observation": "no_prior_action",
                }
            )
    return {
        **base,
        "status": "reconciled",
        "holding_changes": holding_changes,
        "action_observations": action_observations,
        "note": "仅记录截图中观察到的股份变化，不推断是否执行了前一次建议。",
    }


def build_loop_state(positions: Dict[str, Any], signal: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    accounts = positions.get("accounts", [])
    account = normalize_account_name(accounts[0].get("account")) if accounts else ""
    return {
        "schema_version": 1,
        "account": account,
        "snapshot_time": positions.get("snapshot_time"),
        "holdings": list(holding_snapshot(positions).values()),
        "portfolio_actions": signal.get("portfolio_actions", []),
        "data_coverage": signal.get("data_coverage", {}),
        "run_dir": str(run_dir.resolve()),
    }


def loop_paths(workspace: Path, loop_dir: str = DEFAULT_LOOP_DIR) -> Dict[str, Path]:
    root = workspace / loop_dir
    paths = {
        "root": root,
        "positions": root / "positions",
        "runs": root / "runs",
        "backtests": root / "backtests",
        "params": root / "params",
        "cache": root / "cache",
        "state": root / "state",
        "analyses": root / "analyses",
        "market_history": root / "market-history",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def fsync_directory(path: Path) -> None:
    """Best-effort directory fsync for durable rename/unlink metadata."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def lstat_path_entry(path: Path) -> Optional[os.stat_result]:
    """Return a directory entry without following links, or None if absent."""
    try:
        return os.lstat(str(path))
    except FileNotFoundError:
        return None


def is_reparse_point(status: os.stat_result) -> bool:
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(path))
        fsync_directory(path.parent)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_bytes(
        path,
        json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def write_json(path: Path, data: Any) -> None:
    atomic_write_json(path, data)


def allocate_unique_directory(parent: Path, base_name: str) -> Path:
    """Create and return a directory that did not exist before this call."""
    for attempt in range(1, 10001):
        name = base_name if attempt == 1 else f"{base_name}-{attempt}"
        candidate = parent / name
        try:
            candidate.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        except KeyboardInterrupt:
            cleanup_unique_output(candidate)
            raise
        return candidate
    raise OSError(f"unable to allocate unique analysis directory for {base_name}")


def publish_staged_directory(staging: Path, parent: Path, base_name: str) -> Path:
    """Atomically publish a complete staged directory under a collision-safe name."""
    for attempt in range(1, 10001):
        name = base_name if attempt == 1 else f"{base_name}-{attempt}"
        candidate = parent / name
        if lstat_path_entry(candidate) is not None:
            continue
        try:
            os.rename(str(staging), str(candidate))
        except KeyboardInterrupt:
            if lstat_path_entry(staging) is None and lstat_path_entry(candidate) is not None:
                cleanup_unique_output(candidate)
            raise
        except OSError:
            if lstat_path_entry(staging) is not None and lstat_path_entry(candidate) is not None:
                continue
            if lstat_path_entry(staging) is None and lstat_path_entry(candidate) is not None:
                cleanup_unique_output(candidate)
            raise
        try:
            fsync_directory(parent)
        except (OSError, KeyboardInterrupt):
            cleanup_unique_output(candidate)
            raise
        return candidate
    raise OSError(f"unable to publish unique analysis directory for {base_name}")


def cleanup_unique_output(path: Path) -> Optional[str]:
    """Best-effort cleanup limited to a directory allocated by this invocation."""
    try:
        cleanup_output_entry(path)
    except KeyboardInterrupt:
        try:
            cleanup_output_entry(path)
        except (OSError, KeyboardInterrupt) as exc:
            return str(exc)
    except OSError as exc:
        return str(exc)
    return None


def cleanup_output_entry(path: Path) -> None:
    """Remove an output entry without following symlinks or reparse points."""
    status = lstat_path_entry(path)
    if status is None:
        return
    if stat.S_ISLNK(status.st_mode):
        os.unlink(str(path))
        return
    if is_reparse_point(status):
        directory_flag = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0)
        if directory_flag and getattr(status, "st_file_attributes", 0) & directory_flag:
            os.rmdir(str(path))
        else:
            os.unlink(str(path))
        return
    if stat.S_ISDIR(status.st_mode):
        with os.scandir(str(path)) as entries:
            for entry in entries:
                cleanup_output_entry(Path(entry.path))
        os.rmdir(str(path))
        return
    os.unlink(str(path))


def normalize_account_name(value: Any) -> str:
    return str(value or "").strip().strip("*").strip()


def select_account_positions(data: Any, account: Optional[str]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    if not isinstance(data, dict):
        return None, ["positions must be a JSON object"]

    holdings = [item for item in data.get("holdings", []) if isinstance(item, dict)]
    account_rows = [item for item in data.get("accounts", []) if isinstance(item, dict)]
    holding_names = {normalize_account_name(item.get("account")) for item in holdings}
    metadata_names = {normalize_account_name(item.get("account")) for item in account_rows}
    named_holding_accounts = {name for name in holding_names if name}
    named_metadata_accounts = {name for name in metadata_names if name}
    unmarked_holdings = [
        item for item in holdings if not normalize_account_name(item.get("account"))
    ]

    if unmarked_holdings and (
        named_holding_accounts or len(named_metadata_accounts) > 1
    ):
        return None, [
            "ambiguous account assignment: holdings with an omitted account cannot be mixed with named holdings or multiple accounts"
        ]
    if unmarked_holdings and len(named_metadata_accounts) == 1:
        sole_account = next(iter(named_metadata_accounts))
        holdings = [{**item, "account": sole_account} for item in holdings]
        holding_names = {sole_account}

    names = sorted(name for name in holding_names | metadata_names if name)
    requested = normalize_account_name(account)

    if len(names) > 1 and not requested:
        return None, [f"multiple accounts detected ({', '.join(names)}); pass --account or run each account folder separately"]
    if requested and requested not in names:
        return None, [f"account not found: {requested}"]

    chosen = requested or (names[0] if names else "")
    if chosen:
        selected_holdings = [
            {**item, "account": chosen}
            for item in holdings
            if normalize_account_name(item.get("account")) == chosen
        ]
        selected_accounts = [
            {**item, "account": chosen}
            for item in account_rows
            if normalize_account_name(item.get("account")) == chosen
        ]
    else:
        selected_holdings = holdings
        selected_accounts = account_rows

    if len(names) > 1 and not selected_accounts:
        return None, [f"account assets missing for: {chosen}"]

    selected = {**data, "holdings": selected_holdings, "accounts": selected_accounts}
    if selected_accounts:
        assets = selected_accounts[0]
        selected.update(
            {
                "cash": assets.get("cash"),
                "stock_value": assets.get("stock_value"),
                "total_assets": assets.get("total_assets"),
            }
        )
        for field in ("cash_unreadable", "total_assets_lower_bound"):
            if field in assets:
                selected[field] = assets[field]
            else:
                selected.pop(field, None)
    return selected, []


def load_selected_positions(
    path: Path, account: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        return None, [f"positions JSON could not be read: {exc}"]
    return select_account_positions(data, account)


def build_target_positions(codes: List[str], source_positions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = source_positions or {}
    held_by_code = {
        normalize_code(holding.get("code")): holding
        for holding in source.get("holdings", [])
        if isinstance(holding, dict) and len(normalize_code(holding.get("code"))) == 6
    }
    source_accounts = [item for item in source.get("accounts", []) if isinstance(item, dict)]
    source_account = normalize_account_name(source_accounts[0].get("account")) if source_accounts else ""
    holdings: List[Dict[str, Any]] = []
    research_only_codes: List[str] = []
    for code in codes:
        held = held_by_code.get(code)
        if held:
            holdings.append({**held, "code": code})
            continue
        research_only_codes.append(code)
        holdings.append(
            {
                "account": "research",
                "code": code,
                "name": code,
                "shares": 0.0,
                "cost_price": 0.0,
                "last_price": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
            }
        )
    target_positions = {
        "snapshot_time": source.get("snapshot_time") or now_str(),
        "source_screenshots": source.get("source_screenshots", []),
        "accounts": source_accounts,
        "account": source_account or "research",
        "cash": safe_float(source.get("cash")),
        "stock_value": safe_float(source.get("stock_value")),
        "total_assets": safe_float(source.get("total_assets")),
        "holdings": holdings,
        "research_only_codes": research_only_codes,
        "analysis_mode": "target_research",
    }
    for field in ("cash_unreadable", "total_assets_lower_bound"):
        if type(source.get(field)) is bool:
            target_positions[field] = source[field]
    if (
        source.get("cash_unreadable") is True
        or source.get("total_assets_lower_bound") is True
    ):
        visible_account_stock_value = sum(
            number
            for holding in source.get("holdings", [])
            if isinstance(holding, dict)
            for number in [finite_number(holding.get("market_value"))]
            if number is not None and number > 0
        )
        if visible_account_stock_value > 0:
            target_positions["visible_account_stock_value"] = round(
                visible_account_stock_value, 2
            )
    return target_positions


def strict_position_number(value: Any) -> Optional[float]:
    if type(value) not in (int, float):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def validate_positions(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    holdings = data.get("holdings")
    if not isinstance(holdings, list) or not holdings:
        errors.append("positions.holdings must be a non-empty list")
        holdings = []

    normalized: List[Dict[str, Any]] = []
    required = [
        "code",
        "name",
        "shares",
        "cost_price",
        "last_price",
        "unrealized_pnl",
    ]
    for i, item in enumerate(holdings):
        if not isinstance(item, dict):
            errors.append(f"holding[{i}] must be an object")
            continue
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"holding[{i}] missing fields: {', '.join(missing)}")
        code = normalize_code(item.get("code"))
        if len(code) != 6:
            errors.append(f"holding[{i}] invalid code: {item.get('code')}")
        numbers = {
            field: strict_position_number(item.get(field))
            for field in (
                "shares",
                "cost_price",
                "last_price",
                "unrealized_pnl",
            )
        }
        for field, number in numbers.items():
            if field in item and number is None:
                errors.append(f"holding[{i}] {field} must be a finite number")
        shares = numbers["shares"]
        cost_price = numbers["cost_price"]
        last_price = numbers["last_price"]
        unrealized_pnl = numbers["unrealized_pnl"]
        if shares is not None and shares <= 0:
            errors.append(f"holding[{i}] shares must be positive")
        if cost_price is not None and cost_price < 0:
            errors.append(f"holding[{i}] cost_price must be nonnegative")
        if last_price is not None and last_price <= 0:
            errors.append(f"holding[{i}] last_price must be positive")

        market_value = strict_position_number(item.get("market_value"))
        can_derive_market_value = (
            "market_value" not in item
            and item.get("market_value_derived") is True
            and shares is not None
            and shares > 0
            and last_price is not None
            and last_price > 0
        )
        if market_value is None or market_value <= 0:
            if can_derive_market_value:
                market_value = round(shares * last_price, 2)
            else:
                if "market_value" not in item:
                    errors.append(f"holding[{i}] missing fields: market_value")
                else:
                    errors.append(
                        f"holding[{i}] market_value must be a finite positive number"
                    )
                market_value = None

        expected_mv = (
            round(shares * last_price, 2)
            if shares is not None and last_price is not None
            else None
        )
        if (
            expected_mv is not None
            and market_value is not None
            and abs(expected_mv - market_value)
            > max(2.0, market_value * 0.02)
        ):
            errors.append(
                f"holding[{i}] market_value mismatch: shares*last_price={expected_mv}, market_value={market_value}"
            )
        normalized.append(
            {
                **item,
                "code": code,
                "name": str(item.get("name", "")).strip(),
                "shares": shares if shares is not None else 0.0,
                "cost_price": cost_price if cost_price is not None else 0.0,
                "last_price": last_price if last_price is not None else 0.0,
                "market_value": market_value if market_value is not None else 0.0,
                "unrealized_pnl": (
                    unrealized_pnl if unrealized_pnl is not None else 0.0
                ),
            }
        )

    calculated_stock_value = round(
        sum(item["market_value"] for item in normalized), 2
    )
    stock_value = strict_position_number(data.get("stock_value"))
    if stock_value is None or stock_value <= 0:
        errors.append("positions.stock_value must be a finite positive number")
        stock_value = 0.0
    elif abs(calculated_stock_value - stock_value) > max(
        10.0, stock_value * 0.03
    ):
        errors.append(
            "stock_value mismatch: holdings sum="
            f"{calculated_stock_value}, stock_value={stock_value}"
        )

    cash_unreadable = data.get("cash_unreadable") is True
    cash = strict_position_number(data.get("cash"))
    if cash_unreadable:
        cash = 0.0
    elif cash is None or cash < 0:
        errors.append("positions.cash must be a finite nonnegative number")
        cash = 0.0

    total_assets_lower_bound = data.get("total_assets_lower_bound") is True
    total_assets = strict_position_number(data.get("total_assets"))
    if total_assets_lower_bound:
        total_assets = stock_value
    elif total_assets is None or total_assets <= 0:
        errors.append("positions.total_assets must be a finite positive number")
        total_assets = 0.0

    if (
        not total_assets_lower_bound
        and total_assets > 0
        and (
            (not cash_unreadable and abs((stock_value + cash) - total_assets)
             > max(10.0, total_assets * 0.03))
            or (cash_unreadable and total_assets + max(10.0, total_assets * 0.03) < stock_value)
        )
    ):
        errors.append(
            f"total_assets mismatch: stock_value+cash={round(stock_value + cash, 2)}, total_assets={total_assets}"
        )

    normalized_data = {
        **data,
        "holdings": normalized,
        "cash": cash,
        "stock_value": round(stock_value, 2),
        "total_assets": round(total_assets, 2),
        "validated_at": now_str(),
    }
    return not errors, errors, normalized_data


def run_subprocess_json(command: Sequence[str], timeout: int = 30) -> Tuple[Optional[Any], Optional[str]]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONUTF8", "1")
    try:
        proc = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s: {' '.join(command)}"
    except OSError as exc:
        return None, f"failed to execute {' '.join(command)}: {exc}"
    text = proc.stdout.strip()
    if not text:
        if proc.returncode != 0:
            return None, clean_error(proc.stderr or f"exit {proc.returncode}")
        return None, "empty stdout"
    start = min([i for i in [text.find("{"), text.find("[")] if i >= 0], default=-1)
    if start > 0:
        text = text[start:]
    try:
        parsed = json.loads(text)
        if proc.returncode != 0:
            return parsed, summarize_subprocess_failure(proc.returncode, proc.stderr, parsed)
        return parsed, None
    except json.JSONDecodeError as exc:
        if proc.returncode != 0:
            return None, clean_error(proc.stderr or proc.stdout or f"exit {proc.returncode}")
        return None, f"invalid JSON: {exc}"


def summarize_subprocess_failure(returncode: int, stderr: str, payload: Any) -> str:
    stderr_text = clean_error(stderr)
    payload_text = summarize_json_error_payload(payload)
    if stderr_text and payload_text:
        return f"{stderr_text}; {payload_text}"
    return stderr_text or payload_text or f"exit {returncode}"


def summarize_json_error_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        direct_error = payload.get("error") or payload.get("message")
        if direct_error:
            return str(direct_error)
        rows = payload.get("data")
        if isinstance(rows, list):
            row_errors = []
            total_errors = 0
            for row in rows:
                if not isinstance(row, dict) or not row.get("error"):
                    continue
                total_errors += 1
                if len(row_errors) < 3:
                    label = normalize_code(row.get("code")) or str(row.get("name") or "item")
                    row_errors.append(f"{label}: {truncate_error(row.get('error'))}")
            if row_errors:
                suffix = f"; +{total_errors - len(row_errors)} more" if total_errors > len(row_errors) else ""
                return f"row errors: {'; '.join(row_errors)}{suffix}"
    return ""


def truncate_error(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def clean_error(text: str) -> str:
    lines = []
    for line in str(text).splitlines():
        if "Pandas requires version" in line:
            continue
        if "from pandas.core" in line:
            continue
        if (
            re.match(r"^[A-Za-z]:\\Users\\", line.strip())
            and "site-packages" in line
        ):
            continue
        if line.strip():
            lines.append(line)
    return "\n".join(lines).strip()


def chunked(seq: Sequence[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


def fetch_quotes(codes: List[str], a_share_skill: Path) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    script = a_share_skill / "scripts" / "fetch_realtime.py"
    quotes: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    for group in chunked(codes, 10):
        data, err = run_subprocess_json(
            [sys.executable, str(script), "--multi-quote", ",".join(group), "--json"], timeout=35
        )
        if err:
            errors.append(f"quotes {','.join(group)}: {err}")
            fallback, fallback_err = fetch_quotes_direct(group)
            if fallback_err:
                errors.append(f"quotes direct {','.join(group)}: {fallback_err}")
            quotes.update(fallback)
            continue
        rows = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        for row in rows:
            code = normalize_code(first_present(row, [K_CODE, "code"]))
            if code:
                quotes[code] = row
    return quotes, errors


def fetch_quotes_direct(codes: List[str]) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    secids = []
    for code in codes:
        market = "1" if code.startswith(("5", "6", "9")) else "0"
        secids.append(f"{market}.{code}")
    fields = "f12,f14,f2,f3,f4,f5,f6,f7,f8,f15,f16,f17,f18,f20,f21,f62,f100"
    params = urllib.parse.urlencode(
        {
            "fltt": "2",
            "invt": "2",
            "fields": fields,
            "secids": ",".join(secids),
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
    )
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?{params}"
    try:
        session = require_requests().Session()
        session.trust_env = False
        response = session.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {}, str(exc)
    rows = payload.get("data", {}).get("diff", [])
    quotes = {}
    for row in rows:
        code = normalize_code(row.get("f12"))
        if code:
            quotes[code] = {
                K_CODE: code,
                K_NAME: row.get("f14"),
                K_PRICE: row.get("f2"),
                K_CHANGE_PCT: row.get("f3"),
                "今开": row.get("f17"),
                "最高": row.get("f15"),
                "最低": row.get("f16"),
                K_PREV_CLOSE: row.get("f18"),
                "成交量": row.get("f5"),
                "成交额": row.get("f6"),
                "换手率(%)": row.get("f8"),
                K_MAIN_AMOUNT: row.get("f62"),
                K_INDUSTRY: row.get("f100"),
                K_DATA_SOURCE: "eastmoney-direct",
            }
    return quotes, None


def fetch_indices(a_share_skill: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_realtime.py"
    data, err = run_subprocess_json([sys.executable, str(script), "--index", "--json"], timeout=40)
    if err:
        return [], err
    return data if isinstance(data, list) else [], None


def fetch_sector_info(codes: List[str], a_share_skill: Path) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_sector_info.py"
    data, err = run_subprocess_json(
        [sys.executable, str(script), "--workers", "8", "--no-concepts", "--timeout", "15", "--json", *codes],
        timeout=35,
    )
    rows = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    sectors = {normalize_code(row.get("code")): row for row in rows if normalize_code(row.get("code"))}
    failed = [code for code, row in sectors.items() if row.get("error") and not row.get("industry")]
    if err and not sectors:
        return {}, err
    notes = []
    if err:
        notes.append(err)
    if failed:
        notes.append(f"sector_info failed for {len(failed)} codes; quote fallback will be used when available")
    note = "; ".join(notes) if notes else None
    return sectors, note


def fetch_danginvest_industry_fallback(codes: List[str]) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """Map stock codes to DangInvest major industry boards when Eastmoney sector data is unavailable."""
    wanted = {normalize_code(code) for code in codes if normalize_code(code)}
    if not wanted:
        return {}, None

    errors: List[str] = []

    def get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for trust_env in (False, True):
            session = require_requests().Session()
            session.trust_env = trust_env
            session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://dang-invest.com/"})
            try:
                response = session.get(url, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(str(last_exc))

    try:
        summary = get_json(
            DANGINVEST_SUMMARY_URL,
            {"mode": "industry", "limit": "300", "sort": "market_cap_desc"},
        )
    except Exception as exc:
        return {}, f"danginvest industry summary failed: {exc}"

    summary_data = summary.get("data", []) if isinstance(summary, dict) else []
    rows = summary_data.get("items", []) if isinstance(summary_data, dict) else summary_data
    def scan_board(board: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        board_found: Dict[str, Dict[str, Any]] = {}
        board_errors: List[str] = []
        group_key = board.get("groupKey")
        group_label = board.get("groupLabel") or group_key
        if not group_key:
            return board_found, board_errors

        offset = 0
        while True:
            try:
                detail = get_json(
                    DANGINVEST_DETAIL_URL,
                    {
                        "mode": "industry",
                        "groupKey": group_key,
                        "sort": "market_cap_desc",
                        "items_limit": "300",
                        "items_offset": str(offset),
                    },
                )
            except Exception as exc:
                board_errors.append(f"{group_key}: {exc}")
                break

            data = detail.get("data", {}) if isinstance(detail, dict) else {}
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                code = normalize_code(item.get("code"))
                if code in wanted and code not in board_found:
                    board_found[code] = {
                        "code": code,
                        "name": item.get("name"),
                        "industry": str(group_label or ""),
                        "source": "danginvest-industry-fallback",
                        "error": None,
                    }

            meta = data.get("itemsMeta", {}) if isinstance(data, dict) else {}
            if not meta.get("hasMore"):
                break
            next_offset = meta.get("nextOffset")
            if next_offset is None:
                break
            offset = int(next_offset)

        return board_found, board_errors

    found: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(rows)))) as executor:
        futures = [executor.submit(scan_board, board) for board in rows if isinstance(board, dict)]
        for future in as_completed(futures):
            board_found, board_errors = future.result()
            for code, row in board_found.items():
                found.setdefault(code, row)
            errors.extend(board_errors)
            if not (wanted - set(found)):
                break

    missing = sorted(wanted - set(found))
    if missing:
        errors.append(f"danginvest industry missing: {','.join(missing)}")
    return found, "; ".join(errors) if errors else None


def fetch_history(
    code: str, start: str, end: str, a_share_skill: Path, retries: int = 2
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_history.py"
    last_err = None
    for _ in range(retries + 1):
        data, err = run_subprocess_json(
            [
                sys.executable,
                str(script),
                "--kline",
                code,
                "--start",
                start,
                "--end",
                end,
                "--freq",
                "d",
                "--limit",
                "1200",
                "--json",
            ],
            timeout=45,
        )
        if not err and isinstance(data, list) and data:
            return trim_incomplete_daily_rows(normalize_history_rows(data)), None
        last_err = err or "empty history"
        time.sleep(0.5)
    return [], last_err


def normalize_history_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        date = row.get("time") or row.get("date") or row.get("日期")
        if not date:
            continue
        item = {
            "date": str(date)[:10],
            "open": safe_float(row.get("open") or row.get("开盘")),
            "high": safe_float(row.get("high") or row.get("最高")),
            "low": safe_float(row.get("low") or row.get("最低")),
            "close": safe_float(row.get("close") or row.get("收盘")),
            "preclose": safe_float(row.get("preclose") or row.get(K_PREV_CLOSE)),
            "volume": safe_float(row.get("volume") or row.get("成交量")),
            "pctChg": safe_float(row.get("pctChg") or row.get(K_PCT_CHG)),
        }
        if all(item[k] > 0 for k in ("open", "high", "low", "close")):
            out.append(item)
    out.sort(key=lambda x: x["date"])
    return out


def trim_incomplete_daily_rows(
    rows: List[Dict[str, Any]], now: Optional[dt.datetime] = None
) -> List[Dict[str, Any]]:
    """Drop today's daily bar before A-share close data has stabilized."""
    current = now or dt.datetime.now()
    if current.time() >= dt.time(15, 30):
        return rows
    today = current.date().isoformat()
    return [row for row in rows if str(row.get("date", "")) < today]


def first_present(row: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, "", "-", "--"):
            return row.get(key)
    return None


def normalize_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            try:
                return dt.datetime.fromtimestamp(timestamp / 1000).date().isoformat()
            except (OSError, ValueError):
                return str(value)
    return str(value).strip()[:10]


FUND_FLOW_MAIN_NET_KEYS = (
    "main_net_wan",
    K_MAIN_NET,
    "主力净额",
    "主力净流入",
)
FUND_FLOW_MAIN_RATIO_KEYS = (
    "main_ratio_pct",
    K_MAIN_RATIO,
    "main_ratio",
    "主力占比(%)",
    "主力净占比",
    "主力净流入占比",
)
FUND_FLOW_FIVE_DAY_RATIO_KEYS = ("five_day_ratio_pct",)
FUND_FLOW_TEN_DAY_RATIO_KEYS = ("ten_day_ratio_pct",)


def first_finite_number(row: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        if key not in row:
            continue
        number = finite_number(row.get(key))
        if number is not None:
            return number
    return None


def usable_fund_flow_rows(rows: Sequence[Any]) -> List[Dict[str, Any]]:
    usable: List[Dict[str, Any]] = []
    keys = (
        FUND_FLOW_MAIN_NET_KEYS
        + FUND_FLOW_MAIN_RATIO_KEYS
        + FUND_FLOW_FIVE_DAY_RATIO_KEYS
        + FUND_FLOW_TEN_DAY_RATIO_KEYS
    )
    for row in rows or []:
        if isinstance(row, dict) and first_finite_number(row, keys) is not None:
            usable.append(row)
    return usable


def normalize_fund_flow_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        main_net = first_finite_number(row, FUND_FLOW_MAIN_NET_KEYS)
        main_ratio = first_finite_number(row, FUND_FLOW_MAIN_RATIO_KEYS)
        five_day_ratio = first_finite_number(
            row, FUND_FLOW_FIVE_DAY_RATIO_KEYS
        )
        ten_day_ratio = first_finite_number(row, FUND_FLOW_TEN_DAY_RATIO_KEYS)
        if all(
            value is None
            for value in (main_net, main_ratio, five_day_ratio, ten_day_ratio)
        ):
            continue
        normalized.append(
            {
                "date": normalize_date(
                    first_present(row, ("date", K_DATE, "trade_date"))
                ),
                "main_net_wan": main_net,
                "main_ratio_pct": main_ratio,
                "five_day_ratio_pct": five_day_ratio,
                "ten_day_ratio_pct": ten_day_ratio,
                "super_net_wan": safe_float(
                    first_present(row, ("super_net_wan", K_SUPER_NET))
                ),
                "big_net_wan": safe_float(
                    first_present(row, ("big_net_wan", K_BIG_NET))
                ),
                "close": safe_float(first_present(row, ("close", K_CLOSE))),
                "pct_chg": safe_float(
                    first_present(row, ("pct_chg", K_PCT_CHG))
                ),
                "source": row.get("source")
                or row.get("data_source")
                or row.get("鏁版嵁婧?")
                or "unknown",
            }
        )
    normalized.sort(key=lambda x: x.get("date") or "")
    return normalized


def fetch_fund_flow(code: str, a_share_skill: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_realtime.py"
    data, err = run_subprocess_json(
        [sys.executable, str(script), "--fund-flow", code, "--days", "10", "--json"], timeout=25
    )
    if err:
        fallback, fallback_err = fetch_fund_flow_direct(code)
        if fallback:
            return fallback, None
        return [], fallback_err or err
    rows = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
    normalized = normalize_fund_flow_rows(rows)
    if normalized:
        return normalized, None
    fallback, fallback_err = fetch_fund_flow_direct(code)
    if fallback:
        return fallback, None
    return [], fallback_err or "empty fund flow"


def fetch_fund_flow_direct(code: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    market = "1" if code.startswith(("5", "6", "9")) else "0"
    params = urllib.parse.urlencode(
        {
            "lmt": "10",
            "klt": "101",
            "secid": f"{market}.{code}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        }
    )
    payload: Dict[str, Any] = {}
    last_error = ""
    for scheme in ("https", "http"):
        url = f"{scheme}://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?{params}"
        try:
            session = require_requests().Session()
            session.trust_env = False
            response = session.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("data", {}).get("klines"):
                last_error = f"{scheme} returned empty fund flow"
                continue
            break
        except Exception as exc:
            last_error = str(exc)
    else:
        snapshot_rows, snapshot_err = fetch_fund_flow_snapshot_direct(code)
        if snapshot_rows:
            return snapshot_rows, None
        return [], snapshot_err or last_error or "fund flow request failed"
    direct_rows = []
    for line in payload.get("data", {}).get("klines", []) or []:
        parts = line.split(",")
        if len(parts) < 13:
            continue
        direct_rows.append(
            {
                "date": parts[0],
                "main_net_wan": safe_float(parts[1]) / 10000,
                "small_net_wan": safe_float(parts[2]) / 10000,
                "medium_net_wan": safe_float(parts[3]) / 10000,
                "big_net_wan": safe_float(parts[4]) / 10000,
                "super_net_wan": safe_float(parts[5]) / 10000,
                "main_ratio_pct": safe_float(parts[6]),
                "close": safe_float(parts[11]),
                "pct_chg": safe_float(parts[12]),
                "source": "eastmoney-direct",
            }
        )
    normalized = normalize_fund_flow_rows(direct_rows)
    if normalized:
        return normalized, None
    snapshot_rows, snapshot_err = fetch_fund_flow_snapshot_direct(code)
    if snapshot_rows:
        return snapshot_rows, None
    return [], snapshot_err or "empty fund flow"


def fetch_fund_flow_snapshot_direct(code: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    market = "1" if code.startswith(("5", "6", "9")) else "0"
    params = urllib.parse.urlencode(
        {
            "fltt": "2",
            "invt": "2",
            "fields": "f2,f3,f12,f13,f14,f62,f184,f225,f165,f263,f109,f175,f264,f160,f100,f124,f265,f1",
            "secids": f"{market}.{code}",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
    )
    last_error = ""
    for scheme in ("https", "http"):
        url = f"{scheme}://push2.eastmoney.com/api/qt/ulist.np/get?{params}"
        for trust_env in (False, True):
            try:
                session = require_requests().Session()
                session.trust_env = trust_env
                response = session.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=15)
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("data", {}).get("diff", []) or []
                if not rows:
                    last_error = f"{scheme} returned empty fund-flow snapshot"
                    continue
                return fund_flow_snapshot_rows_from_ulist(rows), None
            except Exception as exc:
                last_error = str(exc)
        try:
            from curl_cffi import requests as curl_requests  # type: ignore

            response = curl_requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                timeout=15,
                impersonate="chrome",
            )
            if response.status_code >= 400:
                last_error = f"{scheme} curl status {response.status_code}"
                continue
            payload = response.json()
            rows = payload.get("data", {}).get("diff", []) or []
            if not rows:
                last_error = f"{scheme} curl returned empty fund-flow snapshot"
                continue
            return fund_flow_snapshot_rows_from_ulist(rows), None
        except Exception as exc:
            last_error = str(exc)
    return [], last_error or "empty fund-flow snapshot"


def fund_flow_snapshot_rows_from_ulist(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    row = rows[0]
    return [
        {
            "date": normalize_date(row.get("f124")),
            "main_net_wan": safe_float(row.get("f62")) / 10000,
            "main_ratio_pct": safe_float(row.get("f184")),
            "five_day_ratio_pct": safe_float(row.get("f165")),
            "five_day_chg_pct": safe_float(row.get("f109")),
            "ten_day_ratio_pct": safe_float(row.get("f175")),
            "ten_day_chg_pct": safe_float(row.get("f160")),
            "close": safe_float(row.get("f2")),
            "pct_chg": safe_float(row.get("f3")),
            "source": "eastmoney-ulist-snapshot",
        }
    ]
    rows = []
    for line in payload.get("data", {}).get("klines", []) or []:
        parts = line.split(",")
        if len(parts) < 13:
            continue
        rows.append(
            {
                "日期": parts[0],
                "主力净额(万)": safe_float(parts[1]) / 10000,
                "小单净额(万)": safe_float(parts[2]) / 10000,
                "中单净额(万)": safe_float(parts[3]) / 10000,
                "大单净额(万)": safe_float(parts[4]) / 10000,
                "超大单净额(万)": safe_float(parts[5]) / 10000,
                "主力占比(%)": safe_float(parts[6]),
                "收盘价": safe_float(parts[11]),
                "涨跌幅(%)": safe_float(parts[12]),
                "数据源": "eastmoney-direct",
            }
        )
    return rows, None


def fetch_events(code: str, name: str, a_share_skill: Path) -> Tuple[Dict[str, Any], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_stock_events.py"
    data, err = run_subprocess_json(
        [
            sys.executable,
            str(script),
            "--code",
            code,
            "--name",
            name,
            "--limit",
            "12",
            "--max-seconds",
            "35",
            "--json",
        ],
        timeout=40,
    )
    if err:
        fallback, fallback_err = run_subprocess_json(
            [
                sys.executable,
                str(script),
                "--code",
                code,
                "--name",
                name,
                "--limit",
                "12",
                "--max-seconds",
                "25",
                "--skip-sentiment",
                "--json",
            ],
            timeout=30,
        )
        if isinstance(fallback, dict):
            fallback["_degraded"] = "sentiment skipped after full event fetch failed"
            return fallback, f"full event fetch failed; used degraded retry: {err}"
        return {}, fallback_err or err
    return data if isinstance(data, dict) else {}, None


def fetch_board_summaries(a_share_skill: Path) -> Tuple[Dict[str, Any], List[str]]:
    script = a_share_skill / "scripts" / "fetch_danginvest.py"
    result: Dict[str, Any] = {}
    errors: List[str] = []
    modes = ("major", "sub", "concept")
    with ThreadPoolExecutor(max_workers=len(modes)) as executor:
        futures = {
            mode: executor.submit(
                run_subprocess_json,
                [sys.executable, str(script), "--summary", "--mode", mode, "--limit", "20", "--json"],
                30,
            )
            for mode in modes
        }
        for mode in modes:
            data, err = futures[mode].result()
            if err:
                errors.append(f"boards {mode}: {err}")
            else:
                result[mode] = data
    return result, errors


def _iso_trade_date(value: Any) -> str:
    text = str(value or "").strip()[:10]
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def normalize_board_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    trade_date = _iso_trade_date(meta.get("tradeDate") or meta.get("trade_date"))
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_key = row.get("groupKey") or row.get("group_key")
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        group_key = raw_key.strip()
        normalized.append(
            {
                "group_key": group_key,
                "name": str(row.get("groupLabel") or row.get("name") or group_key).strip(),
                "change_pct": safe_float(row.get("changePct") or row.get("change_pct")),
                "turnover_yuan": safe_float(
                    row.get("totalTurnoverYuan") or row.get("turnover_yuan")
                ),
                "as_of": trade_date,
                "stale": meta.get("stale"),
            }
        )
    return normalized


def fetch_board_rankings(
    a_share_skill: Path,
) -> Tuple[Dict[str, Dict[str, List[Dict[str, Any]]]], str, List[str]]:
    script = a_share_skill / "scripts" / "fetch_danginvest.py"
    modes = ("major", "sub", "concept")
    sorts = ("change_desc", "turnover_desc")
    result = {mode: {} for mode in modes}
    errors: List[str] = []
    trade_dates: List[str] = []
    missing_trade_dates = 0
    requests_to_make = [(mode, sort) for mode in modes for sort in sorts]
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            (mode, sort): executor.submit(
                run_subprocess_json,
                [
                    sys.executable,
                    str(script),
                    "--summary",
                    "--mode",
                    mode,
                    "--sort",
                    sort,
                    "--limit",
                    "20",
                    "--json",
                ],
                30,
            )
            for mode, sort in requests_to_make
        }
        for mode, sort in requests_to_make:
            payload, error = futures[(mode, sort)].result()
            if error:
                errors.append(f"boards {mode} {sort}: {error}")
                result[mode][sort] = []
                continue
            if not isinstance(payload, dict):
                errors.append(f"boards {mode} {sort}: payload is not an object")
                result[mode][sort] = []
                continue
            if not isinstance(payload.get("data"), list):
                errors.append(f"boards {mode} {sort}: data is not a list")
                result[mode][sort] = []
                continue
            result[mode][sort] = normalize_board_rows(payload)
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            trade_date = _iso_trade_date(meta.get("tradeDate") or meta.get("trade_date"))
            if trade_date:
                trade_dates.append(trade_date)
            else:
                missing_trade_dates += 1
    if not trade_dates:
        errors.append("board rankings: no authoritative trade date in successful payloads")
    elif missing_trade_dates:
        errors.append(
            f"board rankings: {missing_trade_dates} successful payload(s) lack an authoritative trade date"
        )
    distinct_trade_dates = sorted(set(trade_dates))
    if len(distinct_trade_dates) > 1:
        errors.append(
            "board rankings: mixed authoritative trade dates: "
            + ", ".join(distinct_trade_dates)
        )
    return result, max(trade_dates) if trade_dates else "", errors


def strict_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", "").replace("%", "")
        if not text or text in {"-", "--", "None", "nan", "NaN"}:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def normalize_market_breadth(
    rows: Sequence[Dict[str, Any]], trade_date: str
) -> Dict[str, Any]:
    changes: List[float] = []
    turnover = 0.0
    turnover_valid_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        change = first_present(row, (K_CHANGE_PCT, "\u6da8\u8dcc\u5e45", "change_pct"))
        numeric_change = strict_float(change)
        if numeric_change is not None:
            changes.append(numeric_change)
        numeric_turnover = strict_float(
            first_present(row, ("\u6210\u4ea4\u989d", "amount", "turnover_yuan"))
        )
        if numeric_turnover is not None and numeric_turnover >= 0:
            turnover += numeric_turnover
            if numeric_change is not None:
                turnover_valid_count += 1
    sample_size = len(changes)
    turnover_coverage_ratio = (
        turnover_valid_count / sample_size if sample_size else 0.0
    )
    turnover_complete = bool(
        turnover_valid_count >= MIN_BREADTH_SAMPLE_SIZE
        and turnover_coverage_ratio >= MIN_TURNOVER_COVERAGE_RATIO
    )
    return {
        "trade_date": trade_date,
        "as_of": trade_date,
        "advancers": sum(1 for value in changes if value > 0),
        "decliners": sum(1 for value in changes if value < 0),
        "unchanged": sum(1 for value in changes if value == 0),
        "median_change_pct": round(statistics.median(changes), 2) if changes else None,
        "turnover_yuan": turnover,
        "sample_size": sample_size,
        "completeness_threshold": MIN_BREADTH_SAMPLE_SIZE,
        "turnover_valid_count": turnover_valid_count,
        "turnover_coverage_ratio": round(turnover_coverage_ratio, 4),
        "turnover_coverage_threshold": MIN_TURNOVER_COVERAGE_RATIO,
        "turnover_complete": turnover_complete,
        # 1,000 valid quotes is deliberately conservative: it rejects index,
        # watchlist, and top-N samples. Requiring 90% matched valid turnover
        # also prevents a mostly price-only sample from supporting total turnover.
        "complete": sample_size >= MIN_BREADTH_SAMPLE_SIZE and turnover_complete,
        "limit_structure_available": False,
        "limit_up": None,
        "limit_down": None,
        "failed_limit_up": None,
    }


def fetch_market_breadth(
    a_share_skill: Path, trade_date: str
) -> Tuple[Dict[str, Any], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_realtime.py"
    payload, error = run_subprocess_json(
        [
            sys.executable,
            str(script),
            "--all-quote",
            "--top",
            "10000",
            "--json",
        ],
        timeout=60,
    )
    if error:
        return {}, error
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}, "all-quote payload is not a list"
    return normalize_market_breadth(rows, trade_date), None


def normalize_provider_stock_code(value: Any) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(?i)(?:(sh|sz|bj)[.:]?)?(\d{6})", text)
    if not match:
        return ""
    prefix, code = match.groups()
    if prefix:
        valid_initials = {
            "sh": {"5", "6", "9"},
            "sz": {"0", "1", "2", "3"},
            "bj": {"4", "8", "9"},
        }
        if code[0] not in valid_initials[prefix.lower()]:
            return ""
    return code


def normalize_board_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload, dict) and isinstance(payload.get("meta"), dict) else {}
    data = payload.get("data") if isinstance(payload, dict) else None
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []
    normalized: List[Dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        code = normalize_provider_stock_code(
            first_present(row, ("code", "stockCode", "symbol", K_CODE))
        )
        if not code:
            continue
        normalized.append(
            {
                "code": code,
                "name": str(first_present(row, ("name", "stockName", K_NAME)) or ""),
                "change_pct": safe_float(
                    first_present(row, ("changePct", "change_pct", K_CHANGE_PCT))
                ),
                "turnover_yuan": safe_float(
                    first_present(row, ("turnoverYuan", "amount", "\u6210\u4ea4\u989d"))
                ),
                "market_cap_yuan": safe_float(
                    first_present(
                        row,
                        ("marketCapYuan", "market_cap_yuan", "\u603b\u5e02\u503c"),
                    )
                )
                or None,
                "limit_up": first_present(row, ("limitUp", "isLimitUp")),
                "ret20": first_present(row, ("ret20", "return20")),
            }
        )
        if len(normalized) == 100:
            break
    return {
        "as_of": _iso_trade_date(meta.get("tradeDate") or meta.get("trade_date")),
        "stale": meta.get("stale"),
        "summary": data.get("summary", {}) if isinstance(data, dict) else {},
        "items": normalized,
    }


def fetch_board_details(
    candidates: Sequence[Dict[str, Any]], a_share_skill: Path
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    script = a_share_skill / "scripts" / "fetch_danginvest.py"
    selected: List[Dict[str, Any]] = []
    seen_identities = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        mode = candidate.get("mode")
        key = candidate.get("group_key")
        if mode not in {"major", "sub", "concept"}:
            continue
        if not isinstance(key, str) or not key.strip():
            continue
        key = key.strip()
        identity = board_identity(mode, key)
        if not identity or identity in seen_identities:
            continue
        selected.append({**candidate, "group_key": key, "board_id": identity})
        seen_identities.add(identity)
        if len(selected) == 12:
            break
    if not selected:
        return {}, []

    details: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    with ThreadPoolExecutor(max_workers=min(6, len(selected))) as executor:
        futures = {
            candidate["board_id"]: executor.submit(
                run_subprocess_json,
                [
                    sys.executable,
                    str(script),
                    "--detail",
                    "--mode",
                    candidate["mode"],
                    "--group-key",
                    candidate["group_key"],
                    "--items-limit",
                    "100",
                    "--json",
                ],
                30,
            )
            for candidate in selected
        }
        for key, future in futures.items():
            payload, error = future.result()
            if error:
                errors.append(f"board detail {key}: {error}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"board detail {key}: payload is not an object")
                continue
            data = payload.get("data")
            if not isinstance(data, dict):
                errors.append(f"board detail {key}: data is not an object")
                continue
            if not isinstance(data.get("items"), list):
                errors.append(f"board detail {key}: items is not a list")
                continue
            details[key] = normalize_board_detail(payload)
    return details, errors


def normalize_indices(
    rows: Sequence[Dict[str, Any]], trade_date: str = ""
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        change_pct = safe_float(first_present(row, (K_CHANGE_PCT, "change_pct", "pct")))
        price = strict_float(first_present(row, (K_PRICE, "price")))
        normalized.append(
            {
                "code": str(first_present(row, (K_CODE, "code")) or ""),
                "name": str(first_present(row, (K_NAME, "name")) or ""),
                "price": price if price is not None and price > 0 else None,
                "change_pct": change_pct,
                "as_of": trade_date,
            }
        )
    return normalized


def market_history_row(
    rankings: Dict[str, Dict[str, List[Dict[str, Any]]]], trade_date: str
) -> Dict[str, Any]:
    trade_date = _iso_trade_date(trade_date)
    top_change: List[str] = []
    top_turnover: List[str] = []
    for mode in ("major", "sub", "concept"):
        mode_rows = rankings.get(mode, {}) if isinstance(rankings, dict) else {}
        if not isinstance(mode_rows, dict):
            continue
        change_rows = mode_rows.get("change_desc", [])
        turnover_rows = mode_rows.get("turnover_desc", [])
        if not isinstance(change_rows, list):
            change_rows = []
        if not isinstance(turnover_rows, list):
            turnover_rows = []
        top_change.extend(
            board_identity(mode, row.get("group_key"))
            for row in change_rows[:20]
            if isinstance(row, dict)
            and bool(trade_date)
            and _iso_trade_date(row.get("as_of")) == trade_date
            and row.get("stale") is False
            and board_identity(mode, row.get("group_key"))
        )
        top_turnover.extend(
            board_identity(mode, row.get("group_key"))
            for row in turnover_rows[:20]
            if isinstance(row, dict)
            and bool(trade_date)
            and _iso_trade_date(row.get("as_of")) == trade_date
            and row.get("stale") is False
            and board_identity(mode, row.get("group_key"))
        )
    return {
        "trade_date": trade_date,
        "top_change": list(dict.fromkeys(top_change)),
        "top_turnover": list(dict.fromkeys(top_turnover)),
    }


def load_market_history(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(row, dict):
            continue
        trade_date = _iso_trade_date(row.get("trade_date"))
        if not trade_date:
            continue
        top_change = row.get("top_change")
        top_turnover = row.get("top_turnover")
        if not isinstance(top_change, list) or not isinstance(top_turnover, list):
            continue
        if any(not is_board_identity(value) for value in [*top_change, *top_turnover]):
            continue
        rows.append({**row, "trade_date": trade_date})
    return rows


def sanitize_market_history(
    value: Any, latest_trade_date: str
) -> List[Dict[str, Any]]:
    """Fail closed on future, malformed, or non-canonical continuity rows."""
    if not latest_trade_date or not isinstance(value, list):
        return []
    by_date: Dict[str, Dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("trade_date")
        if not isinstance(raw_date, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", raw_date
        ):
            continue
        trade_date = _iso_trade_date(raw_date)
        if not trade_date or trade_date > latest_trade_date:
            continue
        collections: Dict[str, List[str]] = {}
        valid = True
        for field in ("top_change", "top_turnover"):
            raw_items = row.get(field)
            if not isinstance(raw_items, list) or any(
                not is_board_identity(item) for item in raw_items
            ):
                valid = False
                break
            collections[field] = list(dict.fromkeys(raw_items))
        if not valid:
            continue
        by_date[trade_date] = {
            "trade_date": trade_date,
            "top_change": collections["top_change"],
            "top_turnover": collections["top_turnover"],
        }
    return [by_date[trade_date] for trade_date in sorted(by_date)]


def append_market_snapshot(path: Path, snapshot: Dict[str, Any]) -> None:
    trade_date = _iso_trade_date(snapshot.get("trade_date"))
    if not trade_date:
        return
    normalized = {**snapshot, "trade_date": trade_date}
    rows = load_market_history(path)
    if any(row.get("trade_date") == trade_date for row in rows):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.append(normalized)
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(
                "".join(
                    json.dumps(row, ensure_ascii=False) + "\n"
                    for row in rows[-60:]
                )
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(path))
        fsync_directory(path.parent)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def prepare_market_inputs(
    collected: CollectedData, history_path: Path
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Build one market input bundle without fabricating source dates."""
    latest_trade_date = _iso_trade_date(collected.latest_trade_date)
    stored_by_date = {
        row["trade_date"]: row
        for row in load_market_history(history_path)
        if not latest_trade_date or row["trade_date"] <= latest_trade_date
    }
    stored_history = [stored_by_date[key] for key in sorted(stored_by_date)]
    current_market_row: Optional[Dict[str, Any]] = None
    history_for_analysis = list(stored_history)
    if latest_trade_date:
        current_market_row = market_history_row(
            collected.board_rankings, latest_trade_date
        )
        history_for_analysis = [
            row
            for row in stored_history
            if row.get("trade_date") != latest_trade_date
        ] + [current_market_row]

    recent_trade_dates: List[str] = []
    for value in [
        latest_trade_date,
        *(
            row.get("trade_date")
            for row in reversed(history_for_analysis)
            if isinstance(row, dict)
        ),
    ]:
        trade_date = _iso_trade_date(value)
        if trade_date and trade_date not in recent_trade_dates:
            recent_trade_dates.append(trade_date)

    return (
        {
            "latest_trade_date": latest_trade_date,
            "recent_trade_dates": recent_trade_dates,
            # CollectedData.indices is already normalized with its own as_of.
            "normalized_indices": list(collected.indices),
            "breadth": dict(collected.breadth),
            "board_rankings": collected.board_rankings,
            "board_details": collected.board_details,
            "market_history": history_for_analysis,
            "evidence_index": [],
        },
        current_market_row,
    )


def fetch_market_news(a_share_skill: Path, limit: int = 80) -> Tuple[Dict[str, Any], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_danginvest.py"
    data, err = run_subprocess_json(
        [sys.executable, str(script), "--news", "--limit", str(limit), "--json"],
        timeout=40,
    )
    if not err and isinstance(data, dict):
        return data, None

    try:
        session = require_requests().Session()
        session.trust_env = False
        response = session.get(
            DANGINVEST_NEWS_URL,
            params={"limit": limit, "offset": 0},
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://dang-invest.com/"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "meta": {
                "url": DANGINVEST_NEWS_URL,
                "limit": limit,
                "offset": 0,
                "count": payload.get("count"),
                "has_more": payload.get("has_more"),
                "update_time": now_str(),
                "data_source": "DangInvest direct",
            },
            "data": payload.get("data") or [],
        }, err
    except Exception as exc:
        return {}, f"{err}; direct news fallback failed: {exc}" if err else str(exc)


def ema(values: List[float], period: int) -> List[Optional[float]]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out: List[Optional[float]] = []
    prev = values[0]
    for value in values:
        prev = alpha * value + (1 - alpha) * prev
        out.append(prev)
    return out


def moving_average(values: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    window: List[float] = []
    total = 0.0
    for value in values:
        window.append(value)
        total += value
        if len(window) > period:
            total -= window.pop(0)
        out.append(total / period if len(window) == period else None)
    return out


def enrich_indicators(history: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    closes = [safe_float(x["close"]) for x in history]
    ma_short = moving_average(closes, int(params["ma_short"]))
    ma_long = moving_average(closes, int(params["ma_long"]))
    ema_fast = ema(closes, int(params["macd_fast"]))
    ema_slow = ema(closes, int(params["macd_slow"]))
    dif = [(a or 0) - (b or 0) for a, b in zip(ema_fast, ema_slow)]
    dea = ema(dif, int(params["macd_signal"]))
    for i, row in enumerate(history):
        row["ma_short"] = ma_short[i]
        row["ma_long"] = ma_long[i]
        row["dif"] = dif[i]
        row["dea"] = dea[i]
        row["macd_hist"] = (dif[i] - (dea[i] or 0)) * 2
        if i >= 5:
            row["ret5"] = (closes[i] / closes[i - 5] - 1) * 100
        if i >= 20:
            row["ret20"] = (closes[i] / closes[i - 20] - 1) * 100
        if i >= 60:
            row["ret60"] = (closes[i] / closes[i - 60] - 1) * 100
    return history


def score_from_row(
    row: Dict[str, Any],
    prev_row: Optional[Dict[str, Any]],
    fund_flow: List[Dict[str, Any]],
    sector_change_pct: float,
    event_bias: float,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    close = safe_float(row.get("close"))
    ma_short = safe_float(row.get("ma_short"))
    ma_long = safe_float(row.get("ma_long"))
    ma_long_prev = safe_float(prev_row.get("ma_long")) if prev_row else 0.0
    dif = safe_float(row.get("dif"))
    dea = safe_float(row.get("dea"))
    hist = safe_float(row.get("macd_hist"))
    ret20 = safe_float(row.get("ret20"))

    trend = 50.0
    if ma_short and close > ma_short:
        trend += 15
    if ma_long and close > ma_long:
        trend += 20
    if ma_long and ma_long_prev and ma_long > ma_long_prev:
        trend += 10
    if ret20 > 15:
        trend += 5
    if ma_long and close < ma_long:
        trend -= 25
    trend = max(0, min(100, trend))

    macd = 50.0
    if dif > dea:
        macd += 20
    if dif > 0 and dea > 0:
        macd += 15
    if hist > 0:
        macd += 10
    if prev_row and hist > safe_float(prev_row.get("macd_hist")):
        macd += 5
    if dif < dea:
        macd -= 20
    macd = max(0, min(100, macd))

    usable_flow = usable_fund_flow_rows(fund_flow)
    flow = 50.0
    if usable_flow:
        latest = usable_flow[-1]
        main_ratio = first_finite_number(latest, FUND_FLOW_MAIN_RATIO_KEYS)
        five_day_ratio = first_finite_number(
            latest, FUND_FLOW_FIVE_DAY_RATIO_KEYS
        )
        ten_day_ratio = first_finite_number(
            latest, FUND_FLOW_TEN_DAY_RATIO_KEYS
        )
        if main_ratio is not None:
            if main_ratio > 5:
                flow += 15
            elif main_ratio > 0:
                flow += 6
            elif main_ratio < -5:
                flow -= 15
            elif main_ratio < 0:
                flow -= 6
        if five_day_ratio:
            if five_day_ratio > 3:
                flow += 14
            elif five_day_ratio > 0:
                flow += 7
            elif five_day_ratio < -3:
                flow -= 14
            elif five_day_ratio < 0:
                flow -= 7
            if ten_day_ratio is not None and ten_day_ratio > 2:
                flow += 6
            elif ten_day_ratio is not None and ten_day_ratio < -2:
                flow -= 6
        else:
            recent_nets = [
                number
                for item in usable_flow[-5:]
                for number in [
                    first_finite_number(item, FUND_FLOW_MAIN_NET_KEYS)
                ]
                if number is not None
            ]
            recent_net = sum(recent_nets)
            positive_days = sum(1 for number in recent_nets if number > 0)
            if recent_net > 3000:
                flow += 14
            elif recent_net > 0:
                flow += 7
            elif recent_net < -3000:
                flow -= 14
            elif recent_net < 0:
                flow -= 7
            if positive_days >= 4:
                flow += 6
            elif len(recent_nets) >= 5 and positive_days <= 1:
                flow -= 6
    flow = max(0, min(100, flow))

    sector = max(0, min(100, 50 + sector_change_pct * 8))
    event = max(0, min(100, 50 + event_bias))
    weights = params["weights"]
    total = (
        trend * weights["trend"]
        + macd * weights["macd"]
        + flow * weights["fund_flow"]
        + sector * weights["sector"]
        + event * weights["event"]
    )
    return {
        "total_score": round(total, 2),
        "trend_score": round(trend, 2),
        "macd_score": round(macd, 2),
        "fund_flow_score": round(flow, 2) if usable_flow else None,
        "sector_score": round(sector, 2),
        "event_score": round(event, 2),
        "score_imputations": (
            {} if usable_flow else {"fund_flow": 50.0}
        ),
    }


def text_from_event_item(item: Dict[str, Any]) -> str:
    values = [
        first_present(item, (K_TITLE, "title", "headline")),
        first_present(item, (K_CONTENT, "content", "summary")),
        first_present(item, (K_SOURCE, "source")),
    ]
    return " ".join(str(x) for x in values if x)


def event_texts(events: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for section_name in ("holder_change_buyback", "regulatory", "major_contracts", "sentiment"):
        section = events.get(section_name, {})
        for item in section.get("items") or []:
            if isinstance(item, dict):
                text = text_from_event_item(item)
                if text:
                    texts.append(text)
    return texts


def structured_event_bias(events: Dict[str, Any]) -> float:
    bias = 0.0
    performance = events.get("performance", {})
    for item in (performance.get("forecast") or []) + (performance.get("express") or []):
        if not isinstance(item, dict):
            continue
        pct = safe_float(first_present(item, (K_NET_PROFIT_YOY, K_PERF_CHANGE_PCT)))
        if pct > 80:
            bias += 22
        elif pct > 30:
            bias += 14
        elif pct > 0:
            bias += 7
        elif pct < -50:
            bias -= 22
        elif pct < -20:
            bias -= 12

    text = "\n".join(event_texts(events))
    positive_keywords = [
        "\u9884\u589e",
        "\u589e\u957f",
        "\u91cf\u4ef7\u9f50\u5347",
        "\u83b7\u5f97\u836f\u54c1\u6ce8\u518c\u8bc1\u4e66",
        "\u673a\u6784\u8c03\u7814",
        "\u8ba2\u5355",
        "\u56de\u8d2d",
        "\u89e3\u9664\u8d28\u62bc",
    ]
    negative_keywords = [
        "\u51cf\u6301",
        "\u5f02\u52a8",
        "\u98ce\u9669\u63d0\u793a",
        "\u95ee\u8be2",
        "\u5904\u7f5a",
        "\u4e8f\u635f",
        "\u65e0\u8d44\u4ea7\u6ce8\u5165",
        "\u672a\u83b7\u5f97\u4efb\u4f55\u8ba2\u5355",
        "\u8e6d\u70ed\u70b9",
        "\u7acb\u6848",
    ]
    bias += min(18, 6 * sum(1 for keyword in positive_keywords if keyword in text))
    bias -= min(24, 8 * sum(1 for keyword in negative_keywords if keyword in text))
    if events.get("_degraded"):
        bias -= 3
    return max(-35.0, min(35.0, bias))


def event_bias(events: Dict[str, Any]) -> float:
    if not events:
        return 0.0
    return structured_event_bias(events)
    perf = events.get("performance", {})
    forecasts = perf.get("forecast") or []
    if forecasts:
        latest = forecasts[0]
        pct = safe_float(latest.get("业绩变动幅度"))
        if pct > 50:
            return 25.0
        if pct > 0:
            return 10.0
        if pct < -30:
            return -25.0
    regulatory = events.get("regulatory", {}).get("items") or []
    titles = " ".join(str(x.get("新闻标题", "")) for x in regulatory[:8])
    bad_words = ["立案", "处罚", "问询", "减持", "亏损", "退市"]
    if any(word in titles for word in bad_words):
        return -15.0
    return 0.0


def board_change_for_industry(industry: str, board_summaries: Dict[str, Any]) -> float:
    if not industry:
        return 0.0
    changes: List[float] = []
    for payload in board_summaries.values():
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        for row in rows:
            label = str(row.get("groupLabel") or row.get("groupKey") or "")
            if label and (industry in label or label in industry):
                changes.append(safe_float(row.get("changePct")))
    return statistics.mean(changes) if changes else 0.0


def market_news_items(market_news: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
    rows = market_news.get("data", []) if isinstance(market_news, dict) else []
    items: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "published_at": row.get("published_at") or row.get(K_PUBLISHED_AT),
                "source": row.get("source") or row.get(K_SOURCE),
                "title": row.get("title") or row.get(K_TITLE) or "",
                "content": row.get("content") or row.get(K_CONTENT) or "",
                "url": row.get("url"),
            }
        )
    return items


def summarize_market_news(market_news: Dict[str, Any]) -> Dict[str, Any]:
    items = market_news_items(market_news, limit=80)
    topic_keywords = {
        "AI/compute": ["AI", "\u7b97\u529b", "\u534a\u5bfc\u4f53", "MLCC", "PCB", "\u5149\u6a21\u5757", "\u79d1\u6280"],
        "robotics": ["\u673a\u5668\u4eba", "\u5177\u8eab\u667a\u80fd", "\u4eba\u5f62\u673a\u5668\u4eba"],
        "commercial_space": ["\u5546\u4e1a\u822a\u5929", "\u536b\u661f", "\u957f\u5f81", "\u822a\u5929"],
        "autos": ["\u6c7d\u8f66", "\u70ed\u7ba1\u7406", "\u96f6\u90e8\u4ef6", "\u534e\u4e3a\u6c7d\u8f66"],
        "chemicals_materials": ["\u5316\u5de5", "\u65b0\u6750\u6599", "\u6c1f", "PEEK", "\u6da8\u4ef7"],
        "medicine": ["\u533b\u836f", "\u836f\u54c1", "\u533b\u7597\u5668\u68b0", "\u6ce8\u518c\u8bc1"],
        "macro_risk": ["CPI", "PPI", "\u91d1\u878d\u6570\u636e", "\u53f0\u98ce", "\u970d\u5c14\u6728\u5179", "\u539f\u6cb9"],
    }
    counts = {topic: 0 for topic in topic_keywords}
    for item in items:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                counts[topic] += 1
    top_topics = [
        {"topic": topic, "hits": hits}
        for topic, hits in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if hits > 0
    ]
    return {
        "source": (market_news.get("meta") or {}).get("data_source") if isinstance(market_news, dict) else None,
        "updated_at": (market_news.get("meta") or {}).get("update_time") if isinstance(market_news, dict) else None,
        "count": len(items),
        "item_count": len(items),
        "top_topics": top_topics[:8],
        "latest": items[:8],
    }


def build_data_coverage(
    positions: Dict[str, Any],
    stock_data: Dict[str, StockData],
    board_summaries: Dict[str, Any],
    indices: List[Dict[str, Any]],
    market_news: Dict[str, Any],
    data_errors: Sequence[str],
) -> Dict[str, Any]:
    holdings = positions.get("holdings", [])
    total = len(holdings)
    histories = [len((stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).history) for h in holdings]
    quote_count = sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).quote)
    history_count = sum(1 for count in histories if count > 0)
    fund_flow_count = sum(
        1
        for holding in holdings
        if usable_fund_flow_rows(
            (
                stock_data.get(holding["code"])
                or StockData(holding["code"], holding.get("name", ""), [], {})
            ).fund_flow
            or []
        )
    )
    event_count = sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).events)
    industry_count = sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).industry)
    market_news_count = len(market_news_items(market_news, limit=200))
    data_error_count = len(data_errors)
    return {
        "holdings": total,
        "holding_count": total,
        "quotes": quote_count,
        "quote_count": quote_count,
        "history": history_count,
        "history_count": history_count,
        "history_rows_min": min(histories) if histories else 0,
        "history_rows_max": max(histories) if histories else 0,
        "fund_flow": fund_flow_count,
        "fund_flow_count": fund_flow_count,
        "events": event_count,
        "event_count": event_count,
        "industry": industry_count,
        "industry_count": industry_count,
        "board_summaries": len(board_summaries),
        "board_modes": sorted(board_summaries.keys()),
        "indices": len(indices),
        "index_count": len(indices),
        "market_news": market_news_count,
        "market_news_count": market_news_count,
        "errors": data_error_count,
        "data_error_count": data_error_count,
    }


def classify_market(indices: List[Dict[str, Any]], board_summaries: Dict[str, Any]) -> Dict[str, Any]:
    pct_values = [
        safe_float(first_present(x, (K_CHANGE_PCT, "change_pct", "pct")))
        for x in indices
    ]
    avg_index = statistics.mean(pct_values) if pct_values else 0.0
    top_boards: List[Dict[str, Any]] = []
    for key, payload in board_summaries.items():
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        for row in rows[:5]:
            top_boards.append(
                {
                    "mode": key,
                    "name": row.get("groupLabel") or row.get("groupKey"),
                    "change_pct": safe_float(row.get("changePct")),
                    "turnover_yuan": safe_float(row.get("totalTurnoverYuan")),
                }
            )
    if avg_index <= -2.0:
        regime = "risk_off"
    elif avg_index >= 1.0:
        regime = "risk_on"
    else:
        regime = "mixed"
    return {
        "as_of": now_str(),
        "regime": regime,
        "avg_index_change_pct": round(avg_index, 2),
        "indices": indices,
        "top_boards": sorted(top_boards, key=lambda x: x["change_pct"], reverse=True)[:10],
    }


def action_for_holding(
    holding: Dict[str, Any],
    score: Dict[str, Any],
    latest_row: Dict[str, Any],
    params: Dict[str, Any],
    total_assets: float,
    missing_data: Optional[List[str]] = None,
) -> Dict[str, Any]:
    pnl_pct = 0.0
    cost = safe_float(holding.get("cost_price"))
    price = safe_float(holding.get("last_price")) or safe_float(latest_row.get("close"))
    if cost > 0:
        pnl_pct = (price / cost - 1) * 100
    total_score = score["total_score"]
    ma_short = safe_float(latest_row.get("ma_short"))
    ma_long = safe_float(latest_row.get("ma_long"))

    if pnl_pct <= params["stop_loss_pct"] or (ma_long and price < ma_long and total_score < params["reduce_score"]):
        action = "exit"
        target_weight = 0.0
        reason = "亏损或趋势失效，优先控制回撤"
    elif total_score < params["hold_score"] or (pnl_pct > params["take_profit_pct"] and total_score < params["entry_score"]):
        action = "reduce"
        target_weight = min(0.05, params["max_single_weight"])
        reason = "评分不足或盈利后动能转弱，降低暴露"
    elif total_score >= params["entry_score"] and ma_short and price >= ma_short:
        action = "add_only_if_triggered"
        target_weight = params["max_single_weight"]
        reason = "趋势和节奏共振，但只能在触发条件成立时加仓"
    else:
        action = "hold"
        target_weight = min(params["max_single_weight"], safe_float(holding.get("market_value")) / total_assets if total_assets else 0)
        reason = "结构未破坏，维持观察"

    missing_data = missing_data or []
    if action == "add_only_if_triggered" and "fund_flow" in missing_data:
        action = "hold"
        target_weight = min(params["max_single_weight"], safe_float(holding.get("market_value")) / total_assets if total_assets else 0)
        reason = "资金流数据缺失，禁止加仓信号升级，仅保留持有观察"

    trigger = f"放量站稳短均线 {round(ma_short, 2) if ma_short else '缺失'} 且总评分不低于 {params['entry_score']}"
    invalidation = f"跌破长均线 {round(ma_long, 2) if ma_long else '缺失'} 或总评分低于 {params['reduce_score']}"
    return {
        "code": holding["code"],
        "name": holding["name"],
        "action": action,
        "reason": reason,
        "trigger": trigger,
        "invalidation": invalidation,
        "target_weight": round(target_weight, 4),
        "risk_note": "条件化策略信号，不代表确定收益；若数据低置信则降级执行。",
    }


def research_action_for_target(
    holding: Dict[str, Any],
    latest_row: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    ma_short = safe_float(latest_row.get("ma_short"))
    ma_long = safe_float(latest_row.get("ma_long"))
    return {
        "code": holding["code"],
        "name": holding["name"],
        "action": "watch",
        "reason": "研究对象，未提供账户持仓，不生成组合配置或自动交易结论。",
        "trigger": f"若后续考虑建仓，先验证收盘站稳短均线 {round(ma_short, 2) if ma_short else '缺失'} 且总评分不低于 {params['entry_score']}",
        "invalidation": f"跌破长均线 {round(ma_long, 2) if ma_long else '缺失'} 或关键基本面证据转弱",
        "target_weight": 0.0,
        "risk_note": "研究结论需要结合公告、财报、行业位置和数据覆盖复核；本对象不在持仓时不输出仓位指令。",
    }


def low_confidence_action(holding: Dict[str, Any], total_assets: float, reason: str) -> Dict[str, Any]:
    return {
        "code": holding["code"],
        "name": holding["name"],
        "action": "watch",
        "reason": reason,
        "trigger": "刷新缺失行情/历史K线/资金流数据后重新评分",
        "invalidation": "关键数据持续缺失或持仓截图字段无法校验",
        "target_weight": 0.0,
        "risk_note": "低置信数据，不生成加仓或减仓结论；仅保留观察和复核要求。",
    }


def evidence_from_source(
    evidence_id: str,
    category: str,
    statement: str,
    source: str,
    as_of: Any,
    latest_trade_date: str,
    recent_trade_dates: Sequence[str],
    scope: str,
    reliability: str,
    stale: Any = SOURCE_STALE_UNSET,
    require_exact_stale: bool = False,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    evidence = make_evidence(
        evidence_id,
        category,
        statement,
        source,
        as_of,
        latest_trade_date or "unknown",
        recent_trade_dates,
        scope,
        reliability,
        url,
    )
    if stale is True:
        evidence["freshness"] = "stale"
        evidence["reliability"] = "low"
    elif stale is False:
        pass
    elif stale is not SOURCE_STALE_UNSET or require_exact_stale:
        evidence["freshness"] = "unknown"
        evidence["reliability"] = "low"
    return evidence


def format_evidence_number(
    value: Any, decimals: int, minimum: Optional[float] = None
) -> Tuple[str, bool]:
    number = finite_number(value)
    if number is None or (minimum is not None and number < minimum):
        return "证据不足", False
    return f"{number:.{decimals}f}", True


def generate_daily_signal(
    positions: Dict[str, Any],
    stock_data: Dict[str, StockData],
    market_regime: Dict[str, Any],
    board_summaries: Dict[str, Any],
    indices: List[Dict[str, Any]],
    market_news: Dict[str, Any],
    data_errors: Sequence[str],
    params: Dict[str, Any],
    market_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stock_scores: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    total_assets = safe_float(positions.get("total_assets")) or safe_float(positions.get("stock_value"))
    research_only_codes = set(positions.get("research_only_codes", []))
    for holding in positions["holdings"]:
        code = holding["code"]
        data = stock_data.get(code)
        if not data or not data.history:
            current_weight = safe_float(holding.get("market_value")) / total_assets if total_assets else 0.0
            stock_scores.append(
                {
                    "code": code,
                    "name": holding["name"],
                    "industry": data.industry if data else "",
                    "current_weight": round(current_weight, 4),
                    "price": safe_float(holding.get("last_price")),
                    "scores": {
                        "total_score": 0.0,
                        "trend_score": 0.0,
                        "macd_score": 0.0,
                        "fund_flow_score": None,
                        "sector_score": 0.0,
                        "event_score": 0.0,
                        "score_imputations": {},
                        "raw": {
                            "reason": "missing history or stock data",
                            "fund_flow_rows": 0,
                            "fund_flow_5d_net_wan": None,
                        },
                    },
                    "latest_indicators": {},
                    "data_confidence": "low",
                    "missing_data": ["history"] if data else ["stock_data"],
                }
            )
            actions.append(low_confidence_action(holding, total_assets, "关键市场数据缺失，停止推断并标记低置信"))
            continue
        history = enrich_indicators([dict(x) for x in data.history], params)
        latest = history[-1]
        prev = history[-2] if len(history) > 1 else None
        sector_change = board_change_for_industry(data.industry, board_summaries)
        bias = event_bias(data.events or {})
        usable_flow = usable_fund_flow_rows(data.fund_flow or [])
        score = score_from_row(
            latest, prev, usable_flow, sector_change, bias, params
        )
        missing_data = []
        if not data.quote:
            missing_data.append("quote")
        if not usable_flow:
            missing_data.append("fund_flow")
        if not data.industry:
            missing_data.append("industry")
        recent_net_values = [
            number
            for item in usable_flow[-5:]
            for number in [first_finite_number(item, FUND_FLOW_MAIN_NET_KEYS)]
            if number is not None
        ]
        score["raw"] = {
            "history_rows": len(data.history),
            "fund_flow_rows": len(usable_flow),
            "fund_flow_5d_net_wan": (
                round(sum(recent_net_values), 2)
                if recent_net_values
                else None
            ),
            "sector_change_pct": round(sector_change, 4),
            "event_bias": round(bias, 4),
        }
        current_weight = safe_float(holding.get("market_value")) / total_assets if total_assets else 0.0
        score_row = {
            "code": code,
            "name": holding["name"],
            "industry": data.industry,
            "current_weight": round(current_weight, 4),
            "price": safe_float(data.quote.get(K_PRICE) or data.quote.get("f2") or latest.get("close")),
            "scores": score,
            "latest_indicators": {
                "close": latest.get("close"),
                "ma_short": latest.get("ma_short"),
                "ma_long": latest.get("ma_long"),
                "dif": latest.get("dif"),
                "dea": latest.get("dea"),
                "macd_hist": latest.get("macd_hist"),
                "ret20": latest.get("ret20"),
                "ret60": latest.get("ret60"),
            },
            "data_confidence": "medium" if missing_data else "high",
            "missing_data": missing_data,
        }
        stock_scores.append(score_row)
        if code in research_only_codes:
            actions.append(research_action_for_target(holding, latest, params))
        else:
            actions.append(action_for_holding(holding, score, latest, params, total_assets, missing_data))

    sorted_scores = sorted(stock_scores, key=lambda x: x["scores"]["total_score"], reverse=True)
    inputs = market_inputs if isinstance(market_inputs, dict) else {}
    latest_trade_date = _iso_trade_date(inputs.get("latest_trade_date"))
    history = sanitize_market_history(
        inputs.get("market_history"), latest_trade_date
    )
    recent_trade_dates: List[str] = []
    recent_values = inputs.get("recent_trade_dates")
    if not isinstance(recent_values, list):
        recent_values = []
    if latest_trade_date:
        for value in [
            latest_trade_date,
            *recent_values,
            *(
                row.get("trade_date")
                for row in reversed(history)
                if isinstance(row, dict)
            ),
        ]:
            if not isinstance(value, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", value
            ):
                continue
            trade_date = _iso_trade_date(value)
            if (
                trade_date
                and trade_date <= latest_trade_date
                and trade_date not in recent_trade_dates
            ):
                recent_trade_dates.append(trade_date)

    initial_evidence = inputs.get("evidence_index")
    evidence_index = (
        [dict(row) if isinstance(row, dict) else row for row in initial_evidence]
        if isinstance(initial_evidence, list)
        else []
    )
    generated_evidence_ids: set[str] = set()

    def add_evidence(row: Dict[str, Any]) -> None:
        evidence_id = row.get("evidence_id")
        if evidence_id not in generated_evidence_ids:
            evidence_index.append(row)
            generated_evidence_ids.add(evidence_id)

    news_items = market_news_items(market_news, limit=80)
    news_meta = (
        market_news.get("meta")
        if isinstance(market_news, dict)
        and isinstance(market_news.get("meta"), dict)
        else {}
    )
    news_stale_state = (
        news_meta["stale"]
        if "stale" in news_meta
        else SOURCE_STALE_UNSET
    )
    scoring_news_items = news_items if news_stale_state is False else []
    rankings = (
        inputs.get("board_rankings")
        if isinstance(inputs.get("board_rankings"), dict)
        else {}
    )
    details = (
        inputs.get("board_details")
        if isinstance(inputs.get("board_details"), dict)
        else {}
    )
    candidates = select_board_candidates(
        rankings,
        scoring_news_items,
        limit=12,
        latest_trade_date=latest_trade_date or None,
    )
    current_details: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        board_id = str(candidate.get("board_id") or "")
        board_evidence_id = f"board:{board_id}"
        candidate["evidence_ids"] = [board_evidence_id]
        board_change, board_change_valid = format_evidence_number(
            candidate.get("change_pct"), 2
        )
        board_turnover, board_turnover_valid = format_evidence_number(
            candidate.get("turnover_yuan"), 0, minimum=0.0
        )
        add_evidence(
            evidence_from_source(
                board_evidence_id,
                "board",
                (
                    f"{candidate.get('name') or board_id}涨跌幅 "
                    f"{board_change}{'%' if board_change_valid else ''}，"
                    f"成交额 {board_turnover}{' 元' if board_turnover_valid else ''}"
                ),
                "DangInvest board rankings",
                candidate.get("as_of"),
                latest_trade_date,
                recent_trade_dates,
                board_id,
                "high" if board_change_valid and board_turnover_valid else "low",
                stale=(
                    candidate["stale"]
                    if "stale" in candidate
                    else SOURCE_STALE_UNSET
                ),
                require_exact_stale=True,
            )
        )

        candidate_name = str(candidate.get("name") or "")
        for news_index, news in enumerate(news_items):
            text = f"{news.get('title', '')} {news.get('content', '')}".strip()
            if not candidate_name or candidate_name not in text:
                continue
            news_evidence_id = f"news:{board_id}:{news_index}"
            candidate["evidence_ids"].append(news_evidence_id)
            add_evidence(
                evidence_from_source(
                    news_evidence_id,
                    "news",
                    text[:240],
                    str(news.get("source") or "market-news"),
                    news.get("published_at"),
                    latest_trade_date,
                    recent_trade_dates,
                    board_id,
                    "medium",
                    stale=news_stale_state,
                    require_exact_stale=True,
                    url=news.get("url"),
                )
            )

        detail = details.get(board_id)
        if not isinstance(detail, dict) or not board_evidence_is_current(
            candidate, detail, latest_trade_date
        ):
            continue
        detail_copy = {**detail, "items": []}
        detail_items = detail.get("items", [])
        if not isinstance(detail_items, list):
            detail_items = []
        for item in detail_items:
            if not isinstance(item, dict):
                continue
            item_copy = dict(item)
            code = normalize_provider_stock_code(item_copy.get("code"))
            if not code:
                continue
            item_copy["code"] = code
            constituent_id = f"constituent:{board_id}:{code}"
            item_copy["evidence_ids"] = [constituent_id]
            detail_copy["items"].append(item_copy)
            item_change, item_change_valid = format_evidence_number(
                item_copy.get("change_pct"), 2
            )
            item_turnover, item_turnover_valid = format_evidence_number(
                item_copy.get("turnover_yuan"), 0, minimum=0.0
            )
            add_evidence(
                evidence_from_source(
                    constituent_id,
                    "constituent",
                    (
                        f"{code} {item_copy.get('name') or code}涨跌幅 "
                        f"{item_change}{'%' if item_change_valid else ''}，"
                        f"成交额 {item_turnover}{' 元' if item_turnover_valid else ''}"
                    ),
                    "DangInvest board detail",
                    detail.get("as_of"),
                    latest_trade_date,
                    recent_trade_dates,
                    board_id,
                    "high" if item_change_valid and item_turnover_valid else "low",
                    stale=(
                        detail["stale"]
                        if "stale" in detail
                        else SOURCE_STALE_UNSET
                    ),
                    require_exact_stale=True,
                )
            )
        current_details[board_id] = detail_copy

    scored_mainlines = score_mainline_candidates(
        candidates,
        current_details,
        scoring_news_items,
        history,
        latest_trade_date=latest_trade_date or None,
    )
    held_codes = {
        str(row.get("code"))
        for row in positions.get("holdings", [])
        if isinstance(row, dict) and row.get("code")
    }
    mainlines = finalize_mainlines(
        scored_mainlines, current_details, held_codes
    )
    for line in mainlines:
        chain = build_fact_logic_chain(line, evidence_index)
        line["logic_chain"] = chain
        line["continuation_conditions"] = chain["continuation_conditions"]
        line["invalidation_conditions"] = chain["invalidation_conditions"]
        line["risk"] = (
            "主线识别是条件化研究结论；板块快速轮动、证据过期或反证出现时必须降级。"
        )

    normalized_indices = inputs.get("normalized_indices", indices)
    if not isinstance(normalized_indices, list):
        normalized_indices = []
    breadth = inputs.get("breadth")
    if not isinstance(breadth, dict):
        breadth = {}
    market_snapshot = build_market_snapshot(
        normalized_indices, breadth, latest_trade_date
    )
    normalized_indices = list(market_snapshot.get("indices", []))
    market_snapshot.update(
        {
            "trading_session": latest_trade_date or "unknown",
            "style_divergence": (
                f"指数涨跌幅极差 {market_snapshot.get('index_divergence_pct')}%"
                if normalized_indices
                else None
            ),
            "risk_appetite": market_snapshot.get("regime"),
        }
    )

    holding_map = {
        str(row.get("code")): row
        for row in positions.get("holdings", [])
        if isinstance(row, dict) and row.get("code")
    }
    for score_row in sorted_scores:
        code = str(score_row.get("code") or "")
        score_evidence_id = f"stock-score:{code}"
        score_row["evidence_ids"] = [score_evidence_id]
        data = stock_data.get(code)
        source_as_of = None
        if data and data.history and isinstance(data.history[-1], dict):
            source_as_of = data.history[-1].get("date")
        if not source_as_of:
            source_as_of = str(positions.get("snapshot_time") or "")[:10]
        reliability = str(score_row.get("data_confidence") or "low")
        if reliability not in {"high", "medium", "low"}:
            reliability = "low"
        score_values = score_row.get("scores")
        if not isinstance(score_values, dict):
            score_values = {}
        score_text, score_valid = format_evidence_number(
            score_values.get("total_score"), 1
        )
        if not score_valid:
            reliability = "low"
        add_evidence(
            evidence_from_source(
                score_evidence_id,
                "price",
                (
                    f"{code} {score_row.get('name') or holding_map.get(code, {}).get('name') or code}"
                    f"综合评分 {score_text}"
                ),
                "stock-strategy-loop",
                source_as_of,
                latest_trade_date,
                recent_trade_dates,
                code,
                reliability,
            )
        )

    for index, index_row in enumerate(normalized_indices):
        if not isinstance(index_row, dict):
            continue
        code = str(index_row.get("code") or index)
        index_change, index_change_valid = format_evidence_number(
            index_row.get("change_pct"), 2
        )
        add_evidence(
            evidence_from_source(
                f"index:{code}:{index}",
                "index",
                (
                    f"{index_row.get('name') or code}涨跌幅 "
                    f"{index_change}{'%' if index_change_valid else ''}"
                ),
                str(index_row.get("source") or "a-share-data index"),
                index_row.get("as_of"),
                latest_trade_date,
                recent_trade_dates,
                "market",
                "high" if index_change_valid else "low",
                stale=(
                    index_row["stale"]
                    if "stale" in index_row
                    else SOURCE_STALE_UNSET
                ),
            )
        )
    if breadth:
        breadth_as_of = breadth.get("as_of") or breadth.get("trade_date")
        advancers_text, advancers_valid = format_evidence_number(
            breadth.get("advancers"), 0, minimum=0.0
        )
        decliners_text, decliners_valid = format_evidence_number(
            breadth.get("decliners"), 0, minimum=0.0
        )
        breadth_turnover, breadth_turnover_valid = format_evidence_number(
            breadth.get("turnover_yuan"), 0, minimum=0.0
        )
        breadth_numbers_valid = (
            advancers_valid and decliners_valid and breadth_turnover_valid
        )
        add_evidence(
            evidence_from_source(
                f"breadth:{breadth_as_of or 'unknown'}",
                "breadth",
                (
                    f"上涨 {advancers_text}、下跌 {decliners_text}、"
                    f"成交额 {breadth_turnover}"
                ),
                str(breadth.get("source") or "a-share-data all-quote"),
                breadth_as_of,
                latest_trade_date,
                recent_trade_dates,
                "market",
                (
                    "high"
                    if breadth.get("complete") is True and breadth_numbers_valid
                    else "low"
                ),
                stale=(
                    breadth["stale"]
                    if "stale" in breadth
                    else SOURCE_STALE_UNSET
                ),
            )
        )

    panorama = build_industry_panorama(sorted_scores)
    portfolio_diagnosis = build_portfolio_diagnosis(
        positions, mainlines, sorted_scores, actions
    )
    holding_analyses = build_holding_analyses(
        positions, mainlines, sorted_scores, panorama, actions
    )
    coverage = build_data_coverage(
        positions,
        stock_data,
        board_summaries,
        normalized_indices,
        market_news,
        data_errors,
    )
    coverage.update(
        {
            "breadth": 1 if breadth else 0,
            "board_details": len(details),
            "mainline_history_sessions": len(
                {
                    _iso_trade_date(row.get("trade_date"))
                    for row in history
                    if isinstance(row, dict)
                    and _iso_trade_date(row.get("trade_date"))
                }
            ),
            "market_trade_date": latest_trade_date or None,
        }
    )
    return {
        "report_schema_version": 2,
        "generated_at": now_str(),
        "snapshot_time": positions.get("snapshot_time"),
        "data_coverage": coverage,
        "evidence_index": evidence_index,
        "market_snapshot": market_snapshot,
        "market_mainlines": mainlines,
        "market_outlook": build_market_outlook(market_snapshot, mainlines),
        "portfolio_diagnosis": portfolio_diagnosis,
        "holding_analyses": holding_analyses,
        "market_regime": market_regime,
        "market_news_context": summarize_market_news(market_news),
        "sector_context": {
            "matched_note": "sector scores use current industry labels matched to market board summaries when available",
            "board_source": "DangInvest via a-share-data fetch_danginvest.py",
        },
        "industry_panorama": panorama,
        "stock_scores": sorted_scores,
        "portfolio_actions": actions,
    }


def score_for_backtest_day(
    history: List[Dict[str, Any]],
    idx: int,
    params: Dict[str, Any],
) -> float:
    row = history[idx]
    prev = history[idx - 1] if idx > 0 else None
    return score_from_row(row, prev, [], 0.0, 0.0, params)["total_score"]


def is_untradable(row: Dict[str, Any]) -> bool:
    return safe_float(row.get("open")) <= 0 or safe_float(row.get("close")) <= 0 or safe_float(row.get("volume")) <= 0


def valuation_price(row: Optional[Dict[str, Any]], last_close: float, field: str) -> float:
    price = safe_float((row or {}).get(field))
    return price if price > 0 else last_close


def portfolio_value(
    cash: float,
    shares: Dict[str, float],
    rows: Dict[str, Dict[str, Any]],
    last_closes: Dict[str, float],
    field: str,
) -> float:
    return cash + sum(
        quantity * valuation_price(rows.get(code), last_closes.get(code, 0.0), field)
        for code, quantity in shares.items()
    )


def run_backtest(
    histories: Dict[str, List[Dict[str, Any]]],
    params: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    enriched = {code: enrich_indicators([dict(x) for x in hist], params) for code, hist in histories.items() if hist}
    by_date: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for code, hist in enriched.items():
        for row in hist:
            if start_date and row["date"] < start_date:
                continue
            if end_date and row["date"] > end_date:
                continue
            by_date.setdefault(row["date"], {})[code] = row
    dates = sorted(by_date)
    if len(dates) < 140:
        return {"status": "insufficient_data", "dates": len(dates), "metrics": {}, "trades": []}

    cash = 1_000_000.0
    shares: Dict[str, float] = {}
    avg_cost: Dict[str, float] = {}
    last_closes: Dict[str, float] = {}
    equity_curve: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    cost_rate = safe_float(params.get("rebalance_cost_bps")) / 10000
    max_holdings = int(params["max_holdings"])
    max_single = safe_float(params["max_single_weight"])

    for i in range(120, len(dates) - 1):
        signal_date = dates[i]
        exec_date = dates[i + 1]
        signal_rows = by_date[signal_date]
        exec_rows = by_date[exec_date]
        current_equity = portfolio_value(cash, shares, exec_rows, last_closes, "open")
        if current_equity <= 0:
            break
        scored: List[Tuple[str, float]] = []
        for code, row in signal_rows.items():
            hist = enriched.get(code, [])
            idx = next((j for j, x in enumerate(hist) if x["date"] == signal_date), -1)
            if idx < 120 or code not in exec_rows:
                continue
            score = score_for_backtest_day(hist, idx, params)
            if score >= safe_float(params["hold_score"]):
                scored.append((code, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [x for x in scored[:max_holdings] if x[1] >= safe_float(params["entry_score"])]
        score_sum = sum(x[1] for x in selected) or 1.0
        targets = {code: min(max_single, score / score_sum) for code, score in selected}

        for code in sorted(set(list(shares) + list(targets))):
            row = exec_rows.get(code)
            if not row or is_untradable(row):
                continue
            open_price = safe_float(row["open"])
            target_value = current_equity * targets.get(code, 0.0)
            current_value = shares.get(code, 0.0) * open_price
            delta_value = target_value - current_value
            if abs(delta_value) < current_equity * 0.002:
                continue
            trade_cost = abs(delta_value) * cost_rate
            qty_delta = (delta_value - math.copysign(trade_cost, delta_value)) / open_price
            if delta_value > 0 and cash < delta_value + trade_cost:
                delta_value = max(0.0, cash / (1 + cost_rate))
                qty_delta = delta_value / open_price
                trade_cost = delta_value * cost_rate
            if abs(qty_delta) <= 0:
                continue
            old_qty = shares.get(code, 0.0)
            new_qty = old_qty + qty_delta
            realized = 0.0
            if qty_delta < 0:
                sell_qty = min(old_qty, -qty_delta)
                realized = (open_price - avg_cost.get(code, open_price)) * sell_qty - trade_cost
            if new_qty <= 1e-8:
                shares.pop(code, None)
                avg_cost.pop(code, None)
            else:
                if qty_delta > 0:
                    old_cost_value = avg_cost.get(code, open_price) * old_qty
                    avg_cost[code] = (old_cost_value + open_price * qty_delta + trade_cost) / new_qty
                shares[code] = new_qty
            cash -= qty_delta * open_price + trade_cost
            trades.append(
                {
                    "date": exec_date,
                    "code": code,
                    "side": "buy" if qty_delta > 0 else "sell",
                    "price": round(open_price, 4),
                    "shares": round(abs(qty_delta), 4),
                    "value": round(abs(delta_value), 2),
                    "cost": round(trade_cost, 2),
                    "realized_pnl": round(realized, 2),
                }
            )

        for code, row in exec_rows.items():
            close = safe_float(row.get("close"))
            if close > 0:
                last_closes[code] = close
        close_equity = portfolio_value(cash, shares, exec_rows, last_closes, "close")
        equity_curve.append({"date": exec_date, "equity": round(close_equity, 2)})

    metrics = compute_metrics(equity_curve, trades)
    return {
        "status": "ok",
        "params": params,
        "start_date": equity_curve[0]["date"] if equity_curve else None,
        "end_date": equity_curve[-1]["date"] if equity_curve else None,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "trades": trades,
    }


def compute_metrics(equity_curve: List[Dict[str, Any]], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(equity_curve) < 2:
        return {}
    equities = [safe_float(x["equity"]) for x in equity_curve]
    returns = [(equities[i] / equities[i - 1] - 1) for i in range(1, len(equities)) if equities[i - 1] > 0]
    total_return = equities[-1] / equities[0] - 1
    years = len(equity_curve) / 244
    annualized = (equities[-1] / equities[0]) ** (1 / years) - 1 if years > 0 and equities[0] > 0 else 0.0
    peak = equities[0]
    drawdowns = []
    for equity in equities:
        peak = max(peak, equity)
        drawdowns.append(equity / peak - 1 if peak else 0)
    max_drawdown = min(drawdowns) if drawdowns else 0.0
    sharpe = 0.0
    if len(returns) > 2 and statistics.pstdev(returns) > 0:
        sharpe = statistics.mean(returns) / statistics.pstdev(returns) * math.sqrt(244)
    realized = [safe_float(t.get("realized_pnl")) for t in trades if t.get("side") == "sell"]
    wins = [x for x in realized if x > 0]
    losses = [x for x in realized if x < 0]
    max_consecutive_losses = 0
    streak = 0
    for pnl in realized:
        if pnl < 0:
            streak += 1
            max_consecutive_losses = max(max_consecutive_losses, streak)
        else:
            streak = 0
    turnover = sum(safe_float(t.get("value")) for t in trades) / max(equities[0], 1)
    return {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(annualized * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe": round(sharpe, 3),
        "win_rate_pct": round(len(wins) / len(realized) * 100, 2) if realized else 0.0,
        "profit_loss_ratio": round((statistics.mean(wins) / abs(statistics.mean(losses))) if wins and losses else 0.0, 3),
        "trade_count": len(trades),
        "turnover": round(turnover, 3),
        "max_single_trade_loss": round(min(losses), 2) if losses else 0.0,
        "max_consecutive_losses": max_consecutive_losses,
    }


def risk_adjusted_score(metrics: Dict[str, Any]) -> float:
    return (
        safe_float(metrics.get("annualized_return_pct")) / 100
        + 0.15 * safe_float(metrics.get("sharpe"))
        + safe_float(metrics.get("max_drawdown_pct")) / 100 * 1.2
    )


def candidate_params(base: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = [base]
    variations = [
        {"entry_score": -4, "hold_score": -3},
        {"entry_score": 4, "hold_score": 3},
        {"weights": {"trend": 0.50, "macd": 0.22, "fund_flow": 0.12, "sector": 0.10, "event": 0.06}},
        {"weights": {"trend": 0.34, "macd": 0.30, "fund_flow": 0.20, "sector": 0.10, "event": 0.06}},
        {"stop_loss_pct": -6.0, "take_profit_pct": 16.0},
        {"stop_loss_pct": -10.0, "take_profit_pct": 22.0},
    ]
    for change in variations:
        item = json.loads(json.dumps(base))
        for key, value in change.items():
            if key == "weights":
                item[key] = value
            elif key in {"stop_loss_pct", "take_profit_pct"}:
                item[key] = value
            elif isinstance(value, (int, float)) and isinstance(item.get(key), (int, float)):
                item[key] = item[key] + value
            else:
                item[key] = value
        candidates.append(item)
    return candidates


def optimize_params(
    histories: Dict[str, List[Dict[str, Any]]],
    current: Dict[str, Any],
    comparable_live_inputs: bool = True,
) -> Dict[str, Any]:
    if not comparable_live_inputs:
        return {
            "status": "skipped",
            "reason": "historical five-factor inputs are unavailable; do not optimize live parameters from a technical-only backtest",
            "selected_params": current,
        }
    all_dates = sorted({row["date"] for hist in histories.values() for row in hist})
    if len(all_dates) < 300:
        return {
            "status": "skipped",
            "reason": "insufficient dates for walk-forward optimization",
            "selected_params": current,
        }
    split = int(len(all_dates) * 0.7)
    train_end = all_dates[split]
    valid_start = all_dates[split + 1] if split + 1 < len(all_dates) else train_end
    base_valid = run_backtest(histories, current, start_date=valid_start)
    base_metrics = base_valid.get("metrics", {})
    base_score = risk_adjusted_score(base_metrics)
    results = []
    selected = current
    selected_reason = "kept current params"
    selected_score = base_score
    for params in candidate_params(current):
        train = run_backtest(histories, params, end_date=train_end)
        valid = run_backtest(histories, params, start_date=valid_start)
        metrics = valid.get("metrics", {})
        score = risk_adjusted_score(metrics)
        accepted = False
        if metrics:
            required = max(abs(base_score) * 0.05, 0.02)
            drawdown_ok = abs(safe_float(metrics.get("max_drawdown_pct"))) <= abs(safe_float(base_metrics.get("max_drawdown_pct"))) * 1.10 + 0.01
            trades_ok = safe_float(metrics.get("trade_count")) >= 30
            loss_ok = safe_float(metrics.get("max_single_trade_loss")) >= safe_float(base_metrics.get("max_single_trade_loss")) * 1.15
            accepted = score - base_score >= required and drawdown_ok and trades_ok and loss_ok
        results.append(
            {
                "params": params,
                "train_metrics": train.get("metrics", {}),
                "validation_metrics": metrics,
                "validation_score": round(score, 4),
                "accepted": accepted,
            }
        )
        if accepted and score > selected_score:
            selected = params
            selected_score = score
            selected_reason = "candidate improved sample-out risk-adjusted score without breaching guardrails"
    return {
        "status": "ok",
        "train_end": train_end,
        "validation_start": valid_start,
        "base_validation_score": round(base_score, 4),
        "selected_validation_score": round(selected_score, 4),
        "selected_params": selected,
        "selected_reason": selected_reason,
        "candidates": results,
    }


def write_report(
    path: Path,
    positions: Dict[str, Any],
    signal: Dict[str, Any],
    backtest: Dict[str, Any],
    optimization: Dict[str, Any],
    data_errors: List[str],
    title: str = "股票策略闭环报告",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_report(
            positions,
            signal,
            backtest,
            optimization,
            data_errors,
            title,
        ),
        encoding="utf-8",
    )


def validate_strategy_params(params: Any) -> List[str]:
    if not isinstance(params, dict):
        return ["strategy params must be an object"]

    errors: List[str] = []
    required = set(DEFAULT_PARAMS)
    missing = sorted(required - set(params))
    if missing:
        errors.append("strategy params missing keys: " + ", ".join(missing))

    integer_fields = {
        "version",
        "ma_short",
        "ma_long",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "max_holdings",
    }
    for field in required - {"weights"}:
        value = params.get(field)
        if field in integer_fields:
            valid_number = type(value) is int
        else:
            valid_number = type(value) in (int, float)
        if not valid_number:
            errors.append(f"strategy params {field} must be a strict number")
            continue
        try:
            if not math.isfinite(value):
                errors.append(f"strategy params {field} must be finite")
        except OverflowError:
            errors.append(f"strategy params {field} must be finite")

    weights = params.get("weights")
    if not isinstance(weights, dict):
        errors.append("strategy params weights must be an object")
        weights = {}
    weight_fields = set(DEFAULT_PARAMS["weights"])
    missing_weights = sorted(weight_fields - set(weights))
    if missing_weights:
        errors.append(
            "strategy params weights missing keys: "
            + ", ".join(missing_weights)
        )
    valid_weights: List[float] = []
    for field in weight_fields:
        value = weights.get(field)
        if type(value) not in (int, float):
            errors.append(
                f"strategy params weights.{field} must be a strict number"
            )
            continue
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            errors.append(f"strategy params weights.{field} must be finite")
        elif value < 0 or value > 1:
            errors.append(
                f"strategy params weights.{field} must be between 0 and 1"
            )
        else:
            valid_weights.append(float(value))
    if len(valid_weights) == len(weight_fields) and not math.isclose(
        sum(valid_weights), 1.0, abs_tol=1e-9
    ):
        errors.append("strategy params weights must sum to 1")

    def number(field: str) -> Optional[float]:
        value = params.get(field)
        if type(value) not in (int, float):
            return None
        try:
            return float(value) if math.isfinite(value) else None
        except OverflowError:
            return None

    if type(params.get("version")) is int and params["version"] != DEFAULT_PARAMS["version"]:
        errors.append(f"strategy params version must equal {DEFAULT_PARAMS['version']}")
    ma_short, ma_long = number("ma_short"), number("ma_long")
    if ma_short is not None and ma_long is not None and not (0 < ma_short < ma_long):
        errors.append("strategy params require 0 < ma_short < ma_long")
    macd_fast, macd_slow = number("macd_fast"), number("macd_slow")
    if macd_fast is not None and macd_slow is not None and not (
        0 < macd_fast < macd_slow
    ):
        errors.append("strategy params require 0 < macd_fast < macd_slow")
    macd_signal = number("macd_signal")
    if macd_signal is not None and macd_signal <= 0:
        errors.append("strategy params macd_signal must be positive")

    entry, hold, reduce = (
        number("entry_score"),
        number("hold_score"),
        number("reduce_score"),
    )
    if None not in (entry, hold, reduce) and not (
        0 <= reduce <= hold <= entry <= 100
    ):
        errors.append(
            "strategy params require 0 <= reduce_score <= hold_score <= entry_score <= 100"
        )
    max_holdings = number("max_holdings")
    if max_holdings is not None and not (1 <= max_holdings <= 8):
        errors.append("strategy params max_holdings must be between 1 and 8")
    max_weight = number("max_single_weight")
    if max_weight is not None and not (0 < max_weight <= 0.15):
        errors.append(
            "strategy params max_single_weight must be greater than 0 and at most 0.15"
        )
    stop_loss = number("stop_loss_pct")
    if stop_loss is not None and not (-100 < stop_loss < 0):
        errors.append("strategy params stop_loss_pct must be between -100 and 0")
    take_profit = number("take_profit_pct")
    trailing = number("trailing_profit_pct")
    if take_profit is not None and not (0 < take_profit <= 100):
        errors.append("strategy params take_profit_pct must be between 0 and 100")
    if trailing is not None and take_profit is not None and not (
        0 < trailing <= take_profit
    ):
        errors.append(
            "strategy params trailing_profit_pct must be positive and no greater than take_profit_pct"
        )
    for field in ("roundtrip_cost_bps", "rebalance_cost_bps"):
        value = number(field)
        if value is not None and not (0 <= value <= 1000):
            errors.append(f"strategy params {field} must be between 0 and 1000")
    return errors


def load_strategy_params(
    paths: Dict[str, Path],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    current = paths["params"] / "strategy_params.json"
    if not current.exists():
        params = json.loads(json.dumps(DEFAULT_PARAMS))
    else:
        try:
            params = read_json(current)
        except (OSError, ValueError, TypeError) as exc:
            return None, [f"strategy_params.json: {exc}"]
    errors = validate_strategy_params(params)
    return (params if not errors else None), errors


def transaction_journal_path(paths: Dict[str, Path]) -> Path:
    return paths["state"] / TRANSACTION_JOURNAL_NAME


def _validated_transaction_target(
    paths: Dict[str, Path], relative_path: str
) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("journal target path must be a non-empty string")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ValueError(f"invalid journal target path: {relative_path}")
    parts = pure.parts
    allowed = False
    if len(parts) == 2 and parts[0] == "params":
        filename = parts[1]
        if filename == "strategy_params.json":
            allowed = True
        else:
            match = re.fullmatch(
                r"strategy_params_(\d{4}-\d{2}-\d{2})\.json", filename
            )
            allowed = bool(
                match and _iso_trade_date(match.group(1)) == match.group(1)
            )
    elif parts == ("market-history", "market_snapshots.jsonl"):
        allowed = True
    elif parts == ("state", "loop_state.json"):
        allowed = True
    elif parts in (
        ("positions", "latest_screenshots.json"),
        ("positions", "positions.json"),
    ):
        allowed = True
    if not allowed:
        raise ValueError(f"journal target is outside the persistence allowlist: {relative_path}")

    root = paths["root"].resolve()
    target = paths["root"].joinpath(*parts)
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ValueError(f"journal target escapes loop root: {relative_path}") from exc
    return target


def _relative_transaction_target(paths: Dict[str, Path], path: Path) -> str:
    root = paths["root"].resolve()
    try:
        relative = path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"transaction target escapes loop root: {path}") from exc
    _validated_transaction_target(paths, relative)
    return relative


def prepare_persistence_journal(
    paths: Dict[str, Path], targets: Sequence[Path]
) -> Path:
    journal = transaction_journal_path(paths)
    if lstat_path_entry(journal) is not None:
        raise FileExistsError(f"unfinished persistence journal exists: {journal}")
    entries: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw_path in targets:
        path = Path(raw_path)
        relative = _relative_transaction_target(paths, path)
        if relative in seen:
            raise ValueError(f"duplicate transaction target: {relative}")
        seen.add(relative)
        existed = path.exists()
        original = path.read_bytes() if existed else None
        entries.append(
            {
                "path": relative,
                "existed": existed,
                "content_b64": (
                    base64.b64encode(original).decode("ascii")
                    if original is not None
                    else None
                ),
            }
        )
    if not entries:
        raise ValueError("persistence journal requires at least one target")
    atomic_write_json(journal, {"version": 1, "entries": entries})
    return journal


def _validated_journal_entries(
    paths: Dict[str, Path], payload: Any
) -> List[Tuple[Path, Optional[bytes]]]:
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != 1
    ):
        raise ValueError("unsupported or malformed persistence journal")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("persistence journal entries must be a non-empty list")
    entries: List[Tuple[Path, Optional[bytes]]] = []
    seen: set[Path] = set()
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise ValueError(f"journal entry {index} must be an object")
        target = _validated_transaction_target(paths, entry.get("path"))
        if target in seen:
            raise ValueError(f"duplicate journal target: {entry.get('path')}")
        seen.add(target)
        existed = entry.get("existed")
        if type(existed) is not bool:
            raise ValueError(f"journal entry {index} existed must be boolean")
        encoded = entry.get("content_b64")
        if existed:
            if not isinstance(encoded, str):
                raise ValueError(f"journal entry {index} content_b64 must be a string")
            try:
                original = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError, TypeError) as exc:
                raise ValueError(f"journal entry {index} has invalid base64") from exc
        else:
            if encoded is not None:
                raise ValueError(f"journal entry {index} absent file must have null content")
            original = None
        entries.append((target, original))
    return entries


def restore_file_bytes(path: Path, original: Optional[bytes]) -> None:
    """Restore bytes atomically without using the high-level JSON writer."""
    if original is None:
        if path.is_symlink() or path.is_file():
            path.unlink()
            fsync_directory(path.parent)
        elif path.exists():
            raise IsADirectoryError(str(path))
        return
    atomic_write_bytes(path, original)


def capture_regular_file_bytes(
    paths: Sequence[Path],
) -> List[Tuple[Path, Optional[bytes]]]:
    """Capture internal output files without following links or reparse points."""
    captured: List[Tuple[Path, Optional[bytes]]] = []
    for path in paths:
        status = lstat_path_entry(path)
        if status is None:
            captured.append((path, None))
            continue
        if (
            stat.S_ISLNK(status.st_mode)
            or is_reparse_point(status)
            or not stat.S_ISREG(status.st_mode)
        ):
            raise OSError(f"output path must be a regular file: {path}")
        captured.append((path, path.read_bytes()))
    return captured


def restore_captured_files(
    captured: Sequence[Tuple[Path, Optional[bytes]]],
) -> List[str]:
    errors: List[str] = []
    for path, original in reversed(captured):
        try:
            restore_file_bytes(path, original)
        except KeyboardInterrupt:
            try:
                restore_file_bytes(path, original)
            except (Exception, KeyboardInterrupt) as exc:
                errors.append(f"{path}: {exc}")
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    return errors


def remove_persistence_journal(paths: Dict[str, Path]) -> None:
    journal = transaction_journal_path(paths)
    journal.unlink()
    fsync_directory(journal.parent)


def recover_pending_transaction(
    paths: Dict[str, Path]
) -> Tuple[bool, List[str]]:
    journal = transaction_journal_path(paths)
    try:
        journal_status = lstat_path_entry(journal)
    except OSError as exc:
        return False, [f"journal validation: unable to inspect journal path: {exc}"]
    if journal_status is None:
        return True, []
    if (
        stat.S_ISLNK(journal_status.st_mode)
        or is_reparse_point(journal_status)
        or not stat.S_ISREG(journal_status.st_mode)
    ):
        return False, ["journal validation: journal path must be a regular file"]
    try:
        entries = _validated_journal_entries(paths, read_json(journal))
    except Exception as exc:
        return False, [f"journal validation: {exc}"]

    errors: List[str] = []
    for path, original in reversed(entries):
        try:
            restore_file_bytes(path, original)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        return False, errors
    try:
        remove_persistence_journal(paths)
    except Exception as exc:
        return False, [f"journal removal: {exc}"]
    return True, []


def persist_loop_progress(
    paths: Dict[str, Path],
    run_date: str,
    params: Dict[str, Any],
    selected_params: Dict[str, Any],
    history_path: Path,
    current_market_row: Optional[Dict[str, Any]],
    state_path: Path,
    state: Dict[str, Any],
    account_manifest: Optional[Dict[str, Any]] = None,
    account_positions: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str], List[str]]:
    """Persist account inputs, params, history, and state as one recoverable unit."""
    dated_params_path = paths["params"] / f"strategy_params_{run_date}.json"
    current_params_path = paths["params"] / "strategy_params.json"
    changed_params = selected_params != params
    write_current_params = changed_params or not current_params_path.exists()
    targets: List[Path] = []
    write_account_inputs = (
        account_manifest is not None and account_positions is not None
    )
    if (account_manifest is None) != (account_positions is None):
        return False, ["account inputs: manifest and positions must be provided together"], []
    if write_account_inputs:
        targets.extend(
            (
                paths["positions"] / "latest_screenshots.json",
                paths["positions"] / "positions.json",
            )
        )
    if changed_params:
        targets.append(dated_params_path)
    if write_current_params:
        targets.append(current_params_path)
    if current_market_row is not None:
        targets.append(history_path)
    targets.append(state_path)

    try:
        prepare_persistence_journal(paths, targets)
    except Exception as exc:
        return False, [f"journal: {exc}"], []

    phase = "persistence"
    try:
        if write_account_inputs:
            phase = "latest_screenshots"
            write_json(
                paths["positions"] / "latest_screenshots.json", account_manifest
            )
            phase = "positions"
            write_json(paths["positions"] / "positions.json", account_positions)
        if changed_params:
            phase = "dated_params"
            write_json(dated_params_path, selected_params)
        if write_current_params:
            phase = "current_params"
            write_json(current_params_path, selected_params)
        if current_market_row is not None:
            phase = "market_history"
            append_market_snapshot(history_path, current_market_row)
        phase = "loop_state"
        write_json(state_path, state)
    except Exception as exc:
        recovered, rollback_errors = recover_pending_transaction(paths)
        if recovered:
            rollback_errors = []
        return False, [f"{phase}: {exc}"], rollback_errors
    try:
        remove_persistence_journal(paths)
    except Exception as exc:
        recovered, rollback_errors = recover_pending_transaction(paths)
        if recovered:
            rollback_errors = []
        return False, [f"journal commit: {exc}"], rollback_errors
    return True, [], []


def collect_stock_data_for_holding(
    holding: Dict[str, Any],
    quotes: Dict[str, Dict[str, Any]],
    sectors: Dict[str, Dict[str, Any]],
    a_share_skill: Path,
    start: str,
    end: str,
    include_events: bool,
) -> Tuple[str, StockData, List[str]]:
    code = holding["code"]
    quote = quotes.get(code, {})
    display_name = str(quote.get(K_NAME) or quote.get("f14") or holding["name"] or code)
    item_errors: List[str] = []
    history, hist_err = fetch_history(code, start, end, a_share_skill)
    if hist_err:
        item_errors.append(f"history {code}: {hist_err}")
    fund_flow, flow_err = fetch_fund_flow(code, a_share_skill)
    if flow_err:
        item_errors.append(f"fund_flow {code}: {flow_err}")
    events: Dict[str, Any] = {}
    if include_events:
        events, event_err = fetch_events(code, display_name, a_share_skill)
        if event_err:
            item_errors.append(f"events {code}: {event_err}")
    sector = sectors.get(code, {})
    return (
        code,
        StockData(
            code=code,
            name=display_name,
            history=history,
            quote=quote,
            industry=str(sector.get("industry", "")),
            fund_flow=fund_flow,
            events=events,
        ),
        item_errors,
    )


def collect_data(
    positions: Dict[str, Any],
    a_share_skill: Path,
    start: str,
    end: str,
    include_events: bool,
) -> CollectedData:
    codes = [h["code"] for h in positions["holdings"]]
    errors: List[str] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        quotes_future = executor.submit(fetch_quotes, codes, a_share_skill)
        sectors_future = executor.submit(fetch_sector_info, codes, a_share_skill)
        indices_future = executor.submit(fetch_indices, a_share_skill)
        news_future = executor.submit(fetch_market_news, a_share_skill)
        rankings_future = executor.submit(fetch_board_rankings, a_share_skill)
        breadth_future = executor.submit(fetch_market_breadth, a_share_skill, end)

        market_news, news_err = news_future.result()
        board_rankings, latest_trade_date, board_errors = rankings_future.result()
        news_rows = market_news_items(market_news, limit=80)
        candidates = select_board_candidates(
            board_rankings,
            news_rows,
            limit=12,
            latest_trade_date=latest_trade_date,
        )
        details_future = executor.submit(fetch_board_details, candidates, a_share_skill)
        quotes, quote_errors = quotes_future.result()
        sectors, sector_err = sectors_future.result()
        raw_indices, index_err = indices_future.result()
        breadth, breadth_error = breadth_future.result()
        board_details, detail_errors = details_future.result()

    indices = normalize_indices(raw_indices, latest_trade_date)
    if breadth:
        breadth["trade_date"] = latest_trade_date
        breadth["as_of"] = latest_trade_date
    board_summaries = {
        mode: {
            "data": [
                {
                    "groupKey": row["group_key"],
                    "groupLabel": row["name"],
                    "changePct": row["change_pct"],
                    "totalTurnoverYuan": row["turnover_yuan"],
                }
                for row in board_rankings.get(mode, {}).get("change_desc", [])
            ]
        }
        for mode in ("major", "sub", "concept")
    }
    errors.extend(quote_errors)
    if sector_err:
        errors.append(f"sector: {sector_err}")
    missing_sector_codes = [code for code in codes if not sectors.get(code, {}).get("industry")]
    if missing_sector_codes:
        board_sectors, board_sector_err = fetch_danginvest_industry_fallback(missing_sector_codes)
        sectors.update({code: row for code, row in board_sectors.items() if row.get("industry")})
        if board_sector_err:
            errors.append(f"sector_board_fallback: {board_sector_err}")
    for code, quote in quotes.items():
        if code not in sectors or not sectors.get(code, {}).get("industry"):
            industry = quote.get(K_INDUSTRY) or quote.get("f100")
            name = quote.get(K_NAME) or quote.get("f14")
            if industry or name:
                sectors[code] = {
                    "code": code,
                    "name": name,
                    "industry": industry or "",
                    "source": quote.get(K_DATA_SOURCE, "quote-fallback"),
                    "error": None,
                }
    errors.extend(board_errors)
    errors.extend(detail_errors)
    if news_err:
        errors.append(f"market_news: {news_err}")
    if index_err:
        errors.append(f"indices: {index_err}")
    if breadth_error:
        errors.append(f"market_breadth: {breadth_error}")

    stock_data: Dict[str, StockData] = {}
    workers = min(8, max(1, len(positions["holdings"])))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                collect_stock_data_for_holding,
                holding,
                quotes,
                sectors,
                a_share_skill,
                start,
                end,
                include_events,
            )
            for holding in positions["holdings"]
        ]
        for future in as_completed(futures):
            code, data, item_errors = future.result()
            stock_data[code] = data
            errors.extend(item_errors)
    return CollectedData(
        stock_data=stock_data,
        board_summaries=board_summaries,
        board_rankings=board_rankings,
        board_details=board_details,
        indices=indices,
        breadth=breadth,
        market_news=market_news,
        latest_trade_date=latest_trade_date,
        errors=errors,
    )


def recover_before_command(paths: Dict[str, Path]) -> bool:
    recovered, errors = recover_pending_transaction(paths)
    if recovered:
        return True
    print(
        json.dumps(
            {"status": "recovery_failed", "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return False


def cmd_analyze_targets(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    paths = loop_paths(workspace, args.loop_dir)
    if not recover_before_command(paths):
        return 9
    try:
        codes = parse_target_codes(args.codes)
    except ValueError as exc:
        print(json.dumps({"status": "invalid_targets", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2

    source_positions: Optional[Dict[str, Any]] = None
    positions_path = Path(args.positions_json) if args.positions_json else paths["positions"] / "positions.json"
    if positions_path.exists():
        selected, selection_errors = load_selected_positions(positions_path, args.account)
        if selection_errors:
            print(json.dumps({"status": "invalid_positions", "errors": selection_errors}, ensure_ascii=False, indent=2))
            return 3
        assert selected is not None
        ok, errors, source_positions = validate_positions(selected)
        if not ok:
            print(json.dumps({"status": "invalid_positions", "errors": errors}, ensure_ascii=False, indent=2))
            return 3

    positions = build_target_positions(codes, source_positions)
    params, param_errors = load_strategy_params(paths)
    if param_errors:
        print(
            json.dumps(
                {"status": "invalid_params", "errors": param_errors},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 10
    assert params is not None
    end_date = args.end_date or dt.date.today().isoformat()
    start_date = args.start_date or (dt.date.fromisoformat(end_date) - dt.timedelta(days=365 * args.years + 20)).isoformat()
    collected = collect_data(
        positions, Path(args.a_share_skill), start_date, end_date, include_events=args.include_events
    )
    stock_data = collected.stock_data
    board_summaries = collected.board_summaries
    indices = collected.indices
    market_news = collected.market_news
    data_errors = collected.errors
    for holding in positions["holdings"]:
        data = stock_data.get(holding["code"])
        if data and data.name:
            holding["name"] = data.name
    market_inputs, _ = prepare_market_inputs(
        collected, paths["market_history"] / "market_snapshots.jsonl"
    )
    market = classify_market(indices, board_summaries)
    signal = generate_daily_signal(
        positions,
        stock_data,
        market,
        board_summaries,
        indices,
        market_news,
        data_errors,
        params,
        market_inputs=market_inputs,
    )
    signal["analysis_mode"] = "target_research"
    contract_errors = validate_signal_v2(signal)
    if contract_errors:
        print(
            json.dumps(
                {
                    "status": "invalid_report_contract",
                    "errors": contract_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 6
    histories = {code: data.history for code, data in stock_data.items() if data.history}
    backtest = run_backtest(histories, params, start_date=start_date, end_date=end_date)
    backtest["scope"] = "technical_only_diagnostic"
    optimization = optimize_params(histories, params, comparable_live_inputs=False)
    selected_params = optimization.get("selected_params", params)
    selected_param_errors = validate_strategy_params(selected_params)
    if selected_param_errors:
        print(
            json.dumps(
                {"status": "invalid_params", "errors": selected_param_errors},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 10

    analysis_id = f"{dt.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{'-'.join(codes)}"
    staging_dir = allocate_unique_directory(paths["analyses"], f".{analysis_id}.staging")
    report_path = staging_dir / "analysis.md"
    analysis_manifest = {
        "status": "ok",
        "analysis_mode": "target_research",
        "codes": codes,
        "research_only_codes": positions.get("research_only_codes", []),
        "source_snapshot_time": source_positions.get("snapshot_time") if source_positions else None,
        "generated_at": now_str(),
        "data_error_count": len(data_errors),
    }
    try:
        write_report(
            report_path,
            positions,
            signal,
            backtest,
            optimization,
            data_errors,
            title="目标股票研究报告",
        )
    except (OSError, ValueError) as exc:
        cleanup_error = cleanup_unique_output(staging_dir)
        print(
            json.dumps(
                {
                    "status": "report_write_failed",
                    "errors": [str(exc)],
                    "cleanup_errors": [cleanup_error] if cleanup_error else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 7
    try:
        write_json(staging_dir / "positions.json", positions)
        write_json(staging_dir / "signal.json", signal)
        write_json(staging_dir / "market_data_errors.json", data_errors)
        write_json(staging_dir / "backtest.json", backtest)
        write_json(staging_dir / "analysis_manifest.json", analysis_manifest)
        analysis_dir = publish_staged_directory(
            staging_dir, paths["analyses"], analysis_id
        )
    except (OSError, ValueError, TypeError) as exc:
        cleanup_error = cleanup_unique_output(staging_dir)
        print(
            json.dumps(
                {
                    "status": "artifact_write_failed",
                    "errors": [str(exc)],
                    "cleanup_errors": [cleanup_error] if cleanup_error else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 11
    print(
        json.dumps(
            {
                "status": "ok",
                "analysis_dir": str(analysis_dir),
                "analysis": str(analysis_dir / "analysis.md"),
                "codes": codes,
                "research_only_codes": positions.get("research_only_codes", []),
                "data_error_count": len(data_errors),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_loop(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    paths = loop_paths(workspace, args.loop_dir)
    if not recover_before_command(paths):
        return 9
    manifest = scan_screenshots(workspace)

    positions_path = Path(args.positions_json) if args.positions_json else paths["positions"] / "positions.json"
    if not positions_path.exists():
        print(
            json.dumps(
                {
                    "status": "positions_required",
                    "message": "No positions JSON found. Use Codex vision to extract latest screenshots, then save .stock-loop/positions/positions.json.",
                    "latest_screenshots": manifest.get("latest_screenshots", []),
                    "schema": "see references/positions-schema.md",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    selected_positions, selection_errors = load_selected_positions(positions_path, args.account)
    if selection_errors:
        print(json.dumps({"status": "invalid_positions", "errors": selection_errors}, ensure_ascii=False, indent=2))
        return 3
    assert selected_positions is not None
    ok, errors, positions = validate_positions(selected_positions)
    if not ok:
        print(json.dumps({"status": "invalid_positions", "errors": errors}, ensure_ascii=False, indent=2))
        return 3
    freshness_errors = validate_snapshot_freshness(positions, manifest)
    if freshness_errors:
        print(json.dumps({"status": "stale_positions", "errors": freshness_errors}, ensure_ascii=False, indent=2))
        return 4
    state_path = paths["state"] / "loop_state.json"
    previous_state = read_json(state_path) if state_path.exists() else None
    loop_review = build_loop_review(previous_state, positions)
    if loop_review["status"] == "unchanged_snapshot":
        print(
            json.dumps(
                {
                    "status": "unchanged_snapshot",
                    "snapshot_time": positions.get("snapshot_time"),
                    "message": loop_review["note"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if loop_review["status"] == "stale_snapshot":
        print(
            json.dumps(
                {
                    "status": "stale_snapshot",
                    "errors": ["positions snapshot is older than loop state"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 5
    params, param_errors = load_strategy_params(paths)
    if param_errors:
        print(
            json.dumps(
                {"status": "invalid_params", "errors": param_errors},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 10
    assert params is not None

    end_date = args.end_date or dt.date.today().isoformat()
    start_date = args.start_date or (dt.date.fromisoformat(end_date) - dt.timedelta(days=365 * args.years + 20)).isoformat()
    run_date = end_date
    run_id = snapshot_run_id(str(positions.get("snapshot_time")))

    collected = collect_data(
        positions, Path(args.a_share_skill), start_date, end_date, include_events=args.include_events
    )
    stock_data = collected.stock_data
    board_summaries = collected.board_summaries
    indices = collected.indices
    market_news = collected.market_news
    data_errors = collected.errors
    history_path = paths["market_history"] / "market_snapshots.jsonl"
    market_inputs, current_market_row = prepare_market_inputs(
        collected, history_path
    )
    market = classify_market(indices, board_summaries)
    signal = generate_daily_signal(
        positions,
        stock_data,
        market,
        board_summaries,
        indices,
        market_news,
        data_errors,
        params,
        market_inputs=market_inputs,
    )
    signal["loop_review"] = loop_review
    contract_errors = validate_signal_v2(signal)
    if contract_errors:
        print(
            json.dumps(
                {
                    "status": "invalid_report_contract",
                    "errors": contract_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 6
    histories = {code: data.history for code, data in stock_data.items() if data.history}
    backtest = run_backtest(histories, params, start_date=start_date, end_date=end_date)
    backtest["scope"] = "technical_only_diagnostic"
    optimization = optimize_params(histories, params, comparable_live_inputs=False)
    selected_params = optimization.get("selected_params", params)
    selected_param_errors = validate_strategy_params(selected_params)
    if selected_param_errors:
        print(
            json.dumps(
                {"status": "invalid_params", "errors": selected_param_errors},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 10

    staging_dir: Optional[Path] = None
    try:
        staging_dir = allocate_unique_directory(paths["runs"], f".{run_id}.staging")
        write_json(staging_dir / "positions.json", positions)
        write_json(staging_dir / "market_data_errors.json", data_errors)
        write_json(staging_dir / "daily_signal.json", signal)
        write_json(staging_dir / "loop_review.json", loop_review)
    except (OSError, ValueError, TypeError, KeyboardInterrupt) as exc:
        cleanup_error = cleanup_unique_output(staging_dir) if staging_dir else None
        print(
            json.dumps(
                {
                    "status": "artifact_write_failed",
                    "errors": [str(exc)],
                    "cleanup_errors": [cleanup_error] if cleanup_error else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 11
    assert staging_dir is not None
    try:
        write_report(
            staging_dir / "report.md",
            positions,
            signal,
            backtest,
            optimization,
            data_errors,
        )
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        cleanup_error = cleanup_unique_output(staging_dir)
        print(
            json.dumps(
                {
                    "status": "report_write_failed",
                    "errors": [str(exc)],
                    "cleanup_errors": [cleanup_error] if cleanup_error else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 7

    backtest_paths = (
        paths["backtests"] / f"backtest_result_{run_date}.json",
        paths["backtests"] / f"optimization_{run_date}.json",
    )
    captured_backtests: List[Tuple[Path, Optional[bytes]]] = []
    run_dir: Optional[Path] = None
    try:
        captured_backtests = capture_regular_file_bytes(backtest_paths)
        run_dir = publish_staged_directory(staging_dir, paths["runs"], run_id)
        write_json(backtest_paths[0], backtest)
        write_json(backtest_paths[1], optimization)
    except (OSError, ValueError, TypeError, KeyboardInterrupt) as exc:
        cleanup_errors: List[str] = []
        for output_dir in (run_dir, staging_dir):
            if output_dir is None:
                continue
            cleanup_error = cleanup_unique_output(output_dir)
            if cleanup_error:
                cleanup_errors.append(cleanup_error)
        cleanup_errors.extend(restore_captured_files(captured_backtests))
        print(
            json.dumps(
                {
                    "status": "artifact_write_failed",
                    "errors": [str(exc)],
                    "cleanup_errors": cleanup_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 11
    assert run_dir is not None
    persisted, persistence_errors, rollback_errors = persist_loop_progress(
        paths,
        run_date,
        params,
        selected_params,
        history_path,
        current_market_row,
        state_path,
        build_loop_state(positions, signal, run_dir),
        manifest,
        positions,
    )
    if not persisted:
        artifact_rollback_errors: List[str] = []
        cleanup_error = cleanup_unique_output(run_dir)
        if cleanup_error:
            artifact_rollback_errors.append(cleanup_error)
        artifact_rollback_errors.extend(restore_captured_files(captured_backtests))
        input_failure = any(
            error.startswith(("latest_screenshots:", "positions:"))
            for error in persistence_errors
        )
        if input_failure:
            print(
                json.dumps(
                    {
                        "status": "artifact_write_failed",
                        "errors": persistence_errors,
                        "rollback_errors": rollback_errors,
                        "cleanup_errors": artifact_rollback_errors,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 11
        print(
            json.dumps(
                {
                    "status": "persistence_failed",
                    "errors": persistence_errors,
                    "rollback_errors": rollback_errors,
                    "artifact_rollback_errors": artifact_rollback_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 8

    summary = {
        "status": "ok",
        "run_dir": str(run_dir),
        "report": str(run_dir / "report.md"),
        "daily_signal": str(run_dir / "daily_signal.json"),
        "backtest_result": str(paths["backtests"] / f"backtest_result_{run_date}.json"),
        "loop_review": str(run_dir / "loop_review.json"),
        "data_error_count": len(data_errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    paths = loop_paths(workspace, args.loop_dir)
    manifest = scan_screenshots(workspace)
    out = paths["positions"] / "latest_screenshots.json"
    write_json(out, manifest)
    print(json.dumps({"status": "ok", "output": str(out), **manifest}, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.positions_json)
    selected_positions, selection_errors = load_selected_positions(path, args.account)
    if selection_errors:
        print(json.dumps({"status": "invalid_positions", "errors": selection_errors}, ensure_ascii=False, indent=2))
        return 1
    assert selected_positions is not None
    ok, errors, normalized = validate_positions(selected_positions)
    print(json.dumps({"status": "ok" if ok else "invalid_positions", "errors": errors, "positions": normalized}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the stock strategy loop.")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace containing screenshots and .stock-loop.")
    parser.add_argument("--loop-dir", default=DEFAULT_LOOP_DIR)
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan-screenshots")
    scan.set_defaults(func=cmd_scan)

    validate = sub.add_parser("validate-positions")
    validate.add_argument("--positions-json", required=True)
    validate.add_argument("--account")
    validate.set_defaults(func=cmd_validate)

    run = sub.add_parser("run")
    run.add_argument("--positions-json")
    run.add_argument("--account")
    run.add_argument("--a-share-skill", default=str(DEFAULT_A_SHARE_SKILL))
    run.add_argument("--years", type=int, default=3)
    run.add_argument("--start-date")
    run.add_argument("--end-date")
    run.add_argument("--include-events", action="store_true")
    run.set_defaults(func=run_loop)

    targets = sub.add_parser("analyze-targets")
    targets.add_argument("--codes", required=True, help="Comma-separated six-digit A-share codes.")
    targets.add_argument("--positions-json")
    targets.add_argument("--account")
    targets.add_argument("--a-share-skill", default=str(DEFAULT_A_SHARE_SKILL))
    targets.add_argument("--years", type=int, default=3)
    targets.add_argument("--start-date")
    targets.add_argument("--end-date")
    targets.add_argument("--include-events", action="store_true")
    targets.set_defaults(func=cmd_analyze_targets)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
