# DOE methodology — screening → characterisation → optimisation

Detail behind SKILL.md Workflow 2. Generic statistical method (the level of Montgomery,
*Design and Analysis of Experiments*, and May & Spanos; named for orientation, nothing
reproduced). Factor ranges, recipes, and response targets are fab property.

The scripts do the algebra: `doe_builder.py` builds the design and prints the alias structure,
`doe_analyze.py` estimates effects and picks the significance test from the data.

---

## The three stages, and why skipping one costs more than it saves

| Stage | Question | Design | Runs (typical) | Output |
|---|---|---|---|---|
| Screening | Which of many factors matter at all? | 2^(k-p) resolution III–IV, or Plackett-Burman | 8–16 for 5–11 factors | A short list, plus a rough direction |
| Characterisation | How do the survivors act, and do they interact? | Full factorial (or resolution V fraction) + centre points | 8–20 for 3–4 factors | Effects, interactions, and a curvature verdict |
| Optimisation | Where is the optimum, and how flat is it? | Central composite / Box-Behnken (RSM) | 15–30 for 3–4 factors | A quadratic model, an optimum, and a process window |

Failure modes of skipping:

- **Screening straight to RSM**: you spend 30 runs modelling factors that do nothing, and the
  factors that matter may not even be in the design.
- **Screening then acting**: a resolution III main effect is aliased with two-factor
  interactions; "raise pressure" may really be "raise pressure *and* lower gap", and the change
  will not reproduce.
- **Characterisation then optimising by eye**: a 2-level design cannot see curvature, so its
  extrapolated "optimum" sits at a corner that may be past the peak. The centre-point curvature
  test is what tells you whether you are allowed to stop.

---

## Factor and range selection (where most DOEs are actually lost)

- **Include the factors you can control on the floor.** A factor that cannot be set on
  production tools produces knowledge you cannot deploy.
- **Hold-constant list is part of the design.** Write down what you are *not* varying and how
  you will keep it fixed (same chamber, same wafer lot, same incoming film, same operator, same
  reticle). Anything on this list that moves during the experiment becomes an uncontrolled
  factor confounded with run order.
- **Range: wide enough to move the response above noise, narrow enough to stay physical.**
  Rule of thumb: the expected response change across the range should be several times the
  short-term measurement noise. Estimate it from history before committing runs.
- **Ranges that break the process are not "informative extremes".** A corner that fails to
  etch, fails to print, or damages a chamber costs you the run *and* biases the whole design
  (missing or censored responses destroy orthogonality). Check every corner for feasibility
  before running, not after.
- **Categorical factors** (chamber, tool, resist lot, part vendor) are legitimate factors and
  are often better handled as blocks — see below.
- **Responses:** pick more than one, and include at least one that captures the thing you
  actually care about (uniformity, profile, defectivity), not only the easy mean. Optimising a
  mean while destroying uniformity is a classic outcome.

---

## Fractional factorials, resolution, and confounding

A 2^(k-p) design runs 1/2^p of the full factorial. The price is aliasing: some effects are
indistinguishable from others.

- **Generators** define the fraction, e.g. `D=AB`, `E=AC`. Each generator implies a *defining
  word*: D=AB → the word ABD. All products of the defining words form the **defining relation**,
  and the shortest word in it is the **resolution**.
- **Resolution III**: main effects are aliased with two-factor interactions. Use for screening
  many factors when interactions are believed small; never act on a single result.
- **Resolution IV**: main effects are clear of two-factor interactions, but 2fi are aliased with
  each other. Good screening default when runs allow.
- **Resolution V**: main effects and 2fi are clear of each other (2fi aliased with 3fi). This is
  a characterisation design.
- **Minimum aberration** picks, among designs of equal resolution, the one with the fewest short
  words in the defining relation — i.e. the least aliasing among low-order effects.

The number of independent contrasts equals (number of distinct runs − 1). A 2^(5-2) in 8 runs
gives 7 contrasts, no matter how many effect names you write down; `doe_analyze.py` collapses
aliased terms into a single contrast for exactly this reason (if it did not, Lenth's effect
count `m` would be wrong).

**Fold-over** is the standard de-aliasing move: run a second fraction with signs reversed
(all factors, or one factor). Combining the two blocks separates main effects from the 2fi
they were aliased with, at the cost of doubling the runs. Plan the fold-over *before* the first
fraction, so the second block is affordable and the blocking is deliberate.

---

## Randomisation, blocking, and run order

- **Randomise run order.** Any factor that drifts with time (chamber conditioning, ambient,
  consumable wear, operator) becomes an unbiased error contribution instead of a bias on
  whichever effect happens to align with time.
- **Randomisation is not free.** Fully randomising a hard-to-change factor (temperature setpoint
  that takes an hour to stabilise) may be impractical; that is a split-plot design, and its
  analysis has two error terms. If you run a split-plot and analyse it as a completely
  randomised design, hard-to-change factors get artificially small p-values. Say so explicitly
  in the plan.
- **Block on the nuisance variable you cannot randomise away**: chamber, tool, day, wafer lot,
  reticle. Blocking removes the block effect from the error term and buys power. In a 2^k, a
  block is created by confounding a high-order interaction (typically the highest) with blocks —
  that interaction becomes unestimable, which is normally an acceptable trade.
- **One block = one chamber, one day, one material lot.** Never split a block across a PM,
  a wet clean, a shift change, or a material-lot boundary. `doe_builder.py --block-on` prints
  exactly which effects the blocking has consumed.
- **Guard against PM confounding.** Write the maintenance schedule next to the run schedule
  before you start. If a PM lands mid-experiment, either (a) finish the design before it,
  (b) treat pre/post-PM as a block, or (c) re-run the affected block. A PM in the middle of an
  unblocked randomised design contaminates every effect a little and none obviously — the worst
  case, because it is invisible in the analysis.
- **Centre points scattered through the run order** are a free drift detector: plot them against
  run order. A trend in the centre points means the process moved during the experiment, and
  every effect estimate is suspect.

---

## Replication, centre points, and power

- **Replicates buy an error estimate and power.** Genuine replicates re-run the whole setup
  (fresh wafer, re-set the tool); re-measuring the same wafer is *not* a replicate, it estimates
  measurement noise only, and using it as pure error will make everything look significant.
- **Centre points** do three jobs: pure error at the centre, a curvature test, and a drift check.
  3–5 centre points is the usual range; fewer than 3 gives a weak error estimate.
- **Power, in plain terms:** the standard error of an effect in a 2-level design with `n` total
  runs is `2σ/√n`, so detecting an effect of size `Δ` at roughly 95 %/80 % power needs about
  `n ≈ 32 σ² / Δ²` runs (the factor is ~(1.96+0.84)² ≈ 8, doubled twice by the effect-vs-
  coefficient convention). Estimate σ from historical short-term variation *before* designing,
  and if the required n is unaffordable, say so at the planning stage rather than running an
  underpowered design and reporting "no significant effects".
- **"No significant effect" is not "no effect"** unless you state the effect size you could
  have detected. Always report the detectable effect size alongside a null result.

---

## Analysis discipline

1. **Look at the data before the model**: response vs. run order (drift), centre points vs. run
   order, any missing or censored runs, any obviously wrong value.
2. **Estimate effects.** Effect = (contrast)/(n/2); the model coefficient is half the effect.
3. **Choose the significance path from the design, not from preference:**
   - replicated (or ≥2 centre points) → pure-error MSE → t-tests, and report the df;
   - unreplicated → **Lenth's method**: `s0 = 1.5·median|effect|`, then
     `PSE = 1.5·median{|effect| : |effect| < 2.5·s0}`, `ME = t(0.975, m/3)·PSE`, and the
     simultaneous `SME = t(γ, m/3)·PSE` with `γ = (1+0.95^(1/m))/2`.
     ME is the individual bar; **SME is the honest bar** when you are scanning all `m` effects.
     An effect above ME but below SME is a candidate for the next experiment, not a conclusion.
4. **Read the half-normal plot.** Inert effects fall on a straight line through the origin;
   real effects break away to the right. This is the most robust read for an unreplicated
   design and it does not depend on any distributional assumption about the noise.
5. **Respect hierarchy.** If an interaction is in the model, keep its parent main effects even
   if they are individually insignificant.
6. **Check the curvature test** whenever centre points exist. Significant curvature means a
   2-level model will mis-locate the optimum → go to RSM.
7. **Translate every significant effect through its alias class** before recommending anything.
   In a resolution III design "A is significant" literally means "A or BD or CE is significant".
8. **Residuals**: check for a pattern vs. fitted value (non-constant variance → consider a
   transformation, e.g. log for a rate or a count) and vs. run order (drift).

---

## Response surface (optimisation)

- **Central composite (CCD)** = factorial (or resolution ≥V fraction) + 2k axial points + centre
  points. Axial distance `α`: `α = (n_factorial)^(1/4)` is rotatable (prediction variance depends
  only on distance from the centre); `α = 1` is face-centred (CCF), which keeps every setting
  inside the original cube — usually the only option when a corner is physically infeasible;
  `α = √k` is spherical.
- **Box-Behnken** avoids the extreme corners entirely (no run has all factors at their limits),
  which is attractive when corners are risky, at the cost of no true factorial corners.
- Fit the full quadratic, then check lack-of-fit against pure error before trusting the optimum.
- **Report the process window, not just the peak.** A flat optimum tolerant to ±5 % on each
  factor is worth more on a production floor than a sharp one that is 2 % better. Overlay the
  contours of every response (mean, uniformity, defectivity, throughput) and take the region
  where all of them are acceptable.
- **Confirmation runs are mandatory.** Predict the response at the chosen point with a
  prediction interval, then run it. If the confirmation lands outside the interval, the model is
  wrong (usually a missing factor, an aliased interaction, or drift during the experiment) — do
  not deploy.

---

## Deploying a DOE result into production

- Confirmation runs at the recommended setting on **more than one chamber**, because a setting
  optimised on one chamber may not transfer (see `chamber-matching.md`).
- Re-establish SPC limits after any deliberate re-centring: old limits describe the old process.
- Record the design, the analysis, the alias structure, the confirmation results, and the
  *reason* for the setting in the change record. A recipe value with no traceable justification
  is the thing that gets "optimised" back the other way in a year.
