#!/usr/bin/env python3
"""Generate synthetic wafer-sort data for the semi-yield-monitor skill.

Produces die_results.csv, history.csv and sort_history.csv in the canonical
schemas (see references/data-formats.md). Four seeded scenarios by default:

  BASE  3 wafers  healthy baseline (Poisson background only, D0 = 0.4 /cm2)
  EDGE  2 wafers  edge-ring failures (extra fail prob in the outer band, bin 7)
  SCRT  1 wafer   scratch (linear chord of failures, bin 9)
  CNTR  1 wafer   center cluster (extra fail prob near center, bin 6)

--extended appends three more signature classes (kept out of the shipped
sample set to stay inside the repo's size budget; used by the eval suite):

  DONT  1 wafer   donut / mid-radius annulus (bin 10)
  HALF  1 wafer   half-moon, left half plane (bin 11)
  RETL  1 wafer   repeating reticle position, 5x5 shot, die (2,3) (bin 12)

Background defectivity is Poisson: p_fail = 1 - exp(-D0 * A) with
D0 = 0.4 defects/cm2 and die area A = 0.25 cm2 (lambda = 0.1, ~90.5% yield).
Die grid: 40 x 40 minus a circular mask (~1200 dies/wafer).

sort_history.csv is a 36-wafer time series for SPC (lot_id,wafer_id,date,
dies,passed) with three seeded features: one gross-excursion wafer inside the
baseline window, a real -2.7 pp step shift, and a suspicious final up-tick.

Usage example:
  python gen_sample_data.py --out ../../../sample-data/semi-yield-monitor --seed 42
  python gen_sample_data.py --out /tmp/extended --seed 42 --extended
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

import numpy as np

GRID_N = 40
DIE_AREA_CM2 = 0.25          # exposed to yield_models.py evals via --die-area 0.25
D0_BASELINE = 0.4            # defects/cm2 seeded into the background
BG_BINS = ((5, 51, 0.70), (8, 81, 0.30))   # (hard, soft, share) for background fails

SCENARIOS = (
    # lot_id, n_wafers, signature
    ("BASE", 3, None),
    ("EDGE", 2, "edge_ring"),
    ("SCRT", 1, "scratch"),
    ("CNTR", 1, "center_cluster"),
)

# appended by --extended; order matters — appending keeps the default
# four-scenario output byte-identical to the shipped sample data
EXTENDED = (
    ("DONT", 1, "donut"),
    ("HALF", 1, "half_moon"),
    ("RETL", 1, "reticle"),
)

# sort_history.csv: (lot_id, n_wafers, true_yield, start_date_offset_days)
SPC_LOTS = (
    ("L01", 3, 0.905), ("L02", 3, 0.905), ("L03", 3, 0.905), ("L04", 3, 0.905),
    ("L05", 3, 0.905), ("L06", 3, 0.905), ("L07", 3, 0.905),
    ("L08", 3, 0.878), ("L09", 3, 0.878), ("L10", 3, 0.878), ("L11", 3, 0.878),
    ("L12", 3, 0.958),
)
SPC_WAFER_SIGMA = 0.010      # wafer-to-wafer sigma beyond binomial (overdispersion)
SPC_EXCURSION = ("L03", "W2", 0.800)   # single gross-excursion wafer in the baseline window
# Offset for the SPC stream, chosen so the REALIZED wafer-to-wafer dispersion of
# the 20 clean baseline wafers (sd 0.0101) matches the nominal SPC_WAFER_SIGMA.
# With the naive offset of 1 the draw happened to land in the bottom ~0.5% of the
# sampling distribution (sd 0.0060) and the overdispersion demo was invisible.
SPC_SEED_OFFSET = 24

EXTENDED_HISTORY_ROWS = [
    ("DONT", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-05"),
    ("DONT", "ETCH-M1", "ETCH-01", "CH-A", "2026-08-06"),
    ("DONT", "CMP-M1", "CMP-01", "CH-A", "2026-08-07"),
    ("HALF", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-06"),
    ("HALF", "ETCH-M1", "ETCH-02", "CH-B", "2026-08-07"),
    ("HALF", "CMP-M1", "CMP-01", "CH-A", "2026-08-08"),
    ("RETL", "LITHO-M1", "LITHO-02", "CH-A", "2026-08-07"),
    ("RETL", "ETCH-M1", "ETCH-01", "CH-A", "2026-08-08"),
    ("RETL", "CMP-M1", "CMP-01", "CH-A", "2026-08-09"),
]

HISTORY_ROWS = [
    # lot_id, step, tool, chamber, date  (EDGE alone runs ETCH-02/CH-B; SCRT alone runs CMP-02)
    ("BASE", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-01"),
    ("BASE", "ETCH-M1", "ETCH-01", "CH-A", "2026-08-02"),
    ("BASE", "CMP-M1", "CMP-01", "CH-A", "2026-08-03"),
    ("EDGE", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-02"),
    ("EDGE", "ETCH-M1", "ETCH-02", "CH-B", "2026-08-03"),
    ("EDGE", "CMP-M1", "CMP-01", "CH-A", "2026-08-04"),
    ("SCRT", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-03"),
    ("SCRT", "ETCH-M1", "ETCH-01", "CH-A", "2026-08-04"),
    ("SCRT", "CMP-M1", "CMP-02", "CH-A", "2026-08-05"),
    ("CNTR", "LITHO-M1", "LITHO-01", "CH-A", "2026-08-04"),
    ("CNTR", "ETCH-M1", "ETCH-01", "CH-A", "2026-08-05"),
    ("CNTR", "CMP-M1", "CMP-01", "CH-A", "2026-08-06"),
]


def wafer_coords(n: int = GRID_N):
    """(x, y, r_norm) for every die inside the circular wafer mask."""
    c = (n - 1) / 2.0
    out = []
    for x in range(n):
        for y in range(n):
            d = math.hypot(x - c, y - c)
            if d <= c + 1e-9:
                out.append((x, y, d / c))
    return out


def synth_wafer(rng: np.random.Generator, coords, signature: str | None):
    lam = D0_BASELINE * DIE_AREA_CM2
    p_bg = 1.0 - math.exp(-lam)
    c = (GRID_N - 1) / 2.0

    if signature == "scratch":
        theta = rng.uniform(0.0, math.pi)
        offset = rng.uniform(-0.35, 0.35) * c
        nx, ny = -math.sin(theta), math.cos(theta)      # unit normal to the scratch line
        px, py = c + offset * nx, c + offset * ny        # a point on the line

    rows = []
    for x, y, rn in coords:
        p_sig, sig_bin = 0.0, None
        if signature == "edge_ring" and rn > 0.82:
            p_sig, sig_bin = 0.45, (7, 71)
        elif signature == "center_cluster" and rn < 0.28:
            p_sig, sig_bin = 0.65, (6, 61)
        elif signature == "scratch":
            dist = abs((x - px) * nx + (y - py) * ny)
            if dist <= 0.8:
                p_sig, sig_bin = 0.90, (9, 91)
        elif signature == "donut" and 0.45 < rn < 0.72:
            p_sig, sig_bin = 0.35, (10, 101)
        elif signature == "half_moon" and x < c:
            p_sig, sig_bin = 0.30, (11, 111)
        elif signature == "reticle" and x % 5 == 2 and y % 5 == 3:
            p_sig, sig_bin = 0.90, (12, 121)

        fail_sig = rng.random() < p_sig
        fail_bg = rng.random() < p_bg
        if fail_sig:
            hb, sb = sig_bin
        elif fail_bg:
            hb, sb = BG_BINS[0][:2] if rng.random() < BG_BINS[0][2] else BG_BINS[1][:2]
        else:
            hb, sb = 1, 1
        rows.append((x, y, hb, sb, 1 if hb == 1 else 0))
    return rows


# ---------------------------------------------------------------- STDF v4 out
# Minimal little-endian STDF v4 writer (no third-party dependency). Emits the
# record subset the yield workflow actually consumes: FAR, MIR, WIR, PIR, PTR,
# PRR, WRR, HBR, SBR, MRR. See references/data-formats.md.

def _cn(s: str) -> bytes:
    """STDF Cn: one length byte then ASCII characters."""
    b = str(s).encode("ascii", "replace")[:255]
    return bytes([len(b)]) + b


def _rec(typ: int, sub: int, body: bytes) -> bytes:
    return struct.pack("<HBB", len(body), typ, sub) + body


def _ptr(test_num, site, result, txt, lo, hi, units) -> bytes:
    failed = not (lo <= result <= hi)
    test_flg = 0x80 if failed else 0x00      # bit 7 = test failed (bit 6 clear = bit 7 valid)
    body = struct.pack("<IBBBBf", test_num, 1, site, test_flg, 0, result)
    body += _cn(txt) + _cn("")               # TEST_TXT, ALARM_ID
    body += struct.pack("<Bbbbff", 0, 0, 0, 0, lo, hi)   # OPT_FLAG, *_SCAL, LO/HI_LIMIT
    body += _cn(units)
    return _rec(15, 10, body)


def write_stdf(path: Path, lot_id: str, wafers: dict, rng: np.random.Generator,
               start_t: int = 1786000000):
    """One lot per file, as real ATE writes it.

    wafers: {wafer_id: [(x, y, hard_bin, soft_bin, pass_flag), ...]}
    """
    out = bytearray()
    out += _rec(0, 10, struct.pack("<BB", 2, 4))                     # FAR: PC endian, v4
    mir = struct.pack("<IIB", start_t - 3600, start_t, 1)
    mir += b"P" + b" " + b" " + struct.pack("<H", 0) + b" "          # MODE/RTST/PROT/BURN/CMOD
    mir += _cn(lot_id) + _cn("DEMO-ASIC") + _cn("TESTER-01")
    mir += _cn("SIM-V93K") + _cn("SORT_PROBE") + _cn("1.0")
    out += _rec(1, 10, mir)

    hbin_cnt, sbin_cnt = {}, {}
    for wafer_id, rows in sorted(wafers.items()):
        wid = wafer_id
        out += _rec(2, 10, struct.pack("<BBI", 1, 1, start_t) + _cn(wid))
        good = 0
        for i, (x, y, hb, sb, pf) in enumerate(rows):
            site = 1 + (i % 4)
            out += _rec(5, 10, struct.pack("<BB", 1, site))          # PIR
            # two parametric tests, deliberately correlated with the bin result
            leak = float(rng.lognormal(-16.0 if pf else -13.5, 0.35))
            fmax = float(rng.normal(1.20 if pf else 1.05, 0.03)) * 1e9
            out += _ptr(1001, site, leak, "IDDQ_LEAK", 0.0, 1e-6, "A")
            out += _ptr(2001, site, fmax, "FMAX", 1.10e9, 2.0e9, "Hz")
            part_flg = 0x00 if pf else 0x08                          # bit 3 = part failed
            prr = struct.pack("<BBBHHHhhI", 1, site, part_flg, 2, hb, sb, x, y, 120)
            prr += _cn(f"{i + 1}") + _cn("") + bytes([0])
            out += _rec(5, 20, prr)                                  # PRR
            hbin_cnt[hb] = hbin_cnt.get(hb, 0) + 1
            sbin_cnt[sb] = sbin_cnt.get(sb, 0) + 1
            good += pf
        wrr = struct.pack("<BBIIIIII", 1, 1, start_t + 900, len(rows), 0, 0, good, 0)
        out += _rec(2, 20, wrr + _cn(wid))                           # WRR

    for b, c in sorted(hbin_cnt.items()):
        out += _rec(1, 40, struct.pack("<BBHI", 255, 255, b, c)
                    + (b"P" if b == 1 else b"F") + _cn(f"HBIN_{b}"))
    for b, c in sorted(sbin_cnt.items()):
        out += _rec(1, 50, struct.pack("<BBHI", 255, 255, b, c)
                    + (b"P" if b == 1 else b"F") + _cn(f"SBIN_{b}"))
    out += _rec(1, 20, struct.pack("<I", start_t + 7200) + b" " + _cn("") + _cn(""))
    path.write_bytes(bytes(out))


def synth_sort_history(seed: int, n_die: int):
    """36-wafer yield time series for SPC. Returns (csv_lines, notes)."""
    rng = np.random.default_rng(seed + SPC_SEED_OFFSET)
    day = 0
    lines = ["lot_id,wafer_id,date,dies,passed"]
    for lot_id, n_wafers, p_true in SPC_LOTS:
        for w in range(1, n_wafers + 1):
            wafer_id = f"W{w}"
            if (lot_id, wafer_id) == SPC_EXCURSION[:2]:
                p = SPC_EXCURSION[2]
            else:
                p = float(np.clip(rng.normal(p_true, SPC_WAFER_SIGMA), 0.01, 0.999))
            passed = int(rng.binomial(n_die, p))
            date = f"2026-06-{1 + day // 3:02d}" if day // 3 < 30 else "2026-06-30"
            lines.append(f"{lot_id},{wafer_id},{date},{n_die},{passed}")
            day += 1
    notes = [
        f"baseline L01-L07 p={SPC_LOTS[0][2]}, wafer-to-wafer sigma={SPC_WAFER_SIGMA}"
        " (deliberately overdispersed vs binomial)",
        f"gross excursion seeded at {SPC_EXCURSION[0]}/{SPC_EXCURSION[1]} p={SPC_EXCURSION[2]}",
        f"real step shift L08-L11 p={SPC_LOTS[7][2]} ({100*(SPC_LOTS[7][2]-SPC_LOTS[0][2]):+.1f} pp)",
        f"suspicious up-tick L12 p={SPC_LOTS[11][2]} ({100*(SPC_LOTS[11][2]-SPC_LOTS[0][2]):+.1f} pp)",
    ]
    return lines, notes


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default=".", help="output directory (default: current dir)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    ap.add_argument("--extended", action="store_true",
                    help="append DONT/HALF/RETL signature lots (donut, half-moon, reticle)")
    ap.add_argument("--no-sort-history", action="store_true",
                    help="skip writing sort_history.csv (the SPC time series)")
    ap.add_argument("--stdf", action="store_true",
                    help="also write sample.stdf (STDF v4) for stdf_ingest.py. Off by "
                         "default: it is ~10x the CSV and the repo has a size budget.")
    ap.add_argument("--stdf-lots", default="BASE",
                    help="comma-separated lots to put in sample.stdf, or ALL (default BASE)")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    coords = wafer_coords()
    rng = np.random.default_rng(args.seed)
    scenarios = SCENARIOS + (EXTENDED if args.extended else ())
    history_rows = HISTORY_ROWS + (EXTENDED_HISTORY_ROWS if args.extended else [])

    lines = ["lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag"]
    summary, by_wafer = [], {}
    for lot_id, n_wafers, signature in scenarios:
        for w in range(1, n_wafers + 1):
            wafer_id = f"W{w}"
            rows = synth_wafer(rng, coords, signature)
            by_wafer[(lot_id, wafer_id)] = rows
            n_pass = sum(r[4] for r in rows)
            summary.append((lot_id, wafer_id, signature or "healthy",
                            len(rows), n_pass, 100.0 * n_pass / len(rows)))
            for x, y, hb, sb, pf in rows:
                lines.append(f"{lot_id},{wafer_id},{x},{y},{hb},{sb},{pf}")

    die_path = outdir / "die_results.csv"
    die_path.write_text("\n".join(lines) + "\n")

    hist_path = outdir / "history.csv"
    hist_path.write_text(
        "lot_id,step,tool,chamber,date\n"
        + "\n".join(",".join(r) for r in history_rows) + "\n"
    )
    written = [die_path, hist_path]

    if not args.no_sort_history:
        spc_lines, spc_notes = synth_sort_history(args.seed, len(coords))
        spc_path = outdir / "sort_history.csv"
        spc_path.write_text("\n".join(spc_lines) + "\n")
        written.append(spc_path)

    if args.stdf:
        have = {k[0] for k in by_wafer}
        want = have if args.stdf_lots.upper() == "ALL" else {
            s.strip() for s in args.stdf_lots.split(",") if s.strip()}
        if not (want & have):
            sys.exit(f"ERROR: --stdf-lots {sorted(want)} matched no generated lot "
                     f"(have {sorted(have)})")
        srng = np.random.default_rng(args.seed + 100)
        for lot_id in sorted(want & have):
            wafers = {w: r for (l, w), r in by_wafer.items() if l == lot_id}
            stdf_path = outdir / f"sample_{lot_id}.stdf"
            write_stdf(stdf_path, lot_id, wafers, srng)
            written.append(stdf_path)

    print(f"dies per wafer: {len(coords)} (grid {GRID_N}x{GRID_N}, circular mask)")
    print(f"seeded background: D0={D0_BASELINE}/cm2, A={DIE_AREA_CM2}cm2 "
          f"-> p_bg={1 - math.exp(-D0_BASELINE * DIE_AREA_CM2):.4f}")
    print(f"{'lot':6}{'wafer':7}{'scenario':16}{'dies':7}{'pass':7}{'yield%':7}")
    for lot, waf, sig, dies, npass, y in summary:
        print(f"{lot:6}{waf:7}{sig:16}{dies:<7}{npass:<7}{y:<7.2f}")
    if not args.no_sort_history:
        print("sort_history.csv seeded features:")
        for n in spc_notes:
            print(f"  - {n}")
    for p in written:
        print(f"wrote {p} ({p.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
