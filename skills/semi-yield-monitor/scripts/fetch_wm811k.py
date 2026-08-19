#!/usr/bin/env python3
"""WM-811K wafer-map dataset: acquisition instructions and a local converter.

THIS SCRIPT NEVER DOWNLOADS ANYTHING. It makes no network calls at all.

WM-811K (a.k.a. LSWMD) is ~811k real wafer maps, roughly a fifth of them
hand-labelled with a failure-pattern class. It is the obvious benchmark for
the spatial-signature classifier in this skill — but it is somebody else's
data, and this repository does not redistribute it.

  Step 1  Read the terms at the source, not from this file. Two places to
          check, in this order:
            - MIR Lab (Multimedia Information Retrieval Lab, National Taiwan
              University), the original publisher of the dataset
            - the Kaggle mirror's "License" panel on the dataset page
              (kaggle.com/datasets/qingyi/wm811k-wafer-map)
          The dataset accompanies Wu, Jang & Chen, "Wafer Map Failure Pattern
          Recognition and Similarity Ranking for Large-Scale Data Sets",
          IEEE Trans. Semiconductor Manufacturing 28(1), 2015. Cite it.

  Step 2  LICENSE STATUS: **UNVERIFIED / TODO**. As of this skill's build the
          redistribution terms could not be confirmed from a primary source,
          so no subset ships in this repo and none should be added until
          somebody reads the actual terms and records them here. Treat
          "a Kaggle mirror exists" as evidence of nothing.

  Step 3  Download LSWMD.pkl yourself (~200 MB) if the terms permit your use.

  Step 4  Convert it to this skill's canonical CSV schema:
            python fetch_wm811k.py --convert --pkl LSWMD.pkl --out wm811k/ \\
                --per-class 40 --labeled-only

Conversion notes (they matter for interpreting any score you get):
  * WM-811K stores a wafer map, not a datalog. Cell values are 0 = no die,
    1 = passing die, 2 = failing die. There are NO bin numbers, NO parametric
    results, NO lot history. hard_bin/soft_bin in the output are placeholders
    (1 = pass, 2 = fail) so the file matches the canonical schema; do not read
    a bin pareto off them.
  * Map sizes vary wafer to wafer; die_x/die_y are map column/row indices, not
    physical coordinates, so die area and D0 are not recoverable.
  * The labels are single-class. Real wafers carry mixed signatures, so a
    single-label benchmark understates a multi-candidate classifier.
  * Class balance is extreme (most labelled maps are "none"). Use --per-class
    to build a balanced subset, and report per-class recall, never accuracy.

Label vocabulary in the dataset, and how it maps to this skill's taxonomy:
  Center -> center_cluster · Donut -> donut · Edge-Ring -> edge_ring ·
  Edge-Loc -> edge-localized (a partial ring; this skill would call it
  half_moon/quadrant depending on angular extent) · Loc -> a local cluster
  (no direct equivalent) · Scratch -> scratch · Random -> none ·
  Near-full -> gross fail (not a spatial signature at all) · none -> none

Usage examples:
  python fetch_wm811k.py                      # print the instructions above
  python fetch_wm811k.py --convert --pkl LSWMD.pkl --out wm811k/ --per-class 40
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

LABEL_MAP = {
    "Center": "center_cluster",
    "Donut": "donut",
    "Edge-Ring": "edge_ring",
    "Edge-Loc": "edge_localized",
    "Loc": "local_cluster",
    "Scratch": "scratch",
    "Random": "none",
    "Near-full": "gross_fail",
    "none": "none",
}


def scalar(v):
    """LSWMD stores several fields as 0-d / 1-element numpy arrays."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None and isinstance(v, np.ndarray):
        if v.size == 0:
            return ""
        v = v.reshape(-1)[0]
    if isinstance(v, (list, tuple)):
        return scalar(v[0]) if v else ""
    return v


def convert(pkl: str, outdir: str, per_class: int | None, limit: int | None,
            labeled_only: bool) -> int:
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        print(f"ERROR: --convert needs numpy and pandas ({exc}). "
              "pip install -r requirements.txt", file=sys.stderr)
        return 2
    p = Path(pkl)
    if not p.exists():
        print(f"ERROR: {pkl} not found. This script does not download it — see the "
              "instructions above (run with no arguments).", file=sys.stderr)
        return 2
    try:
        df = pd.read_pickle(p)
    except Exception as exc:
        print(f"ERROR: could not read {pkl}: {type(exc).__name__}: {exc}\n"
              "Expected the LSWMD.pkl pandas DataFrame. A pickle written by a very "
              "different pandas/numpy version may need the environment that wrote it.",
              file=sys.stderr)
        return 2

    need = {"waferMap"}
    if not need.issubset(df.columns):
        print(f"ERROR: {pkl} has columns {list(df.columns)[:12]}; expected at least "
              "'waferMap' (plus lotName, waferIndex, failureType).", file=sys.stderr)
        return 2

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    label_col = "failureType" if "failureType" in df.columns else None
    labels = ([str(scalar(v)) for v in df[label_col]] if label_col
              else ["" for _ in range(len(df))])
    df = df.assign(_label=labels)
    if labeled_only:
        df = df[df._label.isin(LABEL_MAP)]
    if per_class:
        df = df.groupby("_label", sort=False).head(per_class)
    if limit:
        df = df.head(limit)
    if df.empty:
        print("ERROR: selection is empty — relax --per-class/--limit/--labeled-only",
              file=sys.stderr)
        return 2

    die_path, lab_path = out / "die_results.csv", out / "labels.csv"
    n_rows = 0
    with open(die_path, "w") as fh, open(lab_path, "w") as lf:
        fh.write("lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag\n")
        lf.write("lot_id,wafer_id,wm811k_label,skill_label,rows,cols,dies\n")
        for i, (_, r) in enumerate(df.iterrows()):
            wm = np.asarray(r["waferMap"])
            if wm.ndim != 2:
                continue
            lot = str(scalar(r.get("lotName", f"WM{i:06d}"))) or f"WM{i:06d}"
            widx = scalar(r.get("waferIndex", i))
            try:
                wafer = f"W{int(float(widx))}"
            except (TypeError, ValueError):
                wafer = f"W{i}"
            lot = f"{lot}".replace(",", "_")
            ys, xs = np.nonzero(wm > 0)
            for y, x in zip(ys, xs):
                v = int(wm[y, x])
                pf = 1 if v == 1 else 0
                fh.write(f"{lot},{wafer},{int(x)},{int(y)},{1 if pf else 2},"
                         f"{1 if pf else 2},{pf}\n")
                n_rows += 1
            lab = r["_label"]
            lf.write(f"{lot},{wafer},{lab},{LABEL_MAP.get(lab, '')},"
                     f"{wm.shape[0]},{wm.shape[1]},{len(ys)}\n")
    print(f"wrote {die_path} ({n_rows} die rows from {len(df)} wafers)")
    print(f"wrote {lab_path}")
    print("\nNOTE: hard_bin/soft_bin are placeholders (1 pass / 2 fail). WM-811K has no "
          "bin data — do not run a bin pareto on this file.")
    print("Score the classifier per class, not on overall accuracy:")
    print(f"  python spatial_signature.py --input {die_path} --json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--convert", action="store_true",
                    help="convert an ALREADY-DOWNLOADED LSWMD.pkl to canonical CSVs")
    ap.add_argument("--pkl", help="path to your local LSWMD.pkl")
    ap.add_argument("--out", default="wm811k", help="output directory (default wm811k/)")
    ap.add_argument("--per-class", type=int,
                    help="take at most N wafers per label (build a balanced subset)")
    ap.add_argument("--limit", type=int, help="hard cap on wafers converted")
    ap.add_argument("--labeled-only", action="store_true",
                    help="keep only wafers carrying a failureType label")
    args = ap.parse_args()

    if not args.convert:
        print(__doc__)
        print("No download was attempted and none will be. Re-run with --convert once "
              "you have LSWMD.pkl locally AND have recorded its license terms.")
        return 0
    if not args.pkl:
        ap.error("--convert requires --pkl PATH to a local LSWMD.pkl")
    return convert(args.pkl, args.out, args.per_class, args.limit, args.labeled_only)


if __name__ == "__main__":
    sys.exit(main())
