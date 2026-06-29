#!/usr/bin/env python3
"""Validate common A-share market datasets."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


SCHEMAS = {
    "ohlcv": {"ticker", "date", "open", "high", "low", "close", "volume"},
    "sector": {"date", "sector", "return"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate market dataset CSV structure.")
    parser.add_argument("csv_path", type=Path, help="Path to market CSV")
    parser.add_argument("--type", choices=sorted(SCHEMAS), default="ohlcv", help="Dataset type")
    return parser.parse_args()


def as_float(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def valid_date(value: str) -> bool:
    text = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            pass
    return False


def main() -> int:
    args = parse_args()
    if not args.csv_path.exists():
        print(f"ERROR: file not found: {args.csv_path}", file=sys.stderr)
        return 2

    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        required = SCHEMAS[args.type]
        missing = sorted(required - headers)
        if missing:
            print(f"ERROR: missing required columns: {', '.join(missing)}", file=sys.stderr)
            return 1
        rows = list(reader)

    if not rows:
        print("ERROR: market CSV has no rows", file=sys.stderr)
        return 1

    errors: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for index, row in enumerate(rows, start=2):
        date = (row.get("date") or "").strip()
        if not valid_date(date):
            errors.append(f"line {index}: invalid date {date!r}")

        if args.type == "ohlcv":
            ticker = (row.get("ticker") or "").strip()
            key = (ticker, date)
            if key in seen_keys:
                errors.append(f"line {index}: duplicate ticker/date {ticker} {date}")
            seen_keys.add(key)

            values = {name: as_float(row.get(name, "")) for name in ("open", "high", "low", "close", "volume")}
            for name, number in values.items():
                if number is None:
                    errors.append(f"line {index}: {name} is not numeric")
                elif name != "volume" and number <= 0:
                    errors.append(f"line {index}: {name} must be positive")
                elif name == "volume" and number < 0:
                    errors.append(f"line {index}: volume must be non-negative")

            if all(values[name] is not None for name in ("open", "high", "low", "close")):
                open_, high, low, close = values["open"], values["high"], values["low"], values["close"]
                assert open_ is not None and high is not None and low is not None and close is not None
                if high < max(open_, low, close):
                    errors.append(f"line {index}: high is below open/low/close")
                if low > min(open_, high, close):
                    errors.append(f"line {index}: low is above open/high/close")

        if args.type == "sector":
            sector = (row.get("sector") or "").strip()
            if not sector:
                errors.append(f"line {index}: empty sector")
            if as_float(row.get("return", "")) is None:
                errors.append(f"line {index}: return is not numeric")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {len(rows)} {args.type} rows validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

