# Assembly defect catalog — mechanism → detection → usual suspects

Per assembly step: what goes wrong, how it's found, and the first three knobs to check.
"Usual suspects" are ordered by hit-rate in practice; always confirm with data, never assert
a cause without the corresponding evidence.

## 1. Incoming wafer / backgrind / wafer mount

| Defect | Mechanism | Detection | Usual suspects (in order) |
|---|---|---|---|
| TTV out of spec | Uneven grind, chuck contamination | Thickness map / profilometry | Grind wheel wear · chuck cleanliness · tape thickness variation |
| Backside scratches / grind marks too deep | Wheel grit too coarse for final thickness, coolant starvation | Backside visual, die strength drop | Wheel grit sequence · coolant flow · feed rate |
| Wafer bow/warp | Stress mismatch after thinning (thick backside films, TSV wafers) | Bow gauge | Film stack stress · grind depth vs stress relief (CMP/polish/etch) step missing |
| Edge chipping at mount | Handling of thinned wafer | Edge microscope scan | End-effector contact · tape mounter alignment |

Edge case — **thin die (<100 µm)**: die strength is the leading indicator, not visual. Add
3-point-bend/die-strength SPC at backgrind; a strength drop precedes field TC cracks by weeks.

## 2. Dicing (blade / laser / plasma)

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| Front-side chipping | Blade impact on brittle stack | Die-edge microscope (sample every strip) | Blade wear/dressing · spindle RPM vs feed · street width/test structures in street |
| Backside chipping (BSC) | Exit-side fracture | Backside die-edge inspection | Blade exposure · tape adhesion · feed rate |
| Sidewall/subsurface cracks | Micro-crack propagation later under TC | Die strength, x-section, TC readpoint fails clustered at die edge | Same as chipping + depth-of-cut steps |
| Low-k layer peeling/delam at street | Weak ULK fracture toughness | Edge inspection, C-SAM at die corners after stress | Missing laser groove pass · blade type (use laser groove + blade, or plasma) · street layout |
| Die attach film (DAF) burrs/strings | DAF not fully cut | Visual under die, die-attach tilt | Blade/DAF match · tape/DAF temperature |

Blade vs laser vs plasma: blade = cheapest, chips brittle films; laser groove first = standard
for low-k; full laser = heat-affected zone (HAZ) → strength; plasma = best edge strength +
kerf-free layouts, but needs compatible mask/street design and no metal in street.

## 3. Die attach

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| Voiding (epoxy) | Air entrapment, solvent outgassing | X-ray (% area), C-SAM | Dispense pattern (writing style) · epoxy age/thaw log (freezer discipline!) · cure ramp too fast |
| Voiding (solder/sinter DA) | Flux outgassing, oxidation, pressure profile | X-ray | Atmosphere (formic/N2) · paste age · ramp & pressure profile |
| Die tilt | Uneven bond force / dispense | X-section, shadow gauge, C-SAM focus shift | Bond tool planarity · dispense volume/pattern · placement force |
| BLT out of spec | Wrong volume/force | X-section (destructive sample) | Dispense calibration · die placement force/dwell |
| Resin bleed | Low-viscosity component migrates over pad | Visual/UV, wire bond NSOP downstream | Epoxy formulation/age · leadframe surface energy (plasma clean missing) · time-before-cure |
| Non-conductive DA where conductive needed (or wrong material lot) | Logistics error | Electrical (RDS/thermal), traceability audit | Material lot control at kitting |

Rule of thumb specs (*use device spec when it exists*): total void ≤10–20 % of pad, single
void ≤5–10 %; thermal/power products sit at the tight end. Voiding directly under hot spots
matters more than average % — report location, not just area.

## 4. Wire bond (Au, Cu, Pd-coated Cu (PCC), Ag alloy)

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| NSOP / NSOL (non-stick on pad/lead) | Contamination or bad parameters | Bonder NSOP counters, pull test | Pad contamination (resin bleed, Al oxide, F residue from fab) · plasma clean recipe · US power/force/time |
| Ball lift (interface separation) | Weak IMC coverage | Ball shear (JESD22-B116) low + interfacial failure mode | Bond parameters (IMC coverage %) · pad metal stack/thickness · contamination |
| Cratering (Si/ILD damage under pad) | Excess ultrasonic/force, hard Cu ball | Pull/shear with crater inspection, pad x-section | US energy too high · Cu free-air-ball hardness (EFO settings) · pad stack (thin Al, weak ILD, bond-over-active design) |
| Wire sweep | Mold flow drag | X-ray (sweep % = deflection/span) | Long/low loops · mold transfer speed · compound viscosity (expired/pre-floored compound) |
| Sagging/leaning wires, wire-to-wire shorts | Loop profile vs density | X-ray, electrical shorts | Loop recipe · wire diameter vs span (rule: span/diameter ≤ ~for the wire type; check OSAT rule) |
| Heel crack (2nd bond) | Over-deformation, vibration | Pull test low @ heel break, SEM | Stitch parameters · capillary wear · leadframe plating |
| Au-Al IMC / Kirkendall voiding | High-temp aging growth of intermetallics | HTSL readpoint pull tests, x-section color bands | Junction temp vs mission profile · Br-containing mold compound (halide attack) |
| Cu-Al pad corrosion under bias+humidity | Cl⁻-driven galvanic attack of IMC | HAST/uHAST fails, EDX at bond | Mold compound Cl content · HAST duration · PCC vs bare Cu choice |

Cu vs Au tradeoffs: Cu = cheaper, better electrical/thermal, stiffer (crater risk, needs
tighter window, inert kerf gas), corrosion-sensitive IMC (halides). PCC narrows the gap
(oxidation control, wider window) at small cost premium. Au = widest process window, IMC
aging at high temp is the long-term limiter. Automotive Cu-wire programs live and die on
mold-compound ionic purity + biased HAST data.

## 5. Flip-chip attach + underfill

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| Non-wet / HIP (head-in-pillow) | Warpage separates bump & paste during reflow | X-ray (subtle), dye-and-pry, electrical opens | Dynamic warpage (die/substrate) · paste activity · profile (soak vs ramp) |
| Bump voids | Flux outgassing | X-ray % area | Flux type/volume · reflow atmosphere |
| Underfill voids | Flow front merge, dispense pattern | C-SAM | Dispense pattern (L vs I) · die standoff/pitch vs filler size · plasma clean before UF |
| Incomplete fillet / UF on die top | Volume/keep-out control | Visual, C-SAM | Dispense volume calibration · substrate solder mask topology |
| Die-corner ULK delam ("white bump" family) | CTE stress focused at corner bumps | C-SAM at corners after TC precon, x-section | UF Tg/CTE choice · corner bump layout · die edge quality from dicing |
| Filler settling / UF-die delam | Cure profile, moisture at interface | C-SAM (post-precon) | Bake-before-UF (substrate moisture) · cure schedule · UF pot life |

## 6. Mold

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| Incomplete fill / knit lines | Flow imbalance, gel time too short | Visual, C-SAM | Compound expiry/storage (freezer→floor life) · transfer profile · vent blockage |
| Internal voids | Trapped air | C-SAM, X-ray | Transfer speed/pressure · tablet preheat · vent design |
| Mold–die / mold–pad delam | Adhesion loss, contamination, moisture | **C-SAM (the tool for this)** | Leadframe oxidation/plating · plasma clean before mold · compound adhesion grade · epoxy bleed footprint |
| Flash on pads/leads | Tool wear, clamping | Visual, solderability fail | Mold tool maintenance · compound flow |
| Wire sweep | (see §4) | X-ray | — |

## 7. Ball attach / lead finish / singulation / final

| Defect | Mechanism | Detection | Usual suspects |
|---|---|---|---|
| Missing/bridged balls | Placement/reflow | AOI, X-ray | Flux print · ball placement tool · stencil condition |
| Ball voids | Flux outgassing | X-ray | Flux volume · reflow profile |
| Coplanarity fail | Substrate/package warpage | Coplanarity scanner | Warpage (compound/substrate balance) · ball volume uniformity |
| Poor solderability / black pad (ENIG) | Plating chemistry (hyper-corroded Ni) | J-STD-002 test, brittle joint fractures | ENIG bath control at substrate supplier · storage life/humidity |
| Singulation burrs, chipouts | Saw wear | AOI | Blade condition · feed |
| Bent leads / handling | Trim-form, trays | Visual, coplanarity | Tooling wear · tray fit |

## Triage discipline (applies to every row above)

1. Confirm the measurement before the mechanism (calibrated? artifact? one image ≠ trend).
2. Commonality first: machine · material lot/date-code · time window · operator · tool ID.
   A defect that follows a material date-code is a material problem regardless of which
   machine flagged it.
3. Containment (traceability quarantine) is a separate sentence from root cause. Always
   state both.
4. Reliability-interface defects (die attach, underfill, mold adhesion) cannot be
   dispositioned visually — sample precon + C-SAM before shipping "reworked/screened" lots.
5. Close the loop: which upstream control (SPC chart, incoming inspection, maintenance item)
   should have caught it, and file that action with the 8D (see `semi-failure-analysis`
   skill for the 8D format).
