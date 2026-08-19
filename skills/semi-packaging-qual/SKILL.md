---
name: semi-packaging-qual
description: >-
  Builds and reviews semiconductor package qualification plans and assembly-defect
  dispositions. Use when the user mentions package qualification, JEDEC, JESD47, JESD22,
  MSL, J-STD-020, reliability test plan, AEC-Q100, wire bond, flip chip, WLCSP, fan-out,
  FOWLP, BGA, QFN, delamination, C-SAM, SAT, X-ray inspection, die-attach voiding, wire
  sweep, moisture sensitivity, HAST, uHAST, HTSL, temperature cycling, or OSAT assembly
  defects. Covers package-family selection tradeoffs, per-step assembly defect triage,
  JEDEC-style qualification test matrices (preconditioning, TC, HAST, uHAST, HTSL, THB,
  power temperature cycling, board-level tests) with sample sizes, readpoints, and pass
  criteria, LTPD/AQL sample-size math, MSL classification with floor-life and bake rules,
  and C-SAM/X-ray interpretation with step-gated cross-section confirmation.
license: MIT
metadata:
  version: 0.1.0
  author: Kuzushi Labs
---

# semi-packaging-qual — package qualification & assembly-defect judgment

Structured decision procedures for IC package selection, assembly-defect triage, JEDEC-style
qualification planning, MSL classification, and acoustic/X-ray image disposition. The model
chooses the analysis and applies the gates; the scripts compute every number.

**Division of labor with sibling skills:** electrical root cause of a failing unit →
`semi-failure-analysis`. Die yield / wafer maps → `semi-yield-monitor`. Fab process
excursions → `semi-fab-process`. This skill owns everything from wafer-in-OSAT to
board-level reliability of the *package*.

## Operating rules (binding)

1. **Never fabricate data.** No measurement values, void percentages, delam areas, or test
   results unless the user supplied them or a script computed them. With no data, run the
   intake interview (Workflow 0) and produce a *plan*.
2. **Numeric conditions are templates.** Test conditions/durations encoded here and in
   `scripts/qual_plan.py` are industry-typical values. Every emitted plan must carry its
   `verify` block: confirm conditions against the **current revision** of each cited standard
   (JEDEC standards are free downloads at jedec.org; AEC documents at aecouncil.com) before
   committing hardware. Say this to the user every time a plan is produced.
3. **Cite standards by number and clause, in your own words.** Never reproduce standard text.
4. **Step-gates are hard.** Do not skip a gate because the user is in a hurry; state the gate
   and what evidence clears it.

## Workflow 0 — Intake (always run first)

Collect before any recommendation. Ask only for what's missing; accept "unknown" and record it.

| # | Question | Why it matters |
|---|----------|----------------|
| 1 | Device: die size, node, low-k dielectrics? pad metal (Al/Cu), pad pitch, I/O count, power (W) | Interconnect + family feasibility, low-k gates |
| 2 | Market/mission profile: consumer, industrial, automotive (AEC-Q100 grade 0–3), lifetime, ambient | Test conditions, durations, sample sizes |
| 3 | Package: family, body size/thickness, ball/lead pitch, materials set (mold compound, die attach, substrate, wire metal, ball alloy) | Defect catalog + qual scope |
| 4 | Novelty: new package family / new materials set / new assembly site / derivative of a qualified package? What changed? | Full qual vs qualification-by-similarity |
| 5 | MSL target and reflow: Pb-free? peak temp constraint? handheld product (drop risk)? | Precon level, board-level tests |
| 6 | Prior data: existing qual reports, C-SAM/X-ray images, failure history on the platform | Reuse; derivative justification |

Route by intent: choose a package → Workflow 1 · assembly defect/excursion → Workflow 2 ·
qual plan → Workflow 3 · MSL/floor-life question → Workflow 4 · C-SAM/X-ray image call →
Workflow 5.

## Workflow 1 — Package-family selection

Full tradeoff detail: `references/package-families.md`. Summary matrix:

| Family | I/O density | Thermal | Cost | Board-level reliability | Die-shrink sensitivity |
|---|---|---|---|---|---|
| QFN (wire bond) | Low (≤~100) | Good (exposed pad) | Lowest | Excellent (small, stiff) | Low — pad-limited ring |
| QFP (wire bond) | Low-mid | Poor–fair | Low | Good | Low |
| PBGA (wire bond) | Mid (100s) | Fair | Low-mid | Good | Low |
| FCBGA / FCCSP | High (1000s) | Best (die-back exposed/lid) | High | Fair (large body CTE) | Medium — bump pitch floor |
| WLCSP | Die-limited | Fair | Low @ small die | **Weakest** — bare die on board, drop/TC risk grows with body size | **High — package IS the die** |
| Fan-out (FOWLP) | Mid-high | Fair-good | Mid | Fair-good | Medium — RDL absorbs shrink |
| 2.5D/3D (interposer/stack) | Highest | Hard (stacked power) | Highest | Fair | Low (interposer decouples) |

Selection procedure:
1. Eliminate by hard constraints in this order: I/O count & pitch → power dissipation →
   body-size limit → cost ceiling → board-level environment (handheld drop? automotive vibration?).
2. If two families survive, decide on the *second-order* risks: WLCSP over ~5×5 mm in a
   handheld → demand board-level drop + TC data before committing. Low-k die in wire-bond
   package → bond-over-active and cratering risk; prefer Cu pillar/flip-chip or demand bond
   process qual data. Die will shrink next year → avoid WLCSP (re-layout + re-qual every shrink).
3. Output a one-page decision record: constraints table → surviving families → chosen family →
   top-3 risks with the qual tests that cover each (feeds Workflow 3).

## Workflow 2 — Assembly flow & defect triage

Full catalog with mechanisms and detection: `references/assembly-defects.md`. Flow map:

| Step | Dominant defects | First-look detection |
|---|---|---|
| Backgrind / wafer prep | TTV out of spec, backside scratches/chipping, wafer bow | Profilometry, visual, bow gauge |
| Dicing (blade/laser/plasma) | Edge chipping (front/back), sidewall cracks, low-k peeling | Microscope die-edge inspection, die strength (3-pt bend) |
| Die attach | Voiding, die tilt, bond-line thickness (BLT) off, epoxy bleed, NCDA | **X-ray** (voids), C-SAM, x-section (BLT) |
| Wire bond | NSOP/NSOL, ball lift, cratering, wire sweep (at mold), short/leaning wires, IMC problems | Bond pull (MIL-STD-883 M2011), ball shear (JESD22-B116), optical, x-section |
| Flip-chip attach + underfill | Non-wet opens, bump voids, underfill voids/incomplete fillet, die corner delam | X-ray (bumps), C-SAM (underfill), x-section |
| Mold | Incomplete fill, internal voids, wire sweep, mold–die/mold–pad delam, flash | C-SAM, X-ray (sweep), visual |
| Ball attach / lead finish | Missing/bridged balls, ball void, coplanarity, finish contamination | AOI, X-ray, coplanarity scan, solderability (J-STD-002) |
| Singulation / trim-form | Burrs, lead damage, package chipouts | AOI, visual |
| Final test / mark | Test escapes, bent leads from handling | ATE data (→ semi-yield-monitor), visual |

Triage procedure (defect reported at step N):
1. **Confirm the observation** — is the detection method appropriate and calibrated? (A
   "delam" from a single C-SAM image without a reference scan is unconfirmed → Workflow 5.)
2. **Scope it** — one unit / one strip / one lot / trend? Pull the commonality: machine,
   material lot (mold compound date code, wire spool, epoxy batch), operator, time window.
3. **Check the step's usual suspects** first (tables in `references/assembly-defects.md`),
   e.g. die-attach voiding ↑ → epoxy age/thaw log, dispense pattern, die-attach oven profile;
   wire sweep ↑ → mold transfer speed/viscosity (compound past shelf life?), wire length/loop.
4. **Containment before root cause** — quarantine affected lots by traceability *first*, then
   investigate. State both actions separately.
5. **Escalation gate:** any defect that implicates a *reliability* interface (die attach,
   underfill, mold adhesion) requires disposition with stress data, not visual screening alone
   — a lot that "looks fine after rework" still needs precon + C-SAM sampling before ship.

## Workflow 3 — Qualification plan builder

Deep digest of every test: `references/jedec-qual-digest.md`. Automotive deltas:
`references/aec-q100-mapping.md`.

1. Gather inputs from Workflow 0 (device class, package family, novelty, MSL target).
2. **Run the generator — never hand-write the matrix:**
   ```bash
   python3 scripts/qual_plan.py --device-class automotive_grade1 --package qfn \
     --novelty derivative --msl 2 --format both --out plan.md --json-out plan.json
   ```
   Required: `--device-class {consumer,industrial,automotive_grade0..3}` ·
   `--package` (see `--list-packages`; `bga`/`csp`/`wlp`/`2.5d` are aliases) ·
   `--novelty {new_package,derivative,process_change}` · `--msl {1,2,2a,3,4,5,5a}`.
   Optional: `--handheld` (drop test becomes mandatory) · `--board-level` (force board-level
   drop + board-level TC in) · `--suppress-board-level` (drop the auto-included board-level
   rows — needs a written justification) · `--power-cycling` · `--interconnect` ·
   `--change TEXT` (for `process_change`) · `--device TEXT` ·
   `--format {markdown,json,both}` · `--out` / `--json-out` / `--csv-out`.
   `--scenario file.json` reads the same keys (underscored) from a JSON file; CLI flags win.
3. Review the emitted matrix against the *risk list* from Workflow 1 step 3 — every top risk
   needs a covering test; add tests, never silently remove.
4. **Sample-size gate.** Default env-stress legs are 77 units/lot, accept 0 (exact binomial:
   2.946% LTPD at 90% confidence — the "3%" of the tables). Mechanical legs default to 45/lot
   (4.988% LTPD). Verify or adjust with the calculator; never quote LTPD from memory:
   ```bash
   python3 scripts/sample_size.py --n 77 --accept 0       # → demonstrated LTPD = 2.946 %
   python3 scripts/sample_size.py --ltpd 3                # → min n for c = 0, 1, 2
   python3 scripts/sample_size.py --ltpd 5 --accept 0     # → min n for one accept number
   python3 scripts/sample_size.py --n 231 --fails 1       # → 90% upper bound after 1 fail
   python3 scripts/sample_size.py --table                 # → min-n table, c = 0..2
   python3 scripts/sample_size.py --self-check            # → verify vs known table points
   ```
   LTPD at 90% confidence *is* the one-sided Clopper-Pearson upper bound on the defect rate —
   say it that way when a customer asks what "77/0" buys them.
5. **Lot gate.** New package/materials/site → 3 non-consecutive assembly lots. Derivative →
   1 lot *plus a written similarity justification* (what is identical: materials set, site,
   design rules; what changed and why it doesn't add risk). Process change → 2 lots and a
   documented change-impact analysis that prunes the matrix. Qualification-by-similarity is
   **not allowed** when any of: new mold compound or die-attach material, new assembly site,
   die-to-pad ratio grows beyond the qualified envelope, finer wire/ball pitch, new wire or
   ball metallurgy, thinner die than qualified. Any of those → treat as new.
   **Automotive overrides all of the above with a floor of 3 non-consecutive lots**, even for
   a derivative; the generator applies this automatically and says so in the plan notes.
   Non-consecutive is the load-bearing word — three lots off one shift are one lot wearing
   three labels.
   **House rule the generator applies (and labels as one):** a *new package family* runs to
   at least 1000 TC cycles and 1000 h HTSL even where the class default is shorter. A family
   with no field history needs a wear-out curve, not a pass/fail gate. Drop back to the class
   default only with a written rationale.
6. **Readpoint discipline.** Interim readpoints (e.g., TC 500, HTSL 500 h) exist to catch
   early wear-out; a readpoint fail stops the clock → Workflow 2/5 triage, then
   `semi-failure-analysis` for the unit.
7. **Read the `applicability` field before presenting anything.** Every row is one of:
   - `required` — in the plan, budget the units.
   - `conditional` — carries a **TODO**: something the generator could not settle (does
     constant acceleration apply to this overmolded body? which BLR TC class does the
     customer want? is there a citable standard for Cu-pillar bump pull?). Surface every one
     of these to the user as an open question. Never silently promote a conditional row to
     required, and never silently drop one.
   - `alternative` — mutually exclusive with another row (THB *replaces* biased HAST). Pick
     one, say why, and don't double-count the units.
8. **Never present a plan without the `out_of_scope` block.** HTOL, ELFR and ESD/latch-up
   qualify the *die*, not the package. Stating that boundary is a scope definition; omitting
   it silently is a gap the customer finds at PPAP.
9. Emit the plan with: test table (standard, condition, duration, readpoints, n/lot × lots,
   accept), pass criteria (0 fails electrical to datasheet; no *new* delamination on critical
   interfaces post-stress vs. time-zero C-SAM; solderability per J-STD-002), the `verify`
   block (rule 2), the out-of-scope block, and open risks. Template in
   `references/jedec-qual-digest.md §Plan-skeleton` — `qual_plan.py --format markdown`
   already emits this structure, so hand it over rather than re-typing it.

## Workflow 4 — MSL classification & moisture handling

Decision rules and floor-life/bake tables: `references/msl-guide.md`.

1. Classifying a new SMD package → run:
   ```bash
   python3 scripts/msl_advisor.py --package bga --body-thickness-mm 1.2 \
     --body-volume-mm3 800 --target-msl 3 --reflow-peak-c 260 --carrier tape_reel
   ```
   Required: `--package`, `--body-thickness-mm`. Give volume directly
   (`--body-volume-mm3`) or as a footprint (`--body-size-mm 5x5`, volume = W×L×thickness).
   Optional: `--die-package-ratio 0.0-1.0` or `--die-size-mm 4x4` (mold-cap risk) ·
   `--reflow-peak-c` (the customer's *actual* peak → conflict check) ·
   `--target-msl` · `--solder {pbfree,snpb}` · `--carrier {tray,tape_reel,tube,unknown}` ·
   `--levels-table` · `--json`.
   It returns the Pb-free classification reflow peak (J-STD-020 thickness×volume table), a
   CONFLICT/OK/HEADROOM verdict against the customer's process peak, a starting MSL by family
   adjusted for construction risk, floor life, and bake-recovery guidance (J-STD-033).
   **The starting MSL is a hypothesis for the classification run, never an answer** — the
   script says so in its own output; repeat it to the user.
2. The classification *flow* (J-STD-020): sample → bake dry → weigh → moisture soak at the
   candidate level's condition → 3× reflow at the classification peak → electrical + C-SAM
   vs. time-zero. Fail (new critical-interface delam or electrical fail) → drop to next level.
3. **Floor-life exceeded on the line** → do not reflow. Bake per J-STD-033 (typ. 125 °C for
   24–48 h for ≥1.4 mm bodies; low-temp 40 °C options exist for moisture-sensitive trays),
   then restart floor-life clock. Gate: check tray/tube temperature rating before a 125 °C
   bake, and count cumulative bake time — long/multiple bakes degrade solderability (IMC
   growth, oxidation); >96 h cumulative at 125 °C → re-verify solderability per J-STD-002.
4. **Re-classification triggers:** mold compound change, body thickness change, die-attach
   material change, reflow peak increase (e.g., customer moves to 260 °C) → re-run step 2.

## Workflow 5 — C-SAM / X-ray disposition (step-gated)

Interface-by-interface signatures: `references/sam-xray-interpretation.md`.

1. **Gate A — image validity.** Confirm: transducer frequency appropriate to depth (15–30 MHz
   deep interfaces, 50–230 MHz thin/near-surface), focus at the interface of interest, gain
   not saturating, and a **time-zero reference scan of the same units** exists for any
   "growth" claim. No reference → you may report "delamination present", never "delamination
   grew".
2. **Read pulse-echo phase:** delamination/air gap → phase inversion (classic red/white in
   most palettes). Map which interface: die top / mold-to-pad / die-attach / underfill.
3. **Apply the criticality table** (J-STD-020-style): delam on the *active die face* or
   *any wire-bonded periphery* → reject. Die-attach delam → reject when the package relies on
   the pad for thermal/electrical path; otherwise measure % area and trend. Mold-to-leadframe
   delam away from wires → record, disposition on growth through precon.
4. **X-ray quantification:** die-attach void % of pad area (typical specs: total ≤10–20 %,
   single void ≤5–10 % — use the device spec, not these defaults, when it exists); wire sweep
   = max lateral deflection / wire span, typical limit 5–10 %; bump/ball voids % of ball area.
5. **Gate B — destructive confirmation.** Before scrapping a lot or blaming a supplier on
   acoustic evidence alone: cross-section (or dye-and-pry for board-level opens) at least
   2 units to confirm the delam/void physically. Acoustic artifacts (tilt, warpage shadowing,
   mold filler settling) mimic delam.
6. Record disposition: image IDs, interface, % area, criteria applied, pass/fail, next action.

## Edge cases that change the plan (check every time)

- **Low-k / ULK die**: dicing chipping and die-corner delamination dominate; add die-edge
  inspection after saw, prefer laser groove + blade or plasma dice; TC readpoints must include
  C-SAM focused at die corners; underfill selection (CTE, Tg) is a qual variable.
- **Large die (>~8×8 mm) or large-body FCBGA**: warpage across reflow → HIP/non-wet opens,
  dynamic warpage (shadow-moiré) data belongs in the plan; board-level TC matters more than
  component TC.
- **Thin die (<100 µm)**: handling cracks appear as infant TC fails; add die-strength
  monitoring and backside finish spec to the plan.
- **Cu wire on Al pad**: narrower bond window than Au; cratering and Cl-driven IMC corrosion
  under uHAST/HAST are the signature risks — biased HAST is non-negotiable; Pd-coated Cu
  mitigates but does not waive it.
- **Au wire + Al pad at high junction temp** (automotive under-hood, HTSL ≥150 °C): Au-Al
  IMC growth / Kirkendall voiding → HTSL duration set by mission profile, wire pull at
  readpoints, not only end-of-life.
- **Mixed metallurgy on one substrate** (e.g., SnPb ball on Pb-free reflow or vice versa):
  never mix profiles; classification temp follows the *assembly* profile actually used.
- **Handheld / wearable end product**: JESD22-B111 board-level drop is mandatory for
  WLCSP/CSP/BGA regardless of device class; corner balls / underfill or corner-glue decisions
  come from this data.
- **Exposed-pad packages (QFN) soldered pad-down on large copper**: thermal cycling of the
  solder joint, voiding under pad affects θJA — X-ray void spec on the *board* joint too.

## Outputs this skill produces

1. **Package decision record** (Workflow 1 step 3 format).
2. **Qualification plan** — `qual_plan.py` markdown + JSON (+ CSV), plus risk-coverage note,
   the `verify` block, the `out_of_scope` declaration, and every `conditional` row's TODO
   raised as an open question. Never present a plan missing any of those four.
3. **MSL report** — classification peak, level, floor life, bake rules, line-handling notes.
4. **Image disposition record** (Workflow 5 step 6 format).
5. **Defect triage note** — confirmed/scoped/contained/root-caused, with commonality table.

## Scripts

Python ≥3.10, `pip install -r requirements.txt` (numpy + pandas only — **no scipy**; the
binomial math is implemented directly). Run `--help` on each for full usage.

| Script | Purpose |
|---|---|
| `scripts/qual_plan.py` | Device class + package + novelty + MSL (+ handheld/board-level flags) → full test matrix as markdown, JSON and CSV |
| `scripts/msl_advisor.py` | Family + body geometry + die/package ratio + customer reflow peak → classification peak, peak-conflict verdict, starting MSL, floor life, bake rules, re-classification triggers |
| `scripts/sample_size.py` | Exact-binomial LTPD/AQL math: demonstrated LTPD, min-n for c=0/1/2, upper confidence bounds, min-n table, `--self-check` against known table points |
| `scripts/gen_scenarios.py` | Writes the three eval scenario inputs into `sample-data/semi-packaging-qual/` (`--list`, `--out-dir`, `--force`) |

Every number in an emitted plan comes from these scripts. If you find yourself typing a cycle
count, a sample size or an LTPD figure into a reply by hand, stop and run the script instead.

## Sample data & evals

- `sample-data/semi-packaging-qual/*.json` — three scenario inputs (automotive QFN grade 1
  derivative · consumer WLCSP new package MSL 1 · industrial PBGA derivative). Each carries a
  narrative and an `expected_judgement` a reviewer can argue with.
- `evals/semi-packaging-qual/golden/*.expected.json` — hand-authored expected test sets:
  which tests must appear, which must **not** (e.g. no wire pull on a WLCSP, no solder ball
  shear on a QFN), key conditions, lot counts and sample sizes.
- `evals/semi-packaging-qual/run_evals.py` — runs `qual_plan.py` as a subprocess against each
  scenario and diffs against the golden set, plus the LTPD self-check:
  ```bash
  python3 evals/semi-packaging-qual/run_evals.py --verbose
  ```
- `evals/semi-packaging-qual/EVALS.md` — the measured results of the last run.

## References (load on demand)

- `references/package-families.md` — selection tradeoffs, feasibility limits, risk lists
- `references/assembly-defects.md` — step-by-step defect catalog: mechanism → detection → usual suspects
- `references/jedec-qual-digest.md` — test-by-test digest (purpose, conditions, readpoints, what it precipitates) + plan skeleton
- `references/msl-guide.md` — MSL levels, floor life, classification flow, bake recovery
- `references/sam-xray-interpretation.md` — interface signatures, artifact traps, quantification
- `references/aec-q100-mapping.md` — grades 0–3, condition deltas vs consumer, what AEC adds beyond package qual
