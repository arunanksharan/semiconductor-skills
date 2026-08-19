#!/usr/bin/env python3
"""SPC control charts for fab tool parameters and inline metrology:
I-MR (individuals + moving range), Xbar-R, and EWMA, with Western Electric
rules and a plain-text verdict. Writes a PNG and prints/returns the violations.

Chart choice (see references/fdc-spc.md):
  I-MR    one value per lot/wafer/run -- the fab default for inline metrology
          and for slow tool parameters sampled once per run
  Xbar-R  a rational subgroup of >=2 measurements taken under conditions as
          alike as possible (e.g. 5 sites on one wafer, one chamber, one run)
  EWMA    slow drift you want to catch early (chamber seasoning, target/pad
          wear, precursor depletion); lambda 0.1-0.3 for gradual drift

--baseline N freezes the limits on the first N points, which is what you want
when you are asking "did this excursion break a previously stable process?"
Limits computed over the excursion itself are inflated and will hide it.

Usage examples:
  python3 spc_charts.py --data cd_by_lot.csv --value cd_nm --label lot_id \\
      --chart imr --baseline 30 --png cd_imr.png
  python3 spc_charts.py --data cd_by_lot.csv --value cd_nm --label lot_id \\
      --where etch_tool=ETCH-02 --where etch_chamber=C --chart imr --baseline 20
  python3 spc_charts.py --data cd_sites.csv --value cd_nm --subgroup-col lot_id --chart xbar-r
  python3 spc_charts.py --data metro_monitor.csv --value reading_nm --chart ewma --lambda 0.2
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

# Standard Shewhart control-chart constants (subgroup size n).
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337,
      10: 0.308, 11: 0.285, 12: 0.266, 13: 0.249, 14: 0.235, 15: 0.223, 16: 0.212,
      17: 0.203, 18: 0.194, 19: 0.187, 20: 0.180, 21: 0.173, 22: 0.167, 23: 0.162,
      24: 0.157, 25: 0.153}
D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223,
      11: 0.256, 12: 0.283, 13: 0.307, 14: 0.328, 15: 0.347, 16: 0.363, 17: 0.378,
      18: 0.391, 19: 0.403, 20: 0.415, 21: 0.425, 22: 0.434, 23: 0.443, 24: 0.451,
      25: 0.459}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816,
      10: 1.777, 11: 1.744, 12: 1.717, 13: 1.693, 14: 1.672, 15: 1.653, 16: 1.637,
      17: 1.622, 18: 1.608, 19: 1.597, 20: 1.585, 21: 1.575, 22: 1.566, 23: 1.557,
      24: 1.548, 25: 1.541}
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970,
      10: 3.078, 11: 3.173, 12: 3.258, 13: 3.336, 14: 3.407, 15: 3.472, 16: 3.532,
      17: 3.588, 18: 3.640, 19: 3.689, 20: 3.735, 21: 3.778, 22: 3.819, 23: 3.858,
      24: 3.895, 25: 3.931}


def western_electric(x: np.ndarray, cl: float, sigma: float, labels: list[str]) -> list[dict]:
    """WE rules 1-4 plus two supplementary run rules. Returns one dict per hit."""
    if sigma <= 0:
        return []
    z = (x - cl) / sigma
    n = len(z)
    hits: list[dict] = []

    def add(rule, idx, desc):
        hits.append({"rule": rule, "index": int(idx), "label": labels[idx],
                     "value": float(x[idx]), "z": float(z[idx]), "description": desc})

    for i in range(n):
        if abs(z[i]) > 3:
            add(1, i, "point beyond 3 sigma")
    for i in range(2, n):
        w = z[i - 2:i + 1]
        for s in (1, -1):
            if np.sum(s * w > 2) >= 2 and s * z[i] > 2:
                add(2, i, "2 of 3 consecutive beyond 2 sigma, same side")
                break
    for i in range(4, n):
        w = z[i - 4:i + 1]
        for s in (1, -1):
            if np.sum(s * w > 1) >= 4 and s * z[i] > 1:
                add(3, i, "4 of 5 consecutive beyond 1 sigma, same side")
                break
    for i in range(7, n):
        w = z[i - 7:i + 1]
        if np.all(w > 0) or np.all(w < 0):
            add(4, i, "8 consecutive on one side of the centre line")
    for i in range(5, n):
        d = np.diff(x[i - 5:i + 1])
        if np.all(d > 0) or np.all(d < 0):
            add(5, i, "6 consecutive rising or falling (supplementary: trend)")
    for i in range(14, n):
        if np.all(np.abs(z[i - 14:i + 1]) < 1):
            add(6, i, "15 consecutive within 1 sigma (supplementary: limits too wide, "
                      "or stratified sampling)")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--data", required=True, help="input CSV")
    ap.add_argument("--value", required=True, help="numeric column to chart")
    ap.add_argument("--label", help="column to use as the point label (e.g. lot_id)")
    ap.add_argument("--chart", default="imr", choices=["imr", "xbar-r", "ewma"])
    ap.add_argument("--subgroup-col", help="xbar-r: column defining the rational subgroup")
    ap.add_argument("--where", action="append", default=[],
                    help="filter rows, col=value (repeatable)")
    ap.add_argument("--sort-col", help="sort by this column (default: 'date' if present)")
    ap.add_argument("--baseline", type=int,
                    help="compute limits from the first N points only (frozen limits)")
    ap.add_argument("--lambda", dest="lam", type=float, default=0.2,
                    help="EWMA smoothing constant (default 0.2)")
    ap.add_argument("--L", type=float, default=3.0, help="EWMA control limit width (default 3.0)")
    ap.add_argument("--usl", type=float, help="upper spec limit (for Cp/Cpk)")
    ap.add_argument("--lsl", type=float, help="lower spec limit (for Cp/Cpk)")
    ap.add_argument("--png", help="write the chart PNG here")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    df = pd.read_csv(args.data)
    for w in args.where:
        if "=" not in w:
            sys.exit(f"ERROR: --where {w!r} must be col=value")
        c, v = w.split("=", 1)
        if c not in df.columns:
            sys.exit(f"ERROR: --where column {c!r} not in {list(df.columns)}")
        df = df[df[c].astype(str) == v]
    if args.value not in df.columns:
        sys.exit(f"ERROR: --value {args.value!r} not in {list(df.columns)}")
    sort_col = args.sort_col or ("date" if "date" in df.columns else None)
    if sort_col:
        df = df.sort_values(sort_col, kind="mergesort")  # stable: ties keep file order
    df = df[pd.to_numeric(df[args.value], errors="coerce").notna()].reset_index(drop=True)
    if df.empty:
        sys.exit("ERROR: no rows left after filtering")

    out: dict = {"data": args.data, "value": args.value, "chart": args.chart,
                 "filters": args.where, "n_rows": int(len(df)), "violations": [],
                 "warnings": []}

    # ------------------------------------------------------------ chart maths
    if args.chart == "xbar-r":
        if not args.subgroup_col:
            sys.exit("ERROR: --chart xbar-r needs --subgroup-col")
        g = df.groupby(args.subgroup_col, sort=False)[args.value]
        sizes = g.size()
        if sizes.nunique() != 1:
            sys.exit(f"ERROR: subgroup sizes vary ({sorted(sizes.unique())}); Xbar-R needs a "
                     f"constant n. Fix the sampling plan or chart individuals instead.")
        n = int(sizes.iloc[0])
        if not (2 <= n <= 25):
            sys.exit(f"ERROR: subgroup size {n} outside the constant table (2..25)")
        xbar = g.mean().to_numpy()
        rng = (g.max() - g.min()).to_numpy()
        labels = [str(k) for k in g.groups.keys()]
        base = slice(0, args.baseline) if args.baseline else slice(None)
        cl, rbar = float(xbar[base].mean()), float(rng[base].mean())
        sigma = rbar / D2[n]
        ucl, lcl = cl + A2[n] * rbar, cl - A2[n] * rbar
        second = {"name": "R", "values": rng.tolist(), "cl": rbar,
                  "ucl": D4[n] * rbar, "lcl": D3[n] * rbar}
        primary, pname = xbar, f"Xbar (n={n})"
        out["subgroup_size"] = n
    else:
        primary = df[args.value].astype(float).to_numpy()
        labels = ([str(v) for v in df[args.label]] if args.label and args.label in df.columns
                  else [str(i + 1) for i in range(len(primary))])
        base = slice(0, args.baseline) if args.baseline else slice(None)
        mr = np.abs(np.diff(primary))
        mrbase = mr[: args.baseline - 1] if args.baseline else mr
        if len(mrbase) == 0:
            sys.exit("ERROR: need at least 2 points")
        mrbar = float(mrbase.mean())
        cl = float(primary[base].mean())
        sigma = mrbar / D2[2]
        ucl, lcl = cl + 3 * sigma, cl - 3 * sigma
        second = {"name": "MR", "values": mr.tolist(), "cl": mrbar,
                  "ucl": D4[2] * mrbar, "lcl": 0.0}
        pname = "Individuals"
        if args.chart == "ewma":
            z = np.empty(len(primary))
            prev = cl
            for i, v in enumerate(primary):
                prev = args.lam * v + (1 - args.lam) * prev
                z[i] = prev
            i_arr = np.arange(1, len(primary) + 1)
            width = args.L * sigma * np.sqrt(
                args.lam / (2 - args.lam) * (1 - (1 - args.lam) ** (2 * i_arr)))
            out["ewma"] = {"lambda": args.lam, "L": args.L,
                           "z": z.tolist(), "ucl": (cl + width).tolist(),
                           "lcl": (cl - width).tolist()}

    out.update({"center_line": float(cl), "sigma": float(sigma), "ucl": float(ucl),
                "lcl": float(lcl), "n_points": int(len(primary)),
                "baseline_points": int(args.baseline) if args.baseline else int(len(primary))})
    if args.baseline:
        out["warnings"].append(
            f"limits FROZEN on the first {args.baseline} points "
            f"({labels[0]} .. {labels[min(args.baseline, len(labels)) - 1]})")
        if args.baseline < 20:
            out["warnings"].append(
                f"baseline of {args.baseline} points is thin; limits from <20-25 points are "
                f"themselves uncertain and will over- or under-alarm")

    # ------------------------------------------------------------ violations
    if args.chart == "ewma":
        z = np.array(out["ewma"]["z"])
        u, l = np.array(out["ewma"]["ucl"]), np.array(out["ewma"]["lcl"])
        for i in range(len(z)):
            if z[i] > u[i] or z[i] < l[i]:
                out["violations"].append({"rule": "EWMA", "index": int(i), "label": labels[i],
                                          "value": float(primary[i]), "ewma": float(z[i]),
                                          "description": "EWMA statistic outside its limits"})
        out["verdict"] = ("OUT OF CONTROL" if out["violations"] else "IN CONTROL")
    else:
        out["violations"] = western_electric(primary, cl, sigma, labels)
        core = [v for v in out["violations"] if v["rule"] in (1, 2, 3, 4)]
        out["verdict"] = "OUT OF CONTROL" if core else (
            "IN CONTROL (supplementary run rules only)" if out["violations"] else "IN CONTROL")
        mrv = [{"rule": "MR", "index": i + 1, "label": labels[i + 1], "value": float(second["values"][i]),
                "description": "moving range beyond its UCL -- a single-point jump, not a shift"}
               for i in range(len(second["values"])) if second["values"][i] > second["ucl"]]
        out["range_violations"] = mrv

    # ------------------------------------------------------------ capability
    if args.usl is not None or args.lsl is not None:
        cap = {"usl": args.usl, "lsl": args.lsl, "sigma_within": float(sigma)}
        if args.usl is not None and args.lsl is not None and sigma > 0:
            cap["Cp"] = (args.usl - args.lsl) / (6 * sigma)
        parts = []
        if args.usl is not None and sigma > 0:
            parts.append((args.usl - cl) / (3 * sigma))
        if args.lsl is not None and sigma > 0:
            parts.append((cl - args.lsl) / (3 * sigma))
        if parts:
            cap["Cpk"] = float(min(parts))
        out["capability"] = cap
        if args.usl is not None and ucl > args.usl or args.lsl is not None and lcl < args.lsl:
            out["warnings"].append(
                "control limits fall outside the spec limits: the process is not capable of "
                "meeting spec even when it is in control -- do not 'fix' this by widening the "
                "control limits")

    # ------------------------------------------------------------ plot
    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        nax = 2 if args.chart != "ewma" else 1
        fig, axes = plt.subplots(nax, 1, figsize=(10, 3.2 * nax + 1), dpi=120, squeeze=False)
        ax = axes[0][0]
        idx = np.arange(len(primary))
        if args.chart == "ewma":
            ax.plot(idx, primary, "o-", ms=3, lw=0.7, color="#999999", label="raw")
            ax.plot(idx, out["ewma"]["z"], "o-", ms=4, color="#1f77b4", label="EWMA")
            ax.plot(idx, out["ewma"]["ucl"], "r--", lw=1)
            ax.plot(idx, out["ewma"]["lcl"], "r--", lw=1)
            ax.axhline(cl, color="green", lw=1)
            ax.set_title(f"EWMA (lambda={args.lam}, L={args.L}) -- {args.value}")
            ax.legend(fontsize=8)
        else:
            ax.plot(idx, primary, "o-", ms=4, color="#1f77b4")
            ax.axhline(cl, color="green", lw=1, label=f"CL={cl:.4g}")
            ax.axhline(ucl, color="red", ls="--", lw=1, label=f"UCL={ucl:.4g}")
            ax.axhline(lcl, color="red", ls="--", lw=1, label=f"LCL={lcl:.4g}")
            for s in (1, 2):
                ax.axhline(cl + s * sigma, color="orange", ls=":", lw=0.6)
                ax.axhline(cl - s * sigma, color="orange", ls=":", lw=0.6)
            bad = sorted({v["index"] for v in out["violations"] if v["rule"] in (1, 2, 3, 4)})
            if bad:
                ax.plot(bad, primary[bad], "s", ms=8, mfc="none", mec="red", mew=1.6,
                        label="WE violation")
            ax.set_title(f"{pname} -- {args.value}"
                         + (f"  [{' '.join(args.where)}]" if args.where else ""))
            ax.legend(fontsize=8, loc="best")
        if args.usl is not None:
            ax.axhline(args.usl, color="black", lw=0.8, ls="-.")
        if args.lsl is not None:
            ax.axhline(args.lsl, color="black", lw=0.8, ls="-.")
        step = max(1, len(labels) // 25)
        ax.set_xticks(idx[::step])
        ax.set_xticklabels(labels[::step], rotation=90, fontsize=6)
        ax.grid(alpha=0.25)
        if nax == 2:
            ax2 = axes[1][0]
            ax2.plot(np.arange(1, len(second["values"]) + 1), second["values"], "o-", ms=4,
                     color="#7f7f7f")
            ax2.axhline(second["cl"], color="green", lw=1)
            ax2.axhline(second["ucl"], color="red", ls="--", lw=1)
            ax2.axhline(second["lcl"], color="red", ls="--", lw=1)
            ax2.set_title(f"{second['name']} chart (CL={second['cl']:.4g}, "
                          f"UCL={second['ucl']:.4g})")
            ax2.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(args.png)
        plt.close(fig)

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"chart      : {args.chart}   value: {args.value}   n = {out['n_points']}"
          + (f"   filters: {' '.join(args.where)}" if args.where else ""))
    print(f"limits     : CL {cl:.4f}   UCL {ucl:.4f}   LCL {lcl:.4f}   "
          f"sigma_hat {sigma:.4f}"
          + (f"   (from first {args.baseline} points)" if args.baseline else ""))
    if args.chart != "ewma":
        print(f"{second['name']} chart    : CL {second['cl']:.4f}   UCL {second['ucl']:.4f}")
    if "capability" in out:
        c = out["capability"]
        print(f"capability : " + "  ".join(f"{k}={v:.3f}" for k, v in c.items()
                                           if k in ("Cp", "Cpk")))
    print(f"\nVERDICT    : {out['verdict']}")
    if out["violations"]:
        print(f"{'rule':<6}{'point':<14}{'value':>12}{'z':>8}  description")
        for v in out["violations"]:
            zt = f"{v['z']:+.2f}" if "z" in v else ""
            print(f"{str(v['rule']):<6}{v['label']:<14}{v['value']:>12.4f}{zt:>8}  "
                  f"{v['description']}")
    else:
        print("no Western Electric rule fired")
    for v in out.get("range_violations", []):
        print(f"MR    {v['label']:<14}{v['value']:>12.4f}          {v['description']}")
    for w in out["warnings"]:
        print(f"\nNOTE: {w}")
    if args.png:
        print(f"\nwrote {args.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
