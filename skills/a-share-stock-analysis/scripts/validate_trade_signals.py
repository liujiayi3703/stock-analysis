#!/usr/bin/env python3
"""Validate A-share trading signal CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED = {
    "date",
    "time",
    "stock_code",
    "direction",
    "action",
    "volume",
    "price",
    "signal_id",
}
CODE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")
VALID_DIRECTIONS = {"BUY", "SELL"}
VALID_ACTIONS = {"OPEN", "CLOSE"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate A-share trade signal CSV structure.")
    parser.add_argument("csv_path", type=Path, help="Path to signal CSV")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate signal_id rows for retry/idempotency tests",
    )
    return parser.parse_args()


def as_int(value: str) -> int | None:
    text = (value or "").strip().replace(",", "")
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def as_float(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def valid_date(value: str) -> bool:
    try:
        datetime.strptime((value or "").strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_time(value: str) -> bool:
    try:
        datetime.strptime((value or "").strip(), "%H:%M:%S")
        return True
    except ValueError:
        return False


def emit_text(result: dict[str, Any]) -> None:
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    if result["warnings"]:
        for warning in result["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
    if not result["errors"]:
        print(
            "OK: "
            f"{result['row_count']} rows, "
            f"{result['unique_signal_count']} unique signal IDs, "
            f"{len(result['warnings'])} warnings"
        )


def main() -> int:
    args = parse_args()
    result: dict[str, Any] = {
        "file": str(args.csv_path),
        "row_count": 0,
        "unique_signal_count": 0,
        "errors": [],
        "warnings": [],
    }

    if not args.csv_path.exists():
        result["errors"].append(f"file not found: {args.csv_path}")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            emit_text(result)
        return 2

    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - headers)
        if missing:
            result["errors"].append("missing required columns: " + ", ".join(missing))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                emit_text(result)
            return 1
        rows = list(reader)

    result["row_count"] = len(rows)
    if not rows:
        result["errors"].append("signal CSV has no rows")

    signal_ids: dict[str, list[int]] = {}
    ticker_counts: dict[str, int] = {}

    for index, row in enumerate(rows, start=2):
        date = (row.get("date") or "").strip()
        time = (row.get("time") or "").strip()
        stock_code = (row.get("stock_code") or "").strip().upper()
        direction = (row.get("direction") or "").strip().upper()
        action = (row.get("action") or "").strip().upper()
        signal_id = (row.get("signal_id") or "").strip()
        volume = as_int(row.get("volume", ""))
        price = as_float(row.get("price", ""))

        if not valid_date(date):
            result["errors"].append(f"line {index}: invalid date {date!r}; expected YYYY-MM-DD")
        if not valid_time(time):
            result["errors"].append(f"line {index}: invalid time {time!r}; expected HH:MM:SS")
        if not CODE_RE.match(stock_code):
            result["errors"].append(f"line {index}: invalid stock_code {stock_code!r}")
        if direction not in VALID_DIRECTIONS:
            result["errors"].append(f"line {index}: invalid direction {direction!r}")
        if action not in VALID_ACTIONS:
            result["errors"].append(f"line {index}: invalid action {action!r}")
        if volume is None:
            result["errors"].append(f"line {index}: volume is not an integer")
        elif volume <= 0:
            result["errors"].append(f"line {index}: volume must be positive")
        elif volume % 100 != 0:
            result["errors"].append(f"line {index}: A-share volume should be a multiple of 100")
        if price is None:
            result["errors"].append(f"line {index}: price is not numeric")
        elif price < 0:
            result["errors"].append(f"line {index}: price must be non-negative")
        elif price == 0:
            result["warnings"].append(f"line {index}: price is 0; confirm broker market-order rules")
        if not signal_id:
            result["errors"].append(f"line {index}: empty signal_id")
        else:
            signal_ids.setdefault(signal_id, []).append(index)
        if direction == "SELL" and action == "OPEN":
            result["warnings"].append(
                f"line {index}: SELL OPEN is unusual for ordinary A-share cash accounts"
            )
        if stock_code:
            ticker_counts[stock_code] = ticker_counts.get(stock_code, 0) + 1

    duplicates = {key: lines for key, lines in signal_ids.items() if len(lines) > 1}
    if duplicates and not args.allow_duplicates:
        for signal_id, lines in sorted(duplicates.items()):
            joined = ", ".join(str(line) for line in lines)
            result["errors"].append(f"duplicate signal_id {signal_id!r} on lines {joined}")
    elif duplicates:
        for signal_id, lines in sorted(duplicates.items()):
            joined = ", ".join(str(line) for line in lines)
            result["warnings"].append(f"duplicate signal_id {signal_id!r} allowed on lines {joined}")

    result["unique_signal_count"] = len(signal_ids)
    for ticker, count in sorted(ticker_counts.items()):
        if count >= 5:
            result["warnings"].append(f"{ticker} appears {count} times; check concentration")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        emit_text(result)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
