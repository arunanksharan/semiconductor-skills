#!/usr/bin/env python3
"""Lot-history commonality analysis: which step/tool/chamber is associated
with low yield?

Inputs:
  --history history.csv   lot_id,step,tool,chamber,date  (chamber may be blank)
  and one of:
  --die-results X.csv     canonical die_results.csv (yields computed per lot)
  --yields Y.csv          lot_id,yield  (fraction 0-1 or percent — auto-detected)

For every step, lots are grouped by tool (and chamber when present); groups are
ranked by yield delta vs the grand mean, weighted by sqrt(n_lots). Groups with
a single lot are reported as HYPOTHESIS ONLY — one lot cannot separate the
tool from the lot itself. See references/commonality-analysis.md for pitfalls
(confounding, multiple testing, queue-time effects).

Usage example:
  python commonality.py --history history.csv --die-results die_results.csv
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd


def load_yields(die_results: str | None, yields: str | None) -> pd.DataFrame:
    if die_results:
        df = pd.read_csv(die_results, dtype={"lot_id": str})
        if not {"lot_id", "pass_flag"}.issubset(df.columns):
            sys.exit(f"ERROR: {die_results} lacks lot_id/pass_flag columns")
        return (df.groupby("lot_id").pass_flag.mean().rename("yield").reset_index())
    df = pd.read_csv(yields, dtype={"lot_id": str})
    ycol = "yield" if "yield" in df.columns else df.columns[1]
    df = df.rename(columns={ycol: "yield"})[["lot_id", "yield"]]
    if df["yield"].max() > 1.5:            # given in percent
        df["yield"] = df["yield"] / 100.0
    return df


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--history", required=True, help="history.csv (lot_id,step,tool,chamber,date)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--die-results", help="die_results.csv to compute lot yields from")
    src.add_argument("--yields", help="CSV of lot_id,yield")
    ap.add_argument("--min-delta", type=float, default=2.0,
                    help="min yield delta (pp) to flag a suspect (default 2.0)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    hist = pd.read_csv(args.history, dtype=str)
    need = {"lot_id", "step", "tool"}
    if not need.issubset(hist.columns):
        sys.exit(f"ERROR: {args.history} must have columns lot_id,step,tool[,chamber,date]")
    if "chamber" not in hist.columns:
        hist["chamber"] = ""
    hist["chamber"] = hist["chamber"].fillna("")

    ylots = load_yields(args.die_results, args.yields)
    merged = hist.merge(ylots, on="lot_id", how="inner")
    if merged.empty:
        sys.exit("ERROR: no overlap between history lots and yield lots")
    grand = ylots["yield"].mean()

    steps_out, suspects = {}, []
    for step, d in merged.groupby("step", sort=True):
        rows = []
        for (tool, chamber), g in d.groupby(["tool", "chamber"], sort=True):
            lots = sorted(g.lot_id.unique())
            my = g.drop_duplicates("lot_id")["yield"].mean()
            delta_pp = 100 * (my - grand)
            rows.append({
                "tool": tool, "chamber": chamber, "n_lots": len(lots), "lots": lots,
                "mean_yield_pct": round(100 * my, 2), "delta_pp": round(delta_pp, 2),
            })
            if delta_pp <= -args.min_delta:
                suspects.append({
                    "step": step, "tool": tool, "chamber": chamber,
                    "n_lots": len(lots), "delta_pp": round(delta_pp, 2),
                    "score": round(abs(delta_pp) * (len(lots) ** 0.5), 2),
                    "hypothesis_only": len(lots) < 2,
                })
        steps_out[step] = sorted(rows, key=lambda r: r["delta_pp"])
    suspects.sort(key=lambda s: -s["score"])

    out = {"grand_mean_yield_pct": round(100 * grand, 2),
           "n_lots": int(ylots.lot_id.nunique()), "steps": steps_out, "suspects": suspects}
    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"lots: {out['n_lots']}  grand mean yield: {out['grand_mean_yield_pct']}%\n")
    for step, rows in steps_out.items():
        print(f"step {step}:")
        print(f"  {'tool':<10}{'chamber':<9}{'n':<4}{'mean%':<8}{'delta_pp':<9}lots")
        for r in rows:
            print(f"  {r['tool']:<10}{r['chamber']:<9}{r['n_lots']:<4}"
                  f"{r['mean_yield_pct']:<8}{r['delta_pp']:<9}{','.join(r['lots'])}")
        print()
    if suspects:
        print("SUSPECT RANKING (delta <= -%.1f pp):" % args.min_delta)
        for s in suspects:
            tag = "  [HYPOTHESIS ONLY: single lot]" if s["hypothesis_only"] else ""
            print(f"  {s['step']} / {s['tool']} {s['chamber']}: "
                  f"{s['delta_pp']} pp over {s['n_lots']} lot(s), score {s['score']}{tag}")
        print("\nCaveats: association is not causation; check confounding (same lots on the "
              "same suspect tools at other steps), queue time, and time order before acting.")
    else:
        print("No tool/chamber group is below the grand mean by the --min-delta threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
