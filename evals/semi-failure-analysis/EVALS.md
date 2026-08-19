# semi-failure-analysis — eval scorecard

**Run date:** 2026-08-20 · **Skill version:** 0.1.0
**Environment:** Python 3.11.12 (conda-forge, Clang 18.1.8), numpy 2.2.6, pandas 2.3.3, matplotlib 3.10.8, macOS 24.6.0 (arm64)
**Command:** `python evals/semi-failure-analysis/run_evals.py`

## Headline

```
RESULT: 82/82 checks passed
```

These are recorded results from an actual run, not a projection. Everything below is reproducible
with the shipped seeds (`gen_sample_case.py --seed 17`, `bin_signature.py --seed 7`).

What the suite proves and what it does not: it proves the **deterministic layer** behaves — the
scripts run, the plans are correctly ordered and gated, the statistics separate the seeded
signatures, and the report generator neither invents content nor silently drops it. It does
**not** prove the agent reaches the right mechanism when a human drives the skill in
conversation; that needs a transcript-level eval, which is listed under gaps.

---

## 1. Script verification

Every script compiled with `python -m py_compile` and answered `--help` cleanly.

| Script | `py_compile` | `--help` | Lines | Runtime deps |
|---|---|---|---|---|
| `scripts/technique_selector.py` | PASS | PASS (54 lines of usage) | 812 | stdlib only |
| `scripts/bin_signature.py` | PASS | PASS (47 lines) | 549 | numpy, pandas, matplotlib |
| `scripts/fa_report.py` | PASS | PASS (63 lines) | 478 | stdlib only |
| `scripts/gen_sample_case.py` | PASS | PASS (35 lines) | 873 | numpy |

`requirements.txt` pins nothing beyond numpy / pandas / matplotlib, and the two most-used scripts
need none of them.

---

## 2. `technique_selector.py` on the five golden cases

Each case ran from its intake JSON via `--case-file`. Checks per case: the discriminating
technique(s) appear in an early (non-destructive) phase · every destructive step carries a gate
reference · the gate step is emitted *before* the destructive steps it guards · case-specific
ordering constraints · the correct sample-allocation branch fires · no self-reported plan defect.

| # | Case | Discriminator asserted early | Actual phase | Steps (ND / D) | Gates | Sample mode | Result |
|---|---|---|---|---|---|---|---|
| 1 | EOS from hot-plug transient on a supply pin | `curve_trace` | **N0** | 15 (9 / 6) | D1, D2 | `single_sample_preservation` | PASS |
| 2 | TDDB gate-oxide fail emerging at burn-in | `burnin_delta_review`, `emmi_backside` | **N0**, **N2** | 19 (12 / 7) | D1, D2 | `small_population` | PASS |
| 3 | Intermittent wire-bond NSOP in temp cycling | `contact_elimination`, `in_situ_tc_monitoring`, `xray_2d` | **N0**, **N0**, **N1** | 20 (11 / 9) | D1, D2 | `population` | PASS |
| 4 | ESD (HBM) pin-leakage cluster after tooling change | `bin_signature_analysis`, `curve_trace`, `emmi_frontside` | **N0**, **N0**, **N2** | 12 (10 / 2) | D2 | `population` | PASS |
| 5 | MSL popcorn delamination after reflow | `csam`, `xray_2d` | **N1**, **N1** | 16 (8 / 8) | D1, D2 | `population` | PASS |

**Gating:** 32 destructive steps were emitted across the five plans; **0 were ungated** and **0**
appeared before the gate that guards them.

**Case-specific behaviour actually observed:**

- **Case 1 (N = 1).** The preservation branch fired and emitted **7 phase-P0 steps** before any
  technique: custody log opened, as-received photography before electrical test, imagery-is-the-
  archive, written pre-registered gate expectations plus a second reviewer, FIB preferred over
  mechanical section, and an explicit ban on destructive population tests (wire pull / ball
  shear) on the only unit. `magnetic_current_imaging` was offered in N1 with the rationale that
  its cost is justified precisely because the sample must survive. Three warnings were raised
  (single sample · customer return / chain of custody · `--urgency emergency` behaviour); the
  urgency warning correctly says to launch containment in parallel rather than to skip a gate.
- **Case 3.** `decap_plasma` was selected as the discriminator **and `decap_chemical` was
  explicitly excluded** with the reason that wet acid attacks the Cu wire / Al pad / IMC
  interface the case depends on. `wire_pull_ball_shear` was scoped to sibling units. 4 techniques
  excluded with reasons.
- **Case 4 (bare die).** No decapsulation step at all — `decap_chemical`, `csam`,
  `hermeticity_pind`, `emmi_backside` and `obirch_backside` were all excluded with package-type
  reasons. `internal_optical` and `emmi_frontside` were relocated to **N2 and re-marked
  non-destructive**, so the plan has one gate (D2) rather than two. This is correct: on a bare
  die there is nothing to open.
- **Case 5.** The hard ordering assertion held — `csam` at step 10, `decap_chemical` at step 13,
  `decap_laser_assisted` at step 14. C-SAM strictly precedes every decap route.

---

## 3. `bin_signature.py` on the case-4 wafer-sort data

Input: 4 wafers × 1184 dies (40 × 40 circular mask), two lots — `L2551` before the tooling change,
`L2604` after. Seeded background defectivity (soft bin 51) in both lots; a spatially random
leakage population (soft bin 42) seeded **only** in `L2604`.

Observed output for soft bin 42:

| Statistic | Result | Assertion |
|---|---|---|
| Lot confinement | present in `L2604` only (0 dies in `L2551`) | PASS |
| Count / yield loss | 165 dies (84 + 81), 3.484 percentage points | — |
| Spatial clustering, W01 | **random** — 9 adjacent pairs vs 10.93 expected, ratio 0.824, z −0.61 | PASS |
| Spatial clustering, W02 | **random** — 7 vs 11.04 expected, ratio 0.634, z −1.33 | PASS |
| Radial zones | **uniform** on both wafers (no edge or centre concentration) | PASS |
| Dominant out-of-limit test | test 1050 `IIL_IO2`, 165 of 165 dies | PASS |
| Excursion character | median **103.3×** the limit range → *hard (far outside limit)* | PASS |
| Co-failing test | 1051 `IIH_IO2`, 108 of 165 dies, 18.7× range, flagged *wide spread — check for two populations* | — |
| Ranked findings | 6 produced (`failing_test`, `spatial_random`, `secondary_tests`, `spatial_underpowered`) | PASS |
| PNG bin maps | 4 written | PASS |

Control (background bin 51): **never** read as a spatial signature — verdicts were
`inconclusive_low_power` on three wafers and `random` on one, radial `uniform` on all four. PASS.

The statistics were also sanity-checked against the sibling skill's seeded data
(`sample-data/semi-yield-monitor/die_results.csv`), where the deliberately seeded edge-ring bin
returned **clustered** (ratio 2.43, z 11.95) and **edge_concentrated** (edge rate 0.29 vs wafer
mean 0.147, z 9.9), while the Poisson background bin returned random/uniform on all seven wafers.
The classifier therefore separates both directions, not just the null.

---

## 4. `fa_report.py`

| Check | Result |
|---|---|
| Full 8D from `case1_eos_hotplug_resolved.json`, `--strict` | **exit 0**, 163 lines, D0–D8 all present, zero gap markers |
| FA lab report from the same record, `--strict` | **exit 0**, 116 lines, zero gap markers |
| Two-legged root cause (mechanism **and** escape point) rendered in D4 | PASS |
| Intake-only case (`case5_msl_popcorn.json`) → 8D, `--strict` | **exit 3**, 114 lines, **10 named gaps**, report labelled DRAFT |

The last row is the one that matters most: given a case that is not finished, the generator
refuses to produce a clean-looking report. It names every empty required section, marks the
document a draft, and exits non-zero under `--strict`. Nothing is inferred to fill a hole.

---

## 5. Bugs the eval suite actually caught (and the fixes)

Recording these because a scorecard that only ever shows green is not evidence of testing.

1. **Ungated destructive steps on bare die.** `internal_optical` and `emmi_frontside` were
   relocated to phase N2 for `bare-die` and `wlcsp` but kept their catalog `destructive: "D"`
   flag, producing two destructive steps with no gate in front of them. The plan's own
   self-integrity check reported the defect and the suite failed the case. Fixed by allowing a
   per-case destructiveness override and marking those steps `ND` where the die is genuinely
   already exposed.
2. **Clustering verdict unstable at low fail counts.** On the original 24 × 24 die grid, ~21
   random fails per wafer produced an expected adjacent-pair count near 2, where one extra
   touching pair swings the ratio past the clustering threshold — the statistic reported
   `clustered` for a population that was seeded random. Fixed two ways: a **power guard** that
   returns `inconclusive_low_power` when the expected adjacency count falls below 5 (rather than
   guessing), and a larger 40 × 40 case-4 grid matching the canonical grid used by
   `semi-yield-monitor`. The guard now also fires on the low-count background bin, which is the
   correct and honest behaviour.
3. **Intra-phase ordering was alphabetical.** The first plans listed `curve_trace` before
   `external_visual` and would have listed die inspection before the decap that exposes the die.
   Fixed with an explicit canonical within-phase sequence; physical ordering now wins over
   priority.
4. **One eval assertion was wrong, not the script.** The control-bin check demanded `random` and
   failed when the power guard correctly returned `inconclusive_low_power`. The assertion was
   rewritten to test what actually matters — that background defectivity is never mistaken for a
   spatial signature — rather than weakening the guard to make the test pass.

---

## 6. What a domain expert must review before this ships to a customer

Honest list. None of it is verifiable by running code, and several items would be embarrassing
to get wrong in front of an FA lab.

**High priority — could produce a wrong recommendation**

1. **Cost tiers and turnarounds in `references/technique-matrix.md`.** These are ordering
   heuristics written from general practice, not quotations. An FA manager should replace them
   with their own lab's actual costs and service levels. The current values drive `--budget low`
   deferral decisions, so a wrong tier changes plans.
2. **Technique applicability per package type.** The mapping (which techniques are available
   before vs after opening, per package family) is the load-bearing judgment in
   `technique_selector.py`. Flip-chip and WLCSP backside-access assumptions in particular assume
   a die thin/polish step is routine; that is not true in every lab.
3. **Decap-chemistry selection logic.** The rule "plasma when the hypothesis lives at a Cu-wire /
   Al-pad interface, acid otherwise" is defensible but coarse. A packaging FA specialist should
   review it against Ag-alloy wire, PCC wire, thin-pad and low-k stacks.
4. **The `MIN_EXPECTED_ADJACENCY = 5.0` power threshold and the clustering cut-points**
   (ratio ≥ 1.5 with z ≥ 3 = clustered). These are conventional count-statistic choices, not
   calibrated against real wafer data. They should be tuned against a labelled real dataset —
   the WM-811K subset used by `semi-yield-monitor` would be the natural benchmark.
5. **Radial zone boundaries** (centre ≤ 0.33, mid ≤ 0.70, edge > 0.70 normalized radius). Sensible
   defaults; real edge-exclusion geometry varies by process and wafer size.

**Medium priority — correctness of the written knowledge**

6. **Every mechanism row in `references/failure-mechanisms.md`.** Written in our own words from
   general reliability-physics practice. Activation energies and model exponents carry
   *(rough — verify)* markers precisely because they must not be quoted; a reliability engineer
   should confirm each anchor against the current JEP122 revision or delete it.
7. **The ESD model reasoning in `esd-eos-discrimination.md`.** The energy-per-area argument is
   the right shape, but the file deliberately asserts **no** numeric thresholds. Someone with
   ESD-design experience should confirm the pin-pattern table and the CDM-vs-TDDB discriminator.
8. **8D section semantics in `report-templates.md`** against the customer standards actually in
   force at the client (JEDEC JESD671, VDA 8D, or a customer-specific format). The two-legged
   root cause (occurrence + escape) is standard practice, but section naming and required
   attachments vary by customer.
9. **The five golden cases themselves.** They are original compositions built from classic
   mechanisms in the public literature — plausible, internally consistent, and pedagogically
   right, but not drawn from real case files. An experienced FA engineer should confirm that
   each case's evidence chain is one they would actually accept.

**Known gaps — not yet built**

10. **No transcript-level eval.** The suite tests the scripts, not the agent. The real acceptance
    criterion from the build brief — *the skill must produce the documented mechanism in its
    top-2 hypotheses* — requires driving the skill conversationally against each intake file and
    scoring the hypothesis table. That harness does not exist yet, and this scorecard should not
    be read as having met that criterion.
11. **No STDF parsing.** The brief anticipated sharing an STDF library with `semi-yield-monitor`.
    `bin_signature.py` currently consumes the canonical CSV schemas only. Real FA work starts
    from STDF or a vendor datalog export, so a converter is needed before this touches a
    production flow.
12. **No image analysis.** C-SAM, X-ray and SEM interpretation is entirely prose guidance; nothing
    reads an actual image. The `images` block in the evidence JSON is an inventory, not an
    analysis.
13. **`--budget` / `--urgency` semantics are unvalidated by anyone who runs an FA lab.** The
    current behaviour (defer cost-tier 4+, parallelize rather than skip gates) is a defensible
    policy, not a measured one.
14. **Sample-size logic is simple.** Allocation is a fixed archive/sequence/confirmation split.
    Real labs allocate against the hypothesis set and the customer's return quantity.

---

## 7. Reproducing this run

```bash
pip install -r skills/semi-failure-analysis/requirements.txt

# regenerate the case inputs (deterministic)
python skills/semi-failure-analysis/scripts/gen_sample_case.py \
    --case all --outdir sample-data/semi-failure-analysis/ --seed 17

# run the suite
python evals/semi-failure-analysis/run_evals.py --json results.json
```

Intermediate artifacts land in `evals/semi-failure-analysis/_run/` (plans, generated reports,
bin-signature JSON and PNG maps). They are outputs, not inputs — safe to delete.
