# Bin, datalog and Shmoo signatures — setting the mechanism prior before anyone opens a part

Load at Step 1 (datalog review) and Step 3 (population analysis) of `SKILL.md`, and whenever the words
bin, datalog, retest, burn-in delta or Shmoo appear. All of it is free and non-destructive: finish it
before proposing any physical step, and output a **ranked finding list** (§12), never a mechanism call.
Every numeric cut-point below is an **industry-typical starting value, to be tuned per product, die
size, test program and wafer size** — never a spec, never quotable to a customer as one.

## 1. Ask for the data in this schema

`scripts/bin_signature.py` reads two CSVs. If the requester has STDF (V4 datalogs), export to these;
if they have a PDF or a screenshot, ask for the raw log — a picture of a datalog is not evidence.

| File | Columns | Meaning and traps |
|---|---|---|
| `die_results.csv` | `lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag` | One row per die per insertion. `die_x/die_y` are grid indices, not microns. If retests were merged to one row per die the spatial stats still work but the retest history is gone — ask for the per-insertion export too. |
| `tests.csv` | `lot_id,wafer_id,die_x,die_y,test_num,test_name,value,lo_lim,hi_lim` | One row per executed test per die. **No sequence column exists**, so no script can tell you which test failed *first* — that comes from an order-preserving datalog export. If the export was sorted (by test_num, by name, by anything), drop the phrase "first-failing" and say "most often out of limits" until you get an ordered log. |

Not in the schema and always worth asking for by name: **test program name + rev**, tester ID,
handler/prober ID, **site number per die**, insertion number, temperature, timestamp — carry them as
extra columns or a sidecar file, because the §8 site and tester checks are impossible without them.
**Package-level FA of field returns usually has none of this**: no wafer map, no die coordinates, often
no datalog. There the population work is date-code / lot / assembly-site commonality plus the customer's
own failure-rate data — say so in the report rather than silently skipping Step 3.

## 2. Hard bin vs soft bin vs the first-failing test

| Level | What it encodes | Worth for FA |
|---|---|---|
| Hard bin | Handler destination · coarse disposition class (pass grade, gross fail, parametric, retest) | Logistics. Says what happened to the part, not why; two unrelated mechanisms routinely share one hard bin. |
| Soft bin | Program-defined failure category, usually per test group or per test | The grouping variable for §3–§6. Program-specific: bin 7 means nothing on another product, and nothing on the same product two revs later. |
| First-failing test number | The measurement that first went out of limits | **The fingerprint** — the only layer that maps to physics: a leakage test, a continuity test, a Vmin search, a pattern. |

Case identity is **soft bin + first-failing test + condition (V/T/freq)**; write it that way everywhere.
"Bin 7 fails" is not a signature, "bin 7, first fail test 1420 IDDQ_STBY at 125 C, 40x over limit" is.
Because stop-on-first-fail truncates the flow, that test also tells you what was *never measured* (§11).

## 3. Bin pareto discipline

Run the pareto **twice** — they rank differently and answer different questions.

| View | Question it answers | How the view fails you |
|---|---|---|
| Count pareto | Where is the volume going? | A large continuity/contact bin buries a small, real, mechanism-bearing bin. |
| Yield-loss pareto (yield points, or customer DPPM) | What costs yield now? | Weights toward high-volume lots; a rare bin confined to one lot disappears. |
| Delta vs baseline | What *changed*? | Needs a valid baseline: same program rev, same insertion, same temperature. |

The biggest bin is usually not the actionable one: a bin stable across a year of lots is a design or
centering property, not an excursion. Rank by delta against a stable baseline, then yield loss, then count.

**Check the test program rev before comparing any two dates.** A bin renumbering, a bin definition
change, a limit tightening or a re-ordered flow reshapes a pareto with zero physical change on the
wafer. Ask for the program change log across the window; if it changed, re-map the bins or compare on
the underlying test numbers and limits, which survive renumbering better than bin IDs do.

## 4. Spatial signature → likely origin → what to pull next

Wafer-level (sort) data only. The sibling skill `semi-yield-monitor` carries the full taxonomy and
the classifier; this is the FA-relevant subset.

| Spatial signature | Likely origin | Pull next |
|---|---|---|
| Random, no clustering | Baseline defectivity · particles · random opens/shorts | Defect-inspection map overlay · killer-defect pareto · nothing tool-specific |
| Edge-concentrated ring or band | Edge processes — clamp/pin contact, bevel, edge-bead, radial dep/etch uniformity, edge shots | Radial zone table (§5) · edge-die exclusion policy · chamber uniformity data |
| Center-concentrated | Center-symmetric process — dispense/spin, CMP center pressure, chuck center contact | Same-tool wafers from the same window · chuck and PM history |
| Radial band (mid-radius worst) | Radial non-uniformity — chuck thermal profile, spin dynamics | Finer radius bins · tool temperature map |
| Scratch / chord / linear chain | Mechanical handling — robot, chuck, CMP, cassette contact | Handler and robot logs by time · other wafers in the same carrier · AOI |
| Repeating at reticle pitch | Litho — mask defect, reticle contamination, field-edge focus | Reticle inspection · shot-map overlay · other products on that reticle |
| Same die location across wafers, no radial structure | Probe card / touchdown site, multisite mapping, or a design-fixed weak instance | Site-to-site table (§8) **before** blaming silicon |
| One or two isolated dies, low count | Event-driven — handling, ESD, single defect | Skip spatial reasoning; go to per-unit evidence |

Spatial structure is a **process/tool prior**, spatial randomness a **defectivity or event prior**; the
prior selects which hypotheses enter the Step 4 table and is never itself a conclusion.

## 5. What `scripts/bin_signature.py` computes, and how to read it

```bash
python scripts/bin_signature.py --die-results die_results.csv --tests tests.csv --bin 7 --outdir out/
```

| Computation | How it is computed | How to read it |
|---|---|---|
| Per-bin counts and rates | Fails per hard and soft bin · share of all fails · share of dies tested · yield loss in points | The §3 pareto inputs. Small bins carry wide error bars — do not chase a 3-die bin as a trend. |
| Adjacency clustering | Counts observed adjacent fail–fail die pairs (4-neighbour) and compares them with the count from repeatedly re-placing the same number of fails at random on the same grid (permutation, default 200, fixed seed); reports **ratio = observed/expected** and a Monte-Carlo **z** | Ratio near 1 with small z → spatially random. Verdict bands as shipped (typical starting values, tune): ratio ≥1.5 **and** z ≥3 → clustered; ratio ≥1.2 and z ≥2 → weakly clustered; z ≤ −2 → dispersed, which points at a site/probe-card pattern or a mis-built map rather than physics. |
| Radial zone analysis | Normalized radius from the die-grid centroid; zones **center 0–0.33 · mid 0.33–0.70 · edge 0.70–1.0** (typical starting cut-points, tune per die and wafer size); each zone's fail rate against the wafer mean as ratio and binomial z | Edge or center z ≥3 with ratio ≥1.3 → edge- or center-concentrated; edge z ≤ −3 → edge-depleted; mid-band alone elevated → radial band. Caveat: the centroid comes from the die grid, so a cropped or asymmetric map biases it — eyeball the wafer map before trusting a marginal zone result. |
| Top failing test per bin | For the dies in that bin, which `test_num` is out of limits most often, with the share of dies it accounts for | A bin dominated by one test is one mechanism candidate. A bin spread across unrelated tests is a bin-definition artifact or gross functional failure — split it before hypothesizing. |
| Margin distribution | For that test, the excursion beyond the nearer limit **normalized to the limit range** (hi_lim − lo_lim), reported as median, min, max and a character label | See §6. The normalization means 0.1 = one tenth of the limit window outside, 1.0 = a full limit window outside — always quote raw units too when you write it up. |

Two honest limits: these are descriptive statistics, so any sampling bias in the export propagates straight
through, and both spatial tests assume a complete die grid. State the population behind every number.

## 6. Reading margin distributions

| Shape of the failing values | Reads as | Move |
|---|---|---|
| Tight cluster just outside the limit (script band: median excursion ≤0.10 of the limit range — a typical starting value, tune per test) | Parametric shift — process centering moved, or the limit/correlation is wrong | Compare the *passing* population against baseline lots. Whole distribution shifted → centering or limit issue, not a defect. Check tester correlation before touching silicon. |
| Bimodal or wide-spread — one group near the limit, one far out (the script flags spread only with ≥6 failing dies; below that, plot it yourself) | Two populations under one bin | Split the FA. Look for lot / date-code / site / assembly-site splits, a material mix-up, or a defect subpopulation on top of a normal distribution. Never average across it. |
| Far outside (median excursion >1 limit range), or pinned at the rail / compliance | Hard defect — short, open, gross leakage path | Straight to curve trace and localization; margin analysis has nothing left to give. |
| Wide, structureless spread outside the limit | Measurement problem first, defect second | Repeat with contact elimination (SKILL.md 2a.2) before believing the values. |
| "Failing" values that sit inside the limits in the log | Limit applied at another condition, unit mix-up, or a truncated/mis-parsed log | Stop; fix the data before any interpretation. |

Marginal-vs-hard is the first real fork — marginal points at centering, limits and correlation, hard at a
defect you can localize and image. Declare which one you are in before building the Step 4 table.

## 7. Correlating failing tests — one case or many?

| Across the failing units | Call |
|---|---|
| Same soft bin · same first-failing test · same condition · similar margin | One mechanism. One case; analyze the best-instrumented unit, hold the rest. |
| Same bin · same test · **bimodal** margins or two condition groups | Two cases wearing one bin. Split. |
| Same bin · different first-failing tests | The bin is a category, not a mechanism. Regroup by test number and re-pareto. |
| Different bins · same first-failing test | One mechanism reaching the flow at different points, often condition-dependent. Merge. |
| Same test, different pins/nets | One mechanism class, several sites. Keep as one case with a per-pin map — the map is evidence (adjacent I/O → handling/ESD; power pins → EOS/latch-up). |

Split as soon as two units disagree on **any** of first-failing test, condition window, margin mode or
traceability group: merging two mechanisms into one case is the commonest route to a confident wrong answer.

## 8. Retest and NFF discipline

Retest data is evidence. Every insertion is an experiment; log it.

| Field | Why |
|---|---|
| Insertion # · date/time · operator · program name + rev | Ordering, drift and comparability |
| Tester ID · handler/prober ID · site · socket/contactor ID · load board | The commonality checks below |
| Temperature · supply conditions · any condition deviation | Marginality attribution |
| Result: bin + first-failing test + measured value | Recovery vs mode change |
| Physical action taken between insertions (reseat, clean, new socket, new tray) | Attribution of the recovery |

**Check the test cell before the silicon.** Before any mechanism talk: does the fail follow one site,
tester, handler, contactor or load board? A fail rate that tracks a site number is a probe/contact/board
problem until proven otherwise, and the check costs one pivot table. Same for tester-to-tester and
bench-to-production correlation drift, which turns a real distribution into a fake bin.

| Retest behaviour | Reads as | Action |
|---|---|---|
| Recovers on reseat / new socket / cleaned contacts | Contact or test-cell issue | Reproduce it deliberately (fail–reseat–pass–reseat–fail). If it tracks the reseat, close as test-induced *with data* — a finding, not an embarrassment. |
| Recovers on another tester/site, fails on one | Tester / site / board issue | Correlation study; do not consume samples on FA. |
| Recovers only at another temperature or voltage | Marginal (V/T) | Shmoo (§10) — real device marginality, not noise. |
| Recovers sporadically, no identifiable variable | Intermittent | SKILL.md 2a; no destructive step until reproducible. |
| Never recovers | Hard fail | Standard flow. |

1. **A retest recovery is a finding** and goes in the report with its insertion log. Burying it is how
   an FA reaches "no fault found" while the customer keeps failing units.
2. **Blanket retest policies destroy the signal.** Auto-retest-until-pass converts a measurable
   mechanism into a pass, hides marginality and ships the marginal population — the direct route to
   outgoing DPPM nobody can explain later. If the flow auto-retests, ask for the pre-retest datalog:
   that is the real distribution.
3. **Recovery rate is a diagnostic.** High recovery on first retest points at the test cell; low
   recovery with an occasional pass points at marginality or a true intermittent. Quote it with its
   denominator (recovered / retested), never as a bare percentage.
4. **Guard-band before concluding.** Compare the limit against tester measurement uncertainty and the
   correlation offset between insertions — a "fail" inside the guard band is a metrology statement.
   AEC-Q001 / AEC-Q002 frame outlier-vs-fail arguments in automotive work.

## 9. Burn-in and pre/post delta analysis

For anything that appeared after burn-in, HTOL or any early-life screen, the **delta datalog is the
highest-value artifact in the case** — higher than the post-stress fail log alone. Ask for pre- and
post-stress datalogs on the *same units* and compare per test: which units moved (all, a tail, or a
discrete subpopulation), which tests moved, in which direction. A population-wide small shift in one
direction is a stress-recovery or measurement effect, not a defect; a discrete subpopulation moving hard
while the rest is unchanged is a latent-defect escape. A leakage-only post-stress shift — supply or pin
leakage up, functional/timing/speed unchanged — is the classic latent picture: a voltage-driven weak spot
(dielectric wearout, weak via, partially damaged junction) rather than a handling event after stress.
Confirm by direction (monotonic with stress time and voltage), then localize. JEP122 frames the wearout
families; `references/failure-mechanisms.md` carries the discriminators.

## 10. Reading Shmoo plots

Always compare against a **known-good unit shmooed on the same setup, program rev and day** — a Shmoo
without a reference is a picture, not a measurement. Record step size: a notch narrower than the step
is invisible.

| Shape vs known-good | Suggests | Next |
|---|---|---|
| Whole pass region shrinks uniformly | Global margin loss — slow corner, supply/IR droop, decoupling, global Vt shift | Idd and speed-monitor structures · lot corner data before suspecting a defect |
| Vmin boundary shifted up at all temperatures | Localized weakness — resistive contact/via, degraded device, or a leakage path loading a node | Pre/post-stress delta (§9) · IDDQ · identify the failing path or pattern |
| Boundary moves in **voltage only**, temperature flat | Resistive/parametric element — via, contact, bond, joint | Curve-trace the pin · TDR for opens on BGA/flip-chip |
| Boundary moves in **temperature only**, voltage flat | Thermally activated — leakage path, interface/IMC resistance growth | Hot vs cold datalog delta · lock-in thermography |
| Fails at **high** voltage, passes low | Overstress-limited, leakage/latch-up-prone, or a hold-time race | Watch Idd for runaway · check hold-time paths · stop raising voltage (§11) |
| Notch or hole inside a healthy pass region | Condition-specific race or coupling; often a PLL/DLL lock band | Re-Shmoo with a finer step around the notch · identify the failing cycle/pattern |
| Temperature dependence inverted versus the family norm | Not centering — a physical defect or interface; worth localizing | Compare against family Shmoos · start localization planning |
| Ragged, non-repeating boundary | Contact, supply noise, or a true intermittent | Contact elimination (SKILL.md 2a.2) before any interpretation of the shape |

## 11. Traps

1. **Bin definitions differ between sort and final test**, and between program revs; a limit tightening
   also makes a beautiful new bin trend. Join on test numbers and limits, never bin IDs, and check the
   limits file rev alongside the program rev.
2. **Continuity / open-short runs first and masks the real fail**, binning the die before any parametric
   test runs. A large continuity bin is usually a probe/contact story — read pin-level continuity first.
3. **Stop-on-first-fail truncates the signature.** Request a **full-datalog (continue-on-fail) retest** on
   failing units before physical work — one insertion, and it frequently redefines the case.
4. **Retest at elevated voltage rewrites the evidence**, growing marginal or ESD-type damage into something
   that images like gross overstress. Freeze conditions once a case is open; see
   `references/esd-eos-discrimination.md`.
5. **Merged (last-insertion-wins) exports hide recoveries**, and **single-temperature logs** support no
   temperature-dependence claim — a temperature-dependent mechanism then reads as intermittent.

## 12. From script output to ranked findings

Convert numbers into findings before writing a single hypothesis, one line each:
`finding · evidence (numbers + the artifact they came from) · strength · what would overturn it · hypothesis it feeds`

**Strong** = quantitative · reproduced or population-scale · has a control (known-good, another bin, lot
or site) · robust to the §5 caveats. **Suggestive** = quantitative but single-unit, single-insertion or
uncontrolled. **Weak** = qualitative, or one insertion with no conditions logged.

Rank by **discriminating power** — how many candidate mechanisms the finding kills — not by how large the
number is: a modest edge-zone lift separating process from event beats a dramatic count pareto that
separates nothing. A null result is a finding ("adjacency ratio 1.02, z = 0.3 — no spatial clustering")
and belongs in both the list and the report. Never fuse observation and interpretation in one line —
evidence holds numbers, the finding holds plain language, the mechanism stays out of both. Carry the top
findings into the Step 4 table as evidence for/against, the unresolved ones into its next-test column.

*Grounding: bin and datalog practice as described in EDFAS-community FA literature and ISTFA proceedings;
wearout framing per JEP122; outlier and statistical-bin practice per AEC-Q001 / AEC-Q002; STDF V4 as the
usual source format; problem-analysis framing per JESD671. Summarized in our own words; no standard text
is reproduced.*
