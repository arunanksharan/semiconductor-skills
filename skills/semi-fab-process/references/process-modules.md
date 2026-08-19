# Per-module failure modes — signature, first checks, discriminating evidence

Generic, textbook-level mechanisms (the level of May & Spanos, *Fundamentals of Semiconductor
Manufacturing and Process Control*, and Wolf & Tauber, *Silicon Processing for the VLSI Era*;
named for orientation only, nothing reproduced). **No recipes, no tool-specific settings, no
BKMs** — those are fab property and belong in a private fork.

How to use: find the module, match the *signature* (what the data looks like), run the *first
checks* (cheap, non-destructive, mostly data you already have), then get the *discriminating
evidence* — the observation that separates the surviving hypotheses. Consistent evidence is
not the same as discriminating evidence.

Spatial signatures repeat across modules and are the fastest first cut:

| Within-wafer signature | Usually means |
|---|---|
| Edge ring / outer radius only | Clamp, edge purge/exclusion, chuck edge temperature, flow at the wafer edge, bevel |
| Centre spot / bullseye | Dispense, showerhead centre, gas injection, chuck centre temperature |
| Radial monotonic (centre→edge gradient) | Temperature profile, flow field, polish pressure profile, spin dynamics |
| Left/right or up/down asymmetry | Mechanical: tilt, levelling, alignment, single-side flow, wafer placement |
| Repeating field/shot pattern | Reticle, lens/scanner field, exposure |
| Streak / scratch / arc | Handling, robot, CMP pad/particle, backside contact |
| Random, no structure | Baseline defectivity or measurement noise — check the gauge before chasing the process |

---

## Litho (track + exposure)

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Dose drift | CD shifts uniformly across wafer and field, tracks exposure tool | Exposure dose log, source/lamp output trend, dose monitor wafers | CD vs. dose response (a dose-meter wafer or a dose FEM) reproduces the shift; other tools on the same reticle unaffected |
| Focus drift / defocus | CD shift plus profile change (footing, top rounding), worst at edges of the process window; CD vs. position within field | Focus/levelling logs, wafer flatness/backside particles, chuck cleanliness | Focus-exposure matrix (FEM) or a focus-monitor structure; the affected wafers sit off the Bossung apex |
| Overlay/alignment drift | Registration error with a systematic field or wafer signature (translation, rotation, magnification, higher order) | Overlay data by field/wafer term decomposition, alignment mark quality, chuck/backside cleanliness, reticle alignment | Term decomposition points at the mechanism: wafer-level translation → stage/chuck; field-level mag/rot → lens/reticle; radial → wafer distortion from prior steps |
| Resist thickness variation | CD and reflectivity vary radially or from centre; swing-curve behaviour | Track dispense volume, spin profile, resist temperature/viscosity, bottle/lot change, exhaust | Film-thickness map on a monitor wafer matches the CD map; a resist lot change lines up with the boundary |
| Scumming / incomplete develop | Residual resist in small features, low-yield opens after etch, CD low on dark features | Develop time/dispense, developer normality and temperature, PEB profile, resist age and lot | Cross-section or top-down SEM shows residue; changing develop parameters reproduces/removes it |
| Hotplate (PAB/PEB) non-uniformity | CD map mirrors the plate's thermal signature (zones, edge cool) or one plate in a bank differs | Plate temperature calibration record, per-plate CD split, plate zone logs | Split the same lot across plates: the CD map follows the plate, not the wafer or the exposure tool |
| Reticle defect / contamination | Same defect repeats at the same position in every field; CD error confined to one field-relative position | Reticle inspection history, pellicle condition, days since last reticle qual | Repeating-field wafer-map signature; the defect follows the reticle across exposure tools |
| Airborne contamination (amine) | T-topping / footing on chemically amplified resist, worst with long PEB delay | Filter change dates, delay-time (post-exposure delay) distribution, cleanroom work nearby | Profile changes with deliberate delay time; effect confined to one track/bay |

Litho rule: **CD after litho and CD after etch are different measurements.** If both moved by
the same amount, the cause is at or before litho. If only post-etch moved, litho is innocent.

---

## Etch

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Chamber-to-chamber mismatch | Step in the parameter for one chamber's lots only; commonality is chamber-clean | Last chamber match/qual date, part configuration differences, recipe rev per chamber | Monitor wafer, same recipe, same day, suspect vs. reference chamber (`chamber-matching.md`) |
| Uniformity drift (centre-to-edge) | Radial CD or depth gradient grows over time | Gas flow ratios and ranges, pressure control, chuck temperature zones, edge-part wear | Radial profile on a monitor wafer; compare zone-by-zone against the reference chamber |
| Polymer / by-product build-up on chamber walls | Slow drift in rate, selectivity, or profile between wet cleans; recovers at the clean | RF hours or wafer count since wet clean, drift slope vs. that counter | Parameter vs. hours-since-clean correlates and resets at the clean — a sawtooth in time |
| Endpoint detection drift | Etch time drifts; over- or under-etch; endpoint call scatters | Endpoint traces (signal amplitude, slope, call time), window/viewport transmission, algorithm thresholds | Endpoint call time trend by chamber; a dirty window reduces signal and delays the call while the process itself is unchanged |
| Chamber seasoning / conditioning after clean | Deviation right after a wet clean or part change, **decaying** over the first wafers/lots | Season recipe and count, first-lot-after-clean data across history | Deviation magnitude vs. wafer number after the clean: a decaying curve means seasoning; a flat step means something was changed or installed wrong |
| First-wafer effect | Wafer 1 of each lot differs; worse after long idle | CD/depth by slot position across many lots, idle-time distribution | The effect is locked to slot position and idle time, not to date — invisible unless you subgroup by wafer position |
| Consumable/part wear (focus ring, liner, electrode) | Slow drift correlating with RF hours; step at replacement | RF-hours counters, part replacement log, post-change qual criteria | Parameter vs. RF hours since replacement; a step at the replacement date with no decay |
| Selectivity loss / mask erosion | Profile and depth change together; CD grows with depth loss | Gas ratios, power, mask thickness before/after, over-etch time | Cross-section: mask corner faceting and sidewall angle change together |
| Arcing / RF instability | Sporadic wafer-level or lot-level outliers, sometimes particles | RF reflected power, matching-network position, chamber ground path | FDC trace of reflected power at the affected wafers correlates with the outliers |
| Loading effect (macro/micro) | Parameter depends on exposed area or feature density → product-dependent | Which products are affected, pattern density of affected layers | The deviation tracks the product/pattern density, not the chamber or the date |

---

## Deposition — CVD / PVD / ALD

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Thickness drift (all types) | Mean thickness walks; uniformity may hold | Rate vs. time-since-PM, precursor/target/source status, temperature and pressure trends | Rate per unit time or per cycle vs. the wear counter; a monitor wafer isolates chamber from product |
| PVD target erosion / end of life | Rate and uniformity drift together, accelerating late in life; arcing near end of life | Target kWh vs. rated life, arc counts, deposition rate trend | Rate vs. target kWh — the classic late-life curve; step recovery at target change |
| CVD precursor depletion / delivery | Rate drops, sometimes with a composition or stress change | Bubbler/ampoule level and temperature, carrier flow, line temperature (condensation), source lot change | Rate recovers on source replacement; effect spans all chambers sharing the source |
| ALD dose/purge insufficiency | Loss of self-limiting behaviour: growth per cycle changes with flow/time, conformality degrades | Dose and purge times, valve actuation counts, chamber pressure trace per cycle | Growth-per-cycle vs. dose time: a true ALD window is flat; a sloped response means starved dosing |
| Film stress shift | Wafer bow/warp change, downstream lithography overlay and yield effects, cracking or delamination | Bow/stress metrology trend, power/pressure/temperature, film composition | Stress vs. deposition parameter; correlate against the incoming bow to separate film stress from substrate |
| Chamber leak / virtual leak | Composition change (oxygen/nitrogen incorporation), resistivity or refractive-index shift, sometimes particles | Base pressure, rate-of-rise test, seal/O-ring service history, RGA if available | Rate-of-rise test after the boundary date; composition metrology (RI, XRF, resistivity) shows an oxidiser signature |
| Particles / flaking | Defect count steps up, often after a certain wafer count since clean; localised on wafer | Particle-monitor wafer counts vs. wafer count since clean, chamber kit condition | Particle count vs. wafers-since-clean; particle map matches a fixture/shield location |
| Temperature non-uniformity | Radial thickness or composition gradient | Heater zones, chuck contact/backside gas, pyrometer/thermocouple calibration | Thickness map matches the heater zone map; a lamp/zone failure produces a repeatable pattern |
| Backside/edge deposition | Edge exclusion changes, downstream chucking/handling problems | Edge purge flow, clamp/shield condition | Edge-ring signature on the wafer map; backside inspection |

---

## Implant

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Dose error | Sheet resistance (Rs) shifts uniformly; Vt shift downstream | Beam current and scan integration, dosimetry calibration, Faraday cup condition, charge neutralisation | Rs monitor wafer vs. the dose recipe; the dosimetry chain is the first thing to verify |
| Energy error | Junction depth changes with little Rs change (or vice versa); profile shape changes | Extraction/acceleration settings, analyser magnet calibration, energy contamination checks | SIMS or spreading-resistance profile shows depth shift; Rs alone cannot separate dose from energy |
| Tilt/twist error → channeling | Rs and depth shift on a specific crystal orientation; strong wafer-orientation dependence, sometimes notch-referenced pattern | Tilt/twist recipe values, wafer orientation/notch handling, platen mechanics | Deliberate tilt sweep reproduces the channeling sensitivity; the effect follows notch orientation |
| Beam non-uniformity / scan | Striping or banding on the wafer map, aligned with the scan axis | Scan waveform, beam profile measurement, uniformity monitor wafers | Rs map on a monitor wafer shows the scan-axis pattern |
| Wafer charging | Gate-oxide damage / antenna failures downstream; often no inline parametric signal at all | Neutralisation (electron flood) settings, beam current density, product antenna ratios | Charge-monitor (antenna) structures; damage scales with antenna ratio, not with Rs |
| Cross-contamination | Unexpected species in the profile, unexplained Rs or leakage change | Source/species change history on the implanter, cleaning between species | SIMS finds the contaminant species; effect follows the tool that ran the prior species |
| Photoresist outgassing/carbonisation | Dose loss under high current, resist strip difficulty | Beam current vs. resist type, pressure trace during implant | Effect scales with beam current density and resist thickness |

---

## CMP

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Dishing (wide features) | Recess in large metal/oxide areas; thickness loss is pattern-dependent | Pattern density map, over-polish time, pad hardness, slurry selectivity | Profilometry/AFM across features of different width: dishing scales with width |
| Erosion (dense arrays) | Thickness loss across dense arrays vs. surrounding field | Array density, polish time, selectivity | Step height between dense and isolated regions; scales with pattern density |
| Scratches | Linear/arc defects, often radial; downstream shorts or opens | Slurry filtration, agglomerates, pad condition, conditioner disc, foreign material | Defect map with directional linear defects; slurry particle-size distribution |
| Slurry health | Removal rate drift, defect increase | Slurry lot, age, mixing/dilution, pH, settling, temperature, delivery-line condition | Rate vs. slurry lot/age; a rate step at the lot change |
| Pad wear / glazing | Removal rate falls over pad life; uniformity degrades | Pad hours/wafer count, conditioning recipe, groove depth | Rate vs. pad life curve; recovery at pad change confirms it |
| Conditioner disc wear | Gradual rate loss that a pad change does *not* fix | Disc hours, sweep profile, down-force | Rate does not recover at pad change but does at disc change |
| Non-uniform removal (centre-fast / edge-fast) | Radial thickness gradient after polish | Down-force zone settings, retaining-ring wear, carrier membrane, back-pressure profile | Radial removal-rate map on a blanket monitor wafer; retaining-ring height measurement |
| Post-CMP residue / corrosion | Defects, resistance shifts, discoloration | Post-CMP clean chemistry and timing, queue time to next step | Queue-time correlation; defect chemistry (EDX) identifies residue vs. corrosion |

---

## Diffusion / oxidation / RTP

| Failure mode | Typical signature | First checks | Discriminating evidence |
|---|---|---|---|
| Furnace temperature profile error | Thickness/Rs varies by boat position (top/centre/bottom of the load) | Profile/calibration record, thermocouple drift, zone offsets, load size | Split a monitor load across positions: the signature follows boat position |
| RTP temperature error | Wafer-to-wafer thickness or Rs shift; no boat-position structure | Pyrometer calibration, emissivity assumptions (backside films change emissivity!), lamp condition, reflector cleanliness | Same recipe on wafers with different backside films behaves differently → emissivity/pyrometry, not the process |
| Ramp-rate / spike control | Junction/diffusion depth changes with the same setpoint temperature | Ramp profile logs, overshoot, cooldown rate | Thermal budget reconstruction from the trace; SIMS depth shift with matched peak temperature |
| Ambient/gas purity | Oxidation rate change, unexpected film growth, contamination | Gas lines and purifiers, O2/H2O leaks, N2 purity, source-lot change | Rate-of-rise / leak check; growth on a blanket monitor wafer vs. expected model |
| Contamination (metals, mobile ions) | Reliability/leakage failures with clean inline parameters | Cleanliness of quartz/boat, prior species, cross-tool contamination | C-V (mobile-ion) monitors, lifetime measurements; inline thickness will not see this |
| Loading / depletion in the tube | Rate depends on load size and position | Load configuration, dummy-wafer policy | Rate vs. load size on monitor wafers |

---

## Cross-module discriminators worth remembering

- **Does the deviation follow the chamber, the date, the product, the wafer slot, or the
  measurement tool?** Each answer points at a different family of causes, and the data to
  answer it usually already exists in the history file.
- **Does it decay, step, or ramp?** Decay → seasoning/conditioning. Step → a discrete change
  (part, recipe, cal, software). Ramp → wear/depletion/contamination build-up.
- **Does it reset at a maintenance event?** If yes, the mechanism is tied to that event's
  counter (hours since clean, wafers since PM, target kWh, pad life) and the fix is usually the
  interval or the requal criterion, not the hardware.
- **Is it pattern-dependent?** Then it is a loading/density effect and it will re-appear on the
  next product with different density, no matter what you do to the chamber.
