#!/usr/bin/env python3
"""Build DOE design matrices for process characterisation: full factorial,
2^(k-p) fractional factorial with a PRINTED ALIAS STRUCTURE, and central
composite (CCD) designs for response-surface work.

Everything is computed from the generators you give (or from the built-in
catalogue of standard generators) -- the defining relation, the resolution and
the alias classes are derived, never looked up, so a hand-written generator set
is checked as rigorously as a catalogue one.

Coded units are -1 / 0 / +1 (and +-alpha for CCD axial points). Supplying
--levels adds real-unit columns so the design can go straight to the floor.

Usage examples:
  # 2^3 full factorial, 3 centre points, randomised, real engineering units
  python3 doe_builder.py --design full --factors PRESSURE,POWER,FLOW \\
      --levels "PRESSURE=10:30,POWER=200:400,FLOW=50:150" \\
      --center-points 3 --randomize --seed 7 --out ff.csv

  # 2^(5-2) screening design: prints defining relation + alias classes
  python3 doe_builder.py --design fractional -k 5 -p 2 --alias-order 2 --out screen.csv

  # same design blocked into 2 blocks (e.g. one chamber per block)
  python3 doe_builder.py --design fractional -k 5 -p 2 --block-on BC --out screen_blocked.csv

  # rotatable central composite in 3 factors with 4 centre points
  python3 doe_builder.py --design ccd -k 3 --alpha rotatable --center-points 4 --out ccd.csv
"""
from __future__ import annotations

import argparse
import itertools
import sys

import numpy as np
import pandas as pd

# "I" is reserved for the identity column in DOE notation, so it is not used
# as a factor letter.
LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"

# Standard generator sets (resolution-maximising / minimum-aberration choices as
# published in the usual DOE catalogues). The script prints the resolution it
# actually computes, so these are self-checking; supply --generators for
# anything not listed.
CATALOG: dict[tuple[int, int], list[str]] = {
    (3, 1): ["C=AB"],
    (4, 1): ["D=ABC"],
    (5, 1): ["E=ABCD"],
    (5, 2): ["D=AB", "E=AC"],
    (6, 1): ["F=ABCDE"],
    (6, 2): ["E=ABC", "F=BCD"],
    (6, 3): ["D=AB", "E=AC", "F=BC"],
    (7, 1): ["G=ABCDEF"],
    (7, 2): ["F=ABCD", "G=ABDE"],
    (7, 3): ["E=ABC", "F=BCD", "G=ACD"],
    (7, 4): ["D=AB", "E=AC", "F=BC", "G=ABC"],
    (8, 2): ["G=ABCD", "H=ABEF"],
    (8, 3): ["F=ABC", "G=ABD", "H=BCDE"],
    (8, 4): ["E=BCD", "F=ACD", "G=ABC", "H=ABD"],
}

Word = frozenset  # a "word" is a set of factor names; multiplication is XOR


# ---------------------------------------------------------------- alias algebra
def fmt_word(w: frozenset) -> str:
    """Render a word in canonical order; the empty word is the identity I."""
    return "I" if not w else "".join(sorted(w))


def parse_generators(spec: str) -> list[tuple[str, str]]:
    """'D=AB,E=AC' -> [('D','AB'), ('E','AC')]."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"generator {part!r} must look like D=AB")
        tgt, src = part.split("=", 1)
        tgt, src = tgt.strip().upper(), src.strip().upper().replace("*", "")
        if len(tgt) != 1:
            raise ValueError(f"generator target {tgt!r} must be a single letter")
        if len(src) < 2:
            raise ValueError(f"generator source {src!r} must be at least 2 letters")
        out.append((tgt, src))
    return out


def defining_words(gens: list[tuple[str, str]]) -> list[frozenset]:
    """Generator D=AB implies the defining word ABD (because D*AB = I)."""
    return [frozenset(tgt) ^ frozenset(src) for tgt, src in gens]


def defining_subgroup(words: list[frozenset]) -> list[frozenset]:
    """All 2^p products of the defining words, including the identity."""
    sub = {frozenset()}
    for w in words:
        sub |= {s ^ w for s in sub}
    return sorted(sub, key=lambda w: (len(w), fmt_word(w)))


def resolution(subgroup: list[frozenset]) -> int:
    lens = [len(w) for w in subgroup if w]
    return min(lens) if lens else 0


def alias_class(effect: frozenset, subgroup: list[frozenset]) -> list[frozenset]:
    return sorted({effect ^ w for w in subgroup}, key=lambda w: (len(w), fmt_word(w)))


def alias_report(factors: list[str], subgroup: list[frozenset], max_order: int) -> list[str]:
    """One line per alias class containing at least one effect of order<=max_order."""
    seen: set[frozenset] = set()
    lines: list[str] = []
    for order in range(1, max_order + 1):
        for combo in itertools.combinations(factors, order):
            eff = frozenset(combo)
            cls = alias_class(eff, subgroup)
            key = frozenset(cls)
            if key in seen:
                continue
            seen.add(key)
            lines.append(" = ".join(fmt_word(w) for w in cls))
    return lines


# ------------------------------------------------------------- design matrices
def full_factorial(factors: list[str]) -> pd.DataFrame:
    """2^k in standard (Yates) order: first factor alternates fastest."""
    k = len(factors)
    rows = []
    for i in range(2 ** k):
        rows.append([1 if (i >> j) & 1 else -1 for j in range(k)])
    return pd.DataFrame(rows, columns=factors, dtype=float)


def fractional_factorial(factors: list[str], gens: list[tuple[str, str]]) -> pd.DataFrame:
    base = [f for f in factors if f not in {t for t, _ in gens}]
    df = full_factorial(base)
    for tgt, src in gens:
        missing = [c for c in src if c not in df.columns]
        if missing:
            raise ValueError(
                f"generator {tgt}={src} references {missing} which are not base factors "
                f"({','.join(base)}); reorder factors or change generators"
            )
        col = np.ones(len(df))
        for c in src:
            col = col * df[c].to_numpy()
        df[tgt] = col
    return df[factors]


def ccd(factors: list[str], gens: list[tuple[str, str]] | None, alpha_spec: str
        ) -> tuple[pd.DataFrame, float]:
    fac = fractional_factorial(factors, gens) if gens else full_factorial(factors)
    n_f = len(fac)
    k = len(factors)
    if alpha_spec == "rotatable":
        alpha = float(n_f) ** 0.25
    elif alpha_spec in ("face", "faced", "ccf"):
        alpha = 1.0
    elif alpha_spec == "spherical":
        alpha = float(k) ** 0.5
    else:
        alpha = float(alpha_spec)
    axial = []
    for i in range(k):
        for sign in (-1.0, 1.0):
            row = [0.0] * k
            row[i] = sign * alpha
            axial.append(row)
    ax = pd.DataFrame(axial, columns=factors, dtype=float)
    fac = fac.copy()
    fac["PtType"] = "factorial"
    ax["PtType"] = "axial"
    return pd.concat([fac, ax], ignore_index=True), alpha


def parse_levels(spec: str, factors: list[str]) -> dict[str, tuple[float, float]]:
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        name, rng = part.split("=", 1)
        lo, hi = rng.split(":", 1)
        out[name.strip()] = (float(lo), float(hi))
    unknown = set(out) - set(factors)
    if unknown:
        raise ValueError(f"--levels names not in --factors: {sorted(unknown)}")
    return out


def add_real_units(df: pd.DataFrame, factors: list[str],
                   levels: dict[str, tuple[float, float]]) -> pd.DataFrame:
    for f in factors:
        if f in levels:
            lo, hi = levels[f]
            centre, half = (lo + hi) / 2.0, (hi - lo) / 2.0
            df[f"{f}_real"] = centre + df[f] * half
    return df


# ------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--design", required=True, choices=["full", "fractional", "ccd"])
    ap.add_argument("--factors", help="comma-separated factor names (default A,B,C,... by -k)")
    ap.add_argument("-k", "--k", type=int, help="number of factors (if --factors omitted)")
    ap.add_argument("-p", "--p", type=int, default=0,
                    help="fractional: number of generators (design is 2^(k-p))")
    ap.add_argument("--generators", help="e.g. 'D=AB,E=AC' (overrides the catalogue)")
    ap.add_argument("--alias-order", type=int, default=2,
                    help="print alias classes containing effects up to this order (default 2)")
    ap.add_argument("--levels", help="real units, e.g. 'A=10:30,B=200:400'")
    ap.add_argument("--center-points", type=int, default=0, help="centre points to append")
    ap.add_argument("--replicates", type=int, default=1,
                    help="replicate the factorial/axial points this many times (default 1)")
    ap.add_argument("--block-on", help="confound these words with blocks, e.g. 'ABC' or 'ABC,BCD'")
    ap.add_argument("--randomize", action="store_true", help="randomise run order within blocks")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for --randomize")
    ap.add_argument("--alpha", default="rotatable",
                    help="CCD axial distance: rotatable | face | spherical | <float>")
    ap.add_argument("--response-col", default="Response",
                    help="name of the empty response column to emit (default Response)")
    ap.add_argument("--out", help="write the design matrix to this CSV")
    args = ap.parse_args()

    # ---- factor names
    if args.factors:
        factors = [f.strip() for f in args.factors.split(",") if f.strip()]
    elif args.k:
        if args.k > len(LETTERS):
            sys.exit(f"ERROR: -k max is {len(LETTERS)} without explicit --factors")
        factors = list(LETTERS[: args.k])
    else:
        sys.exit("ERROR: give --factors or -k")
    k = len(factors)

    # ---- generators
    gens: list[tuple[str, str]] = []
    if args.design == "fractional" or (args.design == "ccd" and (args.generators or args.p)):
        if args.generators:
            try:
                gens = parse_generators(args.generators)
            except ValueError as e:
                sys.exit(f"ERROR: {e}")
        else:
            key = (k, args.p)
            if args.p <= 0:
                sys.exit("ERROR: fractional design needs -p or --generators")
            if key not in CATALOG:
                sys.exit(f"ERROR: no catalogue entry for 2^({k}-{args.p}); supply --generators")
            gens = parse_generators(",".join(CATALOG[key]))
        gen_targets = {t for t, _ in gens}
        if not gen_targets <= set(factors):
            sys.exit(f"ERROR: generator targets {sorted(gen_targets - set(factors))} "
                     f"are not among --factors")

    # ---- build
    try:
        if args.design == "full":
            df = full_factorial(factors)
            df["PtType"] = "factorial"
            alpha = None
        elif args.design == "fractional":
            df = fractional_factorial(factors, gens)
            df["PtType"] = "factorial"
            alpha = None
        else:
            df, alpha = ccd(factors, gens or None, args.alpha)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    if args.replicates > 1:
        df = pd.concat([df] * args.replicates, ignore_index=True)

    # ---- blocking (confound named words with blocks)
    block_words: list[frozenset] = []
    if args.block_on:
        block_words = [frozenset(w.strip().upper()) for w in args.block_on.split(",") if w.strip()]
        bad = [fmt_word(w) for w in block_words if not w <= set(factors)]
        if bad:
            sys.exit(f"ERROR: --block-on word(s) {bad} use letters that are not factors")
        signs = []
        for w in block_words:
            col = np.ones(len(df))
            for c in sorted(w):
                col = col * df[c].to_numpy()
            signs.append(np.where(col > 0, 1, 0))
        idx = np.zeros(len(df), dtype=int)
        for b, s in enumerate(signs):
            idx |= (s << b)
        df["Block"] = idx + 1
    else:
        df["Block"] = 1

    # ---- centre points
    if args.center_points > 0:
        cp = pd.DataFrame(0.0, index=range(args.center_points), columns=factors)
        cp["PtType"] = "center"
        # spread centre points over the blocks so each block is self-anchored
        blocks = sorted(df["Block"].unique())
        cp["Block"] = [blocks[i % len(blocks)] for i in range(args.center_points)]
        df = pd.concat([df, cp], ignore_index=True)

    df.insert(0, "StdOrder", range(1, len(df) + 1))

    # ---- run order
    if args.randomize:
        rng = np.random.default_rng(args.seed)
        order = np.empty(len(df), dtype=int)
        pos = 1
        for b in sorted(df["Block"].unique()):
            rows = df.index[df["Block"] == b].to_numpy()
            perm = rng.permutation(len(rows))
            for r, o in zip(rows, perm):
                order[r] = pos + o
            pos += len(rows)
        df["RunOrder"] = order
    else:
        df["RunOrder"] = df["StdOrder"]

    if args.levels:
        try:
            df = add_real_units(df, factors, parse_levels(args.levels, factors))
        except ValueError as e:
            sys.exit(f"ERROR: {e}")

    df[args.response_col] = ""
    cols = (["StdOrder", "RunOrder", "Block", "PtType"] + factors
            + [c for c in df.columns if c.endswith("_real")] + [args.response_col])
    df = df[cols].sort_values("RunOrder").reset_index(drop=True)

    # ---- report
    print(f"design      : {args.design}")
    print(f"factors ({k}): {','.join(factors)}")
    n_fact = int((df.PtType == "factorial").sum())
    n_ax = int((df.PtType == "axial").sum())
    n_c = int((df.PtType == "center").sum())
    print(f"runs        : {len(df)} total  ({n_fact} factorial, {n_ax} axial, {n_c} centre)")
    if alpha is not None:
        print(f"axial alpha : {alpha:.4f} ({args.alpha})")
    if gens:
        words = defining_words(gens)
        sub = defining_subgroup(words)
        res = resolution(sub)
        roman = {3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}.get(res, str(res))
        print(f"generators  : {', '.join(f'{t}={s}' for t, s in gens)}")
        print(f"fraction    : 2^({k}-{len(gens)}) = 1/{2 ** len(gens)} fraction, "
              f"resolution {roman}")
        print("defining relation: I = " + " = ".join(fmt_word(w) for w in sub if w))
        print(f"\nALIAS STRUCTURE (classes containing effects up to order {args.alias_order}):")
        for line in alias_report(factors, sub, args.alias_order):
            print("  " + line)
        if res <= 3:
            print("\n  WARNING resolution III: main effects are aliased with 2-factor "
                  "interactions.\n  Treat every significant main effect as 'this effect OR its "
                  "alias'; plan a fold-over\n  or a higher-resolution follow-up before acting on "
                  "the result.")
        elif res == 4:
            print("\n  NOTE resolution IV: main effects are clear of 2-factor interactions, but "
                  "2fi are\n  aliased with each other. A significant 2fi needs a follow-up "
                  "experiment to resolve.")
    if block_words:
        sub = defining_subgroup(defining_words(gens)) if gens else [frozenset()]
        confounded: list[str] = []
        for w in defining_subgroup(block_words):
            if not w:
                continue
            confounded.append(" = ".join(fmt_word(x) for x in alias_class(w, sub)))
        print(f"blocks      : {df.Block.nunique()} blocks; CONFOUNDED with blocks "
              f"(NOT estimable): " + "; ".join(confounded))
        print("              assign one block per tool/chamber/day; never split a block "
              "across a PM")
    if n_c == 0 and args.design != "fractional":
        print("NOTE: no centre points -> no curvature test and no independent pure-error "
              "estimate.")

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"\nwrote {args.out} ({len(df)} runs)")
    else:
        print()
        print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
