#!/usr/bin/env python3
"""Defect-density (D0) extraction under standard yield models.

Given observed yield Y and die area A (cm2), computes D0 under:
  Poisson            Y = exp(-A*D0)
  Murphy             Y = ((1 - exp(-A*D0)) / (A*D0))^2
  Seeds              Y = 1 / (1 + A*D0)
  Negative binomial  Y = (1 + A*D0/alpha)^(-alpha)   (alpha = cluster factor)

IMPORTANT: a single (A, Y) point fits ALL models exactly — model choice cannot
be made from one die size. See references/yield-models.md for when each model
applies and for D0-extraction pitfalls (systematic vs random split, edge
exclusion, gross-fail exclusion, multi-die-size regression).

D0 means RANDOM defect density. Fit it on the random-yield component only:
strip the systematic bins with --exclude-bins and the edge band with
--edge-exclude, then read Y_random off the residual population.

Usage examples:
  python yield_models.py --input die_results.csv --die-area 0.25 --lot BASE
  python yield_models.py --input die_results.csv --die-area 0.25 --exclude-bins 6,7,9
  python yield_models.py --input die_results.csv --die-area 0.25 --edge-exclude 0.90
  python yield_models.py --yield 0.905 --die-area 0.25 --n 3552 --json
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import beta

REQUIRED = ["lot_id", "wafer_id", "die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"]


def apply_exclusions(df: pd.DataFrame, exclude_bins: set[int], edge_exclude: float | None):
    """Drop systematic-fail populations before fitting a RANDOM defect density.

    --exclude-bins removes dies in the named hard bins entirely (they are a
    different failure population, not random defectivity).
    --edge-exclude removes every die whose normalized radius exceeds the
    threshold, per wafer (the standard edge-exclusion zone).
    Returns (filtered_df, notes).
    """
    notes = []
    # edge exclusion first: the wafer radius must be measured on the full map,
    # before any bin filtering thins out the outer ring
    if edge_exclude is not None:
        keep = pd.Series(False, index=df.index)
        for _, d in df.groupby(["lot_id", "wafer_id"], sort=False):
            x, y = d.die_x.to_numpy(), d.die_y.to_numpy()
            cx, cy = (x.min() + x.max()) / 2.0, (y.min() + y.max()) / 2.0
            r = np.hypot(x - cx, y - cy)
            keep.loc[d.index] = (r / max(r.max(), 1e-9)) <= edge_exclude
        n0 = len(df)
        df = df[keep]
        notes.append(f"edge exclusion r_norm > {edge_exclude}: -{n0 - len(df)} dies")
    if exclude_bins:
        n0 = len(df)
        df = df[~df.hard_bin.isin(exclude_bins)]
        notes.append(f"excluded hard bins {sorted(exclude_bins)}: -{n0 - len(df)} dies")
    if df.empty:
        sys.exit("ERROR: exclusions removed every die; relax --exclude-bins/--edge-exclude")
    return df, notes


def d0_poisson(y: float, a: float) -> float:
    return -math.log(y) / a


def d0_murphy(y: float, a: float) -> float:
    f = lambda d: ((1 - math.exp(-a * d)) / (a * d)) ** 2 - y
    return brentq(f, 1e-9, 1e4)


def d0_seeds(y: float, a: float) -> float:
    return (1 / y - 1) / a


def d0_nb(y: float, a: float, alpha: float) -> float:
    return alpha * (y ** (-1 / alpha) - 1) / a


def wilson_ci(passed: int, n: int):
    """95% Clopper-Pearson interval on yield (exact beta)."""
    lo = beta.ppf(0.025, passed, n - passed + 1) if passed > 0 else 0.0
    hi = beta.ppf(0.975, passed + 1, n - passed) if passed < n else 1.0
    return lo, hi


def fit_all(y: float, a: float, alpha: float) -> dict:
    if not (0 < y < 1):
        return {"error": f"yield {y} outside (0,1); D0 undefined"}
    return {
        "poisson": round(d0_poisson(y, a), 4),
        "murphy": round(d0_murphy(y, a), 4),
        "seeds": round(d0_seeds(y, a), 4),
        f"neg_binomial(alpha={alpha})": round(d0_nb(y, a, alpha), 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="die_results.csv (canonical schema)")
    src.add_argument("--yield", dest="yield_", type=float, help="observed yield as fraction (0-1)")
    ap.add_argument("--die-area", type=float, required=True, help="die area in cm2")
    ap.add_argument("--lot", help="restrict --input to one lot_id")
    ap.add_argument("--alpha", type=float, default=2.0, help="NB cluster factor (default 2.0)")
    ap.add_argument("--n", type=int, help="die count (for CI when using --yield)")
    ap.add_argument("--exclude-bins", default="",
                    help="comma-separated hard bins to drop as systematic (e.g. 6,7,9)")
    ap.add_argument("--edge-exclude", type=float,
                    help="drop dies with normalized radius above this (e.g. 0.90)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    try:
        excl = {int(b) for b in args.exclude_bins.split(",") if b.strip()}
    except ValueError:
        sys.exit(f"ERROR: --exclude-bins must be comma-separated integers, got '{args.exclude_bins}'")
    if (excl or args.edge_exclude is not None) and not args.input:
        sys.exit("ERROR: --exclude-bins/--edge-exclude need --input (they filter die records)")

    out, notes = {}, []
    if args.input:
        df = pd.read_csv(args.input, dtype={"lot_id": str, "wafer_id": str})
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            sys.exit(f"ERROR: {args.input} missing columns {missing}")
        if args.lot:
            df = df[df.lot_id == args.lot]
            if df.empty:
                sys.exit(f"ERROR: lot '{args.lot}' not found")
        df, notes = apply_exclusions(df, excl, args.edge_exclude)
        for lot_id, d in df.groupby("lot_id", sort=True):
            n, p = len(d), int(d.pass_flag.sum())
            y = p / n
            lo, hi = wilson_ci(p, n)
            out[lot_id] = {
                "dies": n, "passed": p, "yield": round(y, 4),
                "yield_ci95": [round(lo, 4), round(hi, 4)],
                "d0_per_cm2": fit_all(y, args.die_area, args.alpha),
                "d0_ci95_poisson": [round(d0_poisson(hi, args.die_area), 4),
                                    round(d0_poisson(lo, args.die_area), 4)]
                if 0 < lo and hi < 1 else None,
            }
    else:
        y = args.yield_
        entry = {"yield": y, "d0_per_cm2": fit_all(y, args.die_area, args.alpha)}
        if args.n:
            p = round(y * args.n)
            lo, hi = wilson_ci(p, args.n)
            entry["yield_ci95"] = [round(lo, 4), round(hi, 4)]
        out["(input)"] = entry

    if args.json:
        print(json.dumps({"exclusions": notes, "lots": out}, indent=2))
        return 0
    for n in notes:
        print(f"exclusion: {n}")
    if notes:
        print("-> yields below are RANDOM-component yields, not final test yield\n")
    for lot_id, e in out.items():
        print(f"lot {lot_id}: yield {e['yield']}"
              + (f"  (95% CI {e['yield_ci95'][0]}-{e['yield_ci95'][1]})" if e.get("yield_ci95") else ""))
        for model, d0 in e["d0_per_cm2"].items():
            print(f"  {model:<24} D0 = {d0} /cm2")
        if e.get("d0_ci95_poisson"):
            print(f"  poisson D0 95% CI        [{e['d0_ci95_poisson'][0]}, {e['d0_ci95_poisson'][1]}]")
    print("\nNOTE: one (A, Y) point fits every model exactly; choosing a model needs "
          "multiple die sizes or defect data — see references/yield-models.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
