# FA technique matrix — what each tool buys, what it costs, what it destroys

Load this when choosing techniques, when reviewing `scripts/technique_selector.py` output, or
when explaining to a requester why a step comes before another. The ordering law of this skill:
**information-preserving before information-destroying, cheap before expensive, localize before
you cut.** A technique that is out of order is not merely inefficient — it deletes evidence the
later techniques needed.

Technique IDs below are the exact strings `scripts/technique_selector.py` emits, so a plan can
be read against this table row by row.

---

## Legend

- **Destructive?** — `ND` non-destructive (unit survives, re-testable) · `ND*` non-destructive
  to the die but alters the sample (backside thinning, lid removal, board de-solder) · `D`
  destructive (unit is consumed or permanently altered) · `D-term` terminal (the sample is gone
  after this; nothing further can be run on that unit).
- **Cost** — relative, 1 (bench-cheap, in-house, minutes) to 5 (specialist lab, days, high
  per-sample fee). Not currency: cost ratios move with region, in-house vs outsourced, and
  whether the tool is idle. Treat as ordering, not budgeting.
- **Turnaround** — typical elapsed time for one unit assuming the tool is available. Queue time
  at a shared or external lab usually dominates and is not included. All figures are
  industry-typical rough ranges to be replaced with your lab's actual quotes. `TODO(verify)`
  against your own lab's service-level data before quoting to a customer.

---

## Phase N0 — Electrical characterization and records (always first, always all of it)

| ID | Technique | What it reveals | Destructive? | Prerequisites | Cost | Turnaround |
|---|---|---|---|---|---|---|
| `external_visual` | Optical/stereo microscope of the as-received part | Burn marks, cracked package, bent/corroded leads, rework evidence, marking/date code, board damage | ND | Nothing. Do it before touching anything else | 1 | minutes |
| `datalog_review` | Re-analysis of the ATE datalog | First-failing test, bin, measured vs limit, margin, test order | ND | Full datalog (not stop-on-first-fail) · program rev | 1 | minutes–hours |
| `retest_matrix` | Structured re-insertion under logged conditions | Reproducibility; separates real from test-induced | ND | Same program rev the requester used | 1 | hours |
| `contact_elimination` | Retest on a different socket/contactor/tester, cleaned leads, gentle lead press | Kills most "intermittents" — proves contact vs silicon | ND | ≥2 sockets or testers | 1 | hours |
| `curve_trace` | Pin-by-pin I-V (curve tracer / SMU) vs a known-good unit | Shorts, opens, leakage, degraded/blown ESD protection diodes, asymmetric vs symmetric damage | ND | Known-good reference unit · pinout · current compliance set low | 1 | hours |
| `shmoo` | Pass/fail region across V, T, frequency | Marginality shape; which parameter the failure tracks | ND | ATE time · known-good Shmoo on the same setup | 2 | hours–1 day |
| `bin_signature_analysis` | Population/bin/spatial statistics (`scripts/bin_signature.py`) | Event vs process prior; clustering; failing-test commonality | ND | die_results.csv (± tests.csv) | 1 | minutes |
| `burnin_delta_review` | Pre- vs post-burn-in datalog comparison | Which units moved, which test moved, direction and magnitude | ND | Both datalogs for the same serials | 1 | hours |
| `in_situ_tc_monitoring` | Continuous resistance/functional monitoring through thermal cycling or vibration | Converts an intermittent into a reproducible, pin-localized failure | ND | Chamber · monitoring fixture · time (days) | 3 | days–weeks |

**N0 judgment.** `curve_trace` against a known-good unit is the single highest information-per-
dollar step in the whole flow and it is skipped constantly. It separates short from open from
leakage, tells you whether the damage is on a protection device or on the core, and often names
the pin before any imaging. Set compliance current low — a curve trace at high compliance is
itself an EOS event and will rewrite the evidence you came to read (see
`esd-eos-discrimination.md`).

Never accept a stop-on-first-fail datalog as the whole electrical picture. A continuity/open-
short test running early can mask the real signature; ask for a full-datalog retest.

---

## Phase N1 — Package-level imaging (non-destructive, do before opening anything)

| ID | Technique | What it reveals | Destructive? | Prerequisites | Cost | Turnaround |
|---|---|---|---|---|---|---|
| `xray_2d` | 2D transmission X-ray | Wire sweep/breaks/shorts, ball and bump voids, solder-joint bridging/opens, die-attach voids, missing/lifted wires, foreign metal | ND | Package with density contrast; weak on organics | 2 | < 1 day |
| `xray_ct` | Computed tomography (3D) | Same features resolved in 3D — a joint that looks fine in one projection, crack planes, stacked-die and interposer detail | ND | Small ROI · long scan · reconstruction time | 3 | 1–3 days |
| `csam` | C-mode scanning acoustic microscopy (C-SAM/SAT) | Delamination at every interface, popcorn cracks, die-attach voids, mold voids, die-face separation | ND | Immersion in DI water · package must tolerate wetting · dry the part after | 2 | < 1 day |
| `hermeticity_pind` | Fine/gross leak plus particle impact noise detection | Seal integrity and loose conductive particles in cavity packages | ND | Cavity/hermetic package only (ceramic, metal can) | 2 | < 1 day |
| `tdr` | Time-domain reflectometry | Distance-to-fault along a net: open or impedance discontinuity in substrate trace, ball, bump, or wire | ND | Controlled-impedance access · reference net · known-good comparison | 2 | < 1 day |
| `magnetic_current_imaging` | SQUID / GMR magnetic field imaging of current paths | Traces the actual current path through an encapsulated package; finds shorts under the die or in the substrate without opening | ND | Specialist lab · biasable short | 4 | days |

**N1 judgment — the order that matters most in the whole skill.** `csam` must precede any
decapsulation, bake, or aggressive drying. Decap chemistry, laser decap heat, and the hot plate
all create or heal the delamination you were sent to find; once the mold compound is opened the
moisture and interface history is unrecoverable. If the case has any reflow, MSL, moisture, or
"failed after board assembly" flavour, C-SAM is mandatory and it is mandatory *first*. The same
logic bans a pre-analysis bake: baking a returned unit erases its moisture state.

`xray_2d` is nearly free and nearly always worth it, but it is a projection: a crack whose plane
lies along the beam is invisible, and a void seen at one angle may be a superposition. When a 2D
image drives an expensive decision, confirm with `xray_ct` or a second projection angle.

`magnetic_current_imaging` is the underused option when the part must stay intact — a customer
return with N=1 and a hard short is the case that justifies its cost.

---

## Phase N2 — Localization without opening the package

| ID | Technique | What it reveals | Destructive? | Prerequisites | Cost | Turnaround |
|---|---|---|---|---|---|---|
| `lock_in_thermography` | Lock-in IR thermography (LIT) | Sub-milliwatt hot spots located through mold compound or from the backside; excellent for shorts and leakage paths | ND | Biasable failure · modulated stimulus · IR-transparent path or thin package | 3 | < 1 day |
| `emmi_backside` | Photoemission microscopy through the thinned silicon backside | Light-emitting sites: junction leakage, gate-oxide breakdown, forward-biased junctions, saturated transistors | ND* | Flip-chip or backside access · silicon thinning + polish · NIR-capable detector | 4 | 1–3 days |
| `obirch_backside` | OBIRCH / thermal laser stimulation from the backside | Resistive anomalies: high-resistance vias, voided lines, marginal contacts — the defects that emit no light | ND* | Same access as above · biasable, current-monitorable failure | 4 | 1–3 days |

**N2 judgment.** Emission (`emmi_*`) finds *light*: leakage and junction sites. Thermal
stimulation (`obirch_*`, `lock_in_thermography`) finds *resistance change*: opens, voids, weak
contacts. A resistive open is invisible to EMMI and a clean junction leak is weak in OBIRCH —
choosing the wrong one and concluding "no defect found" is a classic wasted week. Run the one
that matches the electrical signature from `curve_trace`: leakage/short → emission first;
open/resistive/speed → thermal first.

Access decides the phase. On flip-chip and WLCSP the die backside faces up and these are
genuinely near-non-destructive (`ND*` covers the thinning). On a wire-bonded plastic package the
die face is buried, so photoemission and OBIRCH only become available **after** decap — meaning
they move behind GATE D1 and stop being cheap. The selector script reflects this; if you see
EMMI listed before decap for a molded wire-bond part, the plan is wrong.

---

## GATE D1 — before any package is opened

All five must be satisfied and stated in writing. The gate is defined in `SKILL.md` Step 5; the
technique-specific content of the gate is:

1. Every applicable N0–N2 technique above is either done and logged, or explicitly ruled
   inapplicable with a reason.
2. `csam` (molded/laminate packages) and `xray_2d` are complete — decap destroys what they see.
3. The hypothesis table names which hypothesis decap discriminates, with a pre-registered
   expectation per surviving hypothesis.
4. Sample allocation is stated: which serial is being consumed, which is archived.
5. Explicit user confirmation in the conversation, having been shown: units consumed,
   information gained, information destroyed, and the no-go alternative.

---

## Phase D1 — Decapsulation and die-level access

| ID | Technique | What it reveals | Destructive? | Prerequisites | Cost | Turnaround |
|---|---|---|---|---|---|---|
| `lid_removal` | Controlled removal of a hermetic lid (mechanical or thermal) | Cavity interior, die face, wires, and any loose particles, all intact | `ND*` | Ceramic/metal-can cavity package only · hermeticity and PIND must be complete first, because this voids the seal permanently | 2 | hours |
| `decap_chemical` | Wet acid etch (fuming nitric/sulfuric) of mold compound | Exposes die face and wires for optical and emission work | D | Fume hood · acid-compatible package · Cu wires and Al pads attack easily — parameter control is the whole game | 2 | hours |
| `decap_plasma` | Plasma/RIE removal of mold compound | Gentler on Cu wire, Ag, and thin pad metal; preserves bond interfaces | D | Plasma asher · longer cycle time | 3 | hours–1 day |
| `decap_laser_assisted` | Laser ablation of a cavity, then a short chemical or plasma finish | Fast local access, controllable window | D | Laser decap tool · heat-affected zone risk near the die | 3 | hours |
| `internal_optical` | High-magnification optical inspection of the exposed die and wires | Melt sites, cratering, corrosion, lifted balls, foreign material, passivation damage, mask-level anomalies | D (post-decap) | Successful decap · clean die surface | 1 | hours |
| `emmi_frontside` | Photoemission on the exposed die | Same as `emmi_backside`, from the front | D (post-decap) | Decap that preserved bonding · biasable failure | 3 | 1 day |
| `obirch_frontside` | OBIRCH / thermal laser stimulation on the exposed die | Resistive anomalies on the exposed die | D (post-decap) | As above | 3 | 1 day |
| `pvc_sem` | Passive voltage contrast in SEM | Floating vs grounded nets seen as brightness contrast — finds opens and shorts fast over a whole array | D | Decapped (often delayered) die · SEM time | 3 | 1 day |
| `wire_pull_ball_shear` | Destructive bond-strength testing with failure-mode classification | Bond integrity and the *mode* of failure (lift at pad, heel break, cratering, neck break) — the mode is the diagnosis, not the number | D | Decapped part · JESD22-B116-style ball shear and wire pull method definitions | 2 | hours |

**D1 judgment.** Choose the decap chemistry from the wire and pad metallurgy, not from habit.
Aggressive acid decap on a Cu-wire, Al-pad device dissolves the very interface that a suspected
NSOP or intermetallic case depends on; plasma or laser-assisted decap costs more and takes
longer but keeps the interface intact. State the decap method in the report — a reviewer cannot
judge an interface photo without knowing what removed the compound.

`pvc_sem` deserves more use than it gets: it is fast, it screens a large area, and it answers
"is this net floating?" directly, which is exactly the question a resistive-open hypothesis
poses.

Destructive bond-strength testing (`wire_pull_ball_shear`) is population evidence, not
single-unit evidence. Running it on the only failing unit destroys the very bond you wanted to
cross-section. Do it on siblings, not on the subject.

---

## GATE D2 — before any cutting, milling, or delayering

Same five checks as GATE D1, plus the one that matters: **the cut plane must come from a
localized site** — from `emmi_*`, `obirch_*`, `lock_in_thermography`, `pvc_sem`,
`magnetic_current_imaging`, or an unambiguous optical/X-ray feature. A cross-section through an
unlocalized die is evidence destruction with a photograph attached. If nothing localized,
the honest next step is another localization technique, not a cut.

---

## Phase D2 — Physical sectioning and analytical microscopy (terminal)

| ID | Technique | What it reveals | Destructive? | Prerequisites | Cost | Turnaround |
|---|---|---|---|---|---|---|
| `mechanical_cross_section` | Mount, grind, polish to a target plane | Package-scale structure: solder joints, wire bonds, die attach, delamination cross-section, die cracks | D-term | Target plane chosen in advance · mounting and polish skill · deprocessing rig | 2 | 1–2 days |
| `fib_cross_section` | Focused ion beam site-specific cut (± SEM imaging in situ) | Nanoscale structure at an exact localized site: via voids, oxide breakdown site, EM void, contact defect | D-term | A site localized to ~µm · FIB time · Pt/C protective deposition | 4 | 1–3 days |
| `sem_edx` | SEM imaging plus energy-dispersive X-ray spectroscopy | Morphology plus elemental composition — corrosion products, halogens, foreign material, IMC phases, migrated metal | D-term (on a prepared sample) | Prepared surface · conductive coating for insulators (record it, it adds peaks) | 2 | 1 day |
| `delayering` | Sequential removal of metal/dielectric layers, imaged between layers | Which layer holds the defect; buried shorts and opens; layout comparison against a reference die | D-term | Reference die or layout · deprocessing chemistry per stack | 4 | days |
| `nanoprobing` | Nanoprobes landed on contacts/vias of a deprocessed die | Transistor- and net-level electrical characterization of the suspect device itself | D-term | Deprocessed to the probing layer · layout/netlist · specialist tool | 5 | days |
| `tem_lamella` | FIB-prepared thin lamella imaged in TEM (± EELS/EDX) | Atomic-scale: gate-oxide thickness and breakdown path, IMC layer structure, Kirkendall void morphology, thin-film interfaces | D-term | A site already localized by FIB · lamella prep skill | 5 | 3–7 days |
| `dye_and_pry` | Dye penetrant applied, part pried off the board, fracture surfaces inspected | Which solder joints were cracked *before* the pry, and how far the crack ran | D-term | Board-mounted part · dye cure time · this is the board-level answer, not the die-level one | 2 | 1–2 days |

**D2 judgment.** `fib_cross_section` beats `mechanical_cross_section` when the site is localized
to a micron and the sample is scarce: it consumes almost no material, so the rest of the die
stays available. Mechanical sectioning wins for package-scale features (solder joints, die
attach, mold cracks) where the feature is large and the FIB's field of view is a liability.

`sem_edx` is the workhorse for corrosion, contamination, and IMC questions, and it is also the
most over-interpreted: EDX gives you elements present in an interaction volume, not a
stoichiometry you can quote, and light elements are unreliable. Report "Cl detected at the bond
interface, absent on the reference" — not a compound formula, unless a technique that can
support one was used.

`dye_and_pry` answers a *board-level* question and should not be run on a part whose die-level
mechanism is still open — the pry destroys the package. Sequence it after die-level work, or
run it on a sibling.

---

## Ordering shortcuts by electrical signature

Read this with `curve_trace` results in hand.

| Signature from N0 | Fastest discriminating path | Techniques, in order |
|---|---|---|
| Hard short, one pin to a rail | Find the current path before opening | `curve_trace` → `xray_2d` → `lock_in_thermography` or `magnetic_current_imaging` → GATE D1 → `decap_*` → `emmi_frontside` → GATE D2 → `fib_cross_section` |
| Open on one pin, others fine | Interconnect first, silicon last | `curve_trace` → `xray_2d`/`xray_ct` → `tdr` → GATE D1 → `decap_*` → `internal_optical` → GATE D2 → `mechanical_cross_section` |
| Elevated leakage on I/O pins | Emission before anything mechanical | `curve_trace` → `bin_signature_analysis` → `csam` → GATE D1 → `decap_plasma` → `emmi_frontside` → GATE D2 → `fib_cross_section` + `tem_lamella` |
| Functional fail, no DC anomaly | Localize by stimulation, not by cutting | `shmoo` → `datalog_review` → `obirch_backside`/`lock_in_thermography` → GATE D1 → `pvc_sem` → GATE D2 → `nanoprobing` |
| Speed/timing fail only at V/T corner | Marginality is a parametric story | `shmoo` vs known-good → `burnin_delta_review` → `obirch_*` → GATE D2 → `nanoprobing` |
| Intermittent, mechanically sensitive | Reproduce before you cut | `contact_elimination` → `in_situ_tc_monitoring` → `xray_ct` → GATE D1 → `decap_plasma` → `internal_optical` → `wire_pull_ball_shear` on siblings |
| Failed only after board reflow | Moisture and interfaces first, and C-SAM before all | `csam` → `xray_2d` → `curve_trace` → GATE D1 → `decap_*` → `internal_optical` → GATE D2 → `mechanical_cross_section` |

---

## Package-type applicability

| Package | Notable constraints |
|---|---|
| Wire-bond plastic (QFN/QFP/SOIC) | Die face buried → `emmi_*`/`obirch_*` only post-decap · `csam` and `xray_2d` both high value · chemical vs plasma decap decided by wire metal |
| Wire-bond BGA (PBGA) | Add substrate-level faults: `tdr` and `xray_ct` earn their keep · `csam` sees substrate and die-attach delamination |
| Flip-chip BGA | Backside `emmi`/`obirch` available without decap (thin + polish) · bump and underfill faults need `xray_ct` and `csam` · lid removal is `ND*` |
| WLCSP | No mold to remove; backside access trivial · board-level solder and die-corner cracking dominate · `dye_and_pry` often the decisive step |
| Ceramic hermetic | `hermeticity_pind` applies and nothing else does it · lid removal is controlled and near-reversible · `csam` mostly not applicable |
| Bare die / KGD | Everything is already exposed; handling damage is the leading test-induced artifact |
| Module / SiP | Multiple dies and passives: isolate *which* component fails before any die-level work · `xray_ct` first · treat as a board-level problem until proven otherwise |

---

## When a technique returns nothing

A null result is a result and belongs in the report (`report-templates.md`). But before writing
"no anomaly found", check the three ways a null result is an artifact:

1. **Wrong physics.** Emission technique on a resistive open; thermal technique on a µA junction
   leak; C-SAM on a package with no acoustic contrast at the interface of interest.
2. **Wrong bias state.** The defect only conducts in a state you did not apply. Re-run under the
   condition where the ATE program actually failed, not at a convenient static bias.
3. **Wrong sample.** The unit was already recovered by a retest, or the destructive step landed
   on the archive unit rather than the failing one. Check serials against the custody log.

Only after those three is "no defect detected by this technique" a finding — and then it is a
real one that can retire a hypothesis in the Step 4 table.

---

*Grounding: technique capabilities and ordering reflect general FA practice as described in the
EDFAS community literature and vendor application notes, and JEDEC/ESDA method numbers are cited
by number only. No standard or desk-reference text is reproduced. Cost and turnaround columns
are ordering heuristics, not quotations — replace with your lab's actuals before committing to a
customer schedule.*
