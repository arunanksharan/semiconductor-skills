#!/usr/bin/env python3
"""Lot/wafer yield summary and hard/soft bin paretos from die_results.csv.

Canonical schema: lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag
(see references/data-formats.md).

Usage examples:
  python yield_summary.py --input die_results.csv
  python yield_summary.py --input die_results.csv --lot EDGE --soft --json
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

REQUIRED = ["lot_id", "wafer_id", "die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"]


def load(path: str, lot: str | None) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"lot_id": str, "wafer_id": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: {path} is missing columns {missing}; expected {','.join(REQUIRED)}")
    for c in ("die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"):
        df[c] = pd.to_numeric(df[c], errors="raise").astype(int)
    if lot is not None:
        df = df[df.lot_id == lot]
        if df.empty:
            sys.exit(f"ERROR: lot '{lot}' not found in {path}")
    return df


def pareto(df: pd.DataFrame, col: str) -> pd.DataFrame:
    fails = df[df.pass_flag == 0]
    if fails.empty:
        return pd.DataFrame(columns=[col, "count", "pct_of_fails", "cum_pct"])
    t = fails.groupby(col).size().sort_values(ascending=False).reset_index(name="count")
    t["pct_of_fails"] = (100 * t["count"] / len(fails)).round(2)
    t["cum_pct"] = t["pct_of_fails"].cumsum().round(2)
    return t


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", required=True, help="die_results.csv (canonical schema)")
    ap.add_argument("--lot", help="restrict to one lot_id")
    ap.add_argument("--soft", action="store_true", help="add soft-bin pareto (default: hard bins)")
    ap.add_argument("--top", type=int, default=10, help="pareto rows to show (default 10)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    df = load(args.input, args.lot)
    out = {}
    for lot_id, d in df.groupby("lot_id", sort=True):
        wafers = (
            d.groupby("wafer_id")
            .agg(dies=("pass_flag", "size"), passed=("pass_flag", "sum"))
            .assign(yield_pct=lambda t: (100 * t.passed / t.dies).round(2))
            .reset_index()
        )
        entry = {
            "dies": int(len(d)),
            "passed": int(d.pass_flag.sum()),
            "yield_pct": round(100 * d.pass_flag.mean(), 2),
            "wafers": wafers.to_dict(orient="records"),
            "hard_bin_pareto": pareto(d, "hard_bin").head(args.top).to_dict(orient="records"),
        }
        if args.soft:
            entry["soft_bin_pareto"] = pareto(d, "soft_bin").head(args.top).to_dict(orient="records")
        out[lot_id] = entry

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    for lot_id, e in out.items():
        print(f"lot {lot_id}: yield {e['yield_pct']}%  ({e['passed']}/{e['dies']} pass)")
        print("  per wafer:")
        for w in e["wafers"]:
            print(f"    {w['wafer_id']:<8} dies {w['dies']:<6} yield {w['yield_pct']:.2f}%")
        print("  hard-bin pareto (fails only):")
        print(f"    {'bin':<6}{'count':<8}{'% fails':<9}{'cum %':<7}")
        for r in e["hard_bin_pareto"]:
            print(f"    {r['hard_bin']:<6}{r['count']:<8}{r['pct_of_fails']:<9}{r['cum_pct']:<7}")
        if args.soft:
            print("  soft-bin pareto (fails only):")
            for r in e["soft_bin_pareto"]:
                print(f"    {r['soft_bin']:<6}{r['count']:<8}{r['pct_of_fails']:<9}{r['cum_pct']:<7}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
