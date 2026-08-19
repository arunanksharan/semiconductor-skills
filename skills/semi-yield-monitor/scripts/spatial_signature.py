#!/usr/bin/env python3
"""Rule-based wafer-map spatial-signature classifier (v1).

Reads die_results.csv (schema: lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,
pass_flag — see references/data-formats.md), detects spatial failure
signatures per wafer and per lot (pooled), and ranks them by statistical
strength (z-score). Signatures: scratch, edge_ring, center_cluster, donut,
half_moon, quadrant, reticle. Reports "none" when nothing clears --min-z.

Method: scratch first (connected components + robust line fit); scratch dies
are then masked out and the residual map is tested zonally (radial zones,
angular sectors, reticle periodicity) with two-proportion z-tests.

Usage examples:
  python spatial_signature.py --input die_results.csv --lot SCRT --wafer W1
  python spatial_signature.py --input die_results.csv --lot EDGE --json
  python spatial_signature.py --input die_results.csv            # all lots
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy import ndimage, stats

REQUIRED = ["lot_id", "wafer_id", "die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"]

CAUSE_HINTS = {
    "scratch": "mechanical handling / CMP scratch / wafer transfer — check handlers, CMP, tweezer maps",
    "edge_ring": "edge processes — edge-bead removal, clamp/pin marks, bevel, edge etch/dep uniformity, litho edge shots",
    "center_cluster": "center-symmetric process — dispense/spin (coat/develop), CMP center pressure, chuck center contact",
    "donut": "radial non-uniformity — chuck temperature profile, plasma/dep radial uniformity, spin dynamics",
    "half_moon": "one-sided process — tilted chuck, single-side clamp, gas-flow asymmetry, sputter target asymmetry",
    "quadrant": "orientation-locked asymmetry — notch-referenced handling, quadrant-dependent tooling contact",
    "reticle": "repeating at reticle pitch — mask defect, litho hot spot, reticle contamination",
}


def load(path: str, lot: str | None, wafer: str | None) -> pd.DataFrame:
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
    if wafer is not None:
        df = df[df.wafer_id == wafer]
        if df.empty:
            sys.exit(f"ERROR: wafer '{wafer}' not found for that lot in {path}")
    return df


def two_prop_z(f1: int, n1: int, f2: int, n2: int) -> float:
    """z for rate(zone) vs rate(rest); positive = zone worse."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = f1 / n1, f2 / n2
    p = (f1 + f2) / (n1 + n2)
    se = math.sqrt(max(p * (1 - p) * (1 / n1 + 1 / n2), 1e-12))
    return (p1 - p2) / se


def confidence(z: float) -> str:
    return "high" if z >= 6 else ("medium" if z >= 4 else "low")


def geometry(df_w: pd.DataFrame):
    """Return coordinate arrays and normalized radius/angle for one wafer."""
    x = df_w.die_x.to_numpy()
    y = df_w.die_y.to_numpy()
    cx = (x.min() + x.max()) / 2.0
    cy = (y.min() + y.max()) / 2.0
    r = np.hypot(x - cx, y - cy)
    rmax = max(r.max(), 1e-9)
    ang = np.mod(np.arctan2(y - cy, x - cx), 2 * math.pi)
    return x, y, r / rmax, ang, (cx, cy)


def detect_scratches(df_w: pd.DataFrame, min_z: float):
    """Connected-component + robust line-fit scratch detector.

    Returns (list of scratch dicts, boolean mask over df_w rows marking
    scratch-component dies to exclude from residual zonal analysis).
    """
    x = df_w.die_x.to_numpy()
    y = df_w.die_y.to_numpy()
    fail = df_w.pass_flag.to_numpy() == 0
    W, H = x.max() + 1, y.max() + 1
    grid = np.zeros((W, H), dtype=bool)
    present = np.zeros((W, H), dtype=bool)
    grid[x[fail], y[fail]] = True
    present[x, y] = True

    # wafer geometry, to reject edge-ring arcs masquerading as scratches
    cx, cy = (x.min() + x.max()) / 2.0, (y.min() + y.max()) / 2.0
    rmax = max(np.hypot(x - cx, y - cy).max(), 1e-9)

    labels, n = ndimage.label(grid, structure=np.ones((3, 3), dtype=int))
    scratches, drop_labels = [], set()
    for lab in range(1, n + 1):
        pts = np.argwhere(labels == lab).astype(float)
        if len(pts) < 8:
            continue
        # an arc confined to the edge band is edge-ring structure, not a scratch
        rn_cells = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) / rmax
        if (rn_cells > 0.78).mean() >= 0.5:
            continue
        for _ in range(2):  # PCA fit, then refit on corridor inliers
            mean = pts.mean(axis=0)
            cen = pts - mean
            cov = np.cov(cen.T) if len(pts) > 1 else np.eye(2)
            evals, evecs = np.linalg.eigh(cov)
            u = evecs[:, np.argmax(evals)]          # principal direction
            v = evecs[:, np.argmin(evals)]          # normal
            all_pts = np.argwhere(labels == lab).astype(float)
            perp = (all_pts - mean) @ v
            inliers = all_pts[np.abs(perp) <= 1.5]
            if len(inliers) < 8:
                break
            pts = inliers
        else:
            pass
        if len(pts) < 8:
            continue
        proj = (pts - pts.mean(axis=0)) @ u
        span = proj.max() - proj.min() + 1
        comp_pts = np.argwhere(labels == lab).astype(float)
        ratio = len(pts) / len(comp_pts)
        l1, l2 = np.sort(np.linalg.eigvalsh(np.cov((comp_pts - comp_pts.mean(0)).T)))[::-1]
        aspect = math.sqrt(max(l1, 1e-9) / max(l2, 1e-9))
        if not (span >= 8 and ratio >= 0.70 and aspect >= 2.5):
            continue
        # z: fails inside the fitted corridor vs the rest of the wafer
        px, py = np.nonzero(present)
        rel = np.stack([px, py], axis=1).astype(float) - pts.mean(axis=0)
        in_corr = (np.abs(rel @ v) <= 1.2) & (rel @ u >= proj.min() - 1) & (rel @ u <= proj.max() + 1)
        corr_cells = set(map(tuple, np.stack([px, py], axis=1)[in_corr]))
        die_xy = list(zip(x, y))
        in_c = np.array([xy in corr_cells for xy in die_xy])
        f_in, n_in = int(fail[in_c].sum()), int(in_c.sum())
        f_out, n_out = int(fail[~in_c].sum()), int((~in_c).sum())
        p_out = f_out / max(n_out, 1)
        exp = n_in * p_out
        z = (f_in - exp) / math.sqrt(max(exp * (1 - p_out), 1e-9))
        if z < min_z:
            continue
        drop_labels.add(lab)
        scratches.append({
            "label": "scratch", "z": round(float(z), 2), "confidence": confidence(z),
            "evidence": f"linear chain: {len(comp_pts)} dies, span {span:.0f}, "
                        f"aspect {aspect:.1f}, corridor fail rate "
                        f"{f_in}/{n_in} vs {p_out:.3f} elsewhere",
        })
    row_lab = labels[x, y]
    drop_mask = np.isin(row_lab, list(drop_labels)) & fail if drop_labels else np.zeros(len(df_w), bool)
    return scratches, drop_mask


def zonal_candidates(df_w: pd.DataFrame, drop_mask: np.ndarray, min_z: float, min_lift: float):
    """Radial / sector / quadrant / reticle tests on the residual map."""
    fail = (df_w.pass_flag.to_numpy() == 0) & ~drop_mask
    x, y, rn, ang, _ = geometry(df_w)
    n_all, f_all = len(df_w), int(fail.sum())
    cands, zones_out = [], {}

    zone_masks = {"center": rn <= 0.35, "mid": (rn > 0.35) & (rn <= 0.80), "edge": rn > 0.80}
    zstats = {}
    for name, m in zone_masks.items():
        f1, n1 = int(fail[m].sum()), int(m.sum())
        f2, n2 = f_all - f1, n_all - n1
        rate = f1 / max(n1, 1)
        rest = f2 / max(n2, 1)
        zstats[name] = {"rate": rate, "rest": rest, "z": two_prop_z(f1, n1, f2, n2),
                        "lift": rate / max(rest, 1e-9), "n": n1, "fails": f1}
        zones_out[name] = {"n": n1, "fails": f1, "rate": round(rate, 4),
                           "z": round(zstats[name]["z"], 2)}

    c, m, e = zstats["center"], zstats["mid"], zstats["edge"]

    # edge ring vs edge crescent: require angular coverage for the full ring
    edge_fired = e["z"] >= min_z and e["lift"] >= min_lift
    ring_cov = 0
    if edge_fired:
        for s in range(8):
            sm = zone_masks["edge"] & (ang >= s * math.pi / 4) & (ang < (s + 1) * math.pi / 4)
            if sm.sum() and fail[sm].sum() / sm.sum() > e["rest"]:
                ring_cov += 1
    if edge_fired and ring_cov >= 6:
        cands.append(("edge_ring", e["z"],
                      f"edge rate {e['rate']:.3f} vs {e['rest']:.3f} elsewhere "
                      f"(lift {e['lift']:.1f}x, {ring_cov}/8 sectors elevated)"))
    if c["z"] >= min_z and c["lift"] >= min_lift:
        cands.append(("center_cluster", c["z"],
                      f"center rate {c['rate']:.3f} vs {c['rest']:.3f} elsewhere "
                      f"(lift {c['lift']:.1f}x)"))
    if (m["z"] >= min_z and m["rate"] > 1.3 * c["rate"] and m["rate"] > 1.3 * e["rate"]
            and c["z"] < 2 and not edge_fired):
        cands.append(("donut", m["z"],
                      f"mid-band rate {m['rate']:.3f} > center {c['rate']:.3f} "
                      f"and edge {e['rate']:.3f}"))

    # angular runs (only if no radial signature already explains the map)
    if not any(lbl in ("edge_ring", "center_cluster", "donut") for lbl, _, _ in cands):
        sect_f = np.zeros(8, int)
        sect_n = np.zeros(8, int)
        for s in range(8):
            sm = (ang >= s * math.pi / 4) & (ang < (s + 1) * math.pi / 4)
            sect_f[s], sect_n[s] = int(fail[sm].sum()), int(sm.sum())
        best = None
        for run in (2, 3, 4):
            for s in range(8):
                idx = [(s + k) % 8 for k in range(run)]
                f1, n1 = int(sect_f[idx].sum()), int(sect_n[idx].sum())
                z = two_prop_z(f1, n1, f_all - f1, n_all - n1)
                lift = (f1 / max(n1, 1)) / max((f_all - f1) / max(n_all - n1, 1), 1e-9)
                if z >= min_z and lift >= min_lift and (best is None or z > best[1]):
                    lbl = "quadrant" if run == 2 else "half_moon"
                    best = (lbl, z, f"sectors {idx} rate {f1 / max(n1,1):.3f} "
                                    f"vs {(f_all - f1) / max(n_all - n1, 1):.3f} elsewhere")
        if best:
            cands.append(best)

    # reticle periodicity: chi-square across x%p and y%p residue classes
    best_ret = None
    for axis, vals in (("x", x), ("y", y)):
        for p in range(3, 9):
            res = vals % p
            obs = np.array([fail[res == k].sum() for k in range(p)], float)
            cnt = np.array([(res == k).sum() for k in range(p)], float)
            if (cnt == 0).any() or f_all == 0:
                continue
            exp = cnt * f_all / n_all
            chi2 = float(((obs - exp) ** 2 / np.maximum(exp, 1e-9)).sum())
            pval = float(stats.chi2.sf(chi2, p - 1)) * 12  # Bonferroni: 6 periods x 2 axes
            rates = obs / cnt
            strength = rates.max() / max(rates.min(), 1e-9)
            if pval < 1e-4 and strength >= 1.8:
                z = float(min(stats.norm.isf(max(pval, 1e-300)), 12.0))
                if best_ret is None or z > best_ret[1]:
                    best_ret = ("reticle", z, f"period {p} on {axis}: residue fail rates "
                                              f"{np.round(rates, 3).tolist()} (p={pval:.1e})")
    if best_ret:
        cands.append(best_ret)
    return cands, zones_out


def analyze_wafer(df_w: pd.DataFrame, min_z: float, min_lift: float):
    scratches, drop = detect_scratches(df_w, min_z)
    cands, zones = zonal_candidates(df_w, drop, min_z, min_lift)
    all_c = scratches + [
        {"label": l, "z": round(float(z), 2), "confidence": confidence(z), "evidence": ev}
        for l, z, ev in cands
    ]
    for cand in all_c:
        cand["likely_cause"] = CAUSE_HINTS.get(cand["label"], "")
    all_c.sort(key=lambda d: -d["z"])
    n, f = len(df_w), int((df_w.pass_flag == 0).sum())
    result = {
        "dies": n, "fails": f, "yield_pct": round(100 * (1 - f / n), 2),
        "top": all_c[0]["label"] if all_c else "none",
        "candidates": all_c, "zones": zones,
    }
    return result, drop


def analyze_lot(df_lot: pd.DataFrame, min_z: float, min_lift: float) -> dict:
    df_lot = df_lot.reset_index(drop=True)
    wafers = {}
    pooled_drop = np.zeros(len(df_lot), bool)
    for wid, df_w in df_lot.groupby("wafer_id", sort=True):
        r, drop_w = analyze_wafer(df_w.reset_index(drop=True), min_z, min_lift)
        wafers[wid] = r
        pooled_drop[df_w.index.to_numpy()[drop_w]] = True
    # pooled zonal analysis; per-wafer scratch dies are masked so a single
    # wafer's scratch cannot masquerade as a lot-level angular signature
    pooled_c, pooled_zones = zonal_candidates(df_lot, pooled_drop, min_z, min_lift)
    pooled = [
        {"label": l, "z": round(float(z), 2), "confidence": confidence(z),
         "evidence": ev, "likely_cause": CAUSE_HINTS.get(l, "")}
        for l, z, ev in sorted(pooled_c, key=lambda t: -t[1])
    ]
    scratch_wafers = [w for w, r in wafers.items() if r["top"] == "scratch"]
    top = pooled[0]["label"] if pooled else ("scratch" if scratch_wafers else "none")
    n, f = len(df_lot), int((df_lot.pass_flag == 0).sum())
    return {
        "dies": n, "fails": f, "yield_pct": round(100 * (1 - f / n), 2),
        "top": top, "pooled_candidates": pooled, "pooled_zones": pooled_zones,
        "scratch_wafers": scratch_wafers, "wafers": wafers,
    }


def print_wafer(wid: str, r: dict) -> None:
    print(f"  wafer {wid}: yield {r['yield_pct']}% ({r['fails']}/{r['dies']} fail) "
          f"-> top signature: {r['top'].upper()}")
    for cand in r["candidates"]:
        print(f"    {cand['label']:<15} z={cand['z']:<7} {cand['confidence']:<7} {cand['evidence']}")
        if cand["likely_cause"]:
            print(f"    {'':15} likely cause: {cand['likely_cause']}")
    if not r["candidates"]:
        zs = ", ".join(f"{k}={v['rate']:.3f}" for k, v in r["zones"].items())
        print(f"    no spatial signature above threshold (zone rates: {zs})")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", required=True, help="die_results.csv (canonical schema)")
    ap.add_argument("--lot", help="lot_id to analyze (default: all lots)")
    ap.add_argument("--wafer", help="wafer_id to analyze (requires --lot)")
    ap.add_argument("--min-z", type=float, default=3.0, help="detection threshold z (default 3.0)")
    ap.add_argument("--min-lift", type=float, default=1.5, help="min rate lift (default 1.5)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()
    if args.wafer and not args.lot:
        ap.error("--wafer requires --lot")

    df = load(args.input, args.lot, args.wafer)
    out = {}
    for lot_id, df_lot in df.groupby("lot_id", sort=True):
        if args.wafer:
            r, _ = analyze_wafer(df_lot.reset_index(drop=True), args.min_z, args.min_lift)
            out[lot_id] = {"wafers": {args.wafer: r}, "top": r["top"]}
        else:
            out[lot_id] = analyze_lot(df_lot, args.min_z, args.min_lift)

    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    for lot_id, r in out.items():
        if args.wafer:
            print(f"lot {lot_id}")
            print_wafer(args.wafer, r["wafers"][args.wafer])
            continue
        print(f"lot {lot_id}: yield {r['yield_pct']}% -> lot-level signature: {r['top'].upper()}")
        for cand in r["pooled_candidates"]:
            print(f"  [pooled] {cand['label']:<15} z={cand['z']:<7} {cand['confidence']:<7} {cand['evidence']}")
            if cand["likely_cause"]:
                print(f"  {'':24} likely cause: {cand['likely_cause']}")
        if r["scratch_wafers"]:
            print(f"  scratch detected on wafers: {', '.join(r['scratch_wafers'])}")
        for wid, wr in r["wafers"].items():
            print_wafer(wid, wr)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
