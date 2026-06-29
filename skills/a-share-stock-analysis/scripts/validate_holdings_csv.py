#!/usr/bin/env python3
"""Validate a holdings CSV for the A-share stock analysis skill."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REQUIRED = {"ticker", "name"}
NUMERIC_NON_NEGATIVE = {"shares", "weight", "cost_basis", "latest_price"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate holdings CSV structure.")
    parser.add_argument("csv_path", type=Path, help="Path to holdings CSV")
    return parser.parse_args()


def as_float(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> int:
    args = parse_args()
    if not args.csv_path.exists():
        print(f"ERROR: file not found: {args.csv_path}", file=sys.stderr)
        return 2

    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - headers)
        if missing:
            print(f"ERROR: missing required columns: {', '.join(missing)}", file=sys.stderr)
            return 1

        rows = list(reader)

    if not rows:
        print("ERROR: holdings CSV has no rows", file=sys.stderr)
        return 1

    errors: list[str] = []
    tickers: dict[str, int] = {}
    has_position_size = "shares" in headers or "weight" in headers
    if not has_position_size:
        errors.append("missing both shares and weight; portfolio sizing cannot be reviewed")

    for index, row in enumerate(rows, start=2):
        ticker = (row.get("ticker") or "").strip()
        name = (row.get("name") or "").strip()
        if not ticker:
            errors.append(f"line {index}: empty ticker")
        if not name:
            errors.append(f"line {index}: empty name")
        if ticker:
            tickers[ticker] = tickers.get(ticker, 0) + 1

        for column in sorted(NUMERIC_NON_NEGATIVE & headers):
            number = as_float(row.get(column, ""))
            if number is None:
                continue
            if number < 0:
                errors.append(f"line {index}: {column} is negative")

    duplicates = sorted(ticker for ticker, count in tickers.items() if count > 1)
    if duplicates:
        errors.append("duplicate tickers: " + ", ".join(duplicates))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {len(rows)} holdings rows validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

