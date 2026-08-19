#!/usr/bin/env python3
"""Analyse a two-level DOE: main effects, interactions, and significance.

Significance path is chosen from the data, not by the user:
  * replicated design (or centre-point replicates) -> pure-error MSE -> t-tests
  * unreplicated design                            -> LENTH'S METHOD (PSE),
    reporting both the individual margin of error (ME) and the simultaneous
    margin of error (SME)
Centre points, when present, are held out of the effect estimates and used for
a curvature (lack-of-fit) test.

Half-normal plot data is always emitted (--half-normal-out) and can be drawn
with --plot; the half-normal plot is the primary read for an unreplicated
screening design -- the effects that break away from the straight line are real.

Input CSV: one column per factor in coded units (-1 / 0 / +1), one response
column. Columns StdOrder, RunOrder, Block, PtType are recognised and ignored.
Rows with all factors at 0 (or PtType=center) are treated as centre points.

Usage examples:
  python3 doe_analyze.py --data etch_screening.csv --response CD_NM --max-order 2
  python3 doe_analyze.py --data etch_screening.csv --response CD_NM \\
      --generators "D=AB,E=AC" --half-normal-out hn.csv --plot hn.png
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from doe_builder import (LETTERS, alias_class, defining_subgroup, defining_words,
                             fmt_word, parse_generators)
except ImportError:  # pragma: no cover - only if the sibling script is missing
    LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    alias_class = defining_subgroup = defining_words = fmt_word = parse_generators = None

META_COLS = {"stdorder", "runorder", "block", "pttype", "lot_id", "wafer", "date", "notes"}


def detect_factors(df: pd.DataFrame, response: str) -> list[str]:
    out = []
    for c in df.columns:
        if c == response or c.lower() in META_COLS or c.lower().endswith("_real"):
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if s.isna().any():
            continue
        vals = set(np.round(s.unique(), 9))
        if vals <= {-1.0, 0.0, 1.0} and {-1.0, 1.0} <= vals:
            out.append(c)
    return out


def lenth(effects: dict[str, float], conf: float = 0.95) -> dict:
    """Lenth's pseudo standard error for an unreplicated factorial.

    s0  = 1.5 * median|effect|
    PSE = 1.5 * median{ |effect| : |effect| < 2.5*s0 }
    ME  = t(1-alpha/2, d) * PSE            with d = m/3
    SME = t(gamma, d)     * PSE            with gamma = (1 + conf^(1/m))/2
    """
    e = np.array([abs(v) for v in effects.values()], dtype=float)
    m = len(e)
    if m < 3:
        raise ValueError("Lenth's method needs at least 3 estimated effects")
    s0 = 1.5 * float(np.median(e))
    kept = e[e < 2.5 * s0]
    pse = 1.5 * float(np.median(kept)) if len(kept) else 1.5 * float(np.median(e))
    d = m / 3.0
    alpha = 1.0 - conf
    me = float(stats.t.ppf(1 - alpha / 2.0, d) * pse)
    gamma = (1.0 + conf ** (1.0 / m)) / 2.0
    sme = float(stats.t.ppf(gamma, d) * pse)
    return {"m_effects": m, "s0": s0, "PSE": pse, "df": d, "ME": me, "SME": sme,
            "conf": conf}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--data", required=True, help="design matrix + response CSV")
    ap.add_argument("--response", required=True, help="response column name")
    ap.add_argument("--factors", help="comma-separated factor columns (default: auto-detect)")
    ap.add_argument("--max-order", type=int, default=2,
                    help="highest interaction order to estimate (default 2)")
    ap.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    ap.add_argument("--generators", help="e.g. 'D=AB,E=AC' -> annotate each effect with its alias")
    ap.add_argument("--half-normal-out", help="write half-normal plot data to this CSV")
    ap.add_argument("--plot", help="write a half-normal plot PNG here")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    df = pd.read_csv(args.data)
    if args.response not in df.columns:
        sys.exit(f"ERROR: response column {args.response!r} not in {list(df.columns)}")
    df = df[pd.to_numeric(df[args.response], errors="coerce").notna()].reset_index(drop=True)
    if df.empty:
        sys.exit("ERROR: no rows with a numeric response -- has the design been run yet?")

    factors = ([f.strip() for f in args.factors.split(",")] if args.factors
               else detect_factors(df, args.response))
    if not factors:
        sys.exit("ERROR: no coded (-1/0/+1) factor columns found; pass --factors")
    missing = [f for f in factors if f not in df.columns]
    if missing:
        sys.exit(f"ERROR: factor columns not found: {missing}")

    y = df[args.response].astype(float).to_numpy()
    X = df[factors].astype(float).to_numpy()

    is_center = np.all(np.isclose(X, 0.0), axis=1)
    if "PtType" in df.columns:
        is_center |= df["PtType"].astype(str).str.lower().eq("center").to_numpy()
    fac = ~is_center
    n_f, n_c = int(fac.sum()), int(is_center.sum())
    if n_f < 4:
        sys.exit(f"ERROR: only {n_f} factorial runs -- not enough to estimate effects")

    Xf, yf = X[fac], y[fac]

    # ---------------- effects
    # With --generators the alias algebra is done in single-letter notation, so
    # effects are labelled A,B,AB,... and a legend maps letters to columns.
    use_letters = bool(args.generators)
    letters = LETTERS[: len(factors)]

    def eff_name(combo: tuple[int, ...]) -> str:
        if use_letters:
            return "".join(letters[i] for i in combo)
        names = [factors[i] for i in combo]
        return "".join(names) if all(len(n) == 1 for n in names) else "*".join(names)

    effects: dict[str, float] = {}
    folded: dict[str, list[str]] = {}      # effect -> other terms sharing its contrast
    non_orthogonal: list[str] = []
    seen: dict[bytes, str] = {}            # contrast signature -> first effect on it
    for order in range(1, min(args.max_order, len(factors)) + 1):
        for combo in itertools.combinations(range(len(factors)), order):
            name = eff_name(combo)
            col = np.prod(Xf[:, combo], axis=1)
            if abs(col.sum()) > 1e-9:
                non_orthogonal.append(name)
                continue
            if np.allclose(col, col[0]):
                continue  # contrast is constant -> confounded with the mean
            # A fraction has only n_runs-1 independent contrasts. Two aliased terms
            # ARE the same column: count them once, or Lenth's PSE is computed over
            # duplicated values and the effect count m is wrong.
            canon = col if col[np.flatnonzero(col)[0]] > 0 else -col
            sig = np.round(canon, 9).tobytes()
            if sig in seen:
                folded[seen[sig]].append(name)
                continue
            seen[sig] = name
            folded[name] = []
            effects[name] = float(2.0 * np.dot(col, yf) / n_f)
    if not effects:
        sys.exit("ERROR: no estimable contrasts (is the design balanced?)")

    # ---------------- pure error from replicate groups
    keys = [tuple(np.round(r, 9)) for r in Xf]
    groups: dict[tuple, list[float]] = {}
    for k_, v in zip(keys, yf):
        groups.setdefault(k_, []).append(v)
    ss_pe = sum(float(np.sum((np.array(v) - np.mean(v)) ** 2)) for v in groups.values() if len(v) > 1)
    df_pe = sum(len(v) - 1 for v in groups.values() if len(v) > 1)
    if n_c > 1:
        yc = y[is_center]
        ss_pe += float(np.sum((yc - yc.mean()) ** 2))
        df_pe += n_c - 1
    replicated = df_pe >= 1

    # ---------------- alias annotation
    alias_note: dict[str, str] = {}
    if args.generators:
        if parse_generators is None:
            sys.exit("ERROR: doe_builder.py must sit next to this script for --generators")
        try:
            sub = defining_subgroup(defining_words(parse_generators(args.generators)))
        except ValueError as e:
            sys.exit(f"ERROR: {e}")
        for name in effects:
            cls = alias_class(frozenset(name), sub)
            alias_note[name] = " = ".join(fmt_word(w) for w in cls if fmt_word(w) != name)
    else:
        for name, others in folded.items():
            alias_note[name] = " = ".join(others)

    out: dict = {"data": args.data, "response": args.response, "factors": factors,
                 "n_factorial": n_f, "n_center": n_c, "grand_mean": float(yf.mean()),
                 "effects": [], "method": None, "curvature": None, "warnings": []}
    if non_orthogonal:
        out["warnings"].append(
            f"contrast(s) {non_orthogonal} are not orthogonal to the mean in this design "
            f"and were skipped -- unbalanced or partially-run design?")

    rows = sorted(effects.items(), key=lambda kv: -abs(kv[1]))

    # ---------------- significance
    if replicated:
        mse = ss_pe / df_pe
        se = 2.0 * (mse / n_f) ** 0.5
        out["method"] = {"kind": "t-test on pure error", "MSE": mse, "df_pure_error": df_pe,
                         "se_effect": se}
        for name, eff in rows:
            t = eff / se if se > 0 else float("inf")
            p = float(2 * stats.t.sf(abs(t), df_pe))
            out["effects"].append({"effect": name, "value": eff, "coef": eff / 2.0,
                                   "t": float(t), "p": p, "significant": bool(p < args.alpha),
                                   "alias": alias_note.get(name, "")})
    else:
        try:
            L = lenth(effects, conf=1.0 - args.alpha)
        except ValueError as e:
            sys.exit(f"ERROR: {e}")
        out["method"] = dict(kind="Lenth PSE (unreplicated)", **L)
        for name, eff in rows:
            out["effects"].append({
                "effect": name, "value": eff, "coef": eff / 2.0,
                "significant": bool(abs(eff) > L["ME"]),
                "significant_simultaneous": bool(abs(eff) > L["SME"]),
                "alias": alias_note.get(name, "")})

    # ---------------- curvature
    if n_c >= 1:
        ybar_f, ybar_c = float(yf.mean()), float(y[is_center].mean())
        ss_curv = n_f * n_c * (ybar_f - ybar_c) ** 2 / (n_f + n_c)
        curv = {"mean_factorial": ybar_f, "mean_center": ybar_c,
                "difference": ybar_f - ybar_c, "SS_curvature": float(ss_curv)}
        if replicated:
            f_stat = ss_curv / (ss_pe / df_pe)
            curv["F"] = float(f_stat)
            curv["p"] = float(stats.f.sf(f_stat, 1, df_pe))
            curv["significant"] = bool(curv["p"] < args.alpha)
        else:
            curv["note"] = "no pure error -> curvature not testable; add centre-point replicates"
        out["curvature"] = curv
    else:
        out["warnings"].append("no centre points -> curvature cannot be tested; a 2-level "
                               "design fitted to a curved response will mis-locate the optimum")

    # ---------------- half-normal data
    m = len(rows)
    absr = sorted(((abs(v), k) for k, v in rows))
    hn = []
    for i, (av, name) in enumerate(absr, start=1):
        p = (i - 0.5) / m
        hn.append({"rank": i, "effect": name, "abs_effect": av,
                   "half_normal_quantile": float(stats.norm.ppf(0.5 + p / 2.0))})
    out["half_normal"] = hn
    if args.half_normal_out:
        pd.DataFrame(hn).to_csv(args.half_normal_out, index=False)

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=120)
        xs = [h["half_normal_quantile"] for h in hn]
        ys = [h["abs_effect"] for h in hn]
        ax.plot(xs, ys, "o", color="#1f77b4")
        thresh = out["method"].get("ME") if not replicated else None
        for h in hn:
            big = (h["abs_effect"] > thresh) if thresh else (
                any(e["effect"] == h["effect"] and e.get("significant") for e in out["effects"]))
            if big:
                ax.annotate(h["effect"], (h["half_normal_quantile"], h["abs_effect"]),
                            textcoords="offset points", xytext=(6, -2), fontsize=9)
        if thresh:
            ax.axhline(thresh, color="#d62728", ls="--", lw=1,
                       label=f"Lenth ME = {thresh:.4g}")
            ax.axhline(out["method"]["SME"], color="#d62728", ls=":", lw=1,
                       label=f"Lenth SME = {out['method']['SME']:.4g}")
            ax.legend(fontsize=8)
        ax.set_xlabel("half-normal quantile")
        ax.set_ylabel(f"|effect| on {args.response}")
        ax.set_title(f"Half-normal plot -- {os.path.basename(args.data)}")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(args.plot)
        plt.close(fig)

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"data      : {args.data}   response: {args.response}")
    print(f"factors   : {','.join(factors)}")
    if args.generators:
        print("legend    : " + "  ".join(f"{l}={f}" for l, f in zip(letters, factors)))
    print(f"runs      : {n_f} factorial + {n_c} centre   grand mean = {out['grand_mean']:.4f}")
    n_indep = len(set(tuple(np.round(r, 9)) for r in Xf)) - 1
    print(f"contrasts : {len(effects)} estimated"
          + (f" (design supports at most {n_indep} independent contrasts)"
             if len(effects) >= n_indep else ""))
    print(f"method    : {out['method']['kind']}")
    if replicated:
        print(f"            MSE = {out['method']['MSE']:.5g} on {df_pe} df pure error, "
              f"se(effect) = {out['method']['se_effect']:.4g}")
        w = max(10, max(len(e["effect"]) for e in out["effects"]) + 2)
        print(f"\n{'effect':<{w}}{'value':>12}{'coef':>12}{'t':>9}{'p':>10}  sig  alias")
        for e in out["effects"]:
            print(f"{e['effect']:<{w}}{e['value']:>12.4f}{e['coef']:>12.4f}{e['t']:>9.2f}"
                  f"{e['p']:>10.4f}  {'*' if e['significant'] else ' '}    {e['alias']}")
    else:
        M = out["method"]
        print(f"            PSE = {M['PSE']:.4g}  ME = {M['ME']:.4g}  SME = {M['SME']:.4g}  "
              f"(m={M['m_effects']} effects, d={M['df']:.2f} df)")
        w = max(10, max(len(e["effect"]) for e in out["effects"]) + 2)
        print(f"\n{'effect':<{w}}{'value':>12}{'coef':>12}  >ME  >SME  alias")
        for e in out["effects"]:
            print(f"{e['effect']:<{w}}{e['value']:>12.4f}{e['coef']:>12.4f}   "
                  f"{'*' if e['significant'] else ' '}     "
                  f"{'*' if e['significant_simultaneous'] else ' '}   {e['alias']}")
        print("\n  * >ME  : individually significant at alpha=%.2f" % args.alpha)
        print("  * >SME : significant after correcting for testing all %d effects "
              "(the honest bar for screening)" % M["m_effects"])
    if out["curvature"]:
        c = out["curvature"]
        print(f"\ncurvature : factorial mean {c['mean_factorial']:.4f} vs centre mean "
              f"{c['mean_center']:.4f}  (diff {c['difference']:+.4f})")
        if "F" in c:
            print(f"            F = {c['F']:.3f} on 1,{df_pe} df, p = {c['p']:.4f}"
                  f"  -> {'CURVATURE PRESENT: go to RSM/CCD' if c['significant'] else 'no significant curvature: a linear+2fi model is adequate over this range'}")
        else:
            print(f"            {c['note']}")
    if args.generators:
        print("\nALIAS WARNING: every 'value' above is the sum of its whole alias class. "
              "In a low-resolution\n  fraction you cannot tell an effect from its alias without "
              "a fold-over or a follow-up run.")
    for w in out["warnings"]:
        print(f"\nWARNING: {w}")
    if args.half_normal_out:
        print(f"\nwrote {args.half_normal_out}")
    if args.plot:
        print(f"wrote {args.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
