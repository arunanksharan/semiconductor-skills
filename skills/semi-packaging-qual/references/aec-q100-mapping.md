# AEC-Q100 mapping — grades, condition deltas, and what AEC adds beyond package qual

Own-words digest for planning. **AEC-Q100 is free to download (aecouncil.com) and its tables
move between revisions.** Everything numeric below is an industry-typical template. The
generator (`scripts/qual_plan.py`) emits the same values with a per-row `verify` string —
confirm the grade column against a current copy before a build is committed.

Anything this file could not verify is marked **TODO** rather than asserted. That is
deliberate: a wrong cycle count in an automotive plan is expensive, and a confident-sounding
wrong number is worse than an explicit gap.

## 1. Grades = ambient operating temperature, not "how good the part is"

| Grade | Ambient operating range | Typical placement |
|---|---|---|
| 0 | −40 to +150 °C | On-engine, transmission, exhaust-adjacent |
| 1 | −40 to +125 °C | Under-hood, near-engine-bay modules |
| 2 | −40 to +105 °C | Passenger-compartment power electronics |
| 3 | −40 to +85 °C | Cabin electronics, infotainment |
| 4 | 0 to +70 °C | Rare in practice; effectively consumer-in-a-car |

The grade sets the **ambient**, and the ambient plus the device's own dissipation sets Tj.
Two devices at the same grade with different power can need different HTSL temperatures —
grade alone never finishes the argument.

## 2. What escalates with grade (the shape, not the exact table)

| Stress | Direction as grade number falls (3 → 0) | Encoded default in `qual_plan.py` |
|---|---|---|
| Temperature cycling | Wider swing, more cycles | Grade 3: −40/+125, 1000 cyc · Grades 2/1: −55/+125, 1000 cyc · Grade 0: −65/+150, 2000 cyc |
| HTSL | Higher temperature | Grades 3–1: 150 °C/1000 h · Grade 0: 175 °C/1000 h |
| Biased HAST / uHAST | Roughly constant (moisture, not temperature, drives it) | 130 °C/85 %RH, 96 h at every grade |
| THB | Constant | 85/85, 1000 h |
| Power temperature cycling | Required across automotive grades | 1000 cycles, marked conditional |
| Lots | 3 non-consecutive at every grade | Enforced as a floor, even for derivatives |

**TODO — verify before use:** the exact AEC letter conditions and cycle counts per grade
(the current revision's package-integrity table). Several houses run grade 1 at −50/+150 °C
rather than −55/+125 °C; the generator's `verify` string says so on the TC row. Also confirm
whether the current revision states 1000 or 2000 TC cycles per grade — `qual_plan.py`
extends to 2000 only for *new package families*, as a house rule, and labels it as one.

## 3. What AEC adds that a JEDEC package qual does not

A JESD47-style plan qualifies the *package*. AEC-Q100 qualifies the *product*, so an
automotive programme carries a second body of work this skill deliberately declares out of
scope rather than silently omitting:

| Area | Examples | Owner |
|---|---|---|
| Die-level life | HTOL (JESD22-A108), ELFR (AEC-Q100-008) | Product/reliability team, not package |
| ESD & latch-up | HBM / CDM (JS-001, JS-002), latch-up (AEC-Q100-004) | Design/IO team |
| Electrical characterisation | Full parametric over the grade's temperature range | Test/product engineering |
| Defect avoidance | PPAP, control plans, zero-defect programmes, 8D discipline | Quality |
| Change control | Any change to a qualified part re-enters the flow | Quality + customer |

`qual_plan.py` emits these in an explicit `out_of_scope` block. Keep that block in every
automotive plan you hand over — an omission that is *stated* is a scope boundary; an omission
that is silent is a gap the customer finds during PPAP.

## 4. Lot discipline

- **3 non-consecutive assembly lots** is the automotive expectation, and `qual_plan.py`
  applies it as a floor even when the novelty is `derivative`. Non-consecutive matters:
  three lots run back-to-back on one shift share their material and setup, so they are one
  lot wearing three labels.
- Generic/family data can be leveraged with a documented similarity argument, but any
  reduction below 3 lots needs the customer's written agreement — not an engineer's
  judgement call recorded in a slide.
- Similarity is **disallowed** on any of the triggers listed in SKILL.md Workflow 3 step 5
  (new mold compound or die attach, new site, die-to-pad ratio outside the envelope, finer
  wire/ball pitch, new metallurgy, thinner die). Automotive customers audit this list.

## 5. Package-family notes that bite in automotive specifically

- **QFN/DFN** — the cut-copper lead flank does not wet, so the customer's AOI cannot see a
  fillet. Wettable-flank terminals exist for exactly this reason. Add a board-level
  solder-void X-ray limit for the exposed pad; the thermal spec depends on it.
- **Cu / Pd-coated-Cu wire on Al pads** — the automotive failure mode is halide-driven IMC
  corrosion under bias and humidity. Biased HAST is the leg that finds it. Mold-compound
  ionic purity data belongs in the qual package, not just the test results.
- **Au wire at grade 0/1** — Au-Al IMC growth and Kirkendall voiding at 150–175 °C. Pull and
  shear at HTSL *readpoints*, not only at end of life.
- **Large-body BGA in a vibration environment** — component-level TC is not the binding
  constraint; board-level solder fatigue plus vibration is. Qualify against the customer's
  real board.
- **Exposed-pad power devices** — power temperature cycling reproduces the thermal gradient
  that passive TC cannot. Track RthJC drift, not only electrical pass/fail.

## 6. Mission-profile tailoring (when the defaults are the wrong question)

JESD94 covers knowledge-based/mission-profile qualification: instead of running the table,
derive the required stress from the field profile (temperature histogram, power-on hours,
key-cycle count) with an agreed acceleration model (Coffin-Manson for thermal fatigue,
Arrhenius for diffusion-driven mechanisms, Peck for humidity).

Use it when the default table is clearly mismatched — e.g. a part that sees 60 000 key cycles
of small ΔT rather than 1000 cycles of −55/+125 °C. Two rules:

1. Agree the model and its parameters **in writing with the customer before the build**.
   A retro-fitted acceleration factor is a negotiating position, not data.
2. State the field profile the plan is derived from in the plan itself. A tailored plan
   without its profile is unauditable.
