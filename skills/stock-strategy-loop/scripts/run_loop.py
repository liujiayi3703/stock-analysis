#!/usr/bin/env python3
"""Run a local A-share holding strategy loop.

This script handles deterministic work: locating screenshots, validating a
positions JSON produced by Codex vision, fetching market data, scoring current
holdings, running a no-lookahead backtest, trying bounded parameter candidates,
and writing Markdown/JSON outputs under .stock-loop/.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests


DEFAULT_A_SHARE_SKILL = Path(os.environ.get("A_SHARE_SKILL_DIR", r"C:\Users\liuji\.codex\skills\a-share-data"))
DEFAULT_LOOP_DIR = ".stock-loop"
SCREENSHOT_RE = re.compile(
    r"(?P<date>20\d{2}[-_]?\d{2}[-_]?\d{2})(?:[-_](?P<h>\d{2})[-_](?P<m>\d{2})[-_](?P<s>\d{2}))?",
    re.IGNORECASE,
)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


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
    for path in workspace.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        shot_time = parse_screenshot_time(path)
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


def loop_paths(workspace: Path, loop_dir: str = DEFAULT_LOOP_DIR) -> Dict[str, Path]:
    root = workspace / loop_dir
    paths = {
        "root": root,
        "positions": root / "positions",
        "runs": root / "runs",
        "backtests": root / "backtests",
        "params": root / "params",
        "cache": root / "cache",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def validate_positions(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    holdings = data.get("holdings")
    if not isinstance(holdings, list) or not holdings:
        errors.append("positions.holdings must be a non-empty list")
        holdings = []

    normalized: List[Dict[str, Any]] = []
    required = ["code", "name", "shares", "cost_price", "last_price", "market_value", "unrealized_pnl"]
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
        shares = safe_float(item.get("shares"))
        cost_price = safe_float(item.get("cost_price"))
        last_price = safe_float(item.get("last_price"))
        market_value = safe_float(item.get("market_value"))
        unrealized_pnl = safe_float(item.get("unrealized_pnl"))
        if shares <= 0:
            errors.append(f"holding[{i}] shares must be positive")
        expected_mv = round(shares * last_price, 2)
        if market_value > 0 and abs(expected_mv - market_value) > max(2.0, market_value * 0.02):
            errors.append(
                f"holding[{i}] market_value mismatch: shares*last_price={expected_mv}, market_value={market_value}"
            )
        normalized.append(
            {
                **item,
                "code": code,
                "name": str(item.get("name", "")).strip(),
                "shares": shares,
                "cost_price": cost_price,
                "last_price": last_price,
                "market_value": market_value if market_value > 0 else expected_mv,
                "unrealized_pnl": unrealized_pnl,
            }
        )

    stock_value = safe_float(data.get("stock_value"))
    if stock_value <= 0:
        stock_value = sum(x["market_value"] for x in normalized)
    else:
        calc_stock_value = sum(x["market_value"] for x in normalized)
        if abs(calc_stock_value - stock_value) > max(10.0, stock_value * 0.03):
            errors.append(
                f"stock_value mismatch: holdings sum={round(calc_stock_value, 2)}, stock_value={stock_value}"
            )

    cash = safe_float(data.get("cash"))
    total_assets = safe_float(data.get("total_assets"))
    if total_assets and abs((stock_value + cash) - total_assets) > max(10.0, total_assets * 0.03):
        errors.append(
            f"total_assets mismatch: stock_value+cash={round(stock_value + cash, 2)}, total_assets={total_assets}"
        )

    normalized_data = {
        **data,
        "holdings": normalized,
        "cash": cash,
        "stock_value": round(stock_value, 2),
        "total_assets": round(total_assets if total_assets > 0 else stock_value + cash, 2),
        "validated_at": now_str(),
    }
    return not errors, errors, normalized_data


def run_subprocess_json(command: Sequence[str], timeout: int = 30) -> Tuple[Optional[Any], Optional[str]]:
    try:
        proc = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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
            return parsed, clean_error(proc.stderr or f"exit {proc.returncode}")
        return parsed, None
    except json.JSONDecodeError as exc:
        if proc.returncode != 0:
            return None, clean_error(proc.stderr or proc.stdout or f"exit {proc.returncode}")
        return None, f"invalid JSON: {exc}"


def clean_error(text: str) -> str:
    lines = []
    for line in str(text).splitlines():
        if "Pandas requires version" in line:
            continue
        if "from pandas.core" in line:
            continue
        if line.strip().startswith("C:\\Users\\") and "site-packages" in line:
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
            code = normalize_code(row.get("代码") or row.get("code"))
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
        session = requests.Session()
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
                "代码": code,
                "名称": row.get("f14"),
                "最新价": row.get("f2"),
                "涨跌幅(%)": row.get("f3"),
                "今开": row.get("f17"),
                "最高": row.get("f15"),
                "最低": row.get("f16"),
                "昨收": row.get("f18"),
                "成交量": row.get("f5"),
                "成交额": row.get("f6"),
                "换手率(%)": row.get("f8"),
                "主力净额": row.get("f62"),
                "行业": row.get("f100"),
                "数据源": "eastmoney-direct",
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
    if err:
        return {}, err
    rows = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    sectors = {normalize_code(row.get("code")): row for row in rows if normalize_code(row.get("code"))}
    failed = [code for code, row in sectors.items() if row.get("error") and not row.get("industry")]
    note = f"sector_info failed for {len(failed)} codes; quote fallback will be used when available" if failed else None
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
            session = requests.Session()
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
            return normalize_history_rows(data), None
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
            "preclose": safe_float(row.get("preclose") or row.get("昨收")),
            "volume": safe_float(row.get("volume") or row.get("成交量")),
            "pctChg": safe_float(row.get("pctChg") or row.get("涨跌幅")),
        }
        if all(item[k] > 0 for k in ("open", "high", "low", "close")):
            out.append(item)
    out.sort(key=lambda x: x["date"])
    return out


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


def normalize_fund_flow_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date = normalize_date(first_present(row, ("date", K_DATE, "trade_date")))
        item = {
            "date": date,
            "main_net_wan": safe_float(first_present(row, ("main_net_wan", K_MAIN_NET))),
            "main_ratio_pct": safe_float(first_present(row, ("main_ratio_pct", K_MAIN_RATIO, "main_ratio"))),
            "super_net_wan": safe_float(first_present(row, ("super_net_wan", K_SUPER_NET))),
            "big_net_wan": safe_float(first_present(row, ("big_net_wan", K_BIG_NET))),
            "close": safe_float(first_present(row, ("close", K_CLOSE))),
            "pct_chg": safe_float(first_present(row, ("pct_chg", K_PCT_CHG))),
            "source": row.get("source") or row.get("data_source") or row.get("鏁版嵁婧?") or "unknown",
        }
        if date or item["main_net_wan"] or item["main_ratio_pct"]:
            normalized.append(item)
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
    return normalize_fund_flow_rows(rows), None


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
    url = f"https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?{params}"
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], str(exc)
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
    return normalize_fund_flow_rows(direct_rows), None
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
    for mode in ("major", "sub", "concept"):
        data, err = run_subprocess_json(
            [sys.executable, str(script), "--summary", "--mode", mode, "--limit", "20", "--json"],
            timeout=30,
        )
        if err:
            errors.append(f"boards {mode}: {err}")
        else:
            result[mode] = data
    return result, errors


def fetch_market_news(a_share_skill: Path, limit: int = 80) -> Tuple[Dict[str, Any], Optional[str]]:
    script = a_share_skill / "scripts" / "fetch_danginvest.py"
    data, err = run_subprocess_json(
        [sys.executable, str(script), "--news", "--limit", str(limit), "--json"],
        timeout=40,
    )
    if not err and isinstance(data, dict):
        return data, None

    try:
        session = requests.Session()
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

    flow = 50.0
    if fund_flow:
        latest = fund_flow[-1]
        main_ratio = safe_float(latest.get("main_ratio_pct") or latest.get("main_ratio"))
        recent = fund_flow[-5:]
        recent_net = sum(safe_float(x.get("main_net_wan")) for x in recent)
        positive_days = sum(1 for x in recent if safe_float(x.get("main_net_wan")) > 0)
        if main_ratio > 5:
            flow += 15
        elif main_ratio > 0:
            flow += 6
        elif main_ratio < -5:
            flow -= 15
        elif main_ratio < 0:
            flow -= 6
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
        elif positive_days <= 1:
            flow -= 6
        fund_flow = []
    if fund_flow:
        latest = fund_flow[-1]
        main_ratio = safe_float(
            latest.get("主力占比(%)")
            or latest.get("main_ratio")
            or latest.get("主力净占比")
            or latest.get("主力净流入占比")
        )
        if main_ratio > 5:
            flow += 25
        elif main_ratio > 0:
            flow += 10
        elif main_ratio < -5:
            flow -= 25
        elif main_ratio < 0:
            flow -= 10
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
        "fund_flow_score": round(flow, 2),
        "sector_score": round(sector, 2),
        "event_score": round(event, 2),
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
    best = 0.0
    for payload in board_summaries.values():
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        for row in rows:
            label = str(row.get("groupLabel") or row.get("groupKey") or "")
            if industry in label or label in industry:
                best = max(best, safe_float(row.get("changePct")))
    return best


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
    return {
        "holding_count": total,
        "quote_count": sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).quote),
        "history_count": sum(1 for count in histories if count > 0),
        "history_rows_min": min(histories) if histories else 0,
        "history_rows_max": max(histories) if histories else 0,
        "fund_flow_count": sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).fund_flow),
        "event_count": sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).events),
        "industry_count": sum(1 for h in holdings if (stock_data.get(h["code"]) or StockData(h["code"], h.get("name", ""), [], {})).industry),
        "board_modes": sorted(board_summaries.keys()),
        "index_count": len(indices),
        "market_news_count": len(market_news_items(market_news, limit=200)),
        "data_error_count": len(data_errors),
    }


def classify_market(indices: List[Dict[str, Any]], board_summaries: Dict[str, Any]) -> Dict[str, Any]:
    pct_values = [safe_float(x.get("涨跌幅(%)") or x.get("pct")) for x in indices]
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


def low_confidence_action(holding: Dict[str, Any], total_assets: float, reason: str) -> Dict[str, Any]:
    current_weight = safe_float(holding.get("market_value")) / total_assets if total_assets else 0.0
    return {
        "code": holding["code"],
        "name": holding["name"],
        "action": "watch",
        "reason": reason,
        "trigger": "刷新缺失行情/历史K线/资金流数据后重新评分",
        "invalidation": "关键数据持续缺失或持仓截图字段无法校验",
        "target_weight": round(current_weight, 4),
        "risk_note": "低置信数据，不生成加仓或减仓结论；仅保留观察和复核要求。",
    }


def generate_daily_signal(
    positions: Dict[str, Any],
    stock_data: Dict[str, StockData],
    market_regime: Dict[str, Any],
    board_summaries: Dict[str, Any],
    indices: List[Dict[str, Any]],
    market_news: Dict[str, Any],
    data_errors: Sequence[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    stock_scores: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    total_assets = safe_float(positions.get("total_assets")) or safe_float(positions.get("stock_value"))
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
                        "fund_flow_score": 0.0,
                        "sector_score": 0.0,
                        "event_score": 0.0,
                        "raw": {"reason": "missing history or stock data"},
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
        score = score_from_row(latest, prev, data.fund_flow or [], sector_change, bias, params)
        missing_data = []
        if not data.quote:
            missing_data.append("quote")
        if not data.fund_flow:
            missing_data.append("fund_flow")
        if not data.industry:
            missing_data.append("industry")
        score["raw"] = {
            "history_rows": len(data.history),
            "fund_flow_rows": len(data.fund_flow or []),
            "fund_flow_5d_net_wan": round(sum(safe_float(x.get("main_net_wan")) for x in (data.fund_flow or [])[-5:]), 2),
            "sector_change_pct": round(sector_change, 4),
            "event_bias": round(bias, 4),
        }
        current_weight = safe_float(holding.get("market_value")) / total_assets if total_assets else 0.0
        score_row = {
            "code": code,
            "name": holding["name"],
            "industry": data.industry,
            "current_weight": round(current_weight, 4),
            "price": safe_float(data.quote.get("最新价") or data.quote.get("f2") or latest.get("close")),
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
        actions.append(action_for_holding(holding, score, latest, params, total_assets, missing_data))

    return {
        "generated_at": now_str(),
        "snapshot_time": positions.get("snapshot_time"),
        "data_coverage": build_data_coverage(positions, stock_data, board_summaries, indices, market_news, data_errors),
        "market_regime": market_regime,
        "market_news_context": summarize_market_news(market_news),
        "sector_context": {
            "matched_note": "sector scores use current industry labels matched to market board summaries when available",
            "board_source": "DangInvest via a-share-data fetch_danginvest.py",
        },
        "stock_scores": sorted(stock_scores, key=lambda x: x["scores"]["total_score"], reverse=True),
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
        current_equity = cash + sum(shares.get(c, 0.0) * safe_float(exec_rows.get(c, {}).get("open")) for c in shares)
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

        close_equity = cash + sum(shares.get(c, 0.0) * safe_float(exec_rows.get(c, {}).get("close")) for c in shares)
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
            elif isinstance(value, (int, float)) and isinstance(item.get(key), (int, float)):
                item[key] = item[key] + value
            else:
                item[key] = value
        candidates.append(item)
    return candidates


def optimize_params(histories: Dict[str, List[Dict[str, Any]]], current: Dict[str, Any]) -> Dict[str, Any]:
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
) -> None:
    metrics = backtest.get("metrics", {})
    coverage = signal.get("data_coverage", {})
    news_context = signal.get("market_news_context", {})
    news_topics = ", ".join(f"{x['topic']}({x['hits']})" for x in news_context.get("top_topics", [])[:6]) or "n/a"
    lines = [
        f"# 股票策略闭环报告 - {dt.date.today().isoformat()}",
        "",
        "## 数据事实",
        f"- 截图时间: {positions.get('snapshot_time', 'unknown')}",
        f"- 持仓数量: {len(positions.get('holdings', []))}",
        f"- 股票市值: {positions.get('stock_value')}",
        f"- 总资产: {positions.get('total_assets')}",
        f"- 市场状态: {signal.get('market_regime', {}).get('regime', 'unknown')}",
        "",
        "## 组合动作",
    ]
    lines.extend(
        [
            f"- Data coverage: quotes {coverage.get('quotes', 0)}/{coverage.get('holdings', 0)}, "
            f"history {coverage.get('history', 0)}/{coverage.get('holdings', 0)}, "
            f"fund_flow {coverage.get('fund_flow', 0)}/{coverage.get('holdings', 0)}, "
            f"events {coverage.get('events', 0)}/{coverage.get('holdings', 0)}, "
            f"market_news {coverage.get('market_news', 0)}",
            f"- Market-news topics: {news_topics}",
        ]
    )
    for action in signal.get("portfolio_actions", []):
        lines.append(
            f"- {action['code']} {action['name']}: {action['action']} | 目标权重 {action['target_weight']:.2%} | {action['reason']}"
        )
    lines.extend(
        [
            "",
            "## 个股评分",
            "| 代码 | 名称 | 行业 | 当前权重 | 总分 | 趋势 | MACD | 资金 |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in signal.get("stock_scores", []):
        s = row["scores"]
        lines.append(
            f"| {row['code']} | {row['name']} | {row.get('industry','')} | {row['current_weight']:.2%} | "
            f"{s['total_score']:.1f} | {s['trend_score']:.1f} | {s['macd_score']:.1f} | {s['fund_flow_score']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## 回测证据",
            f"- 状态: {backtest.get('status')}",
            f"- 年化收益: {metrics.get('annualized_return_pct', 'n/a')}%",
            f"- 最大回撤: {metrics.get('max_drawdown_pct', 'n/a')}%",
            f"- Sharpe: {metrics.get('sharpe', 'n/a')}",
            f"- 胜率: {metrics.get('win_rate_pct', 'n/a')}%",
            f"- 交易次数: {metrics.get('trade_count', 'n/a')}",
            "",
            "## 参数迭代",
            f"- 状态: {optimization.get('status')}",
            f"- 结论: {optimization.get('selected_reason', optimization.get('reason', 'n/a'))}",
            "",
            "## 数据问题",
        ]
    )
    if data_errors:
        lines.extend([f"- {err}" for err in data_errors])
    else:
        lines.append("- 无阻断性数据问题。")
    lines.extend(
        [
            "",
            "## 执行纪律",
            "- 本报告是研究和模拟闭环，不自动下单。",
            "- 操作必须按 trigger / invalidation 执行；若关键数据低置信，降低仓位或跳过。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_or_create_params(paths: Dict[str, Path]) -> Dict[str, Any]:
    current = paths["params"] / "strategy_params.json"
    if current.exists():
        return read_json(current)
    write_json(current, DEFAULT_PARAMS)
    return json.loads(json.dumps(DEFAULT_PARAMS))


def collect_data(
    positions: Dict[str, Any],
    a_share_skill: Path,
    start: str,
    end: str,
    include_events: bool,
) -> Tuple[Dict[str, StockData], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], List[str]]:
    codes = [h["code"] for h in positions["holdings"]]
    errors: List[str] = []
    quotes, quote_errors = fetch_quotes(codes, a_share_skill)
    errors.extend(quote_errors)
    sectors, sector_err = fetch_sector_info(codes, a_share_skill)
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
            industry = quote.get("行业") or quote.get("f100")
            name = quote.get("名称") or quote.get("f14")
            if industry or name:
                sectors[code] = {
                    "code": code,
                    "name": name,
                    "industry": industry or "",
                    "source": quote.get("数据源", "quote-fallback"),
                    "error": None,
                }
    board_summaries, board_errors = fetch_board_summaries(a_share_skill)
    errors.extend(board_errors)
    market_news, news_err = fetch_market_news(a_share_skill)
    if news_err:
        errors.append(f"market_news: {news_err}")
    indices, index_err = fetch_indices(a_share_skill)
    if index_err:
        errors.append(f"indices: {index_err}")

    stock_data: Dict[str, StockData] = {}
    for holding in positions["holdings"]:
        code = holding["code"]
        history, hist_err = fetch_history(code, start, end, a_share_skill)
        if hist_err:
            errors.append(f"history {code}: {hist_err}")
        fund_flow, flow_err = fetch_fund_flow(code, a_share_skill)
        if flow_err:
            errors.append(f"fund_flow {code}: {flow_err}")
        events: Dict[str, Any] = {}
        if include_events:
            events, event_err = fetch_events(code, holding["name"], a_share_skill)
            if event_err:
                errors.append(f"events {code}: {event_err}")
        sector = sectors.get(code, {})
        stock_data[code] = StockData(
            code=code,
            name=holding["name"],
            history=history,
            quote=quotes.get(code, {}),
            industry=str(sector.get("industry", "")),
            fund_flow=fund_flow,
            events=events,
        )
    return stock_data, board_summaries, indices, market_news, errors


def run_loop(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    paths = loop_paths(workspace, args.loop_dir)
    manifest = scan_screenshots(workspace)
    write_json(paths["positions"] / "latest_screenshots.json", manifest)

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
    ok, errors, positions = validate_positions(read_json(positions_path))
    if not ok:
        print(json.dumps({"status": "invalid_positions", "errors": errors}, ensure_ascii=False, indent=2))
        return 3
    write_json(paths["positions"] / "positions.json", positions)

    params = load_or_create_params(paths)
    end_date = args.end_date or dt.date.today().isoformat()
    start_date = args.start_date or (dt.date.fromisoformat(end_date) - dt.timedelta(days=365 * args.years + 20)).isoformat()
    run_date = end_date
    run_dir = paths["runs"] / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    stock_data, board_summaries, indices, market_news, data_errors = collect_data(
        positions, Path(args.a_share_skill), start_date, end_date, include_events=args.include_events
    )
    histories = {code: data.history for code, data in stock_data.items() if data.history}
    market = classify_market(indices, board_summaries)
    signal = generate_daily_signal(positions, stock_data, market, board_summaries, indices, market_news, data_errors, params)
    backtest = run_backtest(histories, params, start_date=start_date, end_date=end_date)
    optimization = optimize_params(histories, params)
    selected_params = optimization.get("selected_params", params)
    if selected_params != params:
        write_json(paths["params"] / f"strategy_params_{run_date}.json", selected_params)
        write_json(paths["params"] / "strategy_params.json", selected_params)

    write_json(run_dir / "positions.json", positions)
    write_json(run_dir / "market_data_errors.json", data_errors)
    write_json(run_dir / "daily_signal.json", signal)
    write_json(paths["backtests"] / f"backtest_result_{run_date}.json", backtest)
    write_json(paths["backtests"] / f"optimization_{run_date}.json", optimization)
    write_report(run_dir / "report.md", positions, signal, backtest, optimization, data_errors)

    summary = {
        "status": "ok",
        "run_dir": str(run_dir),
        "report": str(run_dir / "report.md"),
        "daily_signal": str(run_dir / "daily_signal.json"),
        "backtest_result": str(paths["backtests"] / f"backtest_result_{run_date}.json"),
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
    ok, errors, normalized = validate_positions(read_json(path))
    print(json.dumps({"status": "ok" if ok else "invalid", "errors": errors, "positions": normalized}, ensure_ascii=False, indent=2))
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
    validate.set_defaults(func=cmd_validate)

    run = sub.add_parser("run")
    run.add_argument("--positions-json")
    run.add_argument("--a-share-skill", default=str(DEFAULT_A_SHARE_SKILL))
    run.add_argument("--years", type=int, default=3)
    run.add_argument("--start-date")
    run.add_argument("--end-date")
    run.add_argument("--include-events", action="store_true")
    run.set_defaults(func=run_loop)
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
