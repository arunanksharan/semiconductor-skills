# SPC for yield

Read this when deciding whether a yield movement is real, which chart to put it on, or
whether to place a hold.

The question SPC answers is narrow and valuable: **is this variation consistent with the
process I already have, or did something change?** It does not tell you what changed, and it
does not tell you whether the change matters commercially. Those are separate questions and
conflating them is how false alarms get expensive.

## Choosing the chart

| Metric | Chart | Why |
|---|---|---|
| Yield (pass/total) per wafer or lot, subgroup size known | p-chart | Yield is a proportion; limits scale with subgroup size |
| Yield, overdispersed (the usual case) | Laney p'-chart | p-chart limits are far too tight when wafer-to-wafer variation exceeds binomial noise |
| Yield, subgroup size unknown/irrelevant, or one value per period | I-MR | Treats yield as a continuous individual measurement |
| Bin percentage for one bin | p-chart (or p') on that bin | Same logic, applied to the bin of interest |
| Defect count per wafer (defect inspection) | c or u chart | Counts, not proportions; u-chart when inspected area varies |
| A parametric mean (Vt, Idsat, CD) | Xbar-R or Xbar-S | Continuous with real subgroups |
| Small sustained shifts in any of the above | EWMA or CUSUM alongside the Shewhart chart | Shewhart is blind below ~1.5 sigma |

`spc_yield.py --chart auto` measures the dispersion and picks p or p' for you; `--chart imr`
forces individuals.

### Why the plain p-chart is usually wrong for yield

A p-chart assumes each die is an independent Bernoulli trial with a common probability, so
the only variation is binomial sampling noise. Real wafer yield is nothing like that. Dies on
a wafer share a chuck, a coat, an etch, a scanner, a probe touchdown; wafers in a lot share
a boat. So the wafer-to-wafer variance is much bigger than binomial, and a p-chart built on
binomial sigma produces control limits so tight that ordinary wafers fall outside them. Teams
then either chase noise or stop believing the chart. Both are bad.

The diagnostic is **sigma_z**: standardize each subgroup by its binomial sigma, then measure
the dispersion of those standardized values (via their average moving range / 1.128, so a
single excursion does not dominate). If sigma_z is near 1, the binomial assumption holds. If
sigma_z is 1.5, the true variation is 50% larger than binomial and your 3-sigma limits are
really 2-sigma limits.

**Laney's p'-chart** is the fix: keep the p-chart's subgroup-size scaling, then multiply
sigma by sigma_z. It degrades gracefully — when sigma_z is 1, p' *is* the p-chart. On this
skill's sample SPC history, sigma_z measures 1.54 on a clean baseline, so p' limits are 54%
wider than p limits, and the p-chart would flag ordinary wafers.

**I-MR** is the pragmatic alternative and is what many fabs actually run: treat each wafer's
yield as a single measurement and estimate sigma from the moving range. It automatically
absorbs the extra variation. Its weakness is that it ignores subgroup size, so it treats a
1200-die wafer and a 200-die wafer as equally informative.

## Western Electric rules

Applied to the standardized deviates (distance from the centerline in sigma units), with the
zones being 0–1, 1–2, and 2–3 sigma on each side:

| Rule | Trigger | What it catches |
|---|---|---|
| 1 | One point beyond 3 sigma | A spike: a single bad wafer, a gross excursion, an aborted test |
| 2 | 2 of 3 consecutive points beyond 2 sigma, same side | A moderate shift, faster than rule 1 alone |
| 3 | 4 of 5 consecutive points beyond 1 sigma, same side | A smaller shift |
| 4 | 8 consecutive points on one side of the centerline | A small sustained shift with no individual outlier |

Notes that matter in practice:
- Rule 4 is quoted as 8 in the classic Western Electric set and as 9 in Nelson's variant.
  `spc_yield.py` uses 8. State which you used; it changes detection timing.
- **Each added rule adds false alarms.** With four rules running, the in-control false-alarm
  rate is several times the 0.27% you would get from rule 1 alone. Running the full Nelson
  set on a chart you look at every shift will generate signals continuously. Pick the rules
  you will actually act on.
- **Rules 2 and 3 assume equal-width zones**, which requires roughly constant subgroup size.
  With wildly varying wafer die counts, the zones move under the points; prefer I-MR.
- **A yield chart is one-sided in consequence but two-sided in meaning.** Fire the rules on
  both sides and investigate both. See the up-tick section below.

## Real shift or noise: the decision procedure

1. **Is the metric definition stable?** Same test program revision, same bin map, same
   limits, same insertion, same retest policy, same die-in-wafer definition. If any of these
   changed, the chart discontinuity is bookkeeping, not process. Check this *first* — it is
   the single most common cause of a "yield shift" and the cheapest to rule out.
2. **Are the control limits built on a clean baseline?** A gross excursion inside the
   baseline window inflates both the centerline and sigma, and the inflated limits then hide
   the next, smaller shift. Run twice: identify assignable-cause points, then recompute
   limits with `--exclude-subgroups`, keeping those points plotted and still tested. On this
   skill's sample data, that two-pass discipline moves the centerline from 89.64% to 90.21%,
   drops sigma_z from 2.59 to 1.54, and turns an undetected shift into a rule-2/3/4 signal.
3. **Which rule fired, and does the shape match?** A single rule-1 point is one wafer.
   Rules 2–4 firing in sequence is a process shift. One is a containment question, the other
   a root-cause question.
4. **Does the timing line up with a known change?** PM, part swap, new material lot, recipe
   revision, tool qual, software update. Change records first, hypotheses second.
5. **Is the shift big enough to matter?** A statistically significant 0.4-point shift on a
   product with a 10-point margin is real and unimportant. Say both things.
6. **What is the detection lag?** Shewhart rules do not see shifts smaller than roughly 1.5
   sigma with any speed. If the shift is small relative to your wafer-to-wafer sigma, the
   chart will find it late or not at all — which is not evidence it did not happen.

## Small shifts: EWMA and CUSUM

Shewhart charts look at one point at a time, so they are strong on spikes and weak on drifts.
For a sustained shift below about 1.5 sigma you need a memory.

**EWMA**: `z_t' = lambda*z_t + (1-lambda)*z_{t-1}'`, signalling when |z'| exceeds
`L * sqrt(lambda/(2-lambda) * (1 - (1-lambda)^{2t}))`. With `lambda = 0.2` and `L = 2.7`
(the defaults in `spc_yield.py`) it detects roughly 1-sigma shifts several times faster than
the Shewhart rules, at a comparable false-alarm rate. Smaller lambda = more memory = better
on small shifts, slower on big ones.

**CUSUM** accumulates deviations beyond a slack value and is the classic alternative;
similar sensitivity, different tuning. Either is fine — running neither is not.

Two practical points:
- A **single large outlier drives EWMA past its limit** and then it takes several subgroups
  to decay back. Read EWMA runs, not isolated crossings; `spc_yield.py` prints the runs.
- **Aggregating subgroups is the other lever.** Pooling a lot's wafers into one subgroup cuts
  sigma by roughly sqrt(wafers per lot), turning a sub-sigma wafer-level shift into a
  visible lot-level one — at the cost of losing per-wafer resolution and delaying detection
  until the lot completes. `spc_yield.py --by lot` does this.

## The up-tick: verify before you celebrate

**A yield jump is a control-chart violation exactly like a drop, and it deserves the same
investigation.** The asymmetry in how teams react to it is a genuine source of escaped
defects.

Check, in order:
1. **Test program / limit revision.** Widened limits, a removed test, a disabled bin, a
   changed pass criterion. Compare program name and revision across the boundary (STDF MIR
   carries `JOB_NAM`/`JOB_REV`; `stdf_ingest.py` prints both).
2. **Bin map change.** A bin reclassified from fail to pass raises yield with nothing else
   changing. Compare the bin pareto shape, not just the total: a real improvement shrinks a
   specific bin, a bin-map change makes one disappear entirely.
3. **Retest / rebin policy.** More aggressive retesting raises final yield and lowers first-
   pass yield. If only final yield improved, look here.
4. **Tester, probe card, or load board change.** Better contact raises yield legitimately at
   sort, but the dies were always good — this is a test-yield gain, not a fab gain, and it
   should be attributed as such.
5. **Sampling change.** Fewer wafers probed, a subset of dies, or skipped edge dies all
   raise the reported number.
6. **Data pipeline change.** A new parser or a changed die-in-wafer definition.
7. **Only then**: a real process improvement — and it should have a change record, a
   mechanism, and a matching move in the bin that was supposed to improve.

If the up-tick survives all seven, it is real; recompute the control limits from the new
baseline and document the change. If it does not, you have found a test escape, and the
material shipped under the inflated yield needs review.

## Setting and maintaining limits

- **Use 20–25 subgroups minimum** to establish limits. Fewer gives limits that are themselves
  noisy; `spc_yield.py` warns below 8.
- **Baseline on a period you believe was in control**, not simply on "the last N".
  `--baseline-n` and `--baseline-lots` both exist for this.
- **Exclude assignable-cause points from the limit calculation, but keep them on the chart.**
  Removing a point from the picture hides the history; removing it from the arithmetic is
  correct once you know why it happened.
- **Recompute after a deliberate change**, and never after an undeliberate one — recomputing
  limits after an unexplained drop is how a process quietly ratchets downward.
- **Do not set control limits from specification limits.** Control limits describe what the
  process does; specs describe what the customer needs. A yield target is a business number
  and belongs on the chart as a separate reference line, never as a control limit.

## Hold decisions

SPC signals a change; it does not by itself justify a hold. Before holding material, have:
1. A confirmed signal on a chart with a clean baseline (two-pass discipline above).
2. A ruled-out metrology/test-program explanation.
3. An estimate of how much material is at risk and how far back it goes.
4. A containment plan that does not itself perturb the line more than the excursion does.

And the reverse case matters just as much: **a metrology or test false alarm should end with
"no hold" written down**, along with the evidence, so the next person does not re-litigate it.
