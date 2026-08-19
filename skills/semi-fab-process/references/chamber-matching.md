# Chamber matching

Detail behind SKILL.md Workflow 3. Generic methodology. The matched-metric list, the numeric
acceptance bands, and the qual recipes are fab- and tool-specific and belong in a private fork.

Matching is what makes a multi-chamber tool behave like one process. Without it, every chamber
is its own process with its own centre, and product routing silently becomes an uncontrolled
factor: the same recipe produces different wafers depending on which chamber was free.

---

## 1. Define the reference ("golden") chamber

A golden chamber is a *definition*, not a trophy. Requirements:

- **In control** on its own SPC charts over a recent, clean window (not a window containing a
  PM recovery or an excursion).
- **On target**, not merely stable: a stable chamber sitting 3 % off nominal is a bad reference,
  because matching everything to it institutionalises the offset.
- **Recently qualified** with a documented, repeatable qual: same recipe, same monitor-wafer
  type, same metrology recipe and sampling.
- **Documented configuration**: part set and revisions, consumable ages, software/recipe
  revisions, calibration dates. Matching to a chamber whose configuration is unknown is
  unrepeatable — six months later nobody can tell what "matched" meant.
- **Mid-life, not fresh from a PM and not at end of consumable life.** A chamber matched to a
  just-cleaned reference will fail the match a week later when the reference seasons in.

Alternatives when no chamber deserves the title:
- **Match to the mean** of the population (each chamber corrected toward the fleet average) —
  reasonable when the fleet is on target and no single chamber stands out.
- **Match to target** derived from the device requirement — best when the fleet has drifted
  together, which is exactly the failure mode that golden-chamber matching cannot detect.

Re-designate the reference on a schedule, and always after a major change to it.

---

## 2. Choose the matched metrics

Match on what the device cares about, plus the physics that drives it. A metric belongs on the
list if a difference in it produces a difference the device can feel.

| Class | Examples of what to match |
|---|---|
| Primary response | Rate (etch/dep/removal), critical dimension or thickness at target |
| Uniformity | Within-wafer range/σ and its *shape* (radial, edge, asymmetric) — a chamber can match on mean and be badly mismatched in profile |
| Profile / shape | Sidewall angle, taper, corner rounding, step coverage, conformality |
| Selectivity | Ratio to mask and to underlying layer |
| Defectivity | Particle adders at a fixed size threshold, on a monitor wafer |
| Chamber physics | Pressure control, gas flow accuracy, temperature and its uniformity, RF delivered/reflected power, endpoint signal amplitude and call time |
| Wafer-to-wafer | Repeatability across a full carrier, including the first wafer |

Two traps:
- **Matching on the mean alone.** Two chambers with identical mean CD and opposite radial
  profiles are not matched; downstream they behave differently and the difference shows up as
  yield, not as CD.
- **Matching on too many metrics.** Every metric with a band is an alarm source. Keep the list
  short, device-linked, and reviewed — a 40-metric match list guarantees a chamber is always
  "out" on something and the whole system gets ignored.

---

## 3. Paired-wafer design (how to actually measure a match)

The point is to remove every source of variation except the chamber.

1. Take monitor wafers **from one lot / one incoming batch**, ideally consecutive slots, and
   confirm the incoming population is uniform (measure incoming if the metric depends on it).
2. **Split them across chambers in a paired, interleaved order** — not chamber A's wafers first
   and chamber B's after. Alternate or randomise, so any time drift affects both chambers
   equally.
3. Run the **same recipe** on the same day, with equivalent chamber history (both post-season,
   comparable wafers-since-clean, comparable idle time).
4. Measure on **one metrology tool**, one recipe, one sampling map, in an interleaved order.
   The metrology tool must be in control (its own monitor chart) — otherwise you are matching
   chambers with a moving ruler.
5. Analyse **paired differences**, not group means: pair-by-pair difference removes the
   wafer-to-wafer contribution. Report the mean difference *with a confidence interval* and the
   difference in within-wafer profile, not just a single number.
6. Include enough pairs to resolve a difference you care about. Three wafers per chamber gives a
   very wide interval; sizing follows the same logic as DOE power — the detectable difference is
   set by the pairing σ and the number of pairs.
7. **Repeat over time.** A one-shot match is a snapshot. Chambers separate as consumables age;
   a match confirmed once and never re-checked is the reason the fleet drifts apart.

Statistical note: a paired comparison whose confidence interval is entirely inside the
acceptance band is *equivalence*, which is what you want to demonstrate. A non-significant
p-value from an underpowered test is **not** evidence of a match — it is evidence you did not
look hard enough. Say "the 95 % interval on the difference is within ±X" rather than "p > 0.05".

---

## 4. FDC trace comparison

Fault Detection and Classification data is how you tell *why* two chambers differ, and it is
usually available without running anything extra.

- **Summarise traces before comparing them.** Per wafer, per step, extract: mean and σ over the
  stable window, slope, min/max, time-to-stable, step duration, endpoint call time, integrated
  quantities (e.g. total delivered energy or total gas volume). Comparing summary statistics is
  robust; comparing raw traces point-by-point is fragile because of timing offsets.
- **Align on step boundaries, not on wall-clock time.** Recipes step at slightly different
  moments; aligning by absolute time creates differences that are purely bookkeeping.
- **Compare like conditions:** same recipe revision, same step, comparable chamber history. A
  post-clean chamber vs. a late-in-clean-cycle chamber will differ for legitimate reasons.
- **What the differences usually mean** (generic, verify on the tool set):
  - pressure setpoint met but valve position differs → pumping/conductance path differs
    (kit condition, deposit build-up), a leading indicator even when the parameter still matches
  - delivered vs. reflected RF power differs → matching network, ground path, chamber condition
  - temperature reaches setpoint but time-to-stable differs → heater/chuck contact, backside gas
  - endpoint amplitude differs → window/viewport transmission or optical path, not the process
  - flow setpoint met but line pressure differs → MFC calibration or a restriction
- **Sensitivity beats specification.** A trace parameter that differs but is inside its own
  control limits is still the best clue you have about *which* subsystem differs.
- **Multivariate methods** (principal-component distance, T², one-class models built from a
  healthy reference period) compress hundreds of trace features into one distance-from-healthy
  number. They are excellent detectors and poor explainers: always drill back to which feature
  drove the distance before acting.

---

## 5. Acceptance bands

Set the band from what the device tolerates, then check that the tools can actually hold it.

- **Start from the device/product requirement**, allocate a chamber-to-chamber budget out of the
  total variation budget, and only then look at what the fleet can do. A band derived purely
  from current fleet spread just certifies the status quo.
- **Reference the band to short-term variation:** a chamber-to-chamber difference should be a
  fraction of the within-chamber short-term σ (a common target is that the between-chamber
  contribution stays well below the within-chamber contribution, so routing does not dominate
  the total). The exact fraction is a fab decision.
- **Band the profile, not only the mean** — e.g. a limit on the difference in centre-to-edge
  range as well as on the difference in mean.
- **State the measurement uncertainty next to the band.** A ±1 % band measured with a gauge
  whose R&R is 1.5 % is not a real band; you will fail chambers at random. Confirm gauge
  capability before setting the band.
- Bands are limits on a *demonstrated difference with its interval*, not on a point estimate.

---

## 6. When to re-match

Re-run the match after any of:
- a PM, wet clean, or chamber part change on either chamber (per the requal criteria);
- a consumable change, or crossing a wear threshold (hours, kWh, wafer count);
- a recipe or software/firmware revision on the tool;
- adding a chamber, moving a chamber, or returning one from a long idle;
- a chamber-level excursion, after the fix (matching is part of fix verification);
- on a periodic schedule regardless of events — the drift you never looked for is the one that
  gets you.

## 7. Reporting a match

```
CHAMBER MATCH RECORD
  reference chamber + why it qualifies (control status, on-target, last qual, config rev)
  candidate chamber(s), config rev, consumable ages, hours since clean
  design: n pairs, wafer source, split order, date, one metrology tool + recipe
  metrics table: metric | reference | candidate | paired difference | 95% CI | band | pass/fail
  profile comparison (not just means)
  FDC comparison: which trace features differ, by how much, and the subsystem implicated
  verdict: matched / not matched / matched-with-offset (and whether the offset is corrected in
           the recipe -- and if so, that recipe delta is a change and needs the change record)
  next re-match trigger and date
```

A "matched with a recipe offset" chamber is a legitimate outcome, but the offset must be
recorded as a deliberate, approved difference with a reason, or it becomes the mystery recipe
delta that nobody can explain later.
