---
name: semi-fab-process
description: >-
  Triages wafer-fab process excursions and designs process experiments — methodology only,
  no proprietary recipes. Use when the user mentions a process excursion, out of control or
  OOC on an inline or tool parameter, SPC alarm, CD drift, wafer hold or lot hold, DOE or
  design of experiments, screening/RSM/central composite, litho, etch, deposition (CVD, PVD,
  ALD), implant, CMP, diffusion/RTP, FDC, chamber matching, golden chamber, tool qual, PM or
  first-wafer effect, metrology drift, or lot/tool/chamber commonality. Encodes an excursion
  runbook whose hard first gate verifies the metrology before anyone touches the process, then
  scope, commonality, a hold decision tree (targeted chamber hold vs full lot hold vs no hold),
  containment, root cause, fix verification and SPC limit review; per-module failure-mode
  catalogues; DOE building and analysis (fractional designs with printed alias structure,
  Lenth's method); chamber matching; and SPC chart selection with Western Electric rules.
license: MIT
metadata:
  version: 0.1.0
  author: Kuzushi Labs
---

# semi-fab-process — excursion triage, DOE, chamber matching

Decision procedures for wafer-fab process engineering: what to do when an inline or tool
parameter goes out of control, how to design an experiment that will still be true next month,
and how to make several chambers behave like one process. The model chooses the analysis and
enforces the gates; the scripts compute every number.

**Division of labour with sibling skills:** die yield, wafer maps, bin paretos →
`semi-yield-monitor`. Root cause of a *failing unit* (electrical/package) →
`semi-failure-analysis`. Package qualification → `semi-packaging-qual`. This skill owns
everything from "a number moved on the floor" to "the process is back in control and the
limits are right".

## PROPRIETARY BOUNDARY — read before answering anything

This skill carries **methodology only**. Recipes, tool-specific settings, parameter targets,
control-limit values, hold thresholds, matched-metric lists, acceptance bands, and every BKM
are **fab-proprietary** and deliberately absent here. They belong in a private fork of this
skill maintained inside the fab that owns them.

Consequences you must honour in every answer:

1. Never supply a recipe value, a setpoint, a limit, or a threshold "from experience". Ask the
   user for theirs, or state the decision rule and mark the number as the user's to supply.
2. Never present a number that no script computed and no user provided. Mark anything unverified
   as **TODO(verify)**.
3. Textbook sources may be cited by name only (May & Spanos; Montgomery; Wolf & Tauber).
   Never reproduce their text, tables, or figures.
4. If the user pastes proprietary data, use it for the analysis at hand and do not restate it
   into general guidance that outlives the conversation.

## Operating rules (binding)

1. **The metrology gate is not optional.** No hold, no recipe change, no tool-down happens
   before Gate 0 in Workflow 1 has an explicit PASS / FAIL / UNVERIFIED verdict.
2. **Numbers come from scripts.** Effects, control limits, p-values, rankings: run the script.
   Never estimate them in prose.
3. **With no data, interview and plan.** Run Workflow 0, produce a data-request list and a
   procedure. Never invent measurements to fill a template.
4. **Say "not separable" when it is true.** Commonality ties, mirror pairs on a two-tool step,
   and time-confounded groups are real outcomes. Naming a suspect the data cannot single out is
   worse than reporting the tie.
5. **A false alarm is a successful outcome, reported blamelessly.** Write it up with the same
   rigour as a real excursion.

## Workflow 0 — Intake (always run first)

Ask only for what is missing; accept "unknown" and record it as a gap.

| # | Question | Why it matters |
|---|---|---|
| 1 | Which parameter, which step, which chart, which rule fired, at which point(s)? | Decides event-vs-shift and the whole branch structure |
| 2 | First bad point and last good point (dates/lots) | The boundary every root cause must explain |
| 3 | Deviation size in σ **and** in spec units; where are the spec limits? | Control-limit violation ≠ material risk; drives the hold |
| 4 | Metrology: which tool measured it, recipe rev, site map, last cal/PM, monitor-wafer chart | Gate 0 cannot run without this |
| 5 | Lot history available? (lot_id, step, tool, chamber, date) and per-lot metric? | Enables `commonality.py`; without it, scope is guesswork |
| 6 | Change log for the window: PM, wet clean, part/consumable change, recipe edit, limit edit, software update, material lot, facility event | The best root causes are a change with a date |
| 7 | Sampling plan: every lot, skip-lot, wafers/lot, sites/wafer | Sets the size of the invisible population |
| 8 | FDC available for the suspect step? Monitor wafers? Retained wafers? | The independent confirmation the runbook demands |
| 9 | Is material moving now? Anything already shipped or past a point of no return? | Urgency and containment scope |

Route by intent: excursion → Workflow 1 · experiment → Workflow 2 · chambers disagree →
Workflow 3 · chart/limits question → Workflow 4.

---

## Workflow 1 — Excursion triage runbook

Full reasoning, edge-case detail and the record template: `references/excursion-runbook.md`.

### GATE 0 — Verify the metrology before touching the process (HARD GATE)

Nothing downstream runs until this gate has a verdict. An "excursion" is a *measurement* that
moved; the process moving is only one of the two ways that happens. Verifying costs one
re-measure; acting on a false alarm costs held WIP, a stopped tool, and — worst — a recipe
re-centred against a biased gauge.

Run all four checks:

| Check | Clears the gate when | Does **not** clear it |
|---|---|---|
| **Repeat measurement**, same wafers, same tool | Repeat agrees within gauge repeatability | A biased tool repeats its bias perfectly — this rules out a flyer read, not a bias |
| **Second metrology tool** (matched) | Agrees within the tool-to-tool match band | Both tools sharing a reference/recipe error can agree and both be wrong |
| **Gauge event history**: cal, PM, recipe rev, site-map/sampling change, firmware | No change since the last known-good point | "Routine cal" is not exoneration — a cal is a change |
| **SPC on the gauge itself** (reference/monitor wafer) | Monitor chart in control across the whole window | A monitor chart nobody has been reviewing is not evidence |

```bash
# the gauge's own control chart — the single strongest piece of evidence
python3 scripts/spc_charts.py --data metro_monitor.csv --value reading_a --label date \
  --chart imr --where tool=MET-02 --baseline 30 --png met02_monitor.png
```

**Verdicts:**

- **PASS** (measurement verified) → continue to step 1.
- **FAIL** (the gauge moved, not the process) → take the **false-alarm exit** below. Stop.
- **UNVERIFIED** (gauge down, no second tool, no monitor) → record it as UNVERIFIED, take
  **reversible actions only** (no scrap, no recipe re-centre), and treat every downstream
  conclusion as provisional.

#### False-alarm exit (prominent, blameless, and a real result)

1. **No process hold.** Nothing about the process is known to be wrong.
2. **Quarantine the data, not the wafers.** Every measurement from that gauge since the
   suspected event is suspect; list the affected lots by measurement tool + timestamp.
3. Re-measure a representative sample on a verified tool; if in family, restate the process as
   in control over the window and release the data.
4. Corrective action lands on **metrology**: recalibrate, requalify against the reference, and
   fix the escape (skipped post-cal check? monitor chart not reviewed? cal events not visible
   in the excursion data?).
5. **Revert any decision made on the bad data** — a mid-window recipe re-centre is the real
   damage in a metrology excursion.
6. Close it blamelessly and in the standard record format. Punishing false alarms trains people
   to stop reporting marginal data, which costs far more than the re-measure did.

### 1. Confirm the signal

- **Single point vs sustained**: one point beyond 3σ with everything else in family is an
  *event*; run rules (8 on one side, 4 of 5 beyond 1σ, 6 rising) are a *shift or drift*, and the
  start of the run is your boundary date. Do not call a single point a trend.
- **Is the chart valid?** Right chart type, rational subgroups, one process, limits from a clean
  baseline of ≥25 points. Re-read with frozen baseline limits before believing anything
  (Workflow 4).
- **Size it twice**: in σ (process language) and against spec (product language). They drive
  different decisions.

```bash
python3 scripts/spc_charts.py --data cd_by_lot.csv --value cd_nm --label lot_id \
  --chart imr --baseline 30 --usl 46.5 --lsl 43.5 --png cd_imr.png
```

### 2. Scope

Bound the event before hunting a cause. Produce all six:

- **Time** — first bad, last good; boundary sharp (step → discrete change) or gradual
  (ramp → wear/depletion/build-up)?
- **Material** — lots, wafers within lot, sites within wafer. The within-wafer signature is free
  and points straight at a mechanism family (`references/process-modules.md`).
- **Product** — one device/layer or several?
- **Route** — every step that could set this parameter, not just the step where it was measured.
  Post-etch CD is set by litho *and* etch.
- **Tools/chambers** — the candidate set, with how many lots each actually ran in the window.
- **The invisible population** — with skip-lot sampling, unmeasured lots are unknown, not good.
  Write down that population explicitly; it is what you may have to contain.

### 3. Commonality

```bash
python3 scripts/commonality.py --history history.csv --metric cd_by_lot.csv \
  --metric-col cd_nm --since 2026-07-16 --top 10 --pivot-out pivot.csv
```

Read it as evidence, not as an answer:

- The script ranks by **TAIL** (over-representation among flagged lots) when ≥3 lots are
  flagged, else by **SHIFT** (robust two-sample z). A drift that hit only recent lots is
  invisible to a mean-shift test and obvious to the tail test; a whole-population offset is the
  reverse.
- **Chamber before tool.** A chamber-level signal that survives while its parent tool's signal
  is diluted is the single-chamber fingerprint.
- **Scope the window and re-run.** The same chamber is marginal over six weeks and unmistakable
  over the ten days since it started. Do both and report both.
- Read the **when-did-it-start** table: delta ≈ 0 early and large late = a drift with a start
  date; a constant delta = a tool that was always different (look at its last qual, not at
  today's PM).
- Honour the warnings: **TIE / identical-lot-set / MIRROR** → not separable by this data;
  **TIME-CONFOUNDED** → a calendar cause fits equally well (material lot, facility, recipe or
  limit edit, an upstream PM); **THIN** → hypothesis only.
- A commonality result is a hypothesis to confirm with an independent mechanism (FDC trace,
  chamber-part condition, monitor wafer, split lot). Never a conclusion on its own.

### 4. Hold decision tree (GATE — state the branch you took and why)

Work top to bottom; take the first branch that matches.

1. **Gate 0 = FAIL** → **NO HOLD.** False-alarm exit. Quarantine data, not wafers.
2. **Deviation inside spec with adequate margin, mechanism understood and bounded, no
   reliability implication** → **NO HOLD.** Contain the tool (dispatch block), raise sampling,
   fix the process, and take the limit question to step 8.
3. **Affected population identifiable** (chamber-level traceability exists, boundary is sharp,
   commonality is clean and confirmed) → **TARGETED HOLD**: exactly the lots that ran the
   suspect chamber/tool inside the window, plus a dispatch block on that chamber. Smallest
   defensible scope; state what is *not* held and why.
4. **Population not identifiable** — no chamber-level history, big skip-lot gaps, a suspected
   gauge bias that already released material, or a mechanism that could touch everything
   (facility, shared gas line, fab-wide recipe/limit edit) → **BROAD HOLD**: all lots through
   the step in the window.
5. **Scope unknown and growing, or the mechanism threatens reliability rather than parametrics**
   (contamination, mobile ions, gate integrity, corrosion), **or material may already have
   shipped** → **ESCALATE**: broad hold plus notification, and treat reliability risk
   conservatively — it is invisible in the inline number.

Every hold records: what is held, what is explicitly not held and why, who may release, and
**what evidence releases it**. A hold with no release criteria never gets released.

### 5. Containment (independent of the hold)

Dispatch-block the suspect chamber (cheaper than a hold: costs capacity, stops new exposure) ·
raise sampling to 100 % on the affected route (the skip-lot plan that hid this will hide the
next one) · run monitor wafers on suspect and reference chambers, same recipe, same day ·
freeze the change window on that route · notify downstream if material already moved.

### 6. Root cause

- Line the boundary date up against the change log. Best root causes are a change with a date
  and a matching magnitude.
- Compare **FDC traces**: suspect chamber before vs after the boundary, and suspect vs healthy
  chamber on the same recipe and day. Summary features (mean, slope, endpoint time,
  time-to-stable) usually suffice — see `references/chamber-matching.md §4`.
- Work the mechanism catalogue (`references/process-modules.md`) and prefer **discriminating**
  evidence over merely consistent evidence.
- **Confirm by switching it on or off**: reproduce the deviation on a monitor wafer through the
  suspect chamber, or remove the suspected cause and watch it disappear.
- Do not stop at the physical cause. "The ring was worn" is a mechanism; "the replacement
  interval is calendar-based rather than RF-hours-based and there was no post-change requal
  criterion" is a root cause you can fix.

### 7. Fix verification (GATE)

Define "fixed" numerically **before** running the verification: parameter back inside the
pre-excursion limits, and the chamber matched to its reference inside the match band.
Verify on monitor wafers → a few product lots at 100 % sampling → normal sampling. Require
enough consecutive in-family points to distinguish a fix from a lucky draw. **Requalify the
chamber, not just the parameter** (particles, rate/uniformity, matched metrics), and check the
neighbours the intervention could have moved.

### 8. SPC / limit review (after control is restored, never as the way to end an excursion)

Was the chart valid and the subgrouping rational? Did it detect at a reasonable size, or late?
Chronic false alarms → fix the chart structure (mixed populations, wrong subgroup,
autocorrelation) before touching numbers. Is the parameter linked to a device requirement at
all? **Widening a limit is a change**: same review, approval and record as a recipe edit — it is
a recurring root cause of "we never saw it coming".

---

## Edge-case branches — check every one, every time

| Situation | Why it misleads | Discriminating move |
|---|---|---|
| Single-point OOC, rest in family | Reads as a shift; usually an event or a flyer measurement | Re-measure the same wafers; look inside the lot for a single wafer/site outlier; check that lot's own event history |
| Sustained trend, all points in spec | Easiest to ignore, cheapest to fix, most expensive to miss | EWMA/CUSUM; find the wear or depletion mechanism matching the slope; project the spec crossing |
| Excursion right after PM / wet clean / part change | "Not seasoned yet" and "the PM broke it" both fit | Seasoning **decays** over the first wafers/lots. Flat or growing = not seasoning: look at the part, the install, and the post-PM requal criteria |
| First-wafer effect | Wafer 1 always differs; sampling that lands on slot 1 mimics a drift | Subgroup by wafer slot across many lots; if it is locked to the slot and to idle time, it is not a drift |
| Metrology drift posing as process drift | Slow gauge drift draws a textbook process-drift chart | Gate 0: monitor-wafer chart, second tool, cal history, gauge R&R currency |
| Inline OOC but yield fine | Tempting to declare the limit wrong | Prove the parameter→yield link with data first; the yield detector may simply be insensitive. Only then review the limit, as a change |
| Yield loss but inline in spec | What moved is not what is charted | Hunt the uncharted: within-wafer uniformity, profile/shape, defectivity, single-site metrology, steps with no inline metrology; and re-run Gate 0 in reverse (an in-spec reading from a biased gauge) |
| Two candidates tie in commonality | Fab routing correlates tools and steps | Split lot, per-wafer metrology, FDC comparison, or wait for routing to break the correlation. Report "not separable" |
| Skip-lot sampling blind spot | Unmeasured lots are invisible; the event is probably older and wider | Treat unmeasured lots as affected until shown otherwise; 100 % sampling in the window; re-measure retained wafers |
| A recipe or limit edit is the root cause | Nobody diffs the charting system's own configuration | Diff recipe and limit tables across the boundary date. An excursion starting Monday morning with no hardware event is a change-control question |
| The cause is at the *previous* step | Measured at etch, caused at litho | Scope every step that sets the parameter; if pre- and post- measurements moved by the same amount, the later step is innocent |

## Per-module first-look table

Full catalogue — signature, first checks, discriminating evidence, per module:
`references/process-modules.md`.

| Module | Modes that dominate | Fastest discriminator |
|---|---|---|
| **Litho** | Dose/focus drift, overlay drift, resist thickness, scumming, hotplate (PAB/PEB) non-uniformity, reticle defect | Does post-litho CD move as well as post-etch? Does the map follow the plate, the reticle field, or the wafer? |
| **Etch** | Chamber mismatch, uniformity drift, polymer build-up, endpoint drift, seasoning, first-wafer, consumable wear, selectivity loss, loading | Parameter vs hours-since-clean (sawtooth = build-up); decay after clean = seasoning; step at part change = hardware |
| **Deposition (CVD/PVD/ALD)** | Thickness/rate drift, target life, precursor depletion, stress shift, chamber leak, particles/flaking, temperature non-uniformity | Rate vs the wear counter (kWh, cycles, wafers-since-clean); rate-of-rise for a leak; composition metrology for an oxidiser signature |
| **Implant** | Dose error, energy error, tilt/twist → channeling, beam non-uniformity, charging, cross-contamination | Rs alone cannot separate dose from energy — profile (SIMS/SRP) can; charging shows only on antenna structures |
| **CMP** | Dishing, erosion, scratches, slurry health, pad life, conditioner wear, non-uniform removal | Rate vs pad life and vs disc life (recovery at pad change vs at disc change); dishing scales with feature width |
| **Diffusion / RTP** | Furnace profile by boat position, RTP pyrometry/emissivity, ramp control, ambient purity, contamination | Boat-position structure = furnace profile; sensitivity to backside film = emissivity/pyrometry, not the process |

---

## Workflow 2 — DOE

Full method, power sizing, fold-over, RSM detail: `references/doe-methodology.md`.

**Stage gate: never skip a stage.** Screening → characterisation → optimisation. Screening
straight to RSM models factors that do nothing; acting on a resolution III screen deploys an
effect that is really an interaction and will not reproduce.

### 2.1 Screening — which factors matter at all

```bash
python3 scripts/doe_builder.py --design fractional -k 5 -p 2 --alias-order 2 \
  --randomize --seed 7 --out screen.csv
```
Prints the generators, the defining relation, the resolution, and the full **alias structure**,
and warns explicitly at resolution III/IV. Use `--generators "D=AB,E=AC"` to override the
built-in catalogue; the resolution is always computed from the generators actually used, so a
hand-written set is checked as hard as a catalogue one.

Discipline before running: factors must be settable on production tools · write the
hold-constant list · ranges wide enough to move the response several times above measurement
noise, but every corner checked for feasibility · pick more than one response (include
uniformity or profile, not only the mean).

### 2.2 Analysis — the test is chosen by the design, not by preference

```bash
python3 scripts/doe_analyze.py --data screen_with_response.csv --response CD_NM \
  --generators "D=AB,E=AC" --half-normal-out hn.csv --plot hn.png
```
- Unreplicated → **Lenth's method** (PSE), reporting **ME** (individual) and **SME**
  (simultaneous). An effect above ME but below SME is a candidate for the next experiment, not
  a conclusion.
- Replicated or ≥2 centre points → pure-error MSE → t-tests, with df reported.
- The half-normal plot is the primary read for a screen: inert effects lie on a line, real ones
  break away.
- **Translate every significant effect through its alias class before recommending anything.**
  At resolution III, "A is significant" means "A or BD or CE is significant". De-alias with a
  fold-over, planned before the first fraction is run.

### 2.3 Characterisation — how the survivors behave

```bash
python3 scripts/doe_builder.py --design full --factors A,B,C --replicates 2 \
  --center-points 4 --block-on ABC --randomize --seed 7 --out char.csv
python3 scripts/doe_analyze.py --data char_with_response.csv --response CD_NM --max-order 3
```
Centre points do three jobs: pure error, the **curvature test**, and a drift check (plot them
against run order). Significant curvature → a 2-level model will mis-locate the optimum → go
to 2.4.

**Blocking gate:** one block = one chamber, one day, one material lot. Never split a block
across a PM, a wet clean, a shift change, or a material-lot boundary. `--block-on` prints
exactly which effects the blocking consumed. Write the maintenance schedule next to the run
schedule before starting: a PM landing mid-experiment in an unblocked design contaminates every
effect slightly and none obviously.

### 2.4 Optimisation — RSM

```bash
python3 scripts/doe_builder.py --design ccd -k 3 --alpha rotatable --center-points 5 --out ccd.csv
```
`--alpha rotatable` = (n_factorial)^(1/4); `--alpha face` (α=1) keeps every setting inside the
original cube when a corner is infeasible; `--alpha spherical` = √k. Report the **process
window** (the region where every response is acceptable), not just the peak — a flat optimum
tolerant to ±5 % beats a sharp one that is 2 % better. **Confirmation runs are mandatory**, on
more than one chamber, before deployment; re-establish SPC limits after any re-centring.

---

## Workflow 3 — Chamber matching

Full method: `references/chamber-matching.md`.

1. **Define the reference ("golden") chamber**: in control on a clean window, **on target** (a
   stable chamber 3 % off nominal institutionalises the offset), recently qualified with a
   repeatable qual, fully documented configuration, mid-life — not fresh from a PM and not at
   end of consumable life. No chamber qualifies → match to the fleet mean, or to target derived
   from the device requirement.
2. **Choose matched metrics** the device can feel: primary response, **uniformity and its
   shape**, profile, selectivity, defectivity, plus chamber physics (pressure, flow, temperature
   uniformity, RF delivered/reflected, endpoint amplitude). Matching on the mean alone passes
   two chambers with opposite radial profiles. Keep the list short — every banded metric is an
   alarm source.
3. **Paired-wafer design**: monitor wafers from one incoming batch, **split interleaved** across
   chambers (never all of A then all of B), same recipe, same day, comparable chamber history,
   one metrology tool in control, interleaved measurement order. Analyse **paired differences**
   with a confidence interval.
4. **FDC comparison** tells you *why* they differ: align on step boundaries not wall clock,
   compare summary features, and read the classic tells — setpoint met but valve position
   differs (conductance/kit), reflected power differs (match/ground), time-to-stable differs
   (chuck contact/backside gas), endpoint amplitude differs (window transmission, not process).
5. **Acceptance bands** come from the device budget first, then a feasibility check against the
   fleet; band the profile as well as the mean; state the gauge R&R next to the band (a ±1 %
   band with a 1.5 % R&R fails chambers at random).
6. **Equivalence, not absence of significance.** A confidence interval inside the band is a
   match; a non-significant p-value from an underpowered comparison is not.
7. **Re-match** after any PM/wet clean/part change, consumable change or wear threshold, recipe
   or firmware revision, chamber move or long idle, after any chamber excursion fix, and on a
   schedule regardless.

---

## Workflow 4 — SPC on tool and inline parameters

Full detail incl. constants, autocorrelation and FDC alarm tiering: `references/fdc-spc.md`.

**Chart selection:**

| Chart | Use when | Command |
|---|---|---|
| **I-MR** | One value per run/lot/wafer — the fab default | `--chart imr` |
| **X̄-R** | A rational subgroup of 2–10 alike measurements | `--chart xbar-r --subgroup-col lot_id` |
| **EWMA** | Slow drift: seasoning, target/pad wear, precursor depletion, gauge drift | `--chart ewma --lambda 0.2` |

```bash
# per-chamber chart: a mixed-population chart hides a single-chamber drift
python3 scripts/spc_charts.py --data cd_by_lot.csv --value cd_nm --label lot_id \
  --chart imr --where etch_tool=ETCH-02 --where etch_chamber=C --baseline 20
```

**Western Electric rules** (zones A = 2–3σ, B = 1–2σ, C = 0–1σ), all implemented:
1 point beyond 3σ · 2 of 3 beyond 2σ same side · 4 of 5 beyond 1σ same side · 8 consecutive one
side of centre. Supplementary: 6 rising/falling (trend), 15 within 1σ (limits too wide or
stratified sampling). Rules 1–4 together produce a false alarm roughly every 90 points **by
design** — which is exactly why Gate 0 exists.

**Rational subgrouping (the most common way a fab chart lies):**
- Subgroup = the things that should be identical.
- **Sites-within-a-wafer is the wrong subgroup for a lot-level chart**: σ̂ = R̄/d₂ comes out tiny,
  limits close up, and ordinary lot-to-lot variation blows through them. Demonstrated with real
  numbers in `evals/semi-fab-process/EVALS.md`.
- Never mix chambers/tools on one chart unless you are deliberately charting the fleet.
- Split the chart at any recipe change, product-mix change, or re-centring — that is two
  processes on one chart.
- Check autocorrelation between consecutive runs before blaming the process for chronic alarms.

**Limits:** compute from a stable window of ≥25 subgroups containing no known excursion; freeze
them (`--baseline N`) when asking "did this break a previously stable process?"; control limits
are not spec limits; capability (Cp/Cpk, via `--usl/--lsl`) is meaningless on an out-of-control
process.

---

## Outputs this skill produces

1. **Excursion record** — the template in `references/excursion-runbook.md`, always including
   the Gate 0 verdict, the hold branch taken with what is *not* held, and the limit review.
2. **False-alarm record** — same format, ending at Gate 0, with the data-quarantine list and the
   metrology corrective action. Never downgraded to "no issue found".
3. **Commonality report** — script ranking + ties/mirrors/time-confounding + the when-did-it-
   start table + the independent confirmation you will use.
4. **DOE package** — design matrix CSV, printed alias structure, analysis with the significance
   path named (Lenth vs t-test), half-normal plot, curvature verdict, and the alias caveat on
   every recommendation.
5. **Chamber-match record** — the template in `references/chamber-matching.md §7`.
6. **SPC review** — chart choice, subgrouping rationale, limit basis, and any limit change
   routed as a change.

## Scripts

Python ≥3.10, deps in `requirements.txt` (numpy, pandas, scipy, matplotlib only — the DOE
algebra and SPC constants are implemented in-repo, not pulled from pyDOE3/statsmodels). Run
`--help` on each for the full interface.

| Script | Purpose |
|---|---|
| `scripts/doe_builder.py` | Full factorial, 2^(k-p) fractional with computed defining relation / resolution / **alias structure**, and central composite; blocking, centre points, replicates, randomisation; CSV design matrix |
| `scripts/doe_analyze.py` | Main effects + interactions; t-tests on pure error when replicated, **Lenth's PSE (ME and SME)** when not; curvature test from centre points; half-normal data + PNG; alias annotation |
| `scripts/commonality.py` | lot × step × tool/chamber × time pivot; suspect ranking by tail over-representation and robust shift z; tie / mirror / time-confounding / thin-data warnings; when-did-it-start table |
| `scripts/spc_charts.py` | I-MR, X̄-R, EWMA + Western Electric rules; frozen baseline limits, row filters, Cp/Cpk; PNG + text verdict |
| `scripts/gen_excursion_data.py` | Regenerates the synthetic sample scenarios in `sample-data/semi-fab-process/` |

## References (load on demand)

- `references/excursion-runbook.md` — the long-form runbook, every edge-case branch, the record template
- `references/process-modules.md` — per-module failure modes: signature → first checks → discriminating evidence
- `references/doe-methodology.md` — screening/characterisation/optimisation, resolution and confounding, blocking, power, Lenth, RSM
- `references/chamber-matching.md` — golden chamber, matched metrics, paired-wafer design, FDC comparison, acceptance bands
- `references/fdc-spc.md` — chart selection, Western Electric rules, rational subgrouping, limit discipline, FDC features and alarm tiering

## Sample data and evals

`sample-data/semi-fab-process/` holds three synthetic scenarios (etch CD drift confined to one
chamber; a metrology-calibration false alarm; two etch DOE datasets). All of it is synthetic —
never present it as measured fab data. `evals/semi-fab-process/EVALS.md` records the actual
script output for each, including the ranking that identifies the guilty chamber and the
evidence chain that ends the false alarm without a hold.
