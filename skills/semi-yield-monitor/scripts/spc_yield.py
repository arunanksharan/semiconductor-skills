#!/usr/bin/env python3
"""SPC on wafer sort yield: p-chart / Laney p'-chart / I-MR + Western Electric rules.

Input (one of):
  --input sort_history.csv    lot_id,wafer_id,date,dies,passed
                              (yield_pct or yield accepted in place of passed)
  --die-results X.csv         canonical die_results.csv; one subgroup per wafer

Chart selection (--chart, default auto):
  p        binomial p-chart. Correct ONLY when wafer-to-wafer variation is pure
           binomial sampling noise — rare for real sort yield.
  pprime   Laney p'-chart: p-chart limits widened by sigma_z, the observed
           dispersion of the standardized deviates. Use when overdispersed.
  imr      individuals + moving range on the yield fraction. Use when subgroup
           size is unknown/irrelevant or the metric is not a proportion.
  auto     measures sigma_z and picks p (sigma_z <= 1.2) or pprime (> 1.2).

Western Electric rules applied to the standardized deviates:
  1  one point beyond 3 sigma
  2  2 of 3 consecutive points beyond 2 sigma, same side
  3  4 of 5 consecutive points beyond 1 sigma, same side
  4  8 consecutive points on one side of the centerline
Rule 1 fires on single excursions; rules 2-4 are what catch a small real shift.

Shewhart charts are blind to sustained shifts smaller than roughly 1.5 sigma,
which is exactly the size of a real yield-eroding excursion once wafer-to-wafer
overdispersion is accounted for. Two answers, both reported here:
  * EWMA (lambda 0.2, L 2.7) on the deviates — a small-shift detector, always
    computed and reported alongside the Shewhart verdict.
  * --by lot — pool a lot's wafers into one subgroup. Averaging shrinks sigma
    by ~sqrt(wafers per lot) and turns a sub-sigma wafer shift into a Shewhart
    signal, at the cost of losing per-wafer resolution.

Also reports overdispersion, binary-segmentation change points (overdispersion-
corrected), and an explicit UP-SIDE warning: an out-of-control jump UP is a
signal to verify the test program before celebrating, not a win.

Two-pass discipline: run once, identify assignable causes, then re-run with
--exclude-subgroups so those points stop inflating the centerline and sigma.

Usage examples:
  python spc_yield.py --input sort_history.csv
  python spc_yield.py --input sort_history.csv --baseline-n 21 --png spc.png
  python spc_yield.py --input sort_history.csv --baseline-n 21 --exclude-subgroups L03/W2
  python spc_yield.py --input sort_history.csv --by lot --baseline-lots L01,L02,L03
  python spc_yield.py --die-results die_results.csv --chart imr --json
"""
from __future__ import annotations

import argparse
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

D2_N2 = 1.128          # d2 for moving ranges of size 2
OVERDISP_LIMIT = 1.2   # sigma_z above this -> p-chart limits are too tight


def load_subgroups(args) -> pd.DataFrame:
    """Return tidy subgroups: label, lot_id, wafer_id, date, dies, passed, p."""
    if args.die_results:
        df = pd.read_csv(args.die_results, dtype={"lot_id": str, "wafer_id": str})
        need = {"lot_id", "wafer_id", "pass_flag"}
        if not need.issubset(df.columns):
            sys.exit(f"ERROR: {args.die_results} needs columns {sorted(need)}")
        g = (df.groupby(["lot_id", "wafer_id"], sort=True)
               .agg(dies=("pass_flag", "size"), passed=("pass_flag", "sum"))
               .reset_index())
        g["date"] = ""
        return finish(g)

    df = pd.read_csv(args.input, dtype={"lot_id": str, "wafer_id": str})
    if "lot_id" not in df.columns:
        sys.exit(f"ERROR: {args.input} needs a lot_id column")
    if "wafer_id" not in df.columns:
        df["wafer_id"] = ""
    if "date" not in df.columns:
        df["date"] = ""
    if "dies" not in df.columns:
        sys.exit(f"ERROR: {args.input} needs a 'dies' column (subgroup size)")
    df["dies"] = pd.to_numeric(df["dies"], errors="raise").astype(int)
    if "passed" in df.columns:
        df["passed"] = pd.to_numeric(df["passed"], errors="raise").astype(int)
    else:
        ycol = next((c for c in ("yield_pct", "yield") if c in df.columns), None)
        if ycol is None:
            sys.exit(f"ERROR: {args.input} needs 'passed' or 'yield_pct'/'yield'")
        y = pd.to_numeric(df[ycol], errors="raise").astype(float)
        if y.max() > 1.5:
            y = y / 100.0
        df["passed"] = (y * df["dies"]).round().astype(int)
    return finish(df)


def aggregate_by_lot(df: pd.DataFrame) -> pd.DataFrame:
    g = (df.groupby("lot_id", sort=False)
           .agg(dies=("dies", "sum"), passed=("passed", "sum"),
                date=("date", "first"), wafers=("dies", "size"))
           .reset_index())
    g["wafer_id"] = ""
    return finish(g)


def finish(df: pd.DataFrame) -> pd.DataFrame:
    if (df.dies <= 0).any():
        sys.exit("ERROR: subgroup size 'dies' must be positive")
    if (df.passed > df.dies).any() or (df.passed < 0).any():
        sys.exit("ERROR: 'passed' must lie in [0, dies]")
    df = df.reset_index(drop=True)
    df["p"] = df.passed / df.dies
    df["label"] = [f"{a}/{b}" if b else str(a) for a, b in zip(df.lot_id, df.wafer_id)]
    if len(df) < 8:
        print(f"WARNING: only {len(df)} subgroups. Control limits from fewer than ~20-25 "
              "subgroups are unstable; treat every signal as provisional.", file=sys.stderr)
    return df


def baseline_mask(df: pd.DataFrame, n: int | None, lots: str | None,
                  exclude: str | None) -> np.ndarray:
    if lots:
        want = {s.strip() for s in lots.split(",") if s.strip()}
        m = df.lot_id.isin(want).to_numpy()
        if not m.any():
            sys.exit(f"ERROR: no subgroup matches --baseline-lots {sorted(want)}")
    else:
        m = np.zeros(len(df), bool)
        m[: (n if n else len(df))] = True
    if exclude:
        drop = {s.strip() for s in exclude.split(",") if s.strip()}
        labels = set(df.label)
        unknown = drop - labels
        if unknown:
            sys.exit(f"ERROR: --exclude-subgroups {sorted(unknown)} not found. "
                     f"Labels look like {sorted(labels)[:3]}")
        m = m & ~df.label.isin(drop).to_numpy()
    if m.sum() < 2:
        sys.exit("ERROR: fewer than 2 baseline subgroups remain; widen the baseline window")
    return m


def sigma_z_estimate(z: np.ndarray) -> float:
    """Laney sigma_z from the average moving range of the standardized deviates."""
    if len(z) < 2:
        return 1.0
    mr = np.abs(np.diff(z))
    return float(max(mr.mean() / D2_N2, 1e-9))


def western_electric(z: np.ndarray) -> list[dict]:
    """Violations of WE rules 1-4 on standardized deviates z."""
    v = []
    for i, zi in enumerate(z):
        if abs(zi) >= 3:
            v.append({"rule": 1, "index": i, "side": "high" if zi > 0 else "low",
                      "detail": f"z={zi:+.2f} beyond 3 sigma"})
    for i in range(len(z) - 2):
        w = z[i:i + 3]
        for side, sgn in (("high", 1), ("low", -1)):
            if (sgn * w >= 2).sum() >= 2:
                v.append({"rule": 2, "index": i + 2, "side": side,
                          "detail": f"2 of 3 beyond 2 sigma {side} (z={np.round(w, 2).tolist()})"})
    for i in range(len(z) - 4):
        w = z[i:i + 5]
        for side, sgn in (("high", 1), ("low", -1)):
            if (sgn * w >= 1).sum() >= 4:
                v.append({"rule": 3, "index": i + 4, "side": side,
                          "detail": f"4 of 5 beyond 1 sigma {side}"})
    for i in range(len(z) - 7):
        w = z[i:i + 8]
        for side, sgn in (("high", 1), ("low", -1)):
            if (sgn * w > 0).all():
                v.append({"rule": 4, "index": i + 7, "side": side,
                          "detail": f"8 consecutive {side} of centerline"})
    # rule 1 is reported for every point; rules 2-4 only on their first firing
    # per side, so a long run does not bury the output in duplicates
    seen, out = set(), []
    for d in sorted(v, key=lambda d: (d["index"], d["rule"])):
        if d["rule"] == 1:
            out.append(d)
            continue
        if (d["rule"], d["side"]) in seen:
            continue
        seen.add((d["rule"], d["side"]))
        out.append(d)
    return sorted(out, key=lambda d: d["index"])


def ewma_signal(z: np.ndarray, lam: float = 0.2, L: float = 2.7):
    """EWMA on the standardized deviates: catches sustained sub-sigma shifts."""
    e, vals, lims = 0.0, [], []
    for t, zt in enumerate(z, start=1):
        e = lam * zt + (1 - lam) * e
        vals.append(e)
        lims.append(L * float(np.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * t)))))
    vals, lims = np.array(vals), np.array(lims)
    crossings = [int(i) for i in np.nonzero(np.abs(vals) > lims)[0]]
    runs = []
    for i in crossings:
        side = "high" if vals[i] > 0 else "low"
        if runs and runs[-1]["end"] == i - 1 and runs[-1]["side"] == side:
            runs[-1]["end"] = i
        else:
            runs.append({"start": i, "end": i, "side": side})
    first = crossings[0] if crossings else None
    return {"lambda": lam, "L": L, "values": vals, "limits": lims,
            "first_signal_index": first,
            "first_signal_side": (None if first is None
                                  else ("high" if vals[first] > 0 else "low")),
            "n_signals": len(crossings), "runs": runs}


def two_prop_z(f1, n1, f2, n2, sigma_z: float) -> float:
    if n1 == 0 or n2 == 0:
        return 0.0
    p = (f1 + f2) / (n1 + n2)
    se = np.sqrt(max(p * (1 - p) * (1 / n1 + 1 / n2), 1e-18)) * sigma_z
    return float((f1 / n1 - f2 / n2) / se)


def change_points(passed, dies, sigma_z, thresh=4.0, min_seg=3, max_cp=3) -> list[dict]:
    """Binary segmentation on the yield series; z corrected for overdispersion.

    z is signed like delta_pp: negative = yield dropped after the split.
    """
    found = []

    def rec(lo, hi, depth=0):
        if len(found) >= max_cp or hi - lo < 2 * min_seg or depth > 4:
            return
        best = None
        for k in range(lo + min_seg, hi - min_seg + 1):
            z = two_prop_z(passed[k:hi].sum(), dies[k:hi].sum(),
                           passed[lo:k].sum(), dies[lo:k].sum(), sigma_z)
            if best is None or abs(z) > abs(best[1]):
                best = (k, z)
        if best is None or abs(best[1]) < thresh:
            return
        k, z = best
        before = passed[lo:k].sum() / dies[lo:k].sum()
        after = passed[k:hi].sum() / dies[k:hi].sum()
        found.append({"index": int(k), "z": round(z, 2),
                      "mean_before_pct": round(100 * before, 2),
                      "mean_after_pct": round(100 * after, 2),
                      "delta_pp": round(100 * (after - before), 2)})
        rec(lo, k, depth + 1)
        rec(k, hi, depth + 1)

    rec(0, len(passed))
    return sorted(found, key=lambda d: d["index"])


def build_chart(df: pd.DataFrame, chart: str, base: np.ndarray) -> dict:
    passed = df.passed.to_numpy()
    dies = df.dies.to_numpy()
    p = df.p.to_numpy()

    cl = passed[base].sum() / dies[base].sum()
    sig_binom = np.sqrt(np.maximum(cl * (1 - cl) / dies, 1e-18))
    z_binom = (p - cl) / sig_binom
    sz = sigma_z_estimate(z_binom[base])

    if chart == "auto":
        chart = "pprime" if sz > OVERDISP_LIMIT else "p"

    if chart == "p":
        sigma = sig_binom
    elif chart == "pprime":
        sigma = sig_binom * sz
    elif chart == "imr":
        mr = np.abs(np.diff(p[base]))
        s = float(mr.mean() / D2_N2) if len(mr) else float(p[base].std(ddof=1))
        cl = float(p[base].mean())
        sigma = np.full(len(p), max(s, 1e-12))
    else:
        sys.exit(f"ERROR: unknown --chart {chart}")

    z = (p - cl) / sigma
    return {"chart": chart, "cl": float(cl), "sigma": sigma, "z": z,
            "sigma_z": float(sz), "ucl": cl + 3 * sigma, "lcl": np.maximum(cl - 3 * sigma, 0.0)}


def png(df, ch, viol, ew, out, title):
    idx = np.arange(len(df))
    bad = {v["index"] for v in viol}
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1]})
    ax.plot(idx, 100 * df.p, "o-", color="#1c7ed6", ms=4, lw=1, zorder=3, label="yield")
    if bad:
        b = sorted(bad)
        ax.plot(b, 100 * df.p.to_numpy()[b], "o", color="#e03131", ms=9,
                zorder=4, label="WE violation")
    ax.axhline(100 * ch["cl"], color="#495057", lw=1.2, label=f"CL {100*ch['cl']:.2f}%")
    ax.plot(idx, 100 * ch["ucl"], color="#e03131", lw=1, ls="--", label="UCL/LCL (3 sigma)")
    ax.plot(idx, 100 * ch["lcl"], color="#e03131", lw=1, ls="--")
    for s in (1, 2):
        ax.plot(idx, 100 * (ch["cl"] + s * ch["sigma"]), color="#adb5bd", lw=0.6, ls=":")
        ax.plot(idx, 100 * (ch["cl"] - s * ch["sigma"]), color="#adb5bd", lw=0.6, ls=":")
    ax.set_ylabel("yield %")
    ax.set_title(title)
    ax.legend(fontsize=7, loc="lower left")

    ax2.plot(idx, ew["values"], "o-", color="#7048e8", ms=3, lw=1, label="EWMA(z)")
    ax2.plot(idx, ew["limits"], color="#e03131", lw=1, ls="--",
             label=f"+/-{ew['L']} sigma_EWMA")
    ax2.plot(idx, -ew["limits"], color="#e03131", lw=1, ls="--")
    ax2.axhline(0, color="#495057", lw=0.8)
    if ew["first_signal_index"] is not None:
        ax2.axvline(ew["first_signal_index"], color="#f08c00", lw=1.2, ls="-.",
                    label=f"first EWMA signal @ {df.label[ew['first_signal_index']]}")
    ax2.set_ylabel(f"EWMA (lambda={ew['lambda']})")
    ax2.legend(fontsize=7, loc="lower left")

    step = max(1, len(df) // 24)
    ax2.set_xticks(idx[::step])
    ax2.set_xticklabels(df.label[::step], rotation=90, fontsize=6)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="sort_history.csv (lot_id,wafer_id,date,dies,passed)")
    src.add_argument("--die-results", help="die_results.csv; one subgroup per wafer")
    ap.add_argument("--chart", default="auto", choices=("auto", "p", "pprime", "imr"),
                    help="control chart type (default auto)")
    ap.add_argument("--by", default="wafer", choices=("wafer", "lot"),
                    help="subgroup granularity (default wafer)")
    ap.add_argument("--baseline-n", type=int,
                    help="use the first N subgroups to set the limits (default: all)")
    ap.add_argument("--baseline-lots",
                    help="comma-separated lot_ids that define the baseline window")
    ap.add_argument("--exclude-subgroups",
                    help="comma-separated subgroup labels (e.g. L03/W2) to drop from the "
                         "LIMIT estimate after their assignable cause is confirmed; they "
                         "are still plotted and still tested")
    ap.add_argument("--png", help="write the control chart to this PNG path")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    df = load_subgroups(args)
    if args.by == "lot":
        df = aggregate_by_lot(df)
    base = baseline_mask(df, args.baseline_n, args.baseline_lots, args.exclude_subgroups)
    ch = build_chart(df, args.chart, base)
    viol = western_electric(ch["z"])
    ew = ewma_signal(ch["z"])
    cps = change_points(df.passed.to_numpy(), df.dies.to_numpy(), ch["sigma_z"])

    sides = {v["side"] for v in viol} | ({ew["first_signal_side"]}
                                         if ew["first_signal_side"] else set())
    if not viol and ew["first_signal_index"] is None:
        verdict = "IN CONTROL — no Western Electric rule and no EWMA signal"
    elif sides == {"low"}:
        verdict = "OUT OF CONTROL — LOW side"
    elif sides == {"high"}:
        verdict = "OUT OF CONTROL — HIGH side (yield UP)"
    else:
        verdict = "OUT OF CONTROL — both sides"

    out = {
        "chart": ch["chart"], "requested_chart": args.chart, "by": args.by,
        "subgroups": int(len(df)),
        "baseline_subgroups": int(base.sum()),
        "centerline_pct": round(100 * ch["cl"], 3),
        "sigma_z_overdispersion": round(ch["sigma_z"], 3),
        "overdispersed": bool(ch["sigma_z"] > OVERDISP_LIMIT),
        "verdict": verdict,
        "violations": [dict(v, label=df.label[v["index"]],
                            yield_pct=round(100 * df.p[v["index"]], 2)) for v in viol],
        "ewma": {"lambda": ew["lambda"], "L": ew["L"], "n_signals": ew["n_signals"],
                 "first_signal_index": ew["first_signal_index"],
                 "first_signal_side": ew["first_signal_side"],
                 "first_signal_label": (None if ew["first_signal_index"] is None
                                        else df.label[ew["first_signal_index"]]),
                 "runs": [dict(r, start_label=df.label[r["start"]],
                               end_label=df.label[r["end"]]) for r in ew["runs"]]},
        "change_points": [dict(c, label=df.label[c["index"]]) for c in cps],
        "first_signal": ({"index": viol[0]["index"], "label": df.label[viol[0]["index"]],
                          "rule": viol[0]["rule"]} if viol else None),
    }
    if args.png:
        png(df, ch, viol, ew, args.png,
            f"{ch['chart']}-chart — sort yield by {args.by} ({len(df)} subgroups)")
        out["png"] = args.png

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"subgroups: {out['subgroups']} (by {args.by})  baseline: {out['baseline_subgroups']}  "
          f"chart: {ch['chart']}" + (" (auto)" if args.chart == "auto" else ""))
    print(f"centerline: {out['centerline_pct']}%   sigma_z (overdispersion): "
          f"{out['sigma_z_overdispersion']}")
    if out["overdispersed"]:
        fix = {"pprime": "p'-chart limits in use, widened by sigma_z.",
               "imr": "the I-MR limits in use already absorb it.",
               "p": "these p-chart limits are TOO TIGHT — rerun with --chart auto or imr."}
        print("  -> wafer-to-wafer scatter exceeds binomial noise, so a plain p-chart would "
              f"flag normal variation. {fix.get(ch['chart'], '')}")
    else:
        print("  -> dispersion consistent with binomial sampling; a plain p-chart is valid.")
    print(f"\nVERDICT: {verdict}")
    if viol:
        print(f"\nShewhart / Western Electric violations:")
        print(f"{'idx':<5}{'subgroup':<12}{'yield%':<9}{'rule':<6}{'side':<6}detail")
        for v in out["violations"]:
            print(f"{v['index']:<5}{v['label']:<12}{v['yield_pct']:<9}{v['rule']:<6}"
                  f"{v['side']:<6}{v['detail']}")
    else:
        print("\nShewhart / Western Electric: no rule fired.")
    e = out["ewma"]
    if e["first_signal_index"] is None:
        print(f"EWMA (lambda={e['lambda']}, L={e['L']}): no signal — no sustained shift "
              "large enough to accumulate.")
    else:
        print(f"EWMA (lambda={e['lambda']}, L={e['L']}): first signal at idx "
              f"{e['first_signal_index']} ({e['first_signal_label']}), {e['first_signal_side']} "
              f"side, {e['n_signals']} subgroups signalling. EWMA catches sustained shifts "
              "the Shewhart rules are too blunt to see.")
        for r in e["runs"]:
            span = (r["start_label"] if r["start"] == r["end"]
                    else f"{r['start_label']}..{r['end_label']}")
            print(f"    run idx {r['start']}-{r['end']} ({span}) {r['side']} side")
    if viol or e["first_signal_index"] is not None:
        if "high" in sides:
            print("\nUP-SIDE SIGNAL — DO NOT CELEBRATE YET. A yield jump is a control-chart "
                  "violation like any other. Verify before accepting it: test-program or "
                  "limit revision, bin-map/binning change, tester or probe-card swap, "
                  "retest/rebin policy change, sampled-not-full-map data, or a genuine "
                  "process fix with a documented change record.")
    if cps:
        print("\nchange points (binary segmentation, overdispersion-corrected):")
        for c in out["change_points"]:
            print(f"  at idx {c['index']} ({c['label']}): {c['mean_before_pct']}% -> "
                  f"{c['mean_after_pct']}%  ({c['delta_pp']:+} pp, z={c['z']})")
    if args.png:
        print(f"\nwrote {args.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
