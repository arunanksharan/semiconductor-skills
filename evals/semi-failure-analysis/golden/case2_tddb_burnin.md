# Golden case 2 — TDDB gate-oxide failure emerging at burn-in

| | |
|---|---|
| **Intake input** | `sample-data/semi-failure-analysis/case2_tddb_burnin.json` |
| **True mechanism** | **Time-dependent dielectric breakdown (TDDB)** of the gate oxide — extrinsic, defect-driven early-life population, surfaced by the voltage-and-temperature acceleration of dynamic burn-in |
| **Discriminating techniques that must surface early** | `burnin_delta_review` (phase **N0**) and `emmi_backside` (phase **N2**) |
| **Confirming technique** | `fib_cross_section` at the emission site, then `tem_lamella` through the oxide |
| **Edge cases exercised** | Failure that did not exist at t = 0 · flip-chip backside access changes the phase of EMMI · the CDM lookalike |

## Why this case exists

Two reasons. First, it is the timing case: a mechanism that is invisible at final test and
appears only after stress hours. The whole prior shifts on *when* the failure arrived, which is
information already in hand before any lab work — and the skill has to use it.

Second, it is the CDM lookalike. A gate-oxide breakdown path in cross-section can look like
charged-device-model damage. The discriminator is not morphology; it is population and time
(`references/esd-eos-discrimination.md` §6). A run that reaches for "CDM" on a unit that
demonstrably passed final test with margin has skipped the cheapest evidence in the case.

## The intake picture

3 of 231 units fail at the 168 h dynamic burn-in readpoint; 0 fail at 48 h; all 231 passed
pre-burn-in final test with normal margin. The shift is leakage-only — IDDQ on the core domain
is 40–90× the pre-burn-in value on the *same serials* — and the units still function at nominal
voltage. `suspected` is deliberately empty: nobody has named a mechanism yet.

## True mechanism

Extrinsic (defect-related) gate-oxide breakdown. A weak-oxide subpopulation that would have
failed in the field within warranty was accelerated into the burn-in window by elevated voltage
and 125 °C. The leakage-only character with functional patterns still passing is the classic
soft-breakdown (SBD) signature before progression to hard breakdown.

The honest verdict is **TDDB, extrinsic mode**, with the qualification that intrinsic wearout
cannot be excluded from three units — separating extrinsic from intrinsic needs a Weibull fit
over a real population at multiple voltages, which this case does not have.

## Discriminating evidence, in the order it should appear

1. **`burnin_delta_review`, N0.** The highest-value artifact in the case and it costs nothing:
   the same serials, before and after, on the same program. It establishes that (a) the parts
   were good at t = 0, killing every born-defective and CDM-at-assembly hypothesis, and (b) the
   change is confined to leakage, not to timing or function.
2. **`datalog_review`, N0.** Confirms only IDDQ/leakage moved.
3. **`curve_trace`, N0.** Distinguishes a supply-path leak from an I/O-pin leak and gives the
   voltage dependence of the leakage current — a dielectric path has a distinctive character
   against a junction leak.
4. **`emmi_backside`, N2.** Flip-chip: the die backside is accessible, so photoemission runs
   **without decapsulation**. Emission finds *light*, which is exactly what a leaking oxide
   emits. Choosing a thermal technique here instead would likely return nothing and cost a week
   (`references/technique-matrix.md`, N2 judgment).
5. **`fib_cross_section` → `tem_lamella`, D2.** Only TEM resolves oxide thickness and a
   percolation/breakdown path. The gate-oxide question is answered at the oxide or not at all.

## What a correct plan must contain

- `burnin_delta_review` in **N0** — triggered by the `after_burnin` flag, not by guesswork.
- `emmi_backside` in **N2**, i.e. before GATE D1, because the package is `flipchip-bga`. On a
  wire-bond package the same technique would sit *behind* GATE D1; a plan that puts frontside
  EMMI before decap on a molded part is wrong.
- `tem_lamella` in the D2 phase, gated.
- A small-population sample plan (4 units): one archive, one sequence, remainder held — never
  all four through the same destructive step.
- Requests for the data that separates extrinsic from intrinsic: wafer-sort traceability for
  the three serials (common wafer? common reticle field?), and burn-in board position (is this
  a board/socket artifact rather than silicon?).

## What a wrong run looks like

- Naming CDM or handling ESD without first checking that the units passed final test.
- Running a thermal-stimulation technique (OBIRCH) as the primary localization on a leakage
  signature and then reporting "no defect found".
- Decapsulating a flip-chip package to reach the die face when backside access was available.
- Claiming a wearout (intrinsic) conclusion from 3 units — that is a population claim from a
  sample that cannot support one.
- Releasing the qualification on the grounds that "only 1.3% failed" without a mechanism.

## Grounding

Composed for this repository. Dielectric-wearout concepts and the soft/hard breakdown
progression follow general reliability-physics practice; JEDEC JEP122 is the public reference
for failure-mechanism models and JESD91-style methods for activation energies — cited by number
only, with no text reproduced and no numeric model parameters asserted here. Part numbers,
serials, dates and organizations are invented.
