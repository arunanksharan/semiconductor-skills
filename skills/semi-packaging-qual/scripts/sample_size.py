#!/usr/bin/env python3
"""LTPD / AQL sampling math for reliability-qualification legs (exact binomial).

Everything here is computed from the binomial acceptance function

    P_accept(p) = sum_{k=0..c} C(n,k) * p^k * (1-p)^(n-k)

with no scipy dependency (log-space terms via math.lgamma + numpy, root found by
bisection on the monotone P_accept curve).

Definitions used (say them out loud in any report):
  * LTPD  - Lot Tolerance Percent Defective: the defect rate p at which a lot still
            has a 10% chance of being accepted (consumer's risk beta = 0.10). It is
            numerically identical to the one-sided 90% upper confidence bound
            (Clopper-Pearson) on p after observing c failures in n units. "n=77,
            accept 0 demonstrates 3% LTPD at 90% confidence" is this number.
  * AQL   - Acceptable Quality Level: the defect rate at which the plan still accepts
            with high probability (1 - producer's risk alpha, default 95%).
  * The classic MIL-S-19500 / JEDEC LTPD tables mix exact-binomial and Poisson-
    approximation rounding; both are printed so a plan can cite either defensibly.

Usage examples:
  python sample_size.py --n 77 --accept 0            # demonstrated LTPD (=> ~2.95%)
  python sample_size.py --ltpd 3                     # min n for c = 0, 1, 2
  python sample_size.py --ltpd 5 --accept 0 --json
  python sample_size.py --n 231 --fails 1            # 90% upper bound on p after 1 fail
  python sample_size.py --n 77 --accept 0 --aql 0.5  # P(accept) at a 0.5% AQL
  python sample_size.py --table                      # LTPD table, c = 0..2
  python sample_size.py --self-check                 # verify vs known table points
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np

# Known table anchors used by --self-check: (n, c, expected LTPD % , tolerance %)
KNOWN_POINTS = [
    (77, 0, 3.0, 0.10),   # entrenched industry/AEC value for a "3% LTPD" leg
    (45, 0, 5.0, 0.05),   # classic 5% LTPD, accept 0
    (22, 0, 10.0, 0.30),  # classic 10% LTPD, accept 0
    (32, 0, 7.0, 0.15),   # classic 7% LTPD, accept 0
]

# Known table anchors for the inverse direction: (LTPD %, c, expected exact min n)
KNOWN_INVERSE = [
    (10.0, 0, 22),
    (5.0, 0, 45),
    (3.0, 0, 76),   # exact binomial minimum; the tables print 77 (Poisson rounding)
    (1.0, 0, 230),  # exact binomial minimum; the tables print 231
]


def log_binom_pmf(n: int, k: np.ndarray, p: float) -> np.ndarray:
    """log C(n,k) p^k (1-p)^(n-k), vectorised over k."""
    lg = np.array([math.lgamma(n + 1) - math.lgamma(int(ki) + 1) - math.lgamma(n - int(ki) + 1)
                   for ki in np.atleast_1d(k)], dtype=float)
    return lg + k * math.log(p) + (n - k) * math.log1p(-p)


def p_accept(n: int, c: int, p: float) -> float:
    """P(X <= c) for X ~ Binomial(n, p). Exact, log-space."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0 if c < n else 1.0
    if c >= n:
        return 1.0
    k = np.arange(0, c + 1, dtype=float)
    return float(np.exp(log_binom_pmf(n, k, p)).sum())


def _bisect(f, lo: float, hi: float, tol: float = 1e-12, iters: int = 300) -> float:
    """Root of a monotone-decreasing f on [lo, hi]."""
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise ValueError(f"root not bracketed: f({lo})={flo:.6g}, f({hi})={fhi:.6g}")
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < tol or (hi - lo) < tol:
            return mid
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


def ltpd(n: int, c: int = 0, confidence: float = 0.90) -> float:
    """Defect rate (fraction) whose acceptance probability equals 1 - confidence.

    Equivalently the one-sided Clopper-Pearson upper bound on p after c failures in n.
    """
    if c >= n:
        raise ValueError("accept number must be < sample size")
    beta = 1.0 - confidence
    return _bisect(lambda p: p_accept(n, c, p) - beta, 1e-12, 1.0 - 1e-12)


def min_n_for_ltpd(ltpd_frac: float, c: int = 0, confidence: float = 0.90,
                   n_max: int = 2_000_000) -> int:
    """Smallest n whose accept-c plan demonstrates <= ltpd_frac at `confidence`."""
    beta = 1.0 - confidence
    lo, hi = c + 1, max(c + 2, 64)
    while hi < n_max and p_accept(hi, c, ltpd_frac) > beta:
        lo, hi = hi, hi * 2
    if hi >= n_max:
        raise ValueError("required sample size exceeds n_max")
    while lo < hi:  # binary search on the monotone-in-n acceptance probability
        mid = (lo + hi) // 2
        if p_accept(mid, c, ltpd_frac) <= beta:
            hi = mid
        else:
            lo = mid + 1
    return lo


def poisson_m(c: int, confidence: float = 0.90) -> float:
    """Poisson mean m with sum_{k<=c} e^-m m^k/k! = 1 - confidence.

    This is the chi-square/Poisson approximation the printed LTPD tables use;
    min n ~= m / LTPD. Solved by bisection, no scipy.
    """
    beta = 1.0 - confidence

    def cdf(m: float) -> float:
        term, tot = math.exp(-m), 0.0
        for k in range(0, c + 1):
            if k:
                term *= m / k
            tot += term
        return tot

    return _bisect(lambda m: cdf(m) - beta, 1e-9, 1e4)


def aql_for_plan(n: int, c: int, producer_risk: float = 0.05) -> float:
    """Defect rate accepted with probability 1 - producer_risk (i.e. the plan's AQL)."""
    target = 1.0 - producer_risk
    return _bisect(lambda p: p_accept(n, c, p) - target, 1e-12, 1.0 - 1e-12)


def plan_report(n: int, c: int, confidence: float, producer_risk: float,
                aql_pct: float | None = None) -> dict:
    rep = {
        "mode": "evaluate_plan",
        "n": n,
        "accept_number": c,
        "confidence": confidence,
        "ltpd_pct": round(ltpd(n, c, confidence) * 100, 4),
        "point_estimate_pct": round(100.0 * c / n, 4),
        "aql_pct_at_producer_risk": round(aql_for_plan(n, c, producer_risk) * 100, 4),
        "producer_risk": producer_risk,
    }
    if aql_pct is not None:
        rep["p_accept_at_aql"] = round(p_accept(n, c, aql_pct / 100.0), 6)
        rep["aql_pct_queried"] = aql_pct
    return rep


def inverse_report(ltpd_pct: float, accepts: list[int], confidence: float) -> dict:
    frac = ltpd_pct / 100.0
    rows = []
    for c in accepts:
        n_exact = min_n_for_ltpd(frac, c, confidence)
        n_pois = math.ceil(poisson_m(c, confidence) / frac)
        rows.append({
            "accept_number": c,
            "min_n_exact_binomial": n_exact,
            "min_n_poisson_table": n_pois,
            "achieved_ltpd_pct_at_exact_n": round(ltpd(n_exact, c, confidence) * 100, 4),
        })
    return {
        "mode": "required_sample_size",
        "ltpd_pct_target": ltpd_pct,
        "confidence": confidence,
        "plans": rows,
        "note": ("Printed MIL-S-19500 / JEDEC LTPD tables round via the Poisson "
                 "approximation, which is why 3% / accept-0 is tabled as 77 while the "
                 "exact binomial minimum is 76. Either is defensible; state which."),
    }


def ltpd_table(accepts: list[int], grid: list[float], confidence: float) -> dict:
    return {
        "mode": "table",
        "confidence": confidence,
        "ltpd_pct_grid": grid,
        "rows": [
            {"accept_number": c,
             "min_n": {f"{g:g}%": min_n_for_ltpd(g / 100.0, c, confidence) for g in grid}}
            for c in accepts
        ],
    }


def self_check(confidence: float = 0.90) -> tuple[bool, list[dict]]:
    results = []
    ok = True
    for n, c, expect, tol in KNOWN_POINTS:
        got = ltpd(n, c, confidence) * 100
        passed = abs(got - expect) <= tol
        ok &= passed
        results.append({"check": f"LTPD(n={n}, c={c})", "expected_pct": expect,
                        "tolerance_pct": tol, "computed_pct": round(got, 4),
                        "pass": bool(passed)})
    for pct, c, expect_n in KNOWN_INVERSE:
        got_n = min_n_for_ltpd(pct / 100.0, c, confidence)
        passed = got_n == expect_n
        ok &= passed
        results.append({"check": f"min_n(LTPD={pct}%, c={c}) exact",
                        "expected": expect_n, "computed": got_n, "pass": bool(passed)})
    # Round-trip: the exact minimum n must demonstrate <= the target LTPD.
    for pct, c, _ in KNOWN_INVERSE:
        n = min_n_for_ltpd(pct / 100.0, c, confidence)
        got = ltpd(n, c, confidence) * 100
        passed = got <= pct + 1e-9
        ok &= passed
        results.append({"check": f"round-trip LTPD(min_n({pct}%, c={c}))",
                        "expected": f"<= {pct}", "computed_pct": round(got, 4),
                        "pass": bool(passed)})
    return ok, results


def _fmt_plan(rep: dict) -> str:
    w = 46
    conf = "{:.0%}".format(rep["confidence"])
    alpha = "{:.0%}".format(rep["producer_risk"])
    rows = [
        ("Demonstrated LTPD at {} confidence".format(conf), "{:.3f} %".format(rep["ltpd_pct"])),
        ("Point estimate of p", "{:.3f} %".format(rep["point_estimate_pct"])),
        ("AQL at {} producer risk".format(alpha),
         "{:.3f} %".format(rep["aql_pct_at_producer_risk"])),
    ]
    if "p_accept_at_aql" in rep:
        rows.append(("P(accept) at p = {:g} %".format(rep["aql_pct_queried"]),
                     "{:.4f}".format(rep["p_accept_at_aql"])))
    out = ["Sampling plan: n = {}, accept <= {} failures".format(rep["n"], rep["accept_number"]),
           "  (LTPD = one-sided {} upper confidence bound on the defect rate)".format(conf), ""]
    out += ["  {} : {}".format(label.ljust(w), value) for label, value in rows]
    return "\n".join(out)


def _fmt_inverse(rep: dict) -> str:
    out = [f"Required sample size for LTPD = {rep['ltpd_pct_target']:g} % "
           f"at {rep['confidence']:.0%} confidence", "",
           "  accept c | min n (exact binomial) | min n (Poisson table) | LTPD at exact n",
           "  ---------|------------------------|-----------------------|----------------"]
    for r in rep["plans"]:
        out.append(f"  {r['accept_number']:>8} | {r['min_n_exact_binomial']:>22} | "
                   f"{r['min_n_poisson_table']:>21} | {r['achieved_ltpd_pct_at_exact_n']:>13.3f} %")
    out += ["", "  " + rep["note"]]
    return "\n".join(out)


def _fmt_table(rep: dict) -> str:
    grid = rep["ltpd_pct_grid"]
    head = "  accept c | " + " | ".join(f"{g:g}%".rjust(6) for g in grid)
    out = [f"Minimum sample size (exact binomial, {rep['confidence']:.0%} confidence)", "",
           head, "  ---------|" + "|".join("-" * 8 for _ in grid)]
    for r in rep["rows"]:
        cells = " | ".join(str(r["min_n"][f"{g:g}%"]).rjust(6) for g in grid)
        out.append(f"  {r['accept_number']:>8} | {cells}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, help="sample size of the leg")
    ap.add_argument("--accept", "-c", type=int, help="accept number (max allowable failures)")
    ap.add_argument("--fails", type=int,
                    help="observed failures; same math as --accept, reported as an upper bound")
    ap.add_argument("--ltpd", type=float, metavar="PCT",
                    help="LTPD target in %%; inverse mode -> required n")
    ap.add_argument("--accepts", type=int, nargs="+", default=[0, 1, 2],
                    help="accept numbers to solve for in inverse/table mode (default 0 1 2)")
    ap.add_argument("--aql", type=float, metavar="PCT",
                    help="query P(accept) at this defect rate %%")
    ap.add_argument("--confidence", type=float, default=0.90,
                    help="confidence for LTPD (default 0.90 = 10%% consumer risk)")
    ap.add_argument("--producer-risk", type=float, default=0.05,
                    help="alpha used to report the plan's AQL (default 0.05)")
    ap.add_argument("--table", action="store_true", help="print the LTPD min-n table")
    ap.add_argument("--grid", type=float, nargs="+",
                    default=[10, 7, 5, 3, 2, 1], help="LTPD %% grid for --table")
    ap.add_argument("--self-check", action="store_true",
                    help="verify against known table points; exit 1 on mismatch")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    if not (0.0 < args.confidence < 1.0):
        ap.error("--confidence must be in (0,1)")

    if args.self_check:
        ok, results = self_check(args.confidence)
        if args.json:
            print(json.dumps({"mode": "self_check", "pass": ok, "checks": results}, indent=2))
        else:
            print(f"sample_size.py self-check (confidence {args.confidence:.0%})")
            for r in results:
                mark = "PASS" if r["pass"] else "FAIL"
                got = r.get("computed_pct", r.get("computed"))
                exp = r.get("expected_pct", r.get("expected"))
                print(f"  [{mark}] {r['check']:<38} expected {exp}  computed {got}")
            print("  OVERALL:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    if args.table:
        rep = ltpd_table(args.accepts, args.grid, args.confidence)
        print(json.dumps(rep, indent=2) if args.json else _fmt_table(rep))
        return 0

    if args.ltpd is not None:
        if not (0 < args.ltpd < 100):
            ap.error("--ltpd must be a percentage in (0,100)")
        accepts = [args.accept] if args.accept is not None else args.accepts
        rep = inverse_report(args.ltpd, accepts, args.confidence)
        print(json.dumps(rep, indent=2) if args.json else _fmt_inverse(rep))
        return 0

    c = args.accept if args.accept is not None else args.fails
    if args.n is not None and c is not None:
        if c >= args.n:
            ap.error("accept/fails must be smaller than --n")
        rep = plan_report(args.n, c, args.confidence, args.producer_risk, args.aql)
        if args.fails is not None and args.accept is None:
            rep["mode"] = "upper_confidence_bound"
            rep["observed_failures"] = args.fails
        print(json.dumps(rep, indent=2) if args.json else _fmt_plan(rep))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
