---
name: semi-yield-monitor
description: Analyzes semiconductor wafer-sort yield from die-level test data and turns it into a ranked shortlist of suspect process steps. Use when the user mentions yield analysis, low-yield lot triage, a wafer map or wafer signature, bin pareto, hard or soft bins, STDF or KLARF datalogs, defect density or D0, yield models (Poisson, Murphy, Seeds, negative binomial), commonality analysis across lots/tools/chambers, SPC on yield, p-chart or Western Electric rules, parametric correlation, edge ring, scratch, center cluster, donut, half-moon, quadrant or repeating reticle patterns, or a yield up-tick that needs verifying before anyone celebrates. Runs a gated triage workflow — data integrity, yield versus baseline, bin pareto, wafer-to-wafer spread, spatial signature, lot/tool/time commonality, parametric correlation, suspect-step shortlist. Interviews the user when no data is supplied and never fabricates numbers.
license: MIT
metadata:
  version: 0.1.0
  author: Kuzushi Labs
---

# semi-yield-monitor — wafer-sort yield triage

Turn die-level test data into a defensible shortlist of suspect process steps. The model
chooses the analysis and applies the gates; the scripts in `scripts/` compute every number.

**Division of labor with sibling skills:** electrical root cause of an individual failing
unit → `semi-failure-analysis`. Package and assembly defects → `semi-packaging-qual`. Fab
tool excursions and DOE → `semi-fab-process`. This skill owns wafer sort: die maps, bins,
defect density, and the path from a yield number to a suspect step.

## Operating rules (binding)

1. **Never state a number the model computed in its head.** Every yield, bin percentage, z,
   D0, or control limit in your output comes from a script run or from a file the user
   supplied. If you did not run it, do not report it.
2. **Never fabricate data.** With no data files, run Workflow 0 (interview) and produce a
   plan. Refusing to guess is the correct answer, not a failure.
3. **Gates are hard.** Do not advance past a gate that has not cleared. Say which gate is
   blocking and what evidence clears it.
4. **Association is not causation.** Commonality analysis and spatial signatures produce
   suspects. Say "consistent with" for inference and "observed" for measurement, and never
   name a root cause without a physical mechanism plus corroborating tool data.
5. **Report intervals, not just point estimates.** A yield or D0 without its confidence
   interval invites over-reading of noise, especially on a single wafer.
6. **A yield increase is an excursion too.** Route every up-tick through Branch C before
   anyone reports good news.

## Setup

```bash
pip install -r requirements.txt           # numpy, pandas, matplotlib, scipy
SKILL=skills/semi-yield-monitor           # adjust to wherever this skill lives
DATA=sample-data/semi-yield-monitor       # the shipped demo data

# regenerate / extend the demo data (deterministic, seed 42)
python "$SKILL/scripts/gen_sample_data.py" --out "$DATA" --seed 42
python "$SKILL/scripts/gen_sample_data.py" --out /tmp/ext  --seed 42 --extended  # +donut, half-moon, reticle
python "$SKILL/scripts/gen_sample_data.py" --out /tmp/stdf --seed 42 --stdf --stdf-lots BASE
```

## Routing

| The user has / asks | Go to |
|---|---|
| No data files | Workflow 0 — interview |
| An STDF datalog | Workflow 1, step 1 uses `stdf_ingest.py` |
| A `die_results.csv` and "why is this lot low" | Workflow 1 |
| One wafer only | Workflow 1 + Branch A |
| A first-silicon or new-product lot | Workflow 1 + Branch B |
| "Yield went **up**" | Branch C **first**, then Workflow 1 |
| A yield step change over time | Workflow 2 (SPC) |
| "Which tool is causing this" with several lots | Workflow 1 steps 1–4, then step 6 |
| A wafer map image but no die data | Workflow 0 — ask for the die-level export |

## Workflow 0 — No data: interview, then plan

Run this whenever die-level data is missing. Produce two things and nothing else: the list of
what you need, and the analysis plan you will run once you have it.

Ask for these, in order, and stop as soon as you can answer the question actually asked:

| # | Ask for | Why it matters | Min |
|---|---|---|---|
| 1 | Die-level results for the suspect lots — `lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag` (or the STDF) | Everything downstream needs one row per die | ● |
| 2 | The same for a comparable **good** lot, or the recent baseline yield | Without a baseline there is no "low" | ● |
| 3 | Bin definitions: what bins 2, 5, 7, 9 mean on this program | A pareto of unnamed integers is not a pareto | ● |
| 4 | Test program name + revision, and whether either changed | Rules out the most common false excursion | ● |
| 5 | Die area in cm², and the fab's edge exclusion | Required before any D0 statement | |
| 6 | Lot process history: `lot_id,step,tool,chamber,date` | Commonality analysis | |
| 7 | Yield history, 25+ wafers believed in control | SPC limits | |
| 8 | Product maturity (first silicon / ramp / mature) and the yield entitlement | Decides what "bad" means | |
| 9 | In-line defect data (KLARF export) and metrology for the suspect layers | Timestamps a defect to a layer | |

**If item 1 is missing, stop.** Say so plainly: *"I can't produce yield numbers without
die-level data — here is exactly what to export and why."* Point at the export recipe in
`references/data-formats.md`. Do not estimate, do not illustrate with example numbers, and
do not run the workflow on invented data.

If the user has a *picture* of a wafer map, you may describe the geometry qualitatively and
name candidate signatures from the table below — but label it as a visual read and ask for
the die-level export before any percentage is quoted.

## Workflow 1 — Yield triage

### Step 1 — Confirm data integrity (GATE)

Nothing downstream is meaningful if the file disagrees with itself.

For STDF:
```bash
python "$SKILL/scripts/stdf_ingest.py" --check
python "$SKILL/scripts/stdf_ingest.py" --input lot.stdf --out die_results.csv --ptr-out params.csv
```
It prints an 11-check integrity report: FAR/MIR present, MRR present (file closed cleanly),
every wafer has a WRR, PRR count vs `WRR.PART_CNT`, PRR passes vs `WRR.GOOD_CNT`, PRR bin
tallies vs HBR, `PART_FLG` vs the "hard bin 1 = pass" convention, invalid-bin flags,
repeated `(wafer, x, y)` (unresolved retest), and orphan PRRs. If no STDF library is
installed it prints install hints plus the CSV schema to export instead, and exits 3 —
it never crashes.

For CSV, confirm by inspection and by the first summary run:
```bash
python "$SKILL/scripts/yield_summary.py" --input "$DATA/die_results.csv" --soft --top 10
```

**GATE — do not proceed until all of these hold:**
- Every integrity check passes, or each failure has a written explanation.
- Die counts per wafer are consistent and match the expected gross die per wafer.
- Failing dies are present in the file (not a pass-only export).
- Retest policy is known: first-pass or final result, not a mixture.
- Test program name and revision are recorded for every lot in the comparison.

If a check fails, fix the data. A reconciliation error is not a rounding issue.

### Step 2 — Overall yield versus baseline (GATE)

```bash
python "$SKILL/scripts/yield_summary.py" --input "$DATA/die_results.csv"
python "$SKILL/scripts/yield_models.py" --input "$DATA/die_results.csv" --die-area 0.25
```
`yield_models.py` reports the yield with an exact 95% interval per lot.

**GATE — is there actually an excursion?** Compare the suspect lot's interval against the
baseline. If the intervals overlap substantially, say so and stop escalating: you have
normal variation, and the correct output is "no excursion detected, here is the interval".
Chasing an in-family lot burns the credibility you need for the real one.

If the movement is **upward**, go to Branch C now.

### Step 3 — Hard and soft bin pareto

```bash
python "$SKILL/scripts/yield_summary.py" --input "$DATA/die_results.csv" --lot EDGE --soft --top 10
```

Read it this way:
- **Which bin carries the loss?** One dominant bin means one mechanism. A flat pareto means
  distributed defectivity or a mixture.
- **Compare the pareto shape to the good lot, not just the totals.** A real excursion grows
  one bin. A test-program or bin-map change makes a bin appear or vanish entirely — Branch D.
- **Go to soft bins when the hard bin is generic.** Hard bin 5 "functional fail" tells you
  nothing; its soft bins tell you which test.
- **Note the bins you will call systematic.** You need them in step 8 for the D0 refit.

### Step 4 — Wafer-to-wafer spread

`yield_summary.py` prints per-wafer yield within each lot. Classify the spread:

| Pattern | Reading | Next move |
|---|---|---|
| All wafers equally low | Lot-level condition: material, a full-lot process step, or the test program | Steps 5–6, weight commonality heavily |
| One or two wafers low | An event: a single wafer mishandled, one slot, one chuck | Step 5 per wafer; check slot/position |
| Alternating or slot-patterned | Two-chamber tool, double-sided tooling, alternating handler path | Step 6 at chamber/slot granularity |
| Spread wider than baseline but mean unchanged | Loss of control, not a mean shift | Workflow 2 (SPC) on wafer-level data |

### Step 5 — Spatial signature, per wafer and pooled

```bash
python "$SKILL/scripts/spatial_signature.py" --input "$DATA/die_results.csv" --lot EDGE
python "$SKILL/scripts/spatial_signature.py" --input "$DATA/die_results.csv" --lot SCRT --wafer W1
python "$SKILL/scripts/wafermap_render.py"   --input "$DATA/die_results.csv" --lot SCRT --wafer W1 --png-dir maps/
python "$SKILL/scripts/wafermap_render.py"   --input "$DATA/die_results.csv" --lot CNTR --by-bin --no-ascii --png-dir maps/
```

`spatial_signature.py` detects scratches first (connected components + robust line fit),
masks scratch dies, then runs radial, angular, and reticle-periodicity tests on the residual
map, ranking candidates by z. It reports `none` when nothing clears `--min-z` (default 3.0)
and `--min-lift` (default 1.5), and prints the zone rates so the absence is auditable.

Rules for reading it:
- **Rank, never collapse.** Report every candidate with its z and lift. Two candidates
  clearing threshold means a mixed signature — Branch F.
- **Split the map by bin** when a signature is ambiguous: `--by-bin` on the renderer, and
  re-run the classifier on a bin-filtered file. Different mechanisms land in different bins.
- **`none` on a high-yielding wafer is weak evidence.** With few failures no test has power.
  Say "no signature detected (N failures — low power)", not "the wafer is clean".
- **Screening many healthy wafers? Raise `--min-z`.** Measured on 60 healthy wafers, the
  scratch detector produces a low-z false positive on ~3% of them at the default 3.0
  (chance alignment of random fails); `--min-z 4.5` halves that with no loss on any true
  signature. A z below ~5 on a scratch call deserves a look at the map before you act.
- **Confirm the shot grid before believing `reticle`.** A detected period that does not
  match the real reticle layout is a coincidence or the probe touchdown grid — Branch E.

Read `references/wafer-map-signatures.md` for the full physics, discriminating evidence, and
the confusions each signature invites.

### Step 6 — Lot · tool · time commonality

```bash
python "$SKILL/scripts/commonality.py" --history "$DATA/history.csv" \
    --die-results "$DATA/die_results.csv" --min-delta 2.0
```

**Set `--min-delta` before you look at the output.** Lowering it afterwards is how people
talk themselves into a tool change.

Then apply these checks to whatever it ranks — every one of them can kill a suspect:
- **Lot count.** Single-lot groups are tagged `HYPOTHESIS ONLY`: with one lot, "tool X is
  bad" and "lot Y is bad" are the same statement.
- **Time confounding.** Are the suspect group's lots contiguous in time? Then you may have a
  date effect wearing a tool costume. Plot yield against time before believing any tool.
- **Routing correlation.** Compare the lot *lists*, not just the deltas. Identical lot lists
  at two steps cannot be separated by this data at all.
- **A tool that ran every lot explains nothing**, even with a low group mean.
- **Does the physics match?** A suspect etch chamber must produce a map consistent with an
  etch mechanism. If step 5 says `reticle` and step 6 says `etch chamber`, one is wrong.

Read `references/commonality-analysis.md` for the confounders (queue time, rework,
survivorship, chamber aliasing) and the statistics of ranking.

### Step 7 — Parametric correlation

Only meaningful with parametric data (STDF PTR records → `--ptr-out params.csv`).

- Correlate each parametric test's distribution against pass/fail and against die position.
  A parameter whose spatial profile matches the failure signature identifies the mechanism.
- **Separate marginal from catastrophic.** Dies missing a limit by a hair are a
  process-centering problem and respond to recentering; dies at rail are defects. They have
  different owners and different fixes.
- Compare limit distances against the good lot. A distribution that shifted but stayed inside
  limits is an early warning; a distribution unchanged with more fails means the limits
  moved — Branch D.
- If there is no parametric data, say so and skip. Do not infer parametric behaviour from
  bin counts.

### Step 8 — Suspect-step shortlist

Now refit the random defect density with the systematic population removed, so the residual
tells you whether there is a defectivity problem *underneath* the signature:

```bash
python "$SKILL/scripts/yield_models.py" --input "$DATA/die_results.csv" --die-area 0.25 \
    --exclude-bins 6,7,9 --edge-exclude 0.90
```

Assemble the shortlist. Each entry needs all five columns — an entry missing evidence is a
guess and must be labelled one:

| Suspect step/tool | Mechanism | Evidence for | Evidence against | Discriminating test |
|---|---|---|---|---|

Order by: signature-implicated steps first, then commonality suspects with 2+ lots, then
single-lot hypotheses. Cap it at three to five entries — a shortlist of ten is a way of
avoiding a decision.

### Step 9 — Recommended next actions

Produce four separate lists. Do not blur them together:

1. **Free checks, do now.** Test program/revision diff, bin-map diff, fail rate by
   `SITE_NUM`, retest rate, in-line metrology for the suspect layers, tool change/PM records
   around the dates. All of these are data you already have or can pull in an hour.
2. **Cheap experiments.** Split lot across the suspect tool and a reference tool in the same
   time window; notch-rotation split for a directional signature; move a multi-zone setpoint
   and see whether a donut radius follows; retest a sample with a fresh probe card.
3. **Containment**, separated from root cause. State what material is at risk, how far back,
   and what the hold criterion is. **A hold requires**: a confirmed signal on a chart with a
   clean baseline, a ruled-out metrology/test explanation, a quantified material-at-risk, and
   a containment plan that does not perturb the line more than the excursion does.
4. **What would change the conclusion.** Name the single observation that would most cheaply
   falsify your top suspect. If you cannot name one, the analysis is not finished.

Where the evidence does not support a hold, **write down "no hold" and why** — so the next
person does not re-litigate it.

## Workflow 2 — SPC: is this shift real?

```bash
# pass 1: find assignable causes
python "$SKILL/scripts/spc_yield.py" --input "$DATA/sort_history.csv" --baseline-n 21
# pass 2: exclude them from the LIMIT estimate (still plotted, still tested)
python "$SKILL/scripts/spc_yield.py" --input "$DATA/sort_history.csv" --baseline-n 21 \
    --exclude-subgroups L03/W2 --png spc.png
# lot-level view: sigma shrinks by ~sqrt(wafers per lot), small shifts become visible
python "$SKILL/scripts/spc_yield.py" --input "$DATA/sort_history.csv" --by lot \
    --baseline-lots L01,L02,L03,L04,L05,L06,L07
# no separate history file? build subgroups straight from the die data
python "$SKILL/scripts/spc_yield.py" --die-results "$DATA/die_results.csv" --chart imr
```

Run the two passes in that order, every time. A gross excursion left inside the baseline
inflates both the centerline and sigma, and the inflated limits then hide the next, smaller
shift. On the shipped sample data the two-pass discipline moves the centerline from 89.64%
to 90.21%, drops the overdispersion factor from 2.59 to 1.54, and converts an undetected
-2.7 pp shift into rule-2/3/4 signals.

`--chart auto` measures **sigma_z**, the dispersion of the standardized deviates, and picks a
binomial p-chart when sigma_z ≤ 1.2 or a Laney p'-chart when it is larger. Real sort yield is
almost always overdispersed — dies on a wafer are not independent trials — so expect p'. EWMA
(λ 0.2, L 2.7) runs alongside and is reported separately, because Shewhart rules are blind to
sustained shifts below roughly 1.5 sigma.

Then work the decision procedure in `references/spc-for-yield.md`: metric definition stable →
limits from a clean baseline → which rule fired and does the shape match → does the timing
line up with a change record → is the shift big enough to matter.

## Edge-case branches

### Branch A — Single wafer vs whole lot

One wafer is an event; a lot is a condition. With a single wafer:
- Run `spatial_signature.py --lot X --wafer W1`. Pooled lot analysis is unavailable and
  wafer-to-wafer comparison is impossible — say both.
- **Do not run commonality analysis.** One wafer cannot separate a tool from a wafer.
- Widen every interval in your language. A 1200-die wafer gives a yield interval roughly ±2
  points wide; a 3-point "drop" from one wafer is not established.
- Ask for the rest of the lot and for the slot number. Slot position is the single most
  useful extra field for a one-wafer anomaly.

### Branch B — First silicon vs mature product

| | First silicon / new product | Mature product |
|---|---|---|
| Baseline | There isn't one. Compare against the *model* (D0 entitlement, design-rule expectation) and against sibling products on the same process | Recent stable history; SPC limits exist |
| Expected yield | Low and scattered is normal; systematic loss dominates | Random defectivity dominates; systematic loss is the excursion |
| First suspect | Design/layout marginality, test program immaturity, unqualified process integration | Tool, material, or process drift |
| Bin pareto | Expect new bins and program instability; recheck the program every lot | A new bin is itself the signal |
| Correct action | Characterize, do not chase — Shmoo, limit studies, split conditions | Contain and root-cause |
| Wrong move | Building SPC limits from ramp data | Assuming the program is stable without checking |

On first silicon, **say that no baseline exists** rather than inventing one from the first
few lots. And treat a "signature" on first silicon with care: layout-driven systematic
failure often looks spatial because the reticle field is spatial.

### Branch C — Yield went up (verify before celebrating)

A jump upward is a control-chart violation like any other, and it is the shape a test escape
makes. `spc_yield.py` prints an explicit up-side warning for this reason. Check in order and
report which check cleared it:

1. **Test program / limit revision.** Compare `JOB_NAM` and `JOB_REV` across the boundary
   (`stdf_ingest.py` prints both). Widened limits, a removed test, a disabled bin.
2. **Bin map change.** A real improvement shrinks a specific bin; a bin-map change makes one
   vanish. Compare pareto shape, not the total.
3. **Retest / rebin policy.** More retesting raises final yield and lowers first-pass yield.
4. **Tester, probe card, or load board change.** A legitimate gain — but a *test* gain, not a
   fab gain, and it must be attributed as such.
5. **Sampling change.** Fewer wafers, a die subset, skipped edge dies.
6. **Data pipeline change.** New parser, changed die-in-wafer definition.
7. **Only then** a real process improvement — which should have a change record, a mechanism,
   and a matching move in the bin it was supposed to improve.

If it survives all seven, it is real: recompute limits from the new baseline. If it does not,
**you have found a test escape**, and the material shipped under the inflated yield needs
review. Say that explicitly.

### Branch D — Test program or limit change masquerading as a yield shift

Symptoms: a step change exactly at a program revision boundary; a bin that appears or vanishes
outright; total yield moved but no spatial signature and no commonality suspect; parametric
distributions unchanged while fail counts moved.

Do this:
1. Diff the test program name and revision across the boundary — before any process work.
2. Diff the limit set test by test. A tightened limit shows as a parametric distribution that
   did not move while its fail count did.
3. Diff the bin map. Reclassification moves yield with nothing physical changing.
4. Re-run the pareto on the *same* bin definitions on both sides, remapping if necessary.
5. If the program changed, **the comparison is invalid** — say so and stop. Rebuild the
   baseline on the new program before any excursion claim.

### Branch E — Probe card / contact issues

Symptoms: fails concentrated at the wafer edge **and** in a pattern that repeats at the
touchdown grid; continuity/opens/parametric-contact bins dominating; fails that recover on
retest; the effect following the tester or the probe card rather than the fab route.

Do this:
1. **Plot fail rate by `SITE_NUM` first.** A quadrant or a clean spatial block that maps onto
   a site is a probe/channel problem, not a process one. This is the cheapest check in the
   whole skill and it resolves a large fraction of "quadrant" maps.
2. Compare the detected periodicity against the **probe touchdown array**, not only the
   reticle pitch. If they differ, the period tells you which one it is.
3. Check the retest rate and the first-pass vs final delta. Contact problems have a large gap.
4. Check probe card touchdown count, last clean, planarity/alignment records, and whether the
   effect follows the card across testers.
5. If it is contact: this is a **test** problem. Do not open a fab excursion, and correct any
   D0 computed from the contaminated yield.

### Branch F — Mixed signatures

Two or more candidates clear threshold. Do not pick one.

1. Report all candidates ranked, with z and lift.
2. **Split by bin.** Different mechanisms usually sit in different bins; one confusing map
   often becomes two clean ones.
3. **Subtract and re-run.** The classifier already masks scratch dies before the zonal tests;
   do the same by hand for the others — exclude the edge band and see whether the center
   cluster survives.
4. **Split by wafer.** A lot-level "mixed" result is frequently two wafers with two different
   single signatures, pooled.
5. Beware a dominant signature hiding a weaker one: a 45% edge fail rate drags the wafer mean
   up and makes the interior look fine. Compare zones against each other, never against the
   wafer mean.

## Signature → cause → discriminating evidence

| Signature | Geometry | Likely causes | Discriminating evidence | Most confused with |
|---|---|---|---|---|
| **Edge ring** | Closed annulus at the perimeter, ≥6 of 8 sectors elevated | Edge-bead removal, bevel/edge clean, clamp ring or lift pins, focus-ring erosion, edge etch/dep uniformity, litho edge shots, RTP edge cooling | Is the ring radius identical across wafers (hardware) or drifting (process)? Did it change after a PM or part swap? Does in-line metrology show the ring? | Probe-card edge contact loss; an edge crescent (one-sided); partial dies that could never pass |
| **Scratch / linear** | Chain of fails along a line or arc, span ≥8 dies, aspect ≥2.5 | CMP (pad debris, slurry agglomerate, retaining ring), wafer handling/transfer, robot blade, tweezers | Same wafer-relative position on every wafer (fixed hardware) or random (stochastic event)? Arc curving about the wafer center (polish) vs straight chord (handling)? Which layer's KLARF first shows it? | Probe-card damage rows (track the touchdown grid); a reticle row; an edge arc |
| **Center cluster** | Radially symmetric, worst at the center | Spin coat/develop dynamics, CMP center pressure, chuck center contact/thermal path, showerhead directly above center | Radial in-line metrology profile; does the cluster scale with spin speed / dispense volume / down force? | A donut whose hole is hidden by saturation — look at the *rate* vs radius, not the binary map |
| **Donut** | Mid-radius annulus worse than both center and edge | Multi-zone chuck/heater boundary, plasma radial profile (M- or W-shaped), spin regime transition, lamp-zone boundary | Does the ring radius match a known hardware boundary? **Move a zone setpoint — the ring should move.** | Edge ring + center cluster on one wafer (that is a mixed signature, not a donut); a wide edge ring on a large-die product |
| **Half-moon** | One side worse, boundary through the center (3–4 of 8 sectors) | Tilted or unseated chuck, single-sided gas inlet, blocked injector, target/magnet asymmetry, pumping-port asymmetry, one-sided clamping | **Notch-rotation split lot**: does the bad side follow the wafer or stay fixed in the chamber? Is it chamber-specific on a multi-chamber tool? | Quadrant (extent only — report the sector count); a very wide Edge-Loc |
| **Quadrant** | ~90° wedge, or stepwise differences between quadrants | Test site assignment, 4-fold tooling (lift pins, clamps), scan/implant direction, multi-head tooling | **Fail rate by `SITE_NUM` — check this first.** Then notch rotation. | Site-to-site test variation, which is by far the most common cause |
| **Reticle / shot** | Same die position fails in every exposure field | Reticle defect, pellicle contamination, design hot spot, illumination/lens non-uniformity, scanner sync | **Does the detected period match the real shot map?** Reticle inspection; does the pattern follow the reticle or the scanner across tools? | Probe touchdown grid; spurious periodicity when failure counts are small |
| **Random / none** | No zone, sector or period survives testing | Distributed layer defectivity; particle excursions | D0 vs baseline after excluding systematic bins and the edge band; is the yield below what Poisson predicts for the die area (clustering)? | "Clean" — with few failures no test has power; report the failure count |

## Yield models: which one, and how to extract D0

| Model | Y(A,D0) | Assumption | Use when |
|---|---|---|---|
| Poisson | `exp(-A·D0)` | Defects independent and uniform | Conservative floor; small die; state it as a bound |
| Murphy | `((1-exp(-λ))/λ)²`, λ=A·D0 | Triangular density distribution | Reasonable middle default with no clustering data |
| Seeds | `1/(1+A·D0)` | Exponential density distribution (heavy clustering) | Most optimistic; over-predicts for large die |
| Negative binomial | `(1+A·D0/α)^(-α)` | Gamma density; α = cluster factor | The only one to use when you actually measured α |

```bash
python "$SKILL/scripts/yield_models.py" --input "$DATA/die_results.csv" --die-area 0.25 --lot BASE
python "$SKILL/scripts/yield_models.py" --yield 0.905 --die-area 0.25 --n 3552 --alpha 2.0
```

**The trap:** a single (A, Y) point fits *every* model exactly. The four D0 values the script
prints are the same observation in four parameterisations, not four competing estimates. To
select a model you need multiple die sizes on the same process (fit ln Y vs A; curvature is
the clustering evidence), or measured defect counts per die. Without either, quote Poisson,
call it a bound, and stop. The default `--alpha 2.0` is a **placeholder, not a measurement**.

**Earn D0 before you fit it.** D0 means *random* defect density, so strip everything that is
not random first: gross fails, systematic bins, the edge exclusion zone, and parametric
marginality. Then fit, and quote the interval.

```bash
python "$SKILL/scripts/yield_models.py" --input "$DATA/die_results.csv" --die-area 0.25 \
    --exclude-bins 6,7,9 --edge-exclude 0.90
```

On the shipped sample data (seeded D0 = 0.400 /cm²), the raw fit gives 0.39 for the healthy
lot but 0.56–1.01 for lots carrying a signature. After the exclusions, all four lots return
0.37–0.43 with every 95% interval covering the seeded value. Same data, same script,
opposite conclusion.

Never compare raw yields across die sizes — convert to D0 under the same model with the same
exclusions. Read `references/yield-models.md` for die-area normalization, multi-die-size
regression, and the full pitfall list.

## Script reference

| Script | Does | Key flags |
|---|---|---|
| `gen_sample_data.py` | Generates the demo data deterministically | `--out --seed --extended --stdf --stdf-lots --no-sort-history` |
| `stdf_ingest.py` | STDF v4 → canonical CSV + 11-check integrity report | `--input --out --ptr-out --lot-id --max-parts --check --json` |
| `yield_summary.py` | Lot/wafer yields, hard and soft bin paretos | `--input --lot --soft --top --json` |
| `wafermap_render.py` | ASCII and PNG wafer maps, radial zone rates | `--input --lot --wafer --by-bin --no-ascii --png-dir` |
| `spatial_signature.py` | Rule-based signature classifier, ranked by z | `--input --lot --wafer --min-z --min-lift --json` |
| `yield_models.py` | D0 under four models, CIs, systematic exclusions | `--input\|--yield --die-area --lot --alpha --n --exclude-bins --edge-exclude --json` |
| `commonality.py` | Step × tool × chamber yield deltas, suspect ranking | `--history --die-results\|--yields --min-delta --json` |
| `spc_yield.py` | p / Laney p' / I-MR charts, WE rules, EWMA, change points | `--input\|--die-results --chart --by --baseline-n --baseline-lots --exclude-subgroups --png --json` |
| `fetch_wm811k.py` | WM-811K instructions + local converter. **Never downloads.** | `--convert --pkl --out --per-class --limit --labeled-only` |

Every script takes `--help`, and most take `--json` for chaining.

## References — read on demand

| Read | When |
|---|---|
| `references/wafer-map-signatures.md` | A map shows structure and you need physics, discriminating evidence, or to argue a signature *out* (step 5, Branches E and F) |
| `references/yield-models.md` | Quoting a defect density, comparing across die sizes, or projecting a die that does not exist yet (steps 2 and 8) |
| `references/commonality-analysis.md` | Ranking tool suspects, or before acting on any ranking — the confounder list is the point (step 6) |
| `references/spc-for-yield.md` | Deciding whether a movement is real, choosing a chart, or considering a hold (Workflow 2, Branches C and D) |
| `references/data-formats.md` | Asking the user for data, a file will not load, or you need the STDF record fields or the KLARF concept (Workflow 0, step 1) |

## Output format

Every analysis ends with these sections, in this order:

1. **What was measured** — the exact commands run and the numbers they returned.
2. **What that means** — signature, spread, pareto reading, with intervals.
3. **Suspect shortlist** — the five-column table from step 8, three to five entries.
4. **Next actions** — the four separate lists from step 9.
5. **Confidence and gaps** — what you could not check, and the one observation that would
   most cheaply falsify the top suspect.

Mark anything you could not verify as **TODO**. An honest gap is worth more than a confident
guess, and the person reading this has to sign off on holding material.
