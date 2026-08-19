# Excursion runbook — the long form

Detail behind SKILL.md Workflow 1. Load when you are actually working an excursion,
when a branch in the short form needs justification, or when someone wants to skip a gate.

Methodology only. Trigger thresholds, hold rules, and disposition authority are fab-specific
and belong in the private fork (see SKILL.md §Proprietary boundary).

---

## 0. Why the metrology gate comes first

An inline "excursion" is a *measurement* that moved. Two different worlds produce that
observation:

1. the process changed and the measurement is faithful;
2. the process is unchanged and the measurement changed.

Case 2 is not rare. Metrology tools drift, get recalibrated, get new recipes, get new
site-sampling maps, lose focus, get a dirty stage, get a firmware update, and get run by a
different tool after a queue change. Every action available in case 1 — holding lots, stopping
a tool, re-centering a recipe — is *harmful* in case 2. Re-centering a recipe against a biased
gauge writes the metrology error into the process permanently, and you then discover it weeks
later as a yield loss when the gauge is fixed.

Cost asymmetry: verifying the measurement costs one re-measure (minutes to a couple of hours).
Acting on a false alarm costs held WIP, a stopped tool, and possibly a mis-centered recipe.
Verify first, every time, including when the engineer reporting it is senior and certain.

### What clears the gate

| Check | What you are asking | Clears the gate when |
|---|---|---|
| Repeat measurement, same wafers, same tool | Is the number reproducible at all? | Repeat agrees within gauge repeatability |
| Second metrology tool (or a matched tool) | Is the number tool-specific? | Second tool agrees within the tool-to-tool match band |
| Metrology tool event history | Did anything happen to the gauge? | No cal / PM / recipe / sampling / firmware change since the last known-good point |
| SPC on the gauge itself (reference or monitor wafer) | Is the *gauge* in control? | Monitor-wafer chart in control across the window |
| Measurement recipe + sampling identity | Are we comparing like with like? | Same recipe rev, same site map, same site count, same wafer selection |

Practical notes:
- The monitor/reference-wafer chart is the strongest single piece of evidence and it is
  independent of the product. A step in the monitor chart that lines up with a cal event is
  effectively conclusive.
- "The repeat agrees" only rules out a flyer read. It does **not** rule out a bias — a biased
  tool repeats its bias perfectly. You need the second tool or the monitor wafer for bias.
- A second tool that *also* reads high does not prove the process moved; both tools may share
  a common cause (same reference standard, same recipe error, same environment). It does make
  process cause much more likely.
- If the metrology tool cannot be verified in time (tool down, no second tool, no monitor), do
  not treat that as a pass. Record the gate as UNVERIFIED and let that weaken every conclusion
  downstream; take reversible actions only.

### Exiting at the gate — the false-alarm path

If the gate fails (the measurement moved, the process did not), the correct output is:

- **No process hold.** Nothing about the process is known to be wrong.
- **Quarantine the *data*, not the wafers**: every measurement from that gauge since the
  suspected event is suspect. Identify the affected lot list by measurement tool + timestamp.
- Re-measure a representative sample of the affected lots on a verified tool; if they are in
  family, release the data and restate the process as in control over that window.
- Corrective action lands on metrology: re-calibrate, re-qualify against the reference,
  investigate why the change escaped (was a post-cal monitor check skipped? was the monitor
  chart not being reviewed? are cal events even visible in the excursion data?).
- Review any *decision* made on the bad data — a recipe re-center made mid-window must be
  reverted, and that revert is often the real risk in a metrology excursion.
- **Blameless close-out.** A false alarm that is found in one shift is the system working. If
  finding false alarms is punished, engineers stop reporting marginal data and you lose the
  early signal. Write the record as "measurement verified, process confirmed in control" —
  not as "wasted effort".

State the false-alarm exit as a *result*, with the evidence, in the same format as a real
excursion. It is not a non-event.

---

## 1. Confirm the signal (after the gate)

- **One point or many?** A single point beyond 3 sigma with everything else in family is a
  different animal from six points walking up. Do not describe a single point as a "trend".
- **Which rule fired?** Rule 1 (beyond 3 sigma) on an isolated point → suspect a discrete
  event (a specific wafer, a handling error, a one-off measurement). Runs rules (8 on one
  side, 4 of 5 beyond 1 sigma) → suspect a shift or a drift; the start point of the run is
  your event date.
- **Is the chart itself valid?** Limits computed over a window that already contains the
  excursion are inflated and will under-alarm. Recompute limits from a clean baseline and
  re-read the chart. Also check the subgrouping (see `fdc-spc.md`): a chart whose subgroups
  are sites-within-a-wafer will alarm on ordinary lot-to-lot variation.
- **Magnitude vs. spec, not just vs. control limits.** Control limits describe the process;
  spec limits describe the product. A point outside control limits but comfortably inside spec
  is a *process* problem with no immediate material risk — that distinction drives the hold
  decision.

## 2. Scope

Build the boundary of the event before looking for a cause. Answer all of:

- **Time:** first bad point, last good point. Anything before the first bad point that a cause
  must explain? Is the boundary sharp (a step: a discrete change) or gradual (a ramp:
  consumable wear, seasoning, drift)?
- **Material:** which lots, which wafers within a lot, which sites within a wafer. Whole-wafer
  vs. edge vs. centre vs. one radius tells you which physical mechanism to look at, and it is
  free — you already measured it.
- **Product:** one device/layer or several? A problem confined to one product with several
  running through the same chamber points at recipe or design interaction, not chamber health.
- **Route:** which steps could plausibly move this parameter? Do not scope to the step where
  it was measured; scope to every step that touches it. Post-etch CD is set by litho *and*
  etch; film thickness by dep *and* any subsequent removal.
- **Sampling reality:** what fraction of material is actually measured? With skip-lot metrology
  you cannot see unmeasured lots at all — the true scope is at least as wide as the measured
  scope and probably wider. Write down the unmeasured population explicitly; it is the
  population you will have to contain.

## 3. Commonality

Run `scripts/commonality.py`. Read the output as evidence, not as an answer.

- Rank tools and chambers by both keys: mean shift for a whole population that moved, and
  over-representation among flagged lots for a partial/drift excursion. A statistic that is
  right for one is wrong for the other.
- **Chamber before tool.** A chamber-level signal that survives while its parent tool's signal
  is diluted is the classic single-chamber fingerprint.
- **Ties are the normal case, not the exception.** Fabs route lots in correlated ways: the same
  lots hit the same tools at several steps, sequential tools are chosen by the same dispatcher,
  and a maintenance window pulls one chamber out for a day so its lots all ran on a different
  day. Two candidates covering the identical lot set are not separable by any amount of this
  data — say so and get different data (FDC, per-wafer metrology, a split lot).
- **Time confounding.** If a group's lots occupy a distinct calendar block, a calendar cause
  fits equally well: incoming material lot, facility event (chilled water, exhaust, humidity),
  a recipe or limit edit, another tool's PM upstream. Check the change log for that window
  before blaming the tool.
- **Absence of evidence.** Tools that were *not* used by the bad lots are as informative as
  those that were. A chamber with zero bad lots but plenty of lots in the window is genuinely
  exonerated; a chamber with two lots total is not.
- **Multiple-comparisons honesty.** Ranking 30 candidates and reporting the best p-value is
  fishing. Treat a commonality result as a hypothesis to confirm with an independent
  mechanism, never as a conclusion.

## 4. Hold decision

The decision tree lives in SKILL.md. The reasoning behind it:

- A hold is a *containment* action to stop bad material moving, not a punishment and not a
  root-cause step. Its scope should match the scope you can defend, and no more.
- **Targeted hold** (one chamber, one tool, the lots that ran it in a window) is right when
  commonality is clean, the boundary is sharp, and the affected population is identifiable.
  It costs the least and its scope is defensible if challenged.
- **Broad hold** (all lots through the step in a window) is right when the population cannot be
  identified — no chamber-level traceability, skip-lot sampling with big gaps, a suspected
  metrology bias that already released material, or a mechanism that could plausibly touch
  everything (a facility event, a shared gas line, a recipe edit deployed fab-wide).
- **No hold** is right, and must be an available answer, when: the metrology gate failed (false
  alarm); the deviation is inside spec with adequate margin and the mechanism is understood and
  bounded; the affected material is already scrapped or already contained by another hold;
  or the parameter is not correlated to any device requirement (in which case fix the limit,
  see §8).
- **Escalate the hold** when scope is unknown *and* growing, when the mechanism could affect
  reliability rather than parametrics (contamination, mobile ions, gate integrity, metal
  corrosion), or when the excursion may already have shipped. Reliability risk is not visible
  in the inline number; it is a reason to be conservative in a way that parametric risk is not.
- Always record: what is held, what is explicitly *not* held and why, who can release, and what
  evidence releases it. A hold with no release criteria never gets released.

## 5. Containment

Containment is what you do to stop the bleeding while root cause is still open. Independent of
the hold:

- Take the suspect chamber/tool out of the dispatch pool (a "no-run" is often better than a
  hold: it costs nothing but capacity and it stops new exposure).
- Increase sampling on the affected route — the same skip-lot plan that hid the excursion will
  hide the next one. Temporarily go to 100 % lot sampling in the window of concern.
- Run monitor wafers on the suspect chamber and on a matched chamber, same recipe, same day.
- Freeze the change window: no other edits to that route until root cause is closed, or you
  will never untangle which change did what.
- Notify downstream: if material already moved past a point of no return, the downstream owner
  needs to know what to watch for.

## 6. Root cause

Work from the mechanism catalogue in `process-modules.md`, and use evidence that
*discriminates* between hypotheses rather than evidence that is merely consistent with one.

- Line up the excursion start date against the change log: PM, wet clean, part change,
  consumable change, recipe edit, limit edit, software/firmware update, gas or slurry or
  chemical lot change, facility work. The best root causes are usually a change with a date.
- Compare FDC traces from the suspect chamber before and after the boundary, and against a
  healthy chamber on the same recipe and day. Summary statistics (mean, slope, endpoint time,
  time-in-state) are usually enough; whole-trace comparison is for when they are not.
- **Confirm by reproduction or removal**: either reproduce the effect deliberately (run a
  monitor wafer on the suspect chamber and see the deviation) or remove the suspected cause and
  see the deviation disappear. A cause you cannot switch on or off is a hypothesis.
- Distinguish *cause* from *coincidence*: a PM that happened three days before the excursion
  started is only a cause if there is a mechanism connecting them and a matching magnitude.
- Do not stop at the physical cause. "The focus ring was worn" is a mechanism; "the focus-ring
  replacement interval is set by calendar and not by RF hours, and no post-change requal
  criterion existed" is a root cause you can actually fix.

## 7. Fix verification

A fix is not verified because the next lot looked good.

- Define what "fixed" means numerically *before* running verification: the parameter back
  within its old control limits, and the chamber matched to its reference within the match band
  (`chamber-matching.md`).
- Verify on monitor wafers first, then on a small number of product lots with 100 % sampling,
  then release to normal sampling.
- Require enough points to see a shift you would care about — a single point cannot distinguish
  a fixed process from a lucky draw. Several consecutive in-family points, with the count set
  by the size of the shift you need to detect.
- **Re-qualify the chamber, not just the parameter.** A chamber returning from a fix should
  pass its qual criteria (particles, rate/uniformity, the matched metric set), because the
  intervention may have moved something you were not charting.
- Check for the mirror problem: whatever moved the parameter may have moved others that are not
  charted. Look at the neighbours (uniformity, profile, selectivity, downstream electrical) at
  least once before closing.

## 8. SPC / limit review — after, never during

Close every excursion with an explicit limits question, and answer it *after* the process is
back in control, never as a way of ending the excursion:

- Were the limits statistically valid (right chart, rational subgroups, computed from a stable
  window of adequate length, recomputed after any legitimate process change)?
- Did the chart detect the excursion at a reasonable size, or did it detect it late? Late
  detection with a big consequence argues for a tighter chart, an EWMA in parallel for drift,
  or a different sampled parameter — not for wider limits.
- Did it alarm many times without cause? Chronic false alarms are usually a subgrouping error
  or a mixed population (several chambers on one chart), not evidence that the limits are too
  tight. Fix the chart structure before touching the numbers.
- Is the parameter connected to anything that matters? A charted parameter with no link to a
  device requirement generates work without value; a device requirement with no charted
  parameter is an uncontrolled risk. Excursion close-out is the natural time to notice both.
- **Widening limits to stop an alarm is a recipe/limit edit and is itself a change**: it needs
  the same review, approval, and record as a recipe change, precisely because it is a common
  root cause of "we never saw it coming" a quarter later.

---

## Edge-case branches (the ones that actually cost money)

| Situation | Why it misleads | Discriminating move |
|---|---|---|
| Single point OOC, everything else in family | Looks like a shift; usually an event or a measurement flyer | Re-measure the same wafers; check for a wafer-level or site-level outlier inside the lot; check that lot's individual event history |
| Sustained trend but every point in spec | Easy to ignore; it is the cheapest excursion to fix and the most expensive to miss | Chart with EWMA/CUSUM; find the consumable or wear mechanism that matches the slope; project when it crosses spec |
| Excursion starts right after PM / wet clean / part change | Both "chamber not seasoned yet" and "the PM broke something" fit | Seasoning decays: the deviation should shrink over the first wafers/lots and disappear. If it is flat or growing, it is not seasoning — look at the part, the install, and the post-PM qual criteria |
| First-wafer effect | Wafer 1 differs from the rest of every lot, always; can look like an excursion when sampling happens to hit wafer 1 | Compare by wafer position within lot across many lots. If the effect is confined to the same slot, it is a first-wafer/idle-time effect, not a drift |
| Metrology drift mimicking process drift | Slow gauge drift produces a textbook process-drift chart | Monitor/reference-wafer chart on the gauge; second-tool cross-check on retained wafers; gauge R&R currency |
| Inline OOC but yield fine | Tempting to conclude "the limit is wrong" | Confirm the parameter-to-yield link with data (it may be real but with margin, or the yield detector may be insensitive). Only then review the limit — and review it as a change |
| Yield loss with inline in spec | The charted parameters are not the ones that moved | Look for what is *not* charted: uniformity within wafer, profile/shape, defectivity, a parameter measured only at one site, or a step with no inline metrology at all. Also re-check the metrology gate in reverse — an in-spec reading from a biased gauge |
| Two candidates tie in commonality | Fab routing correlates tools; the data cannot separate them | Split-lot experiment, per-wafer metrology, FDC comparison, or wait for natural routing to break the correlation. Say "not separable" rather than picking one |
| Skip-lot sampling blind spot | Unmeasured lots are invisible; the excursion may be older and wider than it looks | Treat the unmeasured population as affected until proven otherwise; go to 100 % sampling in the window; re-measure retained wafers if any exist |
| A recipe or limit edit is the root cause | Nobody looks at the change log for the *charting* system | Diff the recipe and the limit table across the boundary date. An excursion that starts on a Monday morning with no hardware event is a change-control question |
| The excursion is at the *previous* step | Measured at etch, caused at litho | Scope to every step that sets the parameter, and check whether the incoming (pre-etch) measurement moved too. If pre- and post- both moved by the same amount, the etch step is innocent |

---

## Disposition record template

Produce this for every excursion, including false alarms.

```
EXCURSION RECORD
  id / date opened / owner
  parameter, step, chart, limit violated (which rule, which points)
METROLOGY GATE            PASS | FAIL | UNVERIFIED
  repeat measurement:     <values, agrees / disagrees>
  second tool:            <values, delta vs match band>
  gauge event history:    <cal/PM/recipe/sampling changes in window>
  gauge SPC:              <monitor chart verdict>
  -> if FAIL: FALSE ALARM. no process hold. data quarantine + metrology CA. STOP HERE.
SCOPE
  time window, first bad / last good
  lots, wafers, sites; unmeasured population
  products, steps in scope
COMMONALITY
  ranking (script output), top suspect, ties, time-confounding warnings
HOLD DECISION             none | targeted | broad | escalated
  what is held / what is not and why / release criteria / owner
CONTAINMENT
  dispatch changes, sampling changes, monitor wafers, change freeze, notifications
ROOT CAUSE
  mechanism, evidence for, evidence against, alternatives not excluded
  change-log match (event + date + magnitude)
FIX + VERIFICATION
  action taken; verification criteria defined BEFORE the run; results; requal status
SPC / LIMIT REVIEW
  chart valid? detection timeliness? limits changed (and approved as a change)?
LESSONS / SYSTEMIC
  what made this hard to see, and what changes so the next one is seen sooner
```
