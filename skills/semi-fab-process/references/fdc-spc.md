# SPC on tool parameters, and FDC

Detail behind SKILL.md Workflow 4. Generic statistical process control (the level of
Montgomery, *Introduction to Statistical Quality Control*, and May & Spanos; named for
orientation, nothing reproduced). Which parameters a fab charts, at what limits, with what
alarm response, is fab property.

Run the charts with `scripts/spc_charts.py`; it implements the constants and rules below.

---

## 1. Chart selection

| Chart | Use when | Notes |
|---|---|---|
| **I-MR** (individuals + moving range) | One value per run/lot/wafer — the fab default for inline metrology summaries and slow tool parameters | σ̂ = MR̄/d₂ with d₂ = 1.128 for n = 2. Sensitive to non-normality; check the distribution before trusting the limits |
| **X̄-R** | A *rational subgroup* of 2–~10 measurements taken under conditions as alike as possible | σ̂ = R̄/d₂(n). Much better at detecting mean shifts than I-MR — if the subgrouping is right |
| **X̄-S** | Subgroup size ≳10 | S is a more efficient spread estimator than R at larger n |
| **EWMA** | Slow drift you want to catch early: seasoning, target/pad/consumable wear, precursor depletion, gauge drift | λ 0.1–0.3 for gradual drift; smaller λ = more memory = faster on small shifts, slower on large ones |
| **CUSUM** | Same job as EWMA, tuned to a specific shift size you must catch | Set k = δ/2 (δ = shift in σ units) and h for the ARL you want |
| **p / u / c** | Counts and proportions: particle adders, defect counts, scrap fraction | Poisson/binomial limits, not ±3σ of the raw counts |
| **Multivariate (T², PCA)** | Many correlated FDC parameters where a univariate chart on each is unusable | Detects "unusual combination" that no single parameter shows; poor at explaining — always drill down |

Rules of thumb:
- Charting a *derived* metric (a mean over sites) with I-MR throws away the within-wafer
  information. Chart both the location and the spread — a process can hold its mean perfectly
  while its uniformity collapses.
- Do not run three charts on the same parameter hoping one alarms. Pick the chart that matches
  the failure you need to detect and state it.

## 2. Western Electric rules (applied to the individuals or X̄ chart)

Zones measured from the centre line: A = 2–3σ, B = 1–2σ, C = 0–1σ.

| Rule | Condition | Typical meaning |
|---|---|---|
| 1 | 1 point beyond 3σ | A discrete event: one wafer, one measurement, one incident |
| 2 | 2 of 3 consecutive in zone A or beyond, same side | A real shift starting, or a large excursion in progress |
| 3 | 4 of 5 consecutive in zone B or beyond, same side | A moderate sustained shift |
| 4 | 8 consecutive on one side of the centre line | A small sustained shift — the classic "we moved and nobody noticed" |

Supplementary run rules worth having (often attributed to Nelson):
- 6 consecutive rising or falling → a trend (wear, depletion, drift).
- 15 consecutive within ±1σ → limits too wide, or a stratified/mixed sample.
- 8 consecutive all outside ±1σ → a mixture of two populations on one chart.

Cost of rules: each added rule raises the false-alarm rate. Rule 1 alone gives a false alarm
roughly every 370 points; running rules 1–4 together brings that to roughly every 90 points.
On a chart with hundreds of points a month, that is several false alarms a month **by design** —
which is exactly why the excursion runbook starts with a verification gate rather than an
action.

## 3. Rational subgrouping — the most common way a fab chart lies

A control chart compares *between-subgroup* variation against *within-subgroup* variation. The
subgroup definition therefore decides what the chart can see.

- **Subgroup = the things that should be identical.** Sites on one wafer, wafers in one run,
  runs in one hour — pick the level whose variation you consider common cause.
- **Sites-within-a-wafer as the subgroup is usually wrong for a lot-level chart.** Within-wafer
  site scatter is small, so σ̂ = R̄/d₂ comes out tiny, the X̄ limits close up, and ordinary
  lot-to-lot variation blows through them. The chart screams constantly and everyone stops
  reading it. (This is demonstrated with real numbers in `evals/semi-fab-process/EVALS.md`.)
- **Never mix chambers/tools on one chart** unless you are deliberately charting the fleet.
  A mixed chart inflates the limits with between-chamber variation, and a single chamber can
  drift a long way before it shows. Chart per chamber, and additionally chart the
  chamber-to-chamber difference if you care about matching.
- **Time-ordered, one process.** A chart across a recipe change, a product mix change, or a
  re-centring is two processes on one chart; split it at the boundary.
- **Autocorrelation.** Consecutive runs on the same chamber are correlated (thermal state,
  chamber condition). Strong autocorrelation makes MR̄ underestimate σ and the limits too tight.
  Options: subgroup at a longer interval, chart the residuals of a time-series model, or use an
  EWMA whose limits account for the correlation. At minimum, check for it before blaming the
  process for chronic alarms.

## 4. Setting and reviewing limits

- **Compute limits from a stable window**, typically ≥25 subgroups, that contains no known
  excursion. Limits computed over a window that includes the excursion are inflated and hide it;
  limits from 6 points are so uncertain they will both over- and under-alarm.
- **Freeze the limits** when you are asking "did this break a previously stable process?"
  (`spc_charts.py --baseline N`). Rolling limits chase the drift and can normalise it.
- **Control limits ≠ spec limits.** Control limits describe the process's own voice; spec limits
  describe the product requirement. Never draw spec limits on a control chart as if they were
  control limits, and never widen control limits to spec — that is how a process is declared
  "in control" while it drifts to the edge of the window.
- **Capability**: Cp = (USL−LSL)/6σ̂ describes potential; Cpk adds centring. Both are meaningless
  on an out-of-control process — stabilise first, then compute capability.
- **Recompute limits after a deliberate, approved process change**, and only then. Recomputing
  limits because the chart keeps alarming is the mechanism by which slow drift becomes permanent.
- **Every limit change is a change**: same review, approval, and record as a recipe edit. Limit
  edits are a recurring root cause of excursions that "started with no event".

## 5. FDC — fault detection and classification

FDC watches the tool's own sensors continuously, so it sees things inline metrology never will
(and sees them *before* a wafer is measured).

- **Trace → features → charts.** A raw trace is not chartable. Extract per-step features: mean
  and σ over a stable window, slope, min/max, time-to-stable, step duration, endpoint call time,
  integrated quantities. Chart the features.
- **Windowing matters more than the statistic.** Feature windows must be defined relative to
  recipe step boundaries, not wall-clock time, or normal step-timing jitter turns into
  parameter noise.
- **What FDC is good at:** catching a hardware change before the product shows it (valve
  position drifting while pressure still meets setpoint), catching single-wafer events (an arc,
  a flow interrupt) that a lot-average metrology summary averages away, and giving the
  independent confirmation that the excursion runbook demands before acting on a commonality
  result.
- **What FDC is bad at:** telling you whether the wafer is good. FDC parameters in control does
  not mean the product is in spec — the sensor set may not include the physics that moved.
- **Alarm management is the whole game.** Hundreds of features × dozens of chambers generates
  more alarms than any team can action. Tier them: which alarms stop the tool, which hold a lot,
  which page an engineer, which are logged for trend review only. An untiered FDC system gets
  turned off, in practice if not in policy.
- **Model maintenance:** limits and multivariate reference models built on last quarter's
  healthy period go stale after PMs, part changes, and recipe revisions. Schedule re-baselining
  and record it — a re-baseline that quietly absorbs a drift is the FDC version of widening the
  limits.

## 6. Reading a chart in an excursion (the order that avoids mistakes)

1. Is the *gauge* in control? (Its own monitor chart. See the metrology gate in
   `excursion-runbook.md`.)
2. Is the chart structurally valid — right chart type, rational subgroups, one process, limits
   from a clean baseline of adequate length?
3. Which rule fired, and at which point? Rule 1 alone → an event. Run rules → a shift, and the
   run's start is your boundary date.
4. How big is the deviation in σ, and in spec units? Both matter, and they drive different
   decisions.
5. Does the deviation follow a subgroup (chamber, slot, site, product)? Re-chart split by that
   grouping — a mixed-population chart that looks marginal usually becomes unmistakable when
   split by the guilty chamber.
6. Only then, act.
