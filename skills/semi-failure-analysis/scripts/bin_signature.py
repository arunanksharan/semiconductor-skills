#!/usr/bin/env python3
"""Bin-signature analysis for failure analysis: paretos, spatial character, failing-test correlation.

Reads the canonical wafer-sort schemas shared with semi-yield-monitor:

  die_results.csv : lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag
  tests.csv       : lot_id,wafer_id,die_x,die_y,test_num,test_name,value,lo_lim,hi_lim   (optional)

and computes, per soft bin:
  * fail count, share of all fails, and yield loss in absolute percentage points
  * an adjacency clustering statistic - observed 4-neighbour adjacent fail pairs vs the
    distribution obtained by randomly re-placing the same number of fails on the same die
    sites (Monte Carlo, fixed seed) -> ratio and z-score
  * radial zone analysis (center / mid / edge by normalized radius) -> per-zone fail rate
    vs the wafer mean, with a binomial z-score
  * from tests.csv: the test that most often fails for that bin, and the margin distribution
    of that test (just-outside = parametric shift vs far-outside = hard defect, bimodal = two
    populations)

Every number here comes from the data. Interpretation is the agent's job - see
references/bin-signature-analysis.md.

Usage example:
  python bin_signature.py --die-results die_results.csv --tests tests.csv --outdir out/
  python bin_signature.py --die-results die_results.csv --bin 71 --outdir out/ --no-plots

Exit codes: 0 analysis produced · 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "0.1.0"

DIE_COLS = ["lot_id", "wafer_id", "die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"]
TEST_COLS = ["lot_id", "wafer_id", "die_x", "die_y", "test_num", "test_name",
             "value", "lo_lim", "hi_lim"]

ZONES = (("center", 0.0, 0.33), ("mid", 0.33, 0.70), ("edge", 0.70, 1.01))

# Below this expected adjacent-pair count the clustering statistic is integer-noise dominated
# and reports `inconclusive_low_power` instead of a verdict. Industry-typical minimum-expected-
# count convention for count statistics; tune per product and die-grid size.
MIN_EXPECTED_ADJACENCY = 5.0


# --------------------------------------------------------------------------- io
def load_die_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in DIE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; expected {DIE_COLS}")
    for c in ("die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["die_x", "die_y"]].isna().any().any():
        raise ValueError(f"{path}: non-numeric die coordinates present")
    return df


def load_tests(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in TEST_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; expected {TEST_COLS}")
    for c in ("die_x", "die_y", "test_num", "value", "lo_lim", "hi_lim"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ------------------------------------------------------------------- statistics
def adjacency_pairs(coords: set[tuple[int, int]], fails: set[tuple[int, int]]) -> int:
    """4-neighbour adjacent pairs where BOTH dies are in `fails` (each pair counted once)."""
    n = 0
    for (x, y) in fails:
        if (x + 1, y) in fails:
            n += 1
        if (x, y + 1) in fails:
            n += 1
    return n


def clustering_stat(sites: list[tuple[int, int]], fail_sites: list[tuple[int, int]],
                    n_perm: int, rng: np.random.Generator) -> dict:
    """Observed adjacency vs a random re-placement of the same number of fails.

    Returns ratio (obs/expected) and a Monte-Carlo z-score. ratio >> 1 with a large z means
    the fails touch each other far more than chance: a spatial defect, not random defectivity.
    """
    site_set = set(sites)
    k = len(fail_sites)
    obs = adjacency_pairs(site_set, set(fail_sites))
    if k < 2 or k >= len(sites):
        return {"observed_adjacent_pairs": obs, "expected_adjacent_pairs": None,
                "ratio": None, "z": None, "permutations": 0,
                "verdict": "not_enough_fails" if k < 2 else "all_dies_failed"}
    idx = np.arange(len(sites))
    sims = np.empty(n_perm, dtype=float)
    arr = np.array(sites)
    for i in range(n_perm):
        pick = rng.choice(idx, size=k, replace=False)
        sims[i] = adjacency_pairs(site_set, {(int(a), int(b)) for a, b in arr[pick]})
    mean, std = float(sims.mean()), float(sims.std(ddof=1))
    ratio = obs / mean if mean > 0 else None
    z = (obs - mean) / std if std > 0 else None
    # Power guard: with a small expected adjacency count the ratio and z are dominated by
    # integer noise (one extra touching pair can double the ratio). Below MIN_EXPECTED the
    # test cannot separate clustered from random and must say so rather than guess.
    if ratio is None or z is None:
        verdict = "indeterminate"
    elif mean < MIN_EXPECTED_ADJACENCY:
        verdict = "inconclusive_low_power"
    elif ratio >= 1.5 and z >= 3:
        verdict = "clustered"
    elif ratio >= 1.2 and z >= 2:
        verdict = "weakly_clustered"
    elif z is not None and z <= -2:
        verdict = "dispersed"
    else:
        verdict = "random"
    return {"observed_adjacent_pairs": obs, "expected_adjacent_pairs": round(mean, 2),
            "ratio": round(ratio, 3) if ratio is not None else None,
            "z": round(z, 2) if z is not None else None,
            "permutations": n_perm, "verdict": verdict,
            "min_expected_for_power": MIN_EXPECTED_ADJACENCY}


def radial_zones(sites_df: pd.DataFrame, fail_mask: pd.Series) -> dict:
    """Fail rate by normalized-radius zone vs the wafer mean, with a binomial z-score."""
    cx = (sites_df["die_x"].max() + sites_df["die_x"].min()) / 2.0
    cy = (sites_df["die_y"].max() + sites_df["die_y"].min()) / 2.0
    r = np.hypot(sites_df["die_x"] - cx, sites_df["die_y"] - cy)
    rmax = float(r.max()) if float(r.max()) > 0 else 1.0
    rn = r / rmax
    overall = float(fail_mask.mean())
    out = {"overall_fail_rate": round(overall, 5), "zones": []}
    for name, lo, hi in ZONES:
        m = (rn >= lo) & (rn < hi)
        n_sites = int(m.sum())
        if n_sites == 0:
            continue
        n_fail = int(fail_mask[m].sum())
        rate = n_fail / n_sites
        if 0 < overall < 1:
            se = float(np.sqrt(overall * (1 - overall) / n_sites))
            z = (rate - overall) / se if se > 0 else None
        else:
            z = None
        out["zones"].append({
            "zone": name, "r_norm_range": [lo, round(hi, 2)], "dies": n_sites,
            "fails": n_fail, "fail_rate": round(rate, 5),
            "ratio_to_wafer": round(rate / overall, 3) if overall > 0 else None,
            "z": round(z, 2) if z is not None else None,
        })
    edge = next((z for z in out["zones"] if z["zone"] == "edge"), None)
    center = next((z for z in out["zones"] if z["zone"] == "center"), None)
    verdict = "uniform"
    if edge and edge["z"] is not None and edge["z"] >= 3 and (edge["ratio_to_wafer"] or 0) >= 1.3:
        verdict = "edge_concentrated"
    elif center and center["z"] is not None and center["z"] >= 3 and (center["ratio_to_wafer"] or 0) >= 1.3:
        verdict = "center_concentrated"
    elif edge and edge["z"] is not None and edge["z"] <= -3:
        verdict = "edge_depleted"
    out["verdict"] = verdict
    return out


def test_correlation(tests: pd.DataFrame, die_keys: pd.DataFrame) -> dict:
    """For a set of dies, which test fails most often and how far outside its limits."""
    key = ["lot_id", "wafer_id", "die_x", "die_y"]
    sub = tests.merge(die_keys[key].drop_duplicates(), on=key, how="inner")
    if sub.empty:
        return {"dies_with_test_data": 0, "tests": []}
    lo, hi, val = sub["lo_lim"], sub["hi_lim"], sub["value"]
    rng_ = (hi - lo).replace(0, np.nan)
    below = val < lo
    above = val > hi
    sub = sub.assign(
        out_of_limit=below | above,
        # normalized excursion beyond the nearer limit, in units of the limit range
        excursion=np.where(above, (val - hi) / rng_, np.where(below, (lo - val) / rng_, 0.0)),
    )
    rows = []
    n_dies = sub[key].drop_duplicates().shape[0]
    for (tnum, tname), g in sub[sub["out_of_limit"]].groupby(["test_num", "test_name"]):
        exc = g["excursion"].astype(float)
        exc = exc[np.isfinite(exc)]
        med = float(exc.median()) if len(exc) else float("nan")
        character = "unknown"
        if len(exc):
            if med <= 0.10:
                character = "marginal (just outside limit - parametric shift / centering / limit question)"
            elif med <= 1.0:
                character = "moderate excursion"
            else:
                character = "hard (far outside limit - catastrophic defect)"
            if len(exc) >= 6:
                lo_h = (exc <= exc.median()).sum()
                spread = float(exc.max() - exc.min())
                if spread > 0 and float(exc.std(ddof=1)) > 0.6 * abs(med) and 0.3 < lo_h / len(exc) < 0.7:
                    character += " · wide spread - check for two populations"
        rows.append({
            "test_num": int(tnum), "test_name": str(tname),
            "dies_failing_this_test": int(g[key].drop_duplicates().shape[0]),
            "share_of_dies": round(g[key].drop_duplicates().shape[0] / n_dies, 4) if n_dies else None,
            "median_excursion_x_limit_range": round(med, 4) if med == med else None,
            "min_excursion": round(float(exc.min()), 4) if len(exc) else None,
            "max_excursion": round(float(exc.max()), 4) if len(exc) else None,
            "character": character,
        })
    rows.sort(key=lambda r: (-r["dies_failing_this_test"], r["test_num"]))
    return {"dies_with_test_data": n_dies, "tests": rows}


# ---------------------------------------------------------------------- analysis
def analyse(die: pd.DataFrame, tests: pd.DataFrame | None, focus_bin: int | None,
            n_perm: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    total = len(die)
    n_fail = int((die["pass_flag"] == 0).sum())
    result: dict = {
        "generated_by": "bin_signature.py", "version": VERSION,
        "overall": {
            "dies": total, "pass": total - n_fail, "fail": n_fail,
            "yield_pct": round(100.0 * (total - n_fail) / total, 3) if total else None,
            "lots": sorted(die["lot_id"].astype(str).unique().tolist()),
            "wafers": int(die[["lot_id", "wafer_id"]].drop_duplicates().shape[0]),
        },
        "per_wafer": [], "bin_pareto": [], "bins": [], "findings": [],
    }

    for (lot, waf), g in die.groupby(["lot_id", "wafer_id"], sort=True):
        nf = int((g["pass_flag"] == 0).sum())
        result["per_wafer"].append({
            "lot_id": str(lot), "wafer_id": str(waf), "dies": len(g), "fail": nf,
            "yield_pct": round(100.0 * (len(g) - nf) / len(g), 3) if len(g) else None,
        })

    fails = die[die["pass_flag"] == 0]
    for sb, g in fails.groupby("soft_bin", sort=True):
        cnt = len(g)
        result["bin_pareto"].append({
            "soft_bin": int(sb),
            "hard_bins": sorted({int(h) for h in g["hard_bin"].dropna().unique()}),
            "count": cnt,
            "share_of_fails_pct": round(100.0 * cnt / n_fail, 2) if n_fail else None,
            "yield_loss_pct_points": round(100.0 * cnt / total, 3) if total else None,
        })
    result["bin_pareto"].sort(key=lambda r: -r["count"])

    bins_to_do = [focus_bin] if focus_bin is not None else [b["soft_bin"] for b in result["bin_pareto"]]
    if focus_bin is not None and focus_bin not in [b["soft_bin"] for b in result["bin_pareto"]]:
        raise ValueError(f"--bin {focus_bin} has no failing dies in this data")

    for sb in bins_to_do:
        binrec: dict = {"soft_bin": int(sb), "per_wafer": []}
        bin_rows = die[(die["soft_bin"] == sb) & (die["pass_flag"] == 0)]
        binrec["count"] = len(bin_rows)
        for (lot, waf), g in die.groupby(["lot_id", "wafer_id"], sort=True):
            sites = [(int(a), int(b)) for a, b in zip(g["die_x"], g["die_y"])]
            fs = g[(g["soft_bin"] == sb) & (g["pass_flag"] == 0)]
            if len(fs) == 0:
                continue
            fail_sites = [(int(a), int(b)) for a, b in zip(fs["die_x"], fs["die_y"])]
            mask = (g["soft_bin"] == sb) & (g["pass_flag"] == 0)
            binrec["per_wafer"].append({
                "lot_id": str(lot), "wafer_id": str(waf),
                "dies": len(g), "fails_this_bin": len(fs),
                "fail_rate_pct": round(100.0 * len(fs) / len(g), 3),
                "clustering": clustering_stat(sites, fail_sites, n_perm, rng),
                "radial": radial_zones(g, mask),
            })
        if tests is not None:
            binrec["test_correlation"] = test_correlation(tests, bin_rows)
        result["bins"].append(binrec)

    result["findings"] = rank_findings(result)
    return result


def rank_findings(res: dict) -> list[dict]:
    """Turn the statistics into an ordered list of statements that feed the hypothesis table."""
    out = []
    total_fail = res["overall"]["fail"]
    for binrec in res["bins"]:
        sb = binrec["soft_bin"]
        pareto = next((p for p in res["bin_pareto"] if p["soft_bin"] == sb), None)
        loss = pareto["yield_loss_pct_points"] if pareto else 0.0
        share = pareto["share_of_fails_pct"] if pareto else 0.0
        clustered = [w for w in binrec["per_wafer"]
                     if w["clustering"]["verdict"] in ("clustered", "weakly_clustered")]
        random_w = [w for w in binrec["per_wafer"] if w["clustering"]["verdict"] == "random"]
        lowpow = [w for w in binrec["per_wafer"]
                  if w["clustering"]["verdict"] == "inconclusive_low_power"]
        edge_w = [w for w in binrec["per_wafer"] if w["radial"]["verdict"] == "edge_concentrated"]
        ctr_w = [w for w in binrec["per_wafer"] if w["radial"]["verdict"] == "center_concentrated"]

        score = (loss or 0) * 2.0
        if clustered:
            score += 20
        if edge_w or ctr_w:
            score += 15

        if clustered:
            ex = clustered[0]["clustering"]
            out.append({
                "score": round(score, 2), "soft_bin": sb, "kind": "spatial_clustering",
                "statement": f"soft bin {sb} fails are spatially CLUSTERED on "
                             f"{len(clustered)}/{len(binrec['per_wafer'])} wafer(s)",
                "evidence": f"adjacent-fail pairs {ex['observed_adjacent_pairs']} vs "
                            f"{ex['expected_adjacent_pairs']} expected under random placement "
                            f"(ratio {ex['ratio']}, z {ex['z']}, {ex['permutations']} permutations)",
                "so_what": "Clustering points at a process/tool/handling origin acting on adjacent "
                           "dies, not at random defectivity and not at an event on one packaged unit.",
            })
        elif random_w and not edge_w and not ctr_w:
            out.append({
                "score": round(score, 2), "soft_bin": sb, "kind": "spatial_random",
                "statement": f"soft bin {sb} fails are spatially RANDOM across "
                             f"{len(random_w)}/{len(binrec['per_wafer'])} wafer(s)",
                "evidence": "; ".join(
                    f"{w['lot_id']}/{w['wafer_id']}: ratio {w['clustering']['ratio']}, "
                    f"z {w['clustering']['z']}" for w in random_w[:3]),
                "so_what": "Random placement is the signature of baseline defectivity or of a "
                           "per-die event (handling, ESD at a handler, marginal design) rather than "
                           "a spatial process excursion. Look at date-code/handling commonality next.",
            })
        if lowpow:
            out.append({
                "score": round(score - 5, 2), "soft_bin": sb, "kind": "spatial_underpowered",
                "statement": f"soft bin {sb}: the clustering test is UNDERPOWERED on "
                             f"{len(lowpow)}/{len(binrec['per_wafer'])} wafer(s) - no spatial "
                             f"verdict can be given",
                "evidence": "; ".join(
                    f"{w['lot_id']}/{w['wafer_id']}: {w['fails_this_bin']} fails, expected adjacent "
                    f"pairs {w['clustering']['expected_adjacent_pairs']} < "
                    f"{w['clustering']['min_expected_for_power']}" for w in lowpow[:3]),
                "so_what": "Too few fails for the adjacency statistic to separate clustered from "
                           "random - one extra touching pair would flip the ratio. Pool wafers, "
                           "pool lots, or fall back on non-spatial commonality (date code, tool, "
                           "test site). Do NOT report this as 'random'.",
            })
        for w in edge_w:
            zz = next(z for z in w["radial"]["zones"] if z["zone"] == "edge")
            out.append({
                "score": round(score + 5, 2), "soft_bin": sb, "kind": "edge_concentration",
                "statement": f"soft bin {sb} is EDGE-concentrated on {w['lot_id']}/{w['wafer_id']}",
                "evidence": f"edge zone fail rate {zz['fail_rate']:.4f} vs wafer mean "
                            f"{w['radial']['overall_fail_rate']:.4f} "
                            f"(ratio {zz['ratio_to_wafer']}, z {zz['z']})",
                "so_what": "Edge concentration implicates edge-sensitive processing (clamp ring, "
                           "bevel, edge purge, non-uniformity) - a wafer-fab lead, not a package one.",
            })
        for w in ctr_w:
            zz = next(z for z in w["radial"]["zones"] if z["zone"] == "center")
            out.append({
                "score": round(score + 5, 2), "soft_bin": sb, "kind": "center_concentration",
                "statement": f"soft bin {sb} is CENTER-concentrated on {w['lot_id']}/{w['wafer_id']}",
                "evidence": f"center zone fail rate {zz['fail_rate']:.4f} vs wafer mean "
                            f"{w['radial']['overall_fail_rate']:.4f} "
                            f"(ratio {zz['ratio_to_wafer']}, z {zz['z']})",
                "so_what": "Center concentration implicates dispense/spin/chuck-contact processes or "
                           "a chuck thermal profile.",
            })
        tc = binrec.get("test_correlation")
        if tc and tc.get("tests"):
            t0 = tc["tests"][0]
            out.append({
                "score": round(score + 10, 2), "soft_bin": sb, "kind": "failing_test",
                "statement": f"soft bin {sb} is dominated by test {t0['test_num']} "
                             f"'{t0['test_name']}' ({t0['dies_failing_this_test']} of "
                             f"{tc['dies_with_test_data']} dies, {100*(t0['share_of_dies'] or 0):.0f}%)",
                "evidence": f"median excursion {t0['median_excursion_x_limit_range']}x the limit range "
                            f"(min {t0['min_excursion']}, max {t0['max_excursion']}) - {t0['character']}",
                "so_what": "One dominant out-of-limit test across units points at one mechanism: "
                           "treat as one case. The excursion character separates a parametric shift "
                           "from a hard defect. NOTE: tests.csv carries no test-order column, so "
                           "this is 'most often out of limits', not 'first-failing' - confirm the "
                           "first-failing test from an order-preserving datalog export.",
            })
            if len(tc["tests"]) > 1:
                names = ", ".join(f"{t['test_num']}:{t['test_name']}" for t in tc["tests"][1:4])
                out.append({
                    "score": round(score, 2), "soft_bin": sb, "kind": "secondary_tests",
                    "statement": f"soft bin {sb} also fails: {names}",
                    "evidence": "co-failing tests present in tests.csv for the same dies",
                    "so_what": "Multiple co-failing tests suggest either a shared-resource failure "
                               "(supply, reference, clock) or a mixed population. Check whether the "
                               "co-failures track the same dies.",
                })
    out.sort(key=lambda r: -r["score"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
    if total_fail == 0:
        out.append({"rank": 1, "score": 0, "soft_bin": None, "kind": "no_fails",
                    "statement": "no failing dies in this data set",
                    "evidence": "pass_flag == 1 for every row",
                    "so_what": "Nothing to analyse; confirm you were given the right file."})
    return out


# ------------------------------------------------------------------------ output
def plot_maps(die: pd.DataFrame, res: dict, outdir: Path, focus_bin: int | None) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written = []
    bins = [focus_bin] if focus_bin is not None else [b["soft_bin"] for b in res["bin_pareto"][:3]]
    for (lot, waf), g in die.groupby(["lot_id", "wafer_id"], sort=True):
        fig, ax = plt.subplots(figsize=(5.2, 5.2))
        ax.scatter(g["die_x"], g["die_y"], s=9, c="#d9d9d9", marker="s", label="pass/other")
        colors = ["#c0392b", "#2980b9", "#27ae60"]
        for i, sb in enumerate(bins):
            m = (g["soft_bin"] == sb) & (g["pass_flag"] == 0)
            if m.any():
                ax.scatter(g.loc[m, "die_x"], g.loc[m, "die_y"], s=11,
                           c=colors[i % len(colors)], marker="s", label=f"soft bin {sb}")
        ax.set_aspect("equal")
        ax.set_title(f"{lot} / {waf} - bin map", fontsize=10)
        ax.set_xlabel("die_x")
        ax.set_ylabel("die_y")
        ax.legend(fontsize=7, loc="upper right", framealpha=0.9)
        fig.tight_layout()
        p = outdir / f"binmap_{lot}_{waf}.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        written.append(str(p))
    return written


def render_text(res: dict) -> str:
    L = []
    o = res["overall"]
    L.append("=" * 78)
    L.append("BIN SIGNATURE ANALYSIS")
    L.append("=" * 78)
    L.append(f"dies {o['dies']} · pass {o['pass']} · fail {o['fail']} · yield {o['yield_pct']}%")
    L.append(f"lots {', '.join(o['lots'])} · wafers {o['wafers']}")
    L.append("")
    L.append("-- PER WAFER " + "-" * 64)
    L.append(f"  {'lot':<8}{'wafer':<8}{'dies':>7}{'fail':>7}{'yield%':>9}")
    for w in res["per_wafer"]:
        L.append(f"  {w['lot_id']:<8}{w['wafer_id']:<8}{w['dies']:>7}{w['fail']:>7}{w['yield_pct']:>9.2f}")
    L.append("")
    L.append("-- SOFT BIN PARETO (by count; yield loss in absolute % points) " + "-" * 15)
    L.append(f"  {'soft':>6}{'hard':>10}{'count':>8}{'%fails':>9}{'yldloss':>9}")
    for b in res["bin_pareto"]:
        hb = ",".join(str(h) for h in b["hard_bins"])
        L.append(f"  {b['soft_bin']:>6}{hb:>10}{b['count']:>8}"
                 f"{b['share_of_fails_pct']:>9.2f}{b['yield_loss_pct_points']:>9.3f}")
    L.append("")
    for binrec in res["bins"]:
        L.append("-" * 78)
        L.append(f"SOFT BIN {binrec['soft_bin']} - {binrec['count']} failing dies")
        L.append("-" * 78)
        for w in binrec["per_wafer"]:
            c, r = w["clustering"], w["radial"]
            L.append(f"  {w['lot_id']}/{w['wafer_id']}: {w['fails_this_bin']}/{w['dies']} dies "
                     f"({w['fail_rate_pct']}%)")
            L.append(f"    spatial : {c['verdict'].upper()} - adjacent pairs {c['observed_adjacent_pairs']} "
                     f"vs {c['expected_adjacent_pairs']} expected (ratio {c['ratio']}, z {c['z']})")
            zs = " · ".join(f"{z['zone']} {z['fail_rate']:.4f} (x{z['ratio_to_wafer']}, z {z['z']})"
                            for z in r["zones"])
            L.append(f"    radial  : {r['verdict'].upper()} - {zs}")
        tc = binrec.get("test_correlation")
        if tc:
            if not tc.get("tests"):
                L.append(f"    tests   : no out-of-limit rows in tests.csv for these "
                         f"{tc['dies_with_test_data']} dies")
            for t in tc["tests"][:5]:
                L.append(f"    test {t['test_num']:>5} {t['test_name']:<22} "
                         f"{t['dies_failing_this_test']:>4}/{tc['dies_with_test_data']} dies · "
                         f"median excursion {t['median_excursion_x_limit_range']}x range")
                L.append(f"          -> {t['character']}")
        L.append("")
    L.append("=" * 78)
    L.append("RANKED FINDINGS (feed these into the Step 4 hypothesis table)")
    L.append("=" * 78)
    for f in res["findings"]:
        L.append(f"  {f['rank']}. [{f['kind']}] {f['statement']}")
        L.append(f"     evidence: {f['evidence']}")
        L.append(f"     so what : {f['so_what']}")
    L.append("")
    L.append("Statistics only. Mechanism attribution requires the physical evidence in phases "
             "N1-D2 (see references/technique-matrix.md).")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--die-results", required=True, help="die_results.csv path")
    ap.add_argument("--tests", help="optional tests.csv path (per-die per-test values and limits)")
    ap.add_argument("--bin", type=int, dest="focus_bin",
                    help="analyse only this soft bin (default: every failing soft bin)")
    ap.add_argument("--outdir", help="write bin_signature.json and PNG bin maps here")
    ap.add_argument("--permutations", type=int, default=200,
                    help="Monte-Carlo permutations for the clustering z-score (default 200)")
    ap.add_argument("--seed", type=int, default=7, help="RNG seed for the permutations (default 7)")
    ap.add_argument("--no-plots", action="store_true", help="skip PNG generation")
    ap.add_argument("--json", action="store_true", help="print the JSON result instead of the summary")
    args = ap.parse_args(argv)

    try:
        die = load_die_results(Path(args.die_results))
        tests = load_tests(Path(args.tests)) if args.tests else None
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 2
    if die.empty:
        print("error: die_results.csv has no rows", file=sys.stderr)
        return 2

    try:
        res = analyse(die, tests, args.focus_bin, args.permutations, args.seed)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    outdir = Path(args.outdir) if args.outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "bin_signature.json").write_text(json.dumps(res, indent=2) + "\n")
        if not args.no_plots:
            try:
                res["plots"] = plot_maps(die, res, outdir, args.focus_bin)
            except Exception as e:  # noqa: BLE001
                print(f"warning: plots skipped ({e})", file=sys.stderr)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(render_text(res))
        if outdir:
            print(f"[wrote {outdir/'bin_signature.json'}]")
            for p in res.get("plots", []):
                print(f"[wrote {p}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
