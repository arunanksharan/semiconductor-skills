# Yield models and D0 extraction

Read this before quoting a defect density, comparing yield across products of different die
size, or projecting the yield of a die that does not exist yet.

## What the models are for

A yield model answers one question: **given a random defect density D0 and a die area A,
what fraction of dies survive?** Everything else — edge exclusion, systematic bins,
parametric limits — has to be removed before the question even makes sense.

The models differ only in how they handle *clustering*. Defects are not sprinkled uniformly
and independently across a wafer; they arrive in clumps, and clumping means fewer dies are
hit than independence would predict, so real yield is always higher than pure Poisson at the
same average defect count. Each model is a different guess at the clumping.

## The four models

Let `lambda = A * D0` be the mean number of killer defects per die.

| Model | Y(A, D0) | Clustering assumption | D0 from Y |
|---|---|---|---|
| Poisson | `exp(-lambda)` | none — defects independent and uniform | `-ln(Y)/A` |
| Murphy | `((1 - exp(-lambda))/lambda)^2` | D varies across the wafer with a triangular distribution | numeric root |
| Seeds | `1/(1 + lambda)` | exponential distribution of defect density | `(1/Y - 1)/A` |
| Negative binomial | `(1 + lambda/alpha)^(-alpha)` | gamma-distributed density; `alpha` = cluster factor | `alpha*(Y^(-1/alpha) - 1)/A` |

`yield_models.py` implements all four and reports them side by side.

### Poisson
The floor case, and the only one with a clean physical derivation: defects land
independently at a uniform rate, so the count per die is Poisson and yield is the
probability of zero. It is correct for genuinely random, well-mixed defectivity, and it is
what the sample data in this skill is generated from. It **under**-predicts real yield
whenever defects cluster, and the error grows fast with die area — which is exactly why
nobody uses it for large die.

### Murphy
Murphy's model treats defect density as varying across the wafer and integrates yield over
that distribution. The commonly used closed form assumes a triangular density distribution.
It sits between Poisson and Seeds and is a reasonable middle-of-the-road default when you
have no clustering information at all.

### Seeds
Assumes an exponential distribution of defect density — heavy clustering. It is the most
optimistic of the classic models and it tends to over-predict yield for large die. Its
appeal is that it is closed-form and monotonic.

### Negative binomial
The one to use when you actually have data. It comes from a gamma-distributed defect density
and gives you an explicit knob, the cluster factor `alpha`:
- `alpha -> infinity` reduces exactly to Poisson (no clustering).
- Small `alpha` means heavy clustering, and yields well above Poisson.
- Typical fitted values in published work sit in the low single digits; `yield_models.py`
  defaults to `alpha = 2.0`, which is a **placeholder, not a measurement**. Fit it or state
  that you did not.

`alpha` is a property of *your* line at *your* maturity, and it drifts. A single number
carried across products, layers, or years is a fiction.

## The trap: one point fits every model

**A single (A, Y) pair determines D0 exactly under every model, and tells you nothing about
which model is right.** `yield_models.py` prints this warning on every run for a reason. The
four D0 values it returns from one lot are not four competing estimates to average or
choose between — they are the same observation expressed in four different parameterisations.

To actually select a model you need one of:
1. **Multiple die sizes on the same process.** Test structures, different products, or
   different reticle configurations. Fit Y vs A across sizes; the *curvature* discriminates.
   This is the only clean way.
2. **Yield vs measured defect count per die** from in-line defect inspection, so you can
   compare the observed distribution of defects-per-die against Poisson directly. The
   variance-to-mean ratio of that distribution is the clustering evidence.
3. **A window/critical-area analysis** giving killer-defect probability by size, which turns
   raw particle counts into an effective D0.

Absent any of these, quote Poisson as a conservative bound, say that it is a bound, and stop.

## D0 means *random* defect density — earn it before you fit it

Fitting D0 to raw final yield is the most common way to produce a meaningless number. Peel
the yield apart first:

**1. Remove gross fails.** Wafers or dies that failed for a whole-wafer reason — no contact,
scribe misalignment, an aborted test, a bad load board — are not defectivity. Exclude them
and say how many you excluded.

**2. Remove systematic bins.** A bin that is spatially structured (edge ring, scratch,
center cluster) is a *different failure population*. Leaving it in inflates D0 and the
inflated number then propagates into every projection.
```
python yield_models.py --input die_results.csv --die-area 0.25 --exclude-bins 6,7,9
```

**3. Apply edge exclusion.** Edge dies are subject to systematic edge effects that are not
random defectivity. Fabs define an edge exclusion zone; use the same one your metrology uses,
and say what it was.
```
python yield_models.py --input die_results.csv --die-area 0.25 --edge-exclude 0.90
```
`yield_models.py` applies the edge cut *before* the bin cut, because the wafer radius has to
be measured on the full map — filter the bins first and the outer ring thins out, which
moves the apparent radius.

**4. Separate parametric from catastrophic.** Dies failing a speed or leakage limit by a hair
are a process-centering problem, not a defect problem. They respond to recentering, not to
particle reduction. Split them out or you will chase the wrong lever.

**5. Then fit, and quote the interval.** `yield_models.py` reports an exact
(Clopper-Pearson) 95% interval on the yield and propagates it to a Poisson D0 interval. A
D0 quoted without an interval invites over-reading of noise: on a single wafer of ~1200
dies, the interval is wide enough to hide a 15% change in D0.

### What this looks like in practice

On this skill's sample data, seeded with a background D0 of 0.400 defects/cm² and a die area
of 0.25 cm², raw Poisson fits give 0.39 for the healthy lot but 0.56–1.01 for the lots
carrying a signature — pure contamination from the systematic bins. After
`--exclude-bins 6,7,9 --edge-exclude 0.90`, all four lots return to 0.37–0.43, and every
95% interval covers the seeded value. Same data, same script, completely different
conclusion. Measured numbers are in `evals/semi-yield-monitor/EVALS.md`.

## Die-area normalization

To compare two products, or the same product before and after a shrink, you must normalize.

- **Never compare raw yields across die sizes.** A 90% yield on a 5 mm² die and a 90% yield
  on a 50 mm² die describe wildly different lines.
- Convert each to D0 under the *same* model with the *same* exclusions, then compare D0.
- Use **gross die per wafer** consistently: the count of whole dies inside the edge exclusion
  zone, which depends on die aspect ratio and street width, not just area. Two dies of equal
  area but different aspect ratio give different gross die counts.
- For a shrink, remember that D0 itself usually changes: smaller features mean smaller
  particles become killers, so the *effective* D0 for the same physical particle population
  rises. Critical-area analysis is the honest way to handle this; a straight area scaling
  is a first-order guess and should be labelled as one.
- **Multi-die-size regression:** with three or more products on the same process, fit
  ln(Y) vs A. Under Poisson this is a straight line through the origin with slope -D0;
  systematic curvature is direct evidence of clustering and lets you fit `alpha`.

## Other pitfalls that produce wrong D0 values

- **Mixing test insertions.** Sort yield, final-test yield, and post-burn-in yield are
  different populations. Do not fit one model across insertions.
- **Retest and rebin.** If a die was retested and passed, which result is in your file? A
  datalog containing both first-pass and final results double-counts dies and silently
  raises the yield. `stdf_ingest.py` flags repeated (wafer, x, y) coordinates for this
  reason.
- **Partial maps.** Sampled probing (test every third wafer, or a subset of dies) gives an
  unbiased yield only if the sampling is spatially unbiased, which sampled *dies* usually
  are not.
- **Test escape.** A yield that rose because the test program got weaker is not a D0
  improvement. Verify program revision before believing any D0 improvement.
- **Zero-defect wafers.** `-ln(Y)` blows up as Y approaches 1 and is undefined at Y = 1.
  With a handful of failures, report the interval, not the point estimate.
- **Averaging D0 across wafers.** D0 is not linear in yield. Pool the dies and fit once, or
  fit per wafer and report the distribution — do not average the D0 values.

## When to use which model

| Situation | Use | Why |
|---|---|---|
| Small die, mature line, no clustering data | Poisson | Conservative; simple; states its own assumption |
| Large die, no clustering data | Poisson as a floor + Murphy as a working number | Poisson will badly under-predict; say so |
| You have multiple die sizes | Negative binomial, `alpha` fitted from the regression | The only case where the model is actually chosen by data |
| You have defect-inspection counts per die | Negative binomial, `alpha` from the variance-to-mean ratio | Clustering measured directly |
| Comparing two lots of the same product | Any, consistently | Model choice cancels; only the exclusions matter |
| Projecting a die that does not exist yet | Negative binomial with a stated `alpha`, plus a Poisson bound | Show the range; a single number here is a guess in a suit |
