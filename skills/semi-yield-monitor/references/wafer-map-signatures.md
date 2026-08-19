# Wafer-map spatial signatures

Read this when a wafer map shows structure and you need to turn geometry into a
short list of suspect process steps — or when you need to argue a signature *out*.

A signature is a claim about physics, and the geometry alone never settles it. For each
pattern below: what it looks like, what makes that shape physically, what evidence
discriminates it from its neighbours, and the mistakes that get made.

## How to read a map before naming a pattern

1. **Look at the fail rate, not the picture.** A 3% baseline and a 30% baseline produce
   very different-looking maps from the same physics. `spatial_signature.py` compares zone
   rates against the rest of the wafer with a two-proportion z-test for exactly this reason.
2. **Ask whether the pattern repeats across wafers in the lot.** One wafer = an event.
   All wafers = a process condition. Alternating wafers = slot- or chuck-dependent
   (double-sided tooling, two-chamber tools, alternating handler paths).
3. **Ask whether the pattern is bin-specific.** Filter the map to one hard bin. A signature
   that survives in one bin and vanishes in the others is a real mechanism. A signature
   present in every bin equally is usually a probing or data problem, not a process one.
4. **Ask what the pattern is oriented to.** Notch/flat, reticle grid, probe-card touchdown
   grid, chuck features, and slot number are four different coordinate systems. Whichever
   one the pattern locks onto names the tool that made it.
5. **Only then name it.** And name your second choice too, with the observation that would
   separate them.

## Edge ring

**Looks like:** elevated fail rate in an annulus at the wafer perimeter, roughly the outer
5–15% of the radius, closed most of the way around. `spatial_signature.py` requires at
least 6 of 8 angular sectors elevated before it calls a ring rather than a crescent.

**Physics:** every process that behaves differently where the wafer ends.
- Film thickness roll-off/roll-up at the edge: deposition and etch uniformity fall apart
  where gas flow, plasma sheath, and temperature all lose their symmetry.
- Edge-bead removal, bevel clean, and backside/bevel polymer: too aggressive removes
  device area, too little leaves residue that flakes onto later layers.
- Mechanical contact: clamp rings, lift-pin marks, edge grip in a handler, focus-ring wear
  and erosion in an etcher — the ring's radius often matches a specific hardware part.
- Lithography edge shots: partial fields at the wafer edge print differently, are focused
  differently, and sit on a wafer region with different topography.
- Thermal: edge dies see a different heat path in RTP/anneal and cool faster.

**Discriminating evidence:**
- Compare the ring's inner radius across lots. A radius that is *identical* wafer to wafer
  points at a hardware feature (clamp, focus ring, shadow ring). A radius that drifts
  points at a process condition (flow, pressure, temperature).
- Check whether the ring appeared after a PM, part change, or chamber swap. Ring radius
  changing right after a focus-ring replacement is close to conclusive.
- Look for the same ring in in-line metrology (film thickness, CD) before test. If the film
  data has the ring, it is a process ring; if only test has it, suspect probing.
- Exclude the edge exclusion zone and re-fit D0 (`yield_models.py --edge-exclude`). If the
  remaining random D0 is on target, the ring is the whole story.

**Commonly confused with:**
- **Probe-card contact loss at the edge.** Probe cards go out of planarity at the wafer
  edge first, and edge dies are where the chuck's vacuum and flatness are worst. The tell:
  the "fails" are continuity/opens/parametric-contact bins, they recover on retest, and the
  ring changes when you change probe card or touchdown recipe. This is not a fab problem.
- **Edge-Loc / crescent.** If only part of the ring is elevated, this is a one-sided effect;
  see half-moon. Reporting a crescent as a ring sends the investigation to the wrong tools.
- **Wafer-edge die that were never fully patterned.** Some maps include partial dies at the
  perimeter that can never pass. Confirm the probe map's die-in-wafer definition first.

## Scratch / linear defect

**Looks like:** a narrow chain of failing dies along a line or a gentle arc, often running
a good fraction of the wafer across, one to three dies wide. `spatial_signature.py` finds
connected components, fits a principal axis, and requires span ≥ 8 dies, ≥ 70% of the
component inside a 1.5-die-wide corridor, and aspect ratio ≥ 2.5.

**Physics:** something touched the wafer surface and moved.
- CMP: pad debris, a large slurry agglomerate, a conditioner fragment, or retaining-ring
  contact. CMP scratches are usually arcs, because the wafer and the platen were both
  rotating; sharply straight scratches are more often handling.
- Handling: robot blade contact, misaligned end effector, tweezers, cassette/FOUP contact,
  wafer sliding on a chuck. These tend to be straight, and they tend to repeat at the same
  position on every wafer of the lot because the geometry that caused them is fixed.
- Dicing/backgrind reaching the front side (at final test, not sort).

**Discriminating evidence:**
- Is the scratch in the same *wafer-relative* place across wafers? A fixed location means
  fixed hardware; random locations mean a stochastic event like a slurry agglomerate.
- Curvature. An arc whose center of curvature sits near the wafer center is polishing;
  a straight chord is handling.
- Does a defect-inspection scan (KLARF from a bright-field/dark-field tool) show the
  scratch, and at which layer? That timestamps the event to a specific step.
- Bin composition: a scratch that cuts metal lines usually produces opens/continuity fails,
  not parametric shifts.

**Commonly confused with:**
- **A row/column of probe-card damage.** Probe marks track the touchdown grid, so they land
  in a rectangular pattern aligned to the probe-card layout, not on an arbitrary line.
- **Reticle-row effects.** A failing row of dies that is exactly one reticle row tall and
  aligned to the shot grid is a litho problem, not a scratch. Overlay the shot grid before
  calling a scratch.
- **An edge arc.** A ring fragment near the perimeter has high aspect ratio too. The
  classifier explicitly rejects components sitting mostly outside r = 0.78 for this reason.

## Center cluster

**Looks like:** elevated fails concentrated in the middle of the wafer, roughly circular,
falling off with radius.

**Physics:** anything that is worst at the rotation axis.
- Spin coat/develop: at the center the wafer's tangential velocity is near zero, so
  dispense dynamics, striations, and dry-out behave differently there.
- CMP: down-force distribution and slurry transport at the wafer center; center-fast or
  center-slow removal is a classic CMP signature.
- Chuck contact: the center of an electrostatic or vacuum chuck sees different clamping and
  a different thermal path; a center hot or cold spot maps straight into CD or film
  thickness.
- Showerhead/gas injection directly above the wafer center in a CVD/etch chamber.

**Discriminating evidence:**
- Radial in-line metrology. Center clusters almost always have a visible radial signature in
  thickness/CD/overlay data; pull the wafer-level radial profile from the metrology step.
- Does the cluster's size scale with a knob (spin speed, dispense volume, down force)?
- Correlate with the failing test. A center cluster in a speed/Fmax test is a CD or thermal
  story; in a leakage test it is more likely contamination or a film-integrity story.

**Commonly confused with:**
- **A donut whose hole you cannot see** because the fail rate is saturated. Look at the
  *rate* as a function of radius, not the binary map.
- **Probe-card center contact** on cards that bow, though edge contact loss is far more
  common than center.

## Donut

**Looks like:** an annulus at intermediate radius is worse than both the center and the
edge — a ring of failures with a good center. `spatial_signature.py` requires the mid-band
rate to exceed both the center and edge rates by 1.3x, with the center itself not elevated.

**Physics:** a genuinely radial, non-monotonic process profile.
- Chuck temperature zones: multi-zone heaters/chillers meet somewhere, and the crossover
  radius is where the profile is worst controlled.
- Plasma uniformity: the sheath and the radical distribution can produce an M-shaped or
  W-shaped radial etch rate; the bad radius is where the profile crosses the spec edge.
- Spin dynamics: the transition between the center-dominated and edge-dominated regimes.
- Anneal/RTP lamp-zone boundaries.

**Discriminating evidence:**
- The radius of the ring should match a known hardware boundary — a heater-zone edge, a
  gas-ring diameter, a lamp-zone boundary. Ask the tool owner for the zone map.
- Multi-zone tools let you move the ring: change the zone setpoint split and the donut
  radius should move. That is a decisive experiment and cheap.
- Radial metrology profiles will show the same non-monotonic shape.

**Commonly confused with:**
- **Edge ring plus a center cluster** on the same wafer. If both the center and the edge are
  elevated and the mid-band is fine, that is a mixed signature, not a donut, and it usually
  means two different mechanisms.
- **A wide edge ring** on a small-die product, where the "edge" band is a large fraction of
  the wafer. Always report the ring radius in normalized units, not in dies.

## Half-moon

**Looks like:** one side of the wafer is worse, with a boundary that runs roughly through
the wafer center. Detected as a run of 3–4 elevated 45-degree sectors.

**Physics:** an asymmetry that has an absolute direction in the chamber.
- Tilted chuck or wafer not seated: one side sits closer to the showerhead/target.
- Single-sided gas inlet or a blocked/eroded injector.
- Sputter target erosion or magnet asymmetry.
- Slit-valve/pump-port side of a chamber: pumping asymmetry gives a directional gradient.
- Non-uniform clamping so that one side of the wafer bows.

**Discriminating evidence:**
- **Does the boundary rotate with the notch or stay fixed in chamber coordinates?** This is
  the single most useful question. Wafers are loaded at a defined notch angle, so if the
  affected side is the same in *wafer* coordinates on every wafer, the cause travels with
  the wafer (handling, prior layer). If you rotate the wafer 90 degrees at load and the bad
  side rotates too, the cause is in the wafer. If it stays put, the cause is in the chamber.
  A deliberate notch-rotation split lot answers this in one run.
- Compare chambers on a multi-chamber tool: an asymmetry that is chamber-specific localizes
  itself immediately.

**Commonly confused with:**
- **A quadrant pattern** (see below) — the distinction is angular extent, so report the
  sector count and let the reader judge.
- **A very wide Edge-Loc** — a crescent hugging one side of the perimeter is an edge effect
  with an asymmetry on top, which usually means an edge-contacting part is worn on one side.

## Quadrant

**Looks like:** a roughly 90-degree wedge, or the four quadrants differ in a stepwise way.

**Physics:** something with fourfold or notch-referenced structure.
- Handling and chuck features that are placed at 90-degree intervals (lift pins, clamps).
- Scan/stage direction effects in litho or in an ion-implant scan pattern.
- Multi-head or multi-site tooling where each head serves a quadrant.
- Quadrant-wise probe-card or test-site assignment (this is a test artifact, not a process
  one — check the site number distribution first).

**Discriminating evidence:**
- **Plot fail rate by test site number.** If the quadrant maps onto a site, you have a site
  problem — one probe needle, one channel, one load board path. This is by far the most
  common cause of a clean quadrant and the cheapest to check.
- Notch rotation, as with half-moon.

**Commonly confused with:**
- **Site-to-site test variation.** Say it again: check site number first.

## Repeating reticle / shot pattern

**Looks like:** the same die position fails inside every exposure field, so the map shows a
regular lattice at the reticle pitch. `spatial_signature.py` tests fail-rate homogeneity
across `x mod p` and `y mod p` residue classes for p in 3..8 with a Bonferroni-corrected
chi-square, and requires a max/min rate ratio of at least 1.8.

**Physics:** the defect is on the mask, or in the exposure, not on the wafer.
- Reticle defect, pellicle contamination, or a reticle-plane particle.
- A design hot spot: one location in the layout is marginal and prints badly across process
  window; it fails everywhere the reticle is printed.
- Illumination or lens non-uniformity within the exposure slit — this gives a gradient
  *within* the field rather than a single bad position.
- Scanner synchronization or stage vibration at a fixed point in the scan.

**Discriminating evidence:**
- **Confirm the reticle pitch first.** You need the actual shot map (dies per field in x and
  y) from the litho step. A period found by the classifier that does not match the real
  reticle layout is a coincidence or a different periodic structure entirely.
- Reticle inspection and mask-defect data settle it directly.
- Layer identification: if only one layer's reticle is bad, the failing bin should be
  specific to circuits using that layer.
- Compare across scanners. A pattern that follows the *reticle* across scanners is a mask
  issue; one that follows the *scanner* is illumination/lens.

**Commonly confused with:**
- **Probe touchdown pattern.** The probe card also lays down a repeating grid. If the period
  matches the touchdown array rather than the reticle, this is a contact problem. Getting
  this wrong sends a mask to inspection for a tester problem.
- **Any periodicity in an already-thin dataset.** With few failures, a chi-square across six
  candidate periods and two axes finds structure that is not there. That is why the test is
  Bonferroni-corrected and rate-ratio gated; keep both guards.

## Random / baseline defectivity

**Looks like:** failures scattered with no zone, sector, or period surviving a test.
`spatial_signature.py` reports `none` and prints the zone rates so the absence is auditable.

**This is the good outcome and it still needs interpretation:**
- Random does not mean "no problem". It means the loss is distributed defectivity, and the
  lever is D0 — particle counts, defect-inspection excursions per layer, and clean-up of the
  worst layers — not a single tool.
- Random-looking maps still cluster at fine scales. If the yield is far below what a pure
  Poisson model predicts for the die area, defects are clustered; that is what the negative
  binomial cluster factor measures. See `yield-models.md`.
- The absence of a signature is only as strong as the number of failures. On a high-yielding
  wafer with 20 failures, no test has power. Say so rather than declaring the wafer clean.

## Mixed signatures

Real excursions rarely arrive alone. When two candidates both clear the threshold:

1. **Report both, ranked, with their z and lift** — never collapse to one label.
2. **Split the map by bin.** Different mechanisms usually land in different bins, and
   splitting by bin often turns one confusing map into two clean ones.
3. **Subtract the strong one and re-run.** The classifier already does this for scratches:
   scratch dies are masked before the zonal tests so a scratch cannot manufacture a
   spurious angular signature. Do the same by hand for the others — exclude the edge band
   and see whether the center cluster survives.
4. **Split by wafer.** A lot-level "mixed" signature is frequently two wafers with two
   different single signatures, pooled.
5. **Beware of a dominant signature hiding a weaker one.** A 45% edge fail rate drags the
   whole-wafer average up and makes the interior look fine by comparison. Always compare
   zones against each other, not against the wafer mean.

## Quick lookup

| Signature | First place to look | Cheapest discriminating check |
|---|---|---|
| Edge ring | Edge-contacting hardware, EBR, edge etch/dep uniformity | Is the ring radius fixed across wafers? Does in-line metrology show it? |
| Scratch | CMP, wafer handling, transfer | Same wafer-relative position across wafers? Arc or chord? |
| Center cluster | Spin/dispense, CMP center pressure, chuck center | Radial metrology profile |
| Donut | Multi-zone chuck/heater, plasma radial profile | Does the ring radius move when a zone setpoint moves? |
| Half-moon | Tilt, single-sided gas, target/magnet asymmetry | Notch-rotation split: does the bad side follow the wafer or the chamber? |
| Quadrant | Test site assignment, 4-fold tooling | Fail rate by SITE_NUM |
| Reticle | Mask, pellicle, design hot spot | Does the detected period match the real shot map? |
| Random | Layer defectivity, particle excursions | D0 vs baseline after excluding systematic bins |
