#!/usr/bin/env python3
"""Lot x tool x chamber x time commonality: which tool or chamber separates the
excursion population from the healthy one?

Inputs
  --history  history.csv   lot_id,step,tool,chamber,date   (chamber may be blank)
  --metric   metric.csv    lot_id,<numeric metric>         (one row per lot)

TWO ranking keys, because fab excursions come in two shapes and a single
statistic gets one of them wrong:

  SHIFT  z = (mean_in - mean_out) / (sigma_robust * sqrt(1/n_in + 1/n_out))
         sigma_robust = 1.4826 * MAD of all in-scope lots, so a group that is
         internally split (half its lots drifted, half did not) is not punished
         by its own inflated variance the way a Welch t is.
  TAIL   hypergeometric p for over-representation among the FLAGGED lots
         ("4 of the 5 out-of-family lots ran in this chamber") -- this is the
         key that finds a chamber that drifted partway through the window.

Ranking is TAIL first when at least --min-flagged lots are flagged, SHIFT
otherwise; both columns are always printed. Welch t and Cohen's d are reported
for reference but are not the ranking key.

Every candidate is then audited for the three ways commonality lies to you:
  TIE / MIRROR     two candidates score the same, cover the identical lot set,
                   or are complements of each other (a 2-tool step) -- no
                   amount of this data separates them
  TIME-CONFOUNDED  membership correlates with run date, so a calendar cause
                   (incoming material, facility, a recipe or limit edit,
                   another tool's PM) fits exactly as well as the tool does
  THIN             fewer than --min-lots lots on a side: hypothesis only

Scope the window first (--since/--until) and re-run: a chamber that drifted on
a known date looks weak over six weeks of history and unmistakable over the ten
days after it started.

Usage examples:
  python3 commonality.py --history history.csv --metric cd_by_lot.csv --metric-col cd_nm
  python3 commonality.py --history history.csv --metric cd_by_lot.csv --metric-col cd_nm \\
      --since 2026-07-16 --pivot-out pivot.csv --top 8
  python3 commonality.py --history history.csv --metric th_by_lot.csv --metric-col thickness_a \\
      --flag-above 1010.35 --min-flagged 1
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats


def load_metric(path: str, col: str | None) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(path, dtype={"lot_id": str})
    if "lot_id" not in df.columns:
        sys.exit(f"ERROR: {path} needs a lot_id column")
    if col:
        if col not in df.columns:
            sys.exit(f"ERROR: --metric-col {col!r} not in {list(df.columns)}")
    else:
        num = [c for c in df.columns
               if c != "lot_id" and pd.api.types.is_numeric_dtype(df[c])]
        if not num:
            sys.exit(f"ERROR: no numeric metric column in {path}; pass --metric-col")
        col = num[0]
    return df.groupby("lot_id", as_index=False)[col].mean(), col


def robust_sigma(x: np.ndarray) -> float:
    mad = float(np.median(np.abs(x - np.median(x))))
    s = 1.4826 * mad
    return s if s > 0 else float(np.std(x, ddof=1))


def point_biserial(member: np.ndarray, order: np.ndarray) -> float:
    if member.std() == 0 or order.std() == 0:
        return 0.0
    return float(np.corrcoef(member.astype(float), order.astype(float))[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--history", required=True, help="history.csv (lot_id,step,tool,chamber,date)")
    ap.add_argument("--metric", required=True, help="per-lot metric CSV (lot_id,<metric>)")
    ap.add_argument("--metric-col", help="metric column name (default: first numeric column)")
    ap.add_argument("--since", help="only lots with date >= this (YYYY-MM-DD)")
    ap.add_argument("--until", help="only lots with date <= this (YYYY-MM-DD)")
    ap.add_argument("--flag-above", type=float, help="explicit upper flag limit (e.g. the SPC UCL)")
    ap.add_argument("--flag-below", type=float, help="explicit lower flag limit (e.g. the SPC LCL)")
    ap.add_argument("--flag-k", type=float, default=3.0,
                    help="if no explicit limits: flag lots beyond median +- k*robust sigma "
                         "(default 3.0)")
    ap.add_argument("--min-flagged", type=int, default=3,
                    help="flagged lots needed before the TAIL key is used for ranking (default 3)")
    ap.add_argument("--min-lots", type=int, default=2,
                    help="min lots on each side before a candidate is trusted (default 2)")
    ap.add_argument("--top", type=int, default=10, help="candidates to print (default 10)")
    ap.add_argument("--tie-tol", type=float, default=0.15,
                    help="flag a tie when the runner-up scores within this fraction (default 0.15)")
    ap.add_argument("--time-confound-r", type=float, default=0.5,
                    help="|corr(membership, date rank)| above this = TIME-CONFOUNDED (default 0.5)")
    ap.add_argument("--time-buckets", type=int, default=4,
                    help="time buckets for the when-did-it-start table (default 4)")
    ap.add_argument("--pivot-out", help="write the lot x step x tool/chamber pivot to this CSV")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    hist = pd.read_csv(args.history, dtype=str)
    need = {"lot_id", "step", "tool"}
    if not need.issubset(hist.columns):
        sys.exit(f"ERROR: {args.history} needs columns lot_id,step,tool[,chamber,date]")
    if "chamber" not in hist.columns:
        hist["chamber"] = ""
    hist["chamber"] = hist["chamber"].fillna("").astype(str)
    if "date" not in hist.columns:
        hist["date"] = ""
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")

    met, mcol = load_metric(args.metric, args.metric_col)

    lot_date = hist.groupby("lot_id")["date"].min().rename("lot_date").reset_index()
    lots = met.merge(lot_date, on="lot_id", how="left")
    n_all = len(lots)
    if args.since:
        lots = lots[lots.lot_date >= pd.Timestamp(args.since)]
    if args.until:
        lots = lots[lots.lot_date <= pd.Timestamp(args.until)]
    lots = lots.dropna(subset=[mcol]).reset_index(drop=True)
    if len(lots) < 4:
        sys.exit(f"ERROR: only {len(lots)} lots in scope -- widen the window")
    lots["date_rank"] = lots["lot_date"].rank(method="first")

    df = hist.merge(lots, on="lot_id", how="inner")
    if df.empty:
        sys.exit("ERROR: no overlap between history lot_ids and metric lot_ids")

    vals = lots[mcol].to_numpy(dtype=float)
    grand, med = float(vals.mean()), float(np.median(vals))
    sig_r = robust_sigma(vals)
    trend_r, trend_p = stats.spearmanr(lots["date_rank"], vals)

    # ------------------------------------------------------------- flagged lots
    if args.flag_above is not None or args.flag_below is not None:
        hi = args.flag_above if args.flag_above is not None else np.inf
        lo = args.flag_below if args.flag_below is not None else -np.inf
        rule = f"explicit limits [{lo}, {hi}]"
    else:
        hi, lo = med + args.flag_k * sig_r, med - args.flag_k * sig_r
        rule = (f"median {med:.4g} +- {args.flag_k}*robust sigma {sig_r:.4g} "
                f"-> [{lo:.4g}, {hi:.4g}]")
    lots["_flag"] = (vals > hi) | (vals < lo)
    flagged = set(lots.loc[lots._flag, "lot_id"])
    K, N = len(flagged), len(lots)
    tail_usable = K >= args.min_flagged
    # Which way did the excursion go? A group that moved the OTHER way is not the
    # suspect, however large its |z| -- this is what separates a 2-tool step's
    # mirror pair ("tool X is high" vs "tool Y is low").
    direction = 0
    if K:
        direction = 1 if float(lots.loc[lots._flag, mcol].mean()) > med else -1

    # ---------------------------------------------------------------- candidates
    cands = []
    for step, d in df.groupby("step", sort=True):
        step_lots = set(d.lot_id)
        for key in (("tool",), ("tool", "chamber")):
            if key == ("tool", "chamber") and (d["chamber"] == "").all():
                continue
            for vals_key, g in d.groupby(list(key), sort=True):
                vals_key = (vals_key,) if not isinstance(vals_key, tuple) else vals_key
                tool = vals_key[0]
                chamber = vals_key[1] if len(vals_key) > 1 else ""
                if key == ("tool", "chamber") and chamber == "":
                    continue
                in_lots = sorted(set(g.lot_id))
                out_lots = sorted(step_lots - set(in_lots))
                if not out_lots:
                    continue  # covers every lot at this step -> no contrast possible
                a = lots.loc[lots.lot_id.isin(in_lots), mcol].to_numpy(dtype=float)
                b = lots.loc[lots.lot_id.isin(out_lots), mcol].to_numpy(dtype=float)
                delta = float(a.mean() - b.mean())
                z = float(delta / (sig_r * np.sqrt(1.0 / len(a) + 1.0 / len(b)))) if sig_r else 0.0
                if len(a) > 1 and len(b) > 1:
                    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                                 / (len(a) + len(b) - 2))
                    dcohen = float(delta / sp) if sp > 0 else float("nan")
                    t, p_t = stats.ttest_ind(a, b, equal_var=False)
                    t, p_t = float(t), float(p_t)
                else:
                    dcohen, t, p_t = float("nan"), float("nan"), float("nan")
                k_in = len(flagged & set(in_lots))
                p_tail = (float(stats.hypergeom.sf(k_in - 1, N, K, len(a)))
                          if K and k_in else 1.0)
                tail_score = (-np.log10(max(p_tail, 1e-300))) if tail_usable else 0.0
                member = lots.lot_id.isin(in_lots).to_numpy()
                r_time = point_biserial(member, lots["date_rank"].to_numpy())
                flags = []
                if len(a) < args.min_lots or len(b) < args.min_lots:
                    flags.append("THIN")
                if abs(r_time) > args.time_confound_r:
                    flags.append("TIME-CONFOUNDED")
                cands.append({
                    "step": step, "tool": tool, "chamber": chamber,
                    "label": f"{step}/{tool}" + (f"/{chamber}" if chamber else ""),
                    "level": "chamber" if chamber else "tool",
                    "n_in": len(a), "n_out": len(b),
                    "mean_in": float(a.mean()), "mean_out": float(b.mean()),
                    "delta": delta, "shift_z": z, "cohens_d": dcohen,
                    "welch_t": t, "welch_p": p_t,
                    "flagged_in": k_in, "flagged_total": K, "p_tail": p_tail,
                    "tail_score": float(round(tail_score, 2)),
                    "shift_score": float(z * direction if direction else abs(z)),
                    "sort_key": (float(round(tail_score, 2)),
                                 float(z * direction if direction else abs(z))),
                    "r_membership_vs_time": r_time, "flags": flags,
                    "lots_in": in_lots,
                    "first_date": str(g["lot_date"].min().date()) if g["lot_date"].notna().any() else "",
                    "last_date": str(g["lot_date"].max().date()) if g["lot_date"].notna().any() else "",
                })
    if not cands:
        sys.exit("ERROR: no candidate tool/chamber groups with a contrast")
    cands.sort(key=lambda c: (-c["sort_key"][0], -c["sort_key"][1]))

    # ---------------------------------------------------------------- tie audit
    by_set: dict[frozenset, list[str]] = {}
    for c in cands:
        by_set.setdefault(frozenset(c["lots_in"]), []).append(c["label"])
    step_lots_map = {s: set(d.lot_id) for s, d in df.groupby("step")}
    for c in cands:
        s_in = frozenset(c["lots_in"])
        twins = [l for l in by_set[s_in] if l != c["label"]]
        if twins:
            c["flags"].append("TIE:identical-lot-set-with " + ",".join(twins))
        comp = frozenset(step_lots_map[c["step"]] - set(c["lots_in"]))
        mirrors = [l for l in by_set.get(comp, []) if l != c["label"]]
        if mirrors:
            c["flags"].append("MIRROR-of " + ",".join(mirrors)
                              + " (same comparison, sign flipped)")
    top = cands[0]
    ties = [c["label"] for c in cands[1:]
            if c["sort_key"][0] == top["sort_key"][0]
            and top["sort_key"][1] > 0
            and c["sort_key"][1] >= (1 - args.tie_tol) * top["sort_key"][1]
            and c["label"] not in " ".join(top["flags"])]
    if ties:
        top["flags"].append("TIE:score-within-%.0f%%-of " % (100 * args.tie_tol) + ",".join(ties))

    # --------------------------------------------------------- when did it start
    bucket_tbl = []
    lots["_bucket"] = pd.qcut(lots["date_rank"], min(args.time_buckets, len(lots)),
                              labels=False, duplicates="drop")
    member = lots.lot_id.isin(top["lots_in"])
    for b, g in lots.groupby("_bucket"):
        gi, go = g[member.loc[g.index]], g[~member.loc[g.index]]
        bucket_tbl.append({
            "bucket": int(b),
            "from": str(g["lot_date"].min().date()) if g["lot_date"].notna().any() else "",
            "to": str(g["lot_date"].max().date()) if g["lot_date"].notna().any() else "",
            "n_in": int(len(gi)), "mean_in": float(gi[mcol].mean()) if len(gi) else float("nan"),
            "n_out": int(len(go)), "mean_out": float(go[mcol].mean()) if len(go) else float("nan"),
            "delta": (float(gi[mcol].mean() - go[mcol].mean())
                      if len(gi) and len(go) else float("nan")),
        })

    # ---------------------------------------------------------------- pivot
    pivot = None
    if args.pivot_out:
        df["_grp"] = df["tool"] + np.where(df["chamber"] != "", "/" + df["chamber"], "")
        pivot = df.pivot_table(index="lot_id", columns="step", values="_grp", aggfunc="first")
        pivot = (pivot.reset_index()
                 .merge(lots[["lot_id", "lot_date", mcol, "_flag"]], on="lot_id", how="left")
                 .sort_values("lot_date"))
        pivot.to_csv(args.pivot_out, index=False)

    out = {"metric": mcol, "lots_in_scope": int(N), "lots_total": int(n_all),
           "window": [str(lots.lot_date.min().date()), str(lots.lot_date.max().date())],
           "grand_mean": grand, "median": med, "robust_sigma": sig_r,
           "flag_rule": rule, "n_flagged": K, "flagged_lots": sorted(flagged),
           "excursion_direction": {1: "HIGH", -1: "LOW", 0: "undetermined"}[direction],
           "ranking_key": "TAIL (hypergeometric over-representation among flagged lots)"
                          if tail_usable else "SHIFT (robust two-sample z)",
           "global_time_trend": {"spearman_r": float(trend_r), "p": float(trend_p)},
           "candidates": cands[: args.top], "top": top, "time_buckets": bucket_tbl}

    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"metric        : {mcol}")
    print(f"scope         : {N}/{n_all} lots, {out['window'][0]} .. {out['window'][1]}")
    print(f"grand mean    : {grand:.4f}   median {med:.4f}   robust sigma {sig_r:.4f}")
    print(f"flag rule     : {rule}")
    print(f"flagged lots  : {K}" + (f"  ({', '.join(sorted(flagged))})" if 0 < K <= 12 else ""))
    print(f"ranking key   : {out['ranking_key']}"
          + ("" if tail_usable else
             f"   [only {K} flagged lot(s) < --min-flagged {args.min_flagged}: the tail test "
             f"has no power here]"))
    print(f"direction     : excursion is {out['excursion_direction']}"
          + ("  (groups that moved the other way rank below)" if direction else
             "  (no flagged lots: ranking on |z|, sign ignored)"))
    print(f"global drift  : Spearman r(metric, time) = {trend_r:+.3f} (p={trend_p:.3g})"
          + ("  <- the whole population is moving; a single tool may not be the story"
             if abs(trend_r) > 0.5 else ""))
    hdr = (f"\n{'#':<3}{'candidate':<24}{'lvl':<8}{'n_in':>5}{'n_out':>6}{'mean_in':>10}"
           f"{'delta':>9}{'shift_z':>9}{'flag_in':>9}{'p_tail':>10}{'d':>7}{'t':>8}")
    print(hdr)
    print("-" * (len(hdr) - 1))
    for i, c in enumerate(cands[: args.top], start=1):
        print(f"{i:<3}{c['label']:<24}{c['level']:<8}{c['n_in']:>5}{c['n_out']:>6}"
              f"{c['mean_in']:>10.3f}{c['delta']:>+9.3f}{c['shift_z']:>9.2f}"
              f"{str(c['flagged_in']) + '/' + str(K):>9}{c['p_tail']:>10.3g}"
              f"{c['cohens_d']:>7.2f}{c['welch_t']:>8.2f}")
        if c["flags"]:
            print(f"     flags: {'; '.join(c['flags'])}")
    print(f"\nTOP SUSPECT   : {top['label']}   delta {top['delta']:+.4g} "
          f"({top['n_in']} lots vs {top['n_out']}), shift z = {top['shift_z']:.2f}, "
          f"{top['flagged_in']}/{K} flagged lots, p_tail = {top['p_tail']:.3g}")
    if any(f.startswith("TIE") for f in top["flags"]):
        print("  ** NOT A UNIQUE ANSWER ** "
              + "; ".join(f for f in top["flags"] if f.startswith("TIE")))
        print("  Break the tie with data this analysis cannot supply: FDC traces, per-wafer "
              "(not per-lot)\n  metrology, a split lot, or a deliberate re-run on the candidate "
              "tools.")
    if any(f.startswith("MIRROR") for f in top["flags"]):
        print("  ** MIRROR ** " + "; ".join(f for f in top["flags"] if f.startswith("MIRROR"))
              + "\n  A step with only two tools cannot tell 'tool X is high' from 'tool Y is "
                "low'.")
    if "TIME-CONFOUNDED" in top["flags"]:
        print("  ** TIME-CONFOUNDED ** these lots also occupy a distinct slice of the calendar "
              "(r = %+.2f).\n  Rule out incoming material, facility, and recipe/limit edits "
              "before blaming the tool." % top["r_membership_vs_time"])
    print(f"\nWHEN did the separation appear (top suspect vs rest):")
    print(f"  {'bucket':<8}{'from':<12}{'to':<12}{'n_in':>5}{'mean_in':>10}"
          f"{'n_out':>6}{'mean_out':>10}{'delta':>9}")
    for b in bucket_tbl:
        mi = f"{b['mean_in']:.3f}" if np.isfinite(b["mean_in"]) else "-"
        mo = f"{b['mean_out']:.3f}" if np.isfinite(b["mean_out"]) else "-"
        dl = f"{b['delta']:+.3f}" if np.isfinite(b["delta"]) else "-"
        print(f"  {b['bucket']:<8}{b['from']:<12}{b['to']:<12}{b['n_in']:>5}{mi:>10}"
              f"{b['n_out']:>6}{mo:>10}{dl:>9}")
    print("  delta ~0 in early buckets and large in late ones = a DRIFT with a start date "
          "(look for what\n  changed then: PM, part change, recipe edit). A constant delta = a "
          "tool that was always\n  different (look at the last qual/match, not at today's PM).")
    if pivot is not None:
        print(f"\nwrote {args.pivot_out} ({len(pivot)} lots)")
    print("\nAssociation is not causation. Confirm the top suspect with an independent mechanism"
          "\n(FDC trace, chamber-part condition, a monitor wafer, a split lot) before any "
          "irreversible action.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
