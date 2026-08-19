# Data formats

Read this when asking the user for data, when a file will not load, or when deciding whether
what you were handed can answer the question.

## The canonical CSVs

Every script in this skill reads plain CSV. If a user has anything at all, it can be reshaped
into these three files, and doing so is usually faster than debugging their tooling.

### `die_results.csv` — one row per probed die

```
lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag
BASE,W1,1,14,1,1,1
EDGE,W1,38,20,7,71,0
```

| Column | Type | Meaning | STDF source |
|---|---|---|---|
| `lot_id` | string | Lot identifier | `MIR.LOT_ID` |
| `wafer_id` | string | Unique within the lot | `WIR.WAFER_ID` |
| `die_x` | int | Column index on the wafer map | `PRR.X_COORD` |
| `die_y` | int | Row index on the wafer map | `PRR.Y_COORD` |
| `hard_bin` | int | Hard bin; 1 = pass by near-universal convention | `PRR.HARD_BIN` |
| `soft_bin` | int | Soft bin (finer failure category) | `PRR.SOFT_BIN` |
| `pass_flag` | int | 1 = passing die, 0 = failing die | `PRR.PART_FLG` bit 3 inverted |

Requirements the scripts depend on:
- **One row per die, no aggregation.** A pre-summarised file cannot produce a wafer map.
- **Failing dies must be present.** A file containing only passing dies is unusable; this
  happens more often than you would think when someone exports "the good die map".
- **Original bin numbers, unremapped.** Remapping destroys the bin pareto.
- **Consistent coordinate origin** across wafers in a lot. The scripts derive the wafer
  center from the coordinate extents, so a shifted origin on one wafer distorts its zones.
- Coordinates are die indices, not microns. Negative coordinates are legal in STDF and
  handled, but mixing conventions within a file is not.

Optional columns are ignored by the loaders, so extra context (site number, test time, wafer
scribe id) can be carried along safely — and site number in particular is worth carrying,
because "check fail rate by site" is the first move on a quadrant signature.

### `history.csv` — lot process history, for commonality

```
lot_id,step,tool,chamber,date
EDGE,ETCH-M1,ETCH-02,CH-B,2026-08-03
```

`chamber` may be blank. `date` is not currently used arithmetically by `commonality.py` but
should be present: time confounding is the main failure mode of commonality analysis, and
you cannot check it without timestamps. Add slot/port columns if you have them — the finer
the granularity, the sharper a real effect gets.

### `sort_history.csv` — yield time series, for SPC

```
lot_id,wafer_id,date,dies,passed
L01,W1,2026-06-01,1184,1074
```

`spc_yield.py` also accepts `yield_pct` or `yield` in place of `passed` (given `dies`), and
can build subgroups directly from a `die_results.csv` with `--die-results`. Order matters:
rows are treated as a time-ordered sequence in file order.

## STDF v4

STDF (Standard Test Data Format) is the ATE industry's datalog format: a stream of
binary records, each with a 4-byte header (`REC_LEN` u2, `REC_TYP` u1, `REC_SUB` u1)
followed by fields. Byte order is declared by the first record. The specification is a SEMI
standard; this file describes only what the yield workflow needs, in its own words.

`stdf_ingest.py` reads it via an optional third-party parser (pystdf or Semi-ATE STDF, both
verified at build time) and degrades to CSV-export instructions when neither is installed.

### The record subset that matters

| Record | (typ, sub) | What you take from it |
|---|---|---|
| **FAR** | 0,10 | File Attributes: `CPU_TYPE` (byte order) and `STDF_VER`. First record in the file; its absence means this is not STDF. |
| **MIR** | 1,10 | Master Information: `LOT_ID`, `PART_TYP`, `JOB_NAM` + `JOB_REV` (test program and revision — the field that settles most "yield shift" arguments), `TSTR_TYP`, `NODE_NAM`, `TST_TEMP`, `SBLOT_ID`, `PROC_ID`, `START_T`. |
| **WIR** | 2,10 | Wafer Information: opens a wafer. `WAFER_ID`, `HEAD_NUM`, `START_T`. |
| **PIR** | 5,10 | Part Information: opens a part. `HEAD_NUM`, `SITE_NUM`. Its role is to bracket the test records that follow. |
| **PTR** | 15,10 | Parametric Test Result: `TEST_NUM`, `TEST_TXT`, `RESULT`, `TEST_FLG` (bit 7 = failed), `LO_LIMIT`/`HI_LIMIT`, `UNITS`, `RES_SCAL`. The parametric-correlation data. |
| **PRR** | 5,20 | Part Results: closes a part and carries the die record — `X_COORD`, `Y_COORD`, `HARD_BIN`, `SOFT_BIN`, `PART_FLG`, `NUM_TEST`, `TEST_T`, `SITE_NUM`. This is where the wafer map comes from. |
| **WRR** | 2,20 | Wafer Results: closes a wafer with `PART_CNT`, `GOOD_CNT`, `RTST_CNT`, `ABRT_CNT`. **The reconciliation key** — compare against your own PRR tally. |
| **HBR** | 1,40 | Hard Bin Record: `HBIN_NUM`, `HBIN_CNT`, `HBIN_PF`, `HBIN_NAM`. Summary counts, written per head/site and usually also with `HEAD_NUM = 255` for the all-heads total. |
| **SBR** | 1,50 | Soft Bin Record: same shape with `SBIN_*`. |
| **MRR** | 1,20 | Master Results: closes the file. **A missing MRR means the datalog was truncated or the job aborted.** |

Other records exist (ATR, SDR, PCR, TSR, MPR, FTR, GDR, DTR, PMR/PGR/PLR, BPS/EPS) and are
skipped here. `PCR` (part counts per site) and `TSR` (per-test summaries) are worth reaching
for if you need site-level or test-level rollups without re-tallying every PRR.

### Field conventions that cause bugs

- **`PART_FLG` bit 3 = part failed.** Bit 4 = bin data invalid. Bits 0–2 concern retest and
  supersession. Do not assume "hard bin != 1" and `PART_FLG` agree — when they disagree,
  something in the program or the parser is wrong, and every downstream yield number is
  suspect. `stdf_ingest.py` counts disagreements as an explicit integrity check.
- **`TEST_FLG` bit 7 = test failed**, valid only when bit 6 is clear.
- **Coordinates are signed 16-bit** and may be negative depending on the probe map origin.
- **`Cn` strings are length-prefixed** (one length byte), so an empty string is one zero
  byte, not nothing. `Bn` binary fields work the same way.
- **Records may be truncated after their required fields** — trailing optional fields are
  simply absent, and a parser must tolerate that. Do not treat a short record as corrupt.
- **Scaling.** `RES_SCAL`/`LLM_SCAL`/`HLM_SCAL` are power-of-ten exponents that some testers
  use and others leave at zero. If parametric values look off by 1e3 or 1e6, this is why.
- **Endianness** is per file, from `FAR.CPU_TYPE`. Both supported parsers handle it.
- **Retest.** A retested part produces a second PIR/PRR pair for the same coordinates. Files
  may contain first-pass results, final results, or both. Repeated `(wafer, x, y)`
  coordinates are the tell; decide which pass you mean before computing anything.

### Integrity checks worth running every time

`stdf_ingest.py` runs all of these and prints a pass/fail report:

1. FAR present and `STDF_VER == 4`.
2. MIR present with a lot id, and `JOB_NAM`/`JOB_REV` recorded for later comparison.
3. MRR present — the file closed cleanly.
4. Every wafer has a WRR.
5. PRR count == `WRR.PART_CNT`, per wafer.
6. PRR passes == `WRR.GOOD_CNT`, per wafer.
7. PRR-derived hard-bin tallies == HBR summary counts.
8. `PART_FLG` fail bit agrees with the "hard bin 1 == pass" convention.
9. No `PART_FLG` bit 4 (bin data invalid) set.
10. No repeated `(wafer, x, y)` — i.e. no unresolved retest.
11. No PRR outside a WIR/WRR pair.

Any failure means the datalog and its own summary records disagree. Resolve it before
quoting a yield number; a reconciliation error is not a rounding issue.

### Generating a sample STDF

No `.stdf` ships in this repo (size budget). Generate one:

```
python gen_sample_data.py --out /tmp/stdf --seed 42 --stdf --stdf-lots BASE
python stdf_ingest.py --input /tmp/stdf/sample_BASE.stdf --out /tmp/stdf/from_stdf.csv
```

The writer in `gen_sample_data.py` is a small pure-`struct` STDF v4 emitter covering the
record subset above; it round-trips exactly through both supported parsers.

## KLARF (concept only)

KLARF is KLA's defect-result file format, produced by inspection tools (bright-field,
dark-field, macro). It answers a different question from STDF: **where are the physical
defects**, at a given layer, rather than **which dies failed at test**.

Structure, in outline: a text file with a header block of key/value records (inspection
station, setup, wafer id, lot id, orientation, die pitch and origin, sample plan), followed
by per-defect records — defect id, wafer/die coordinates, coordinates within the die, size
estimate, area, classification code, and optionally an image reference. Multiple inspections
of the same wafer can appear as separate blocks.

Why it matters here:
- **It timestamps a defect to a layer.** A scratch visible in a KLARF after CMP but not
  before localizes the event to that step. Test data alone can never do this.
- **It feeds critical-area / kill-ratio analysis** — the bridge from raw particle counts to
  an effective D0. Not every defect kills a die; the kill ratio by defect size and layer is
  what converts inspection data into a yield prediction.
- **Defect-to-fail overlay** is the highest-value analysis in the whole toolbox: match
  inspection coordinates to failing die coordinates and you get a direct, physical link
  between a particle at a layer and a bin at test.

Practical cautions: KLARF revisions differ in field sets, coordinate origins and units vary
between tools and recipes, and the die grid in a KLARF must be aligned to the probe map's
grid before any overlay is meaningful — an off-by-one in die origin silently destroys the
correlation. Sampled inspection (a subset of dies or a swath plan) means absence of a defect
record is not evidence of absence.

**Status in this skill: no KLARF parser is implemented.** If you need defect-to-fail overlay,
ask the user to export defect coordinates as a CSV with `lot_id,wafer_id,die_x,die_y,
defect_id,size_um,class_code,layer` and join it to `die_results.csv` on the first four
columns. TODO for a future revision.

## What to ask for when the user has nothing

Ask in this order; stop as soon as you can answer the question that was actually asked.

1. **The wafer maps** — `die_results.csv` above, or the STDF, for the lots in question and
   for a comparable good lot. Without a comparison lot you have no baseline.
2. **Die area in cm²**, and the edge exclusion the fab uses. Required for any D0 statement.
3. **Bin definitions** — what bins 2, 5, 7, 9 actually mean on this program. A bin pareto
   without bin names is a histogram of integers.
4. **Test program name and revision**, and whether it changed in the period of interest.
5. **Lot process history** — `history.csv` above.
6. **Yield history** — `sort_history.csv` above, ideally 25+ wafers of a period believed to
   be in control, for SPC limits.
7. **Product maturity** — first silicon, ramp, or mature — and the current yield entitlement
   or target. This decides what "bad" means.

Never fill any of these in with a plausible-looking number. If item 2 is missing, report
yields and skip D0 entirely; if item 3 is missing, report bin numbers and say the names are
unknown.
