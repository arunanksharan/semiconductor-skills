# Golden case 4 — ESD (HBM) pin-leakage cluster after a probe-card / handling change

| | |
|---|---|
| **Intake inputs** | `sample-data/semi-failure-analysis/case4_esd_hbm_cluster.json` · `case4_die_results.csv` · `case4_tests.csv` |
| **True mechanism** | **Human-body-model-class ESD damage to the IO2 pin-pair protection structures, inflicted at probe** by an ungrounded discharge path introduced with the new load board — a handling/tooling event, not a die defect and not a test artifact |
| **Discriminating techniques that must surface early** | `bin_signature_analysis` and `curve_trace` (both phase **N0**) |
| **Confirming techniques** | `emmi_frontside` (phase **N2** — bare die needs no decap), then `fib_cross_section` |
| **Edge cases exercised** | Bare die / KGD (no package to open, so localization is non-destructive) · change-point evidence · spatial randomness as a positive finding · the clustering statistic's power limit |

## Why this case exists

It is the case where **the statistics do the discriminating**, before anyone touches a die. Three
hypotheses are live at intake — a real die defect, a test artifact, and damage being inflicted at
probe — and they make different, checkable predictions about the *spatial* distribution of the
failing bin. Running `bin_signature.py` costs minutes and separates them.

It is also the bare-die edge case. There is nothing to decapsulate, so frontside optical and
emission work are genuinely non-destructive and belong **before** any gate. A plan that inserts
a decap step here does not understand the package type.

## The intake picture

Soft bin 42 (I/O leakage) jumped from effectively zero to roughly 6% of dies, starting with the
first lot probed after a probe-card replacement and a load-board swap on prober PR-03. The test
program revision did not change. `suspected: ["esd"]` reflects a live suspicion, not a
conclusion — the intake explicitly asks whether this is a die problem, a test artifact, or
damage inflicted at probe.

## True mechanism

An ungrounded discharge path introduced with load board LB-22 allowed human-body-scale
discharges into the IO2 pin pair during handling and touchdown. The protection structures took
the events and degraded, leaving a leakage path. The dies were good before probe.

## Discriminating evidence, in the order it should appear

1. **`bin_signature_analysis`, N0.** This is the step the case turns on. Actual output from the
   shipped data (`--bin 42`):

   | Statistic | Result |
   |---|---|
   | Bin 42 lot confinement | present in **L2604 only** (post-change); zero dies in L2551 |
   | Bin 42 count | 165 dies (84 + 81 across two wafers), 3.48 percentage points of yield loss |
   | Spatial clustering | **RANDOM** on both wafers — adjacent-fail pairs 9 vs 10.93 expected (ratio 0.824, z −0.61) and 7 vs 11.04 expected (ratio 0.634, z −1.33) |
   | Radial | **UNIFORM** on both wafers — no edge or centre concentration |
   | Dominant out-of-limit test | test 1050 `IIL_IO2` on **165 of 165** dies, median excursion **103×** the limit range → *hard (far outside limit)* |
   | Co-failing test | test 1051 `IIH_IO2` on 108 of 165 dies, median excursion 18.7× range, flagged *wide spread — check for two populations* |

   Read together: a **hard**, **pin-specific** leakage failure that is **spatially random** and
   **confined to the lot processed after a tooling change**. Spatial randomness is the positive
   finding here, not an absence of one — a wafer-process cause would cluster or show a radial
   signature, and neither is present. Random + change-point + one pin pair = a per-touchdown
   event at the prober.

2. **`curve_trace`, N0.** On the picked dies vs pre-change reference dies: leakage on the IO2
   pin pair with degraded protection-device I-V, everything else matching. Confirms the damage
   sits on the protection structure — the ESD network having taken the event
   (`references/esd-eos-discrimination.md` §2, §4).
3. **Retest / cross-prober experiment (intake `open_questions`).** Re-probe failing dies on a
   different prober with the old card, and re-probe *passing* dies with extra touchdowns. If
   passing dies start failing, the damage is being created at probe — which is a containment
   trigger on its own, before any mechanism is proven.
4. **`internal_optical` and `emmi_frontside`, N2.** Bare die: no decap needed. Emission localizes
   the leakage to the IO2 protection structure.
5. **`fib_cross_section`, D2, gated.** Confirms a small, localized melt filament confined to the
   clamp — HBM-scale damage, not the wide melt of an EOS event.

## What a correct plan must contain

- `bin_signature_analysis` in **N0**, run before anything physical, with the die-level CSVs.
- `curve_trace` in **N0** against pre-change reference dies.
- No decapsulation step at all, and `decap_chemical` explicitly excluded with the reason "bare
  die / KGD — there is nothing to decapsulate".
- `internal_optical` and `emmi_frontside` marked **non-destructive** and placed in **N2**, ahead
  of the only gate in the plan (`GATE D2`).
- Containment recommended as soon as the signature is known — quarantine post-change material
  and audit the load-board grounding — without waiting for the cross-section.

## What a wrong run looks like

- Treating spatial randomness as "no information" and going straight to physical analysis.
- Calling this a die/process defect because 6% is a large number — the lot confinement and the
  unchanged background bin 51 both argue against it.
- Calling it a test artifact and re-testing the lot: the excursion is 103× the limit range, which
  is a real leakage path, not a measurement error. (A *marginal* excursion just outside the limit
  would have supported the artifact hypothesis; that is what the excursion character is for.)
- Inserting a decap step for a bare die.
- Skipping the ESD-control audit of the new load board — the mechanism is only half the root
  cause; the escape point is that the tooling change was released without an ESD-path
  verification.

## Note on the clustering statistic's power

The background defectivity bin (51) in the same data returns `inconclusive_low_power` on three of
four wafers rather than `random`. That is correct behaviour, not a bug: with ~50 fails per wafer
the expected adjacent-pair count falls below the script's minimum-expected threshold, where one
extra touching pair would swing the ratio. The script refuses to give a verdict it cannot
support. Bin 42, with ~82 fails per wafer, clears the threshold and returns a real verdict. Any
run that reports "random" for an underpowered bin is overclaiming.

## Grounding

Composed for this repository; the wafer-sort data is synthetic and seeded (see
`skills/semi-failure-analysis/scripts/gen_sample_case.py`, seed 17), using the canonical
`die_results.csv` / `tests.csv` schemas shared with `semi-yield-monitor`. HBM model definition
cited by number only (ANSI/ESDA/JEDEC JS-001; JEDEC JESD22-A114). No standard text is
reproduced. Part numbers, lot IDs, tool IDs and organizations are invented.
