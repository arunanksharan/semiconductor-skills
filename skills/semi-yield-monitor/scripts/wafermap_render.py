#!/usr/bin/env python3
"""Render wafer maps from die_results.csv as ASCII (stdout) and/or PNG.

ASCII: '.' = pass, 'X' = fail ('#' with --by-bin shows the hard bin's last
digit for fails). PNG: green = pass, red = fail (--by-bin colors by hard bin).
Also prints radial-zone fail rates (center / mid / edge) per wafer.

Usage examples:
  python wafermap_render.py --input die_results.csv --lot SCRT --wafer W1
  python wafermap_render.py --input die_results.csv --lot EDGE --png-dir maps/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REQUIRED = ["lot_id", "wafer_id", "die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"]


def load(path: str, lot: str | None, wafer: str | None) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"lot_id": str, "wafer_id": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: {path} is missing columns {missing}; expected {','.join(REQUIRED)}")
    for c in ("die_x", "die_y", "hard_bin", "soft_bin", "pass_flag"):
        df[c] = pd.to_numeric(df[c], errors="raise").astype(int)
    if lot:
        df = df[df.lot_id == lot]
        if df.empty:
            sys.exit(f"ERROR: lot '{lot}' not found")
    if wafer:
        df = df[df.wafer_id == wafer]
        if df.empty:
            sys.exit(f"ERROR: wafer '{wafer}' not found for that selection")
    return df


def zone_rates(d: pd.DataFrame) -> str:
    x, y = d.die_x.to_numpy(), d.die_y.to_numpy()
    cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
    rn = np.hypot(x - cx, y - cy)
    rn = rn / max(rn.max(), 1e-9)
    fail = d.pass_flag.to_numpy() == 0
    parts = []
    for name, m in (("center", rn <= 0.35), ("mid", (rn > 0.35) & (rn <= 0.8)), ("edge", rn > 0.8)):
        parts.append(f"{name} {fail[m].mean():.3f}" if m.sum() else f"{name} n/a")
    return " | ".join(parts)


def ascii_map(d: pd.DataFrame, by_bin: bool) -> str:
    W, H = d.die_x.max() + 1, d.die_y.max() + 1
    grid = [[" "] * W for _ in range(H)]
    for r in d.itertuples():
        if r.pass_flag == 1:
            ch = "."
        else:
            ch = str(r.hard_bin % 10) if by_bin else "X"
        grid[r.die_y][r.die_x] = ch
    return "\n".join("".join(row) for row in reversed(grid))


def png_map(d: pd.DataFrame, by_bin: bool, title: str, out: Path) -> None:
    W, H = d.die_x.max() + 1, d.die_y.max() + 1
    img = np.full((H, W), np.nan)
    for r in d.itertuples():
        img[r.die_y, r.die_x] = (r.hard_bin if by_bin else (0 if r.pass_flag else 1))
    fig, ax = plt.subplots(figsize=(5, 5))
    if by_bin:
        im = ax.imshow(img, origin="lower", cmap="tab10", interpolation="nearest")
        fig.colorbar(im, ax=ax, label="hard_bin", shrink=0.8)
    else:
        ax.imshow(img, origin="lower", cmap=matplotlib.colors.ListedColormap(["#2f9e44", "#e03131"]),
                  vmin=0, vmax=1, interpolation="nearest")
    ax.set_title(title)
    ax.set_xlabel("die_x")
    ax.set_ylabel("die_y")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", required=True, help="die_results.csv (canonical schema)")
    ap.add_argument("--lot", help="lot_id (default: all lots)")
    ap.add_argument("--wafer", help="wafer_id (default: all wafers in selection)")
    ap.add_argument("--by-bin", action="store_true", help="color/label by hard bin")
    ap.add_argument("--no-ascii", action="store_true", help="skip ASCII output")
    ap.add_argument("--png-dir", help="write one PNG per wafer into this directory")
    args = ap.parse_args()

    df = load(args.input, args.lot, args.wafer)
    if args.png_dir:
        Path(args.png_dir).mkdir(parents=True, exist_ok=True)

    for (lot_id, wafer_id), d in df.groupby(["lot_id", "wafer_id"], sort=True):
        y = 100 * d.pass_flag.mean()
        print(f"lot {lot_id} wafer {wafer_id}: yield {y:.2f}%  zones: {zone_rates(d)}")
        if not args.no_ascii:
            print(ascii_map(d, args.by_bin))
            print()
        if args.png_dir:
            out = Path(args.png_dir) / f"{lot_id}_{wafer_id}.png"
            png_map(d, args.by_bin, f"{lot_id} {wafer_id} — {y:.1f}%", out)
            print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
