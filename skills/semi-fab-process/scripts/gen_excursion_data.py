#!/usr/bin/env python3
"""Synthesise the sample excursion scenarios shipped with semi-fab-process.

Everything here is SYNTHETIC. The numbers are physically plausible but they are
not measurements from any tool, fab, or process. They exist so the runbook and
the scripts can be exercised end to end and so the evals have a known ground
truth to score against.

Scenarios
  etch   sample-data/semi-fab-process/etch_cd_drift/
         60 lots, 4 process steps. ONE etch chamber (ETCH-02/C) drifts high on
         post-etch CD after a chamber part change; every other tool/chamber is
         healthy. Ground truth: ETCH-02/C, drift starts 2026-07-16.
  metro  sample-data/semi-fab-process/metro_false_alarm/
         44 lots of film thickness. A calibration on metrology tool MET-02
         puts a positive bias on everything it measures afterwards; exactly one
         lot crosses the control limit. Ground truth: NO process problem, the
         metrology tool is biased. The right answer is "re-measure, no hold".
  doe    sample-data/semi-fab-process/doe_etch/
         a 2^(5-2) screening design (unreplicated -> Lenth's method) and a 2^3
         characterisation design with replicates and centre points (-> t-tests
         and a curvature test).

Usage example:
  python3 gen_excursion_data.py --outdir ../../../sample-data/semi-fab-process
  python3 gen_excursion_data.py --outdir /tmp/sd --scenario etch --seed 12
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

D2_N2 = 1.128  # d2 for a moving range of 2


def imr_limits(x: np.ndarray, baseline: int) -> tuple[float, float, float]:
    b = x[:baseline]
    mr = np.abs(np.diff(b))
    sigma = mr.mean() / D2_N2
    cl = b.mean()
    return cl, cl + 3 * sigma, cl - 3 * sigma


# --------------------------------------------------------------------- scenario 1
def gen_etch(outdir: str, seed: int) -> dict:
    """Etch CD drift confined to one chamber, starting after a part change."""
    rng = np.random.default_rng(seed)
    n_lots = 60
    start = date(2026, 7, 1)
    drift_start = date(2026, 7, 16)
    guilty_tool, guilty_chamber = "ETCH-02", "C"

    litho_tools = ["LITH-01", "LITH-02", "LITH-03"]
    litho_off = {"LITH-01": -0.10, "LITH-02": 0.05, "LITH-03": 0.06}
    etch_combos = [(t, c) for t in ("ETCH-01", "ETCH-02") for c in ("A", "B", "C")]
    etch_off = {("ETCH-01", "A"): 0.05, ("ETCH-01", "B"): -0.06, ("ETCH-01", "C"): 0.02,
                ("ETCH-02", "A"): -0.04, ("ETCH-02", "B"): 0.08, ("ETCH-02", "C"): 0.03}
    cmp_tools = ["CMP-01", "CMP-02"]
    cmp_off = {"CMP-01": 0.02, "CMP-02": -0.02}
    metro_tools = ["MET-01", "MET-02"]
    metro_off = {"MET-01": 0.0, "MET-02": 0.04}

    # balanced-ish random assignment, then shuffle
    etch_assign = [etch_combos[i % 6] for i in range(n_lots)]
    rng.shuffle(etch_assign)

    rows, hist, fdc, sites = [], [], [], []
    for i in range(n_lots):
        lot = f"L{i + 1:04d}"
        d = start + timedelta(days=i // 2)
        lt = litho_tools[int(rng.integers(0, 3))]
        et, ec = etch_assign[i]
        ct = cmp_tools[int(rng.integers(0, 2))]
        mt = metro_tools[int(rng.integers(0, 2))]

        days_in = (d - drift_start).days
        excursion = 0.0
        if (et, ec) == (guilty_tool, guilty_chamber) and days_in >= 0:
            excursion = 2.2 * min(1.0, (days_in + 1) / 6.0)  # ramp over ~6 days, then flat

        cd = (45.0 + litho_off[lt] + etch_off[(et, ec)] + cmp_off[ct] + metro_off[mt]
              + excursion + rng.normal(0, 0.30))
        rows.append({"lot_id": lot, "date": d.isoformat(), "litho_tool": lt,
                     "etch_tool": et, "etch_chamber": ec, "cmp_tool": ct, "metro_tool": mt,
                     "cd_nm": round(cd, 3)})
        for step, tool, ch in (("LITHO", lt, ""), ("ETCH", et, ec), ("CMP", ct, ""),
                               ("METRO", mt, "")):
            hist.append({"lot_id": lot, "step": step, "tool": tool, "chamber": ch,
                         "date": d.isoformat()})
        # per-wafer / per-site metrology (3 wafers x 5 sites, radial signature)
        for w in (1, 13, 25):
            for s, radial in enumerate(
                    [0.0, -0.05, -0.05, 0.10, 0.10], start=1):  # centre, 2 mid, 2 edge
                sites.append({"lot_id": lot, "wafer": w, "site": s,
                              "cd_nm": round(cd + radial + rng.normal(0, 0.18), 3)})
        # FDC summary for the etch step
        ep = 62.0 + rng.normal(0, 0.7) + (2.6 * (excursion / 2.2) if excursion else 0.0)
        fdc.append({"lot_id": lot, "date": d.isoformat(), "tool": et, "chamber": ec,
                    "etch_time_s": round(ep + 8.0 + rng.normal(0, 0.4), 2),
                    "endpoint_time_s": round(ep, 2),
                    "chamber_pressure_mtorr": round(30.0 + rng.normal(0, 0.25), 3),
                    "rf_hours_since_pm": round(float((i % 14) * 5.5 + rng.normal(0, 1.5)), 1)})

    events = [
        {"date": "2026-07-03", "tool": "ETCH-01", "chamber": "B", "event": "WET_CLEAN",
         "note": "scheduled chamber wet clean + season"},
        {"date": "2026-07-08", "tool": "CMP-01", "chamber": "", "event": "PM",
         "note": "pad change, conditioner disc replaced"},
        {"date": "2026-07-11", "tool": "LITH-02", "chamber": "", "event": "PM",
         "note": "scheduled optics/stage PM, qual passed"},
        {"date": "2026-07-15", "tool": "ETCH-02", "chamber": "C", "event": "PART_CHANGE",
         "note": "focus ring + upper liner replaced; short season, qual on 1 monitor wafer"},
        {"date": "2026-07-22", "tool": "MET-01", "chamber": "", "event": "CAL",
         "note": "routine CD-SEM magnification calibration, monitor unchanged"},
        {"date": "2026-07-26", "tool": "ETCH-01", "chamber": "A", "event": "WET_CLEAN",
         "note": "scheduled chamber wet clean + season"},
    ]

    d_out = os.path.join(outdir, "etch_cd_drift")
    os.makedirs(d_out, exist_ok=True)
    lots = pd.DataFrame(rows)
    lots.to_csv(os.path.join(d_out, "cd_by_lot.csv"), index=False)
    pd.DataFrame(hist).to_csv(os.path.join(d_out, "history.csv"), index=False)
    pd.DataFrame(sites).to_csv(os.path.join(d_out, "cd_sites.csv"), index=False)
    pd.DataFrame(fdc).to_csv(os.path.join(d_out, "fdc_etch.csv"), index=False)
    pd.DataFrame(events).to_csv(os.path.join(d_out, "events.csv"), index=False)

    x = lots.cd_nm.to_numpy()
    cl, ucl, lcl = imr_limits(x, 30)
    g = lots[(lots.etch_tool == guilty_tool) & (lots.etch_chamber == guilty_chamber)]
    return {"dir": d_out, "lots": n_lots,
            "ground_truth": f"{guilty_tool}/{guilty_chamber} CD drift from {drift_start}",
            "guilty_lots": int(len(g)),
            "guilty_lots_after_drift": int((g.date >= drift_start.isoformat()).sum()),
            "imr_cl": round(cl, 3), "imr_ucl": round(ucl, 3), "imr_lcl": round(lcl, 3),
            "points_above_ucl": int((x > ucl).sum()),
            "spec": "target 45.0 nm, LSL 43.5, USL 46.5"}


# --------------------------------------------------------------------- scenario 2
def gen_metro(outdir: str, seed: int) -> dict:
    """Metrology calibration bias that looks like a process excursion."""
    n_lots, baseline = 44, 30
    start = date(2026, 8, 1)
    cal_day = date(2026, 8, 16)
    bias = 7.0          # angstrom step put on MET-02 by a bad calibration
    sd = 4.0

    dep_combos = [(t, c) for t in ("DEP-01", "DEP-02") for c in ("A", "B")]
    dep_off = {("DEP-01", "A"): 0.8, ("DEP-01", "B"): -0.6,
               ("DEP-02", "A"): -0.9, ("DEP-02", "B"): 0.7}
    rtp_tools = ["RTP-01", "RTP-02"]

    chosen = None
    for offset in range(400):                      # find a realisation with EXACTLY one OOC point
        rng = np.random.default_rng(seed + offset)
        assign = [dep_combos[i % 4] for i in range(n_lots)]
        rng.shuffle(assign)
        recs = []
        for i in range(n_lots):
            d = start + timedelta(days=i // 2)
            dt, dc = assign[i]
            mt = ["MET-01", "MET-02"][i % 2]
            b = 0.0
            if mt == "MET-02" and d >= cal_day:
                b = bias
            recs.append({"lot_id": f"F{i + 1:04d}", "date": d.isoformat(), "dep_tool": dt,
                         "dep_chamber": dc, "rtp_tool": rtp_tools[int(rng.integers(0, 2))],
                         "metro_tool": mt,
                         "thickness_a": round(1000.0 + dep_off[(dt, dc)] + b
                                              + rng.normal(0, sd), 2)})
        df = pd.DataFrame(recs)
        x = df.thickness_a.to_numpy()
        cl, ucl, lcl = imr_limits(x, baseline)
        above = np.where(x > ucl)[0]
        below = np.where(x < lcl)[0]
        if len(above) == 1 and len(below) == 0:
            r = df.iloc[above[0]]
            if r.metro_tool == "MET-02" and r.date >= cal_day.isoformat():
                chosen = (df, cl, ucl, lcl, int(above[0]), offset)
                break
    if chosen is None:
        sys.exit("ERROR: no realisation with exactly one OOC point; change --seed")
    df, cl, ucl, lcl, ooc_i, offset = chosen
    rng = np.random.default_rng(seed + offset + 1000)
    ooc = df.iloc[ooc_i]

    hist = []
    for _, r in df.iterrows():
        for step, tool, ch in (("DEP", r.dep_tool, r.dep_chamber), ("RTP", r.rtp_tool, ""),
                               ("METRO", r.metro_tool, "")):
            hist.append({"lot_id": r.lot_id, "step": step, "tool": tool, "chamber": ch,
                         "date": r.date})

    # daily reference-wafer monitor on each metrology tool (the gauge's own SPC).
    # Starts well before the lots so the chart has a real baseline (>=25 points).
    mon = []
    mon_start = date(2026, 7, 15)
    for dd in range((date(2026, 8, 22) - mon_start).days + 1):
        d = mon_start + timedelta(days=dd)
        for tool in ("MET-01", "MET-02"):
            b = bias if (tool == "MET-02" and d >= cal_day) else 0.0
            base = 1000.0 + (0.2 if tool == "MET-02" else 0.0)
            mon.append({"date": d.isoformat(), "tool": tool, "wafer_id": "REF-STD-07",
                        "reading_a": round(base + b + rng.normal(0, 1.2), 2)})

    metro_events = [
        {"date": "2026-08-04", "tool": "MET-01", "event": "PM",
         "note": "scheduled PM; reference wafer re-measured, within limits"},
        {"date": "2026-08-16", "tool": "MET-02", "event": "CAL",
         "note": "calibration after light-source service; reference-wafer check skipped"},
        {"date": "2026-08-20", "tool": "MET-02", "event": "GAUGE_STUDY",
         "note": "gauge R&R scheduled, not yet run"},
    ]

    # the re-measurement evidence chain for the one OOC lot
    re_rows = [
        {"lot_id": ooc.lot_id, "measurement": "original", "tool": "MET-02",
         "date": ooc.date, "thickness_a": ooc.thickness_a,
         "note": "the reading that tripped the chart"},
        {"lot_id": ooc.lot_id, "measurement": "repeat_same_tool", "tool": "MET-02",
         "date": ooc.date, "thickness_a": round(ooc.thickness_a + rng.normal(0, 0.8), 2),
         "note": "repeatability is fine -- this is not a flyer read"},
        {"lot_id": ooc.lot_id, "measurement": "second_tool", "tool": "MET-01",
         "date": ooc.date, "thickness_a": round(ooc.thickness_a - bias + rng.normal(0, 1.0), 2),
         "note": "same wafers, different metrology tool"},
        {"lot_id": ooc.lot_id, "measurement": "post_recal_same_tool", "tool": "MET-02",
         "date": "2026-08-24",
         "thickness_a": round(ooc.thickness_a - bias + rng.normal(0, 1.0), 2),
         "note": "after MET-02 was re-calibrated against the reference wafer"},
    ]
    post_cal = df[(df.metro_tool == "MET-02") & (df.date >= cal_day.isoformat())]
    for lid in post_cal.lot_id.tail(3):
        if lid == ooc.lot_id:
            continue
        orig = float(df.loc[df.lot_id == lid, "thickness_a"].iloc[0])
        re_rows += [
            {"lot_id": lid, "measurement": "original", "tool": "MET-02",
             "date": df.loc[df.lot_id == lid, "date"].iloc[0], "thickness_a": orig,
             "note": "in spec, but measured after the calibration"},
            {"lot_id": lid, "measurement": "second_tool", "tool": "MET-01",
             "date": "2026-08-21", "thickness_a": round(orig - bias + rng.normal(0, 1.0), 2),
             "note": "same offset appears on every MET-02 lot, not just the OOC one"},
        ]

    d_out = os.path.join(outdir, "metro_false_alarm")
    os.makedirs(d_out, exist_ok=True)
    df.to_csv(os.path.join(d_out, "thickness_by_lot.csv"), index=False)
    pd.DataFrame(hist).to_csv(os.path.join(d_out, "history.csv"), index=False)
    pd.DataFrame(mon).to_csv(os.path.join(d_out, "metro_monitor.csv"), index=False)
    pd.DataFrame(metro_events).to_csv(os.path.join(d_out, "metro_events.csv"), index=False)
    pd.DataFrame(re_rows).to_csv(os.path.join(d_out, "remeasure.csv"), index=False)

    return {"dir": d_out, "lots": n_lots, "seed_offset": offset,
            "ground_truth": f"MET-02 calibration on {cal_day} put a +{bias:.1f} A bias on "
                            f"every lot it measured afterwards; the process is fine",
            "ooc_lot": ooc.lot_id, "ooc_value": float(ooc.thickness_a),
            "imr_cl": round(cl, 2), "imr_ucl": round(ucl, 2), "imr_lcl": round(lcl, 2),
            "spec": "target 1000 A, LSL 970, USL 1030"}


# --------------------------------------------------------------------- scenario 3
def gen_doe(outdir: str, seed: int) -> dict:
    """Two etch DOE datasets: an unreplicated screen and a replicated characterisation."""
    rng = np.random.default_rng(seed)
    d_out = os.path.join(outdir, "doe_etch")
    os.makedirs(d_out, exist_ok=True)

    # --- 2^(5-2) screening, generators D=AB, E=AC, unreplicated -> Lenth
    base = []
    for i in range(8):
        a = 1 if (i >> 0) & 1 else -1
        b = 1 if (i >> 1) & 1 else -1
        c = 1 if (i >> 2) & 1 else -1
        base.append([a, b, c, a * b, a * c])
    X = np.array(base, dtype=float)
    names = ["A_pressure", "B_gap", "C_rf_power", "D_cf4_flow", "E_o2_flow"]
    # true model: A and C dominate, B modest, D/E inert; noise ~0.10 nm
    y = (45.0 - 1.30 * X[:, 0] + 0.35 * X[:, 1] + 0.95 * X[:, 2]
         + 0.02 * X[:, 3] - 0.05 * X[:, 4] + rng.normal(0, 0.10, 8))
    scr = pd.DataFrame(X, columns=names)
    scr.insert(0, "PtType", "factorial")
    scr.insert(0, "RunOrder", rng.permutation(np.arange(1, 9)))
    scr.insert(0, "StdOrder", np.arange(1, 9))
    scr["CD_NM"] = np.round(y, 3)
    scr = scr.sort_values("RunOrder").reset_index(drop=True)
    scr.to_csv(os.path.join(d_out, "screening_2_5_2_response.csv"), index=False)

    # --- 2^3 characterisation on the survivors, 2 replicates + 4 centre points, curvature
    rows = []
    std = 0
    for rep in (1, 2):
        for i in range(8):
            a = 1 if (i >> 0) & 1 else -1
            b = 1 if (i >> 1) & 1 else -1
            c = 1 if (i >> 2) & 1 else -1
            std += 1
            val = (45.0 - 1.28 * a + 0.92 * c + 0.30 * b - 0.41 * a * c
                   + rng.normal(0, 0.16))
            rows.append({"StdOrder": std, "Block": rep, "PtType": "factorial",
                         "A_pressure": a, "B_gap": b, "C_rf_power": c,
                         "CD_NM": round(val, 3)})
    for j in range(4):
        std += 1
        rows.append({"StdOrder": std, "Block": 1 + j % 2, "PtType": "center",
                     "A_pressure": 0, "B_gap": 0, "C_rf_power": 0,
                     "CD_NM": round(45.0 + 0.62 + rng.normal(0, 0.16), 3)})  # curvature
    char = pd.DataFrame(rows)
    char["RunOrder"] = rng.permutation(np.arange(1, len(char) + 1))
    char = char.sort_values("RunOrder").reset_index(drop=True)
    char.to_csv(os.path.join(d_out, "characterisation_2_3_response.csv"), index=False)

    return {"dir": d_out,
            "ground_truth": "screen: A and C are real (B marginal, D/E inert); "
                            "characterisation: A, C, B, AC real + genuine curvature "
                            "(+0.62 nm at the centre) -> RSM is justified",
            "screen_runs": 8, "char_runs": len(char)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", required=True, help="root output directory")
    ap.add_argument("--scenario", default="all", choices=["all", "etch", "metro", "doe"])
    ap.add_argument("--seed", type=int, default=20260820, help="RNG seed (default 20260820)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    todo = ["etch", "metro", "doe"] if args.scenario == "all" else [args.scenario]
    for s in todo:
        info = {"etch": gen_etch, "metro": gen_metro, "doe": gen_doe}[s](args.outdir, args.seed)
        print(f"=== scenario: {s} ===")
        for k, v in info.items():
            print(f"  {k:<24}{v}")
        files = sorted(os.listdir(info["dir"]))
        total = sum(os.path.getsize(os.path.join(info["dir"], f)) for f in files)
        print(f"  files                   {', '.join(files)}")
        print(f"  bytes                   {total}")
    print("\nAll data is synthetic. Do not present it as measured fab data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
