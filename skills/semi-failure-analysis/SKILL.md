---
name: semi-failure-analysis
description: Structured semiconductor failure analysis from first symptom to physical root cause. Use when the user mentions a failure analysis or FA request, an RMA or customer return, a bin signature, curve trace or Shmoo anomaly, a burn-in or reliability failure, suspected ESD, EOS or latch-up damage, or asks about localization (EMMI, OBIRCH, TDR, C-SAM), decap or cross-section decisions, an 8D report, or electrical/package root cause. Enforces evidence-first intake, symptom classification (hard, parametric, marginal, intermittent, no-fault-found), competing-hypothesis tables, a cost- and destructiveness-ordered technique sequence with hard gates before decap and FIB/SEM cross-section, sample preservation and chain of custody, containment versus root cause, and generation of 8D and FA lab reports with runnable analysis scripts.
license: MIT
metadata:
  version: 0.1.0
  author: Kuzushi Labs
---

# Semiconductor Failure Analysis

Run a failure analysis the way a disciplined FA lab does: evidence before hypothesis,
non-destructive before destructive, competing hypotheses before a verdict, and a report
that separates what was observed from what was inferred.

## Operating rules (read first, non-negotiable)

1. **Never fabricate numbers or observations.** Every measurement in your output comes from
   a user-provided artifact or a script in `scripts/`. If data is missing, say so and ask.
2. **Never hypothesize failure physics before minimum evidence is in hand** (Step 1 checklist).
   With insufficient evidence, your only output is the intake interview and a data request.
3. **Non-destructive before destructive, always.** Destructive steps sit behind HARD GATES
   (Step 5). Do not present decap, cross-section, or FIB as next steps until their gate passes.
4. **Samples are evidence.** State the sample-preservation plan before any physical step.
   A single-sample case follows the single-sample protocol (Step 5.4) without exception.
5. **Report language discipline:** "observed" for direct evidence, "consistent with" for
   inference. Never assign blame (e.g., "customer caused EOS") — report mechanism and energy
   reasoning; attribution is a business conclusion, not an FA one.

## Step 1 — Intake: collect before you think

Ask for every row. Mark what arrives; do not proceed past Step 2 until the **minimum bar**
(marked ●) is met — everything else can be gathered in parallel.

| # | Artifact | Why it matters | Min |
|---|----------|----------------|-----|
| 1 | Failure description in the requester's words | Anchors scope; often contains the event | ● |
| 2 | ATE datalog (or bench log) of the failure: failing test(s), bin, measured vs limits | The electrical fingerprint | ● |
| 3 | Test conditions at failure: voltage, temp, frequency, program/rev | Reproduce or explain marginality | ● |
| 4 | Sample inventory: how many units, serials, current location, powered since failure? | Preservation planning | ● |
| 5 | Failure rate / population: 1 unit? x of N in lot? DPPM trend? | Event vs process prior (see `references/bin-signature-analysis.md`) | ● |
| 6 | Lot / date-code / wafer / assembly traceability | Commonality analysis | |
| 7 | Shmoo plots (pass region vs known-good) | Marginality shape | |
| 8 | Life history: burn-in? reflow (profile, cycles)? board rework? field hours? environment? | Wearout vs event vs assembly | |
| 9 | Application conditions: supply rails, hot-plug?, connectors, ESD controls at handler | Overstress plausibility | |
| 10 | Handling history & recent changes: new tray/tester/operator/site, date change introduced | Change-point evidence | |
| 11 | Known-good reference units (same lot if possible) | Comparison baseline | |
| 12 | Photos of unit/board as received | External evidence before anyone touches it | |

**If the minimum bar is not met:** output the interview (missing rows + why each matters)
and stop. Explicitly refuse to rank mechanisms: *"I can't responsibly hypothesize physics
yet — here's exactly what I need."*

**Customer return / RMA extra step:** open chain of custody now — photograph as-received
(package, markings, leads/balls, board if attached), record serials, log every transfer and
every action with date + operator. Do not electrically test before as-received photos exist.

## Step 2 — Classify the symptom (choose the path)

| Class | Definition | Path |
|-------|-----------|------|
| **Hard fail** | Fails gross functional/continuity every insertion, all conditions | Standard flow, Step 3 → 5 |
| **Parametric** | Specific test out of limits, otherwise functional | Standard flow; margin analysis first |
| **Marginal (V/T)** | Passes/fails depending on voltage, temp, or frequency | Shmoo both ways; compare to known-good Shmoo before any physical step |
| **Intermittent** | Comes and goes across insertions/time/mechanical stress | Intermittent protocol (2a) |
| **NFF / no-fault-found** | Reported fail; passes everything you run | NFF protocol (2b) |

### 2a — Intermittent protocol (edge case: evidence evaporates)
1. Retest ≥3 insertions; log pass/fail per insertion with conditions.
2. **Contact elimination:** different socket/contactor, cleaned leads/balls, different tester;
   gentle lead press during bench test. Most "intermittents" die here — that is a finding
   (contact, not silicon) and may close the case as test-induced.
3. If it survives: **in-situ monitoring through stress** — continuous resistance/functional
   monitoring during thermal cycling and/or vibration (`in_situ_tc_monitoring`). Target:
   convert intermittent → reproducible, and localize to pin(s).
4. **EXTRA GATE:** no destructive step until the failure is reproducible on demand or a pin
   and condition window is nailed. Destroying an unreproduced intermittent destroys the case.

### 2b — NFF protocol
1. Retest with the *requester's* conditions and program rev, not just yours (program deltas
   are a classic NFF cause). Then margin-Shmoo beyond spec.
2. Replicate application conditions: their board if available, supply sequencing, connectors.
3. Interview for escapes: mixed product? mis-binned? board-level fault? test-coverage gap?
4. **Terminal gate: never perform destructive analysis on a unit that has not failed for
   you.** If unreproduced after the above, report NFF with the retest matrix and stop.

## Step 3 — Population & bin-signature analysis (when >1 unit or die-level data exists)

Population statistics set the mechanism prior *before* any physical work
(full logic: `references/bin-signature-analysis.md`):

- 1 unit from millions → event-driven prior (overstress, handling, board event).
- Cluster in one lot/date-code → process/assembly excursion prior. Check commonality.
- Rate emerging **after burn-in / early life** → latent defect or wearout-screen escape
  (TDDB, EM, weak vias). Compare pre/post-burn-in datalogs — the delta is the evidence.
- Same soft bin + same first-failing test across units → single mechanism; treat as one case.

If die-level CSVs exist, run the script — never eyeball:

```bash
python scripts/bin_signature.py --die-results die_results.csv --tests tests.csv --outdir out/
```

It reports bin paretos, per-bin spatial character (clustered / edge / center / random on the
wafer), the dominant out-of-limit test per soft bin, margin statistics, and a ranked findings
list to paste into Step 4. Spatially **random** + one leakage test + date-codes after a handling
change reads very differently from **edge-clustered** + many bins.

Two things to respect in its output:
- **`inconclusive_low_power` is not `random`.** When a bin has too few fails for the adjacency
  statistic to separate clustered from random, the script says so instead of guessing. Pool
  wafers or lots, or fall back on non-spatial commonality — never report it as random.
- **"Dominant out-of-limit test" is not "first-failing test."** `tests.csv` carries no test-order
  column. Confirm the first-failing test from an order-preserving datalog export.

## Step 4 — Hypothesis table (competing, falsifiable, updated)

Build the table before selecting techniques; update it after every result. Rules:
- **≥2 competing hypotheses always** (if you can only think of one, add the strongest
  alternative from `references/failure-mechanisms.md` and the test-induced-artifact row).
- Every hypothesis gets a **discriminating next test** — the cheapest observation that would
  separate it from the others. If two hypotheses share all evidence, find the discriminator
  before physical work.
- Kill hypotheses in writing (move to a "retired" section with the killing evidence).

| Hypothesis | Evidence for | Evidence against | Discriminating next test | Cost/destructive |
|------------|--------------|------------------|--------------------------|------------------|
| e.g. ESD (HBM) at handler | leakage on 2 adjacent I/O pins; started after tray change | no handler audit yet | curve-trace pin map vs known-good; EMMI after gate | low / ND then D |
| e.g. test-induced (contact) | recovers on reseat 1 of 5 | persists on bench | contact elimination (2a.2) | low / ND |

Mechanism taxonomy with electrical signatures, physical appearance, and discriminating
evidence per mechanism: `references/failure-mechanisms.md`.
ESD vs EOS is the classic confusion — read `references/esd-eos-discrimination.md` before
writing either word in a hypothesis table.

## Step 5 — Technique sequence with hard gates

Generate the ordered plan with the script (it encodes package-type applicability, sample
allocation, and the gates), then review it against the hypothesis table:

```bash
python scripts/technique_selector.py \
  --symptom-class parametric --package-type wirebond-plastic --sample-count 12 \
  --powered-signature leakage --suspected esd --customer-return \
  --budget medium --urgency expedite --output plan.json
```

Budget and urgency shape *what is affordable and what runs in parallel*, never the gate order:
`--budget low` defers cost-tier 4-5 techniques unless they are the discriminating step (and says
so), `--budget high` buys parallel non-destructive work and external-lab access, and
`--urgency emergency` tells you to launch containment in parallel rather than to skip a gate.

Canonical phase order (details and traps per technique: `references/technique-matrix.md`):

| Phase | Nature | Typical content |
|-------|--------|-----------------|
| N0 — Electrical & records | Non-destructive | external visual, datalog review, curve trace pin map vs known-good, Shmoo, population/bin signature, burn-in delta review |
| N1 — Package imaging | Non-destructive | X-ray (wires, balls, voids), C-SAM (delamination — molded packages), hermeticity/PIND (cavity), TDR (BGA/flip-chip opens) |
| N2 — Localization | Non-destructive* | lock-in thermography, magnetic current imaging; EMMI/OBIRCH (may require decap/backside thinning — if so it moves after GATE D1) |
| **GATE D1** | — | see below |
| D1 — Decapsulation | Destructive | wet acid / plasma / laser-assisted decap; internal optical; EMMI/OBIRCH on exposed die; PVC-SEM |
| **GATE D2** | — | see below |
| D2 — Physical sectioning | Destructive, final | FIB or mechanical cross-section, SEM/EDX, delayering, nanoprobing, dye-and-pry (board joints), TEM |

**GATE D1 (before any decap or package removal) — all must be true:**
1. All applicable N0–N2 results are logged in the hypothesis table.
2. The table names which hypothesis decap will discriminate, and what you expect to see for
   each surviving hypothesis (pre-registered expectation).
3. Failure site or at least failing pin/net is localized as far as ND techniques allow.
4. Sample allocation reviewed (5.4); the unit being opened is the designated one.
5. **Explicit user confirmation obtained in this conversation.** Present: units consumed,
   information gained, information *destroyed* (e.g., decap erases delamination and
   moisture evidence — C-SAM must be done first), and the no-go alternative.

**GATE D2 (before cross-section / FIB / delayering):** same five checks, plus: the cut plane
is chosen from a localized site (EMMI/OBIRCH/PVC/thermography), not a guess — a blind
cross-section through an unlocalized die is evidence destruction, not analysis.

### 5.4 — Sample allocation & preservation
- **N = 1 (single-sample case):** exhaust *every* applicable ND technique; photo-document
  each step; gates require written expected-outcomes; prefer FIB (site-specific, minimal
  material loss) over mechanical section; archive all imagery before each irreversible step.
- **N = 2–4:** designate 1 archive unit (untouched), run the sequence on 1; remaining units
  held for cross-check of the mechanism call.
- **N ≥ 5:** 1 archive, 1 full-sequence, 1 for independent confirmation of the final
  mechanism, rest returned/held. Never run all units through the same destructive step.
- Known-good reference unit goes through the same ND imaging for comparison — never through
  destructive steps unless separately approved.

## Step 6 — Containment vs root cause (keep the tracks separate)

- **Containment** protects the customer *now*: screen/purge suspect date codes, hold
  shipments, add an outgoing test. It needs only the failure *signature*, not the mechanism.
  Recommend containment as soon as the signature is known (often end of Step 3).
- **Root cause** explains *why* and enables corrective action. It needs the full flow.
- Never let a plausible containment story close the FA ("we screened it out" ≠ root cause),
  and never delay containment waiting for root cause. Track both, report both.

## Step 7 — Report (8D or FA lab report)

Assemble the evidence JSON as the case progresses (schema in `scripts/fa_report.py`
docstring), then generate:

```bash
python scripts/fa_report.py --evidence case.json --format 8d --out 8d_report.md
python scripts/fa_report.py --evidence case.json --format fa --out fa_report.md
```

8D mapping and section skeletons: `references/report-templates.md`. Verdict rules:
- Mechanism call = primary + (if honest) secondary, each with confidence and the evidence
  chain. "Consistent with ESD (CDM-type), based on: …" — never a bare assertion.
- Unwitnessed overstress: report damage character + energy reasoning; use neutral wording
  (industry practice: "electrically induced physical damage") — see
  `references/esd-eos-discrimination.md`.
- Every photo/scan referenced with caption: unit serial, technique, magnification, finding.

## Edge cases & traps (check every case against this list)

1. **Test-induced artifacts as the real mechanism** — probe damage, bent pins, socket wear,
   hot-switching, wrong program rev. Always a standing hypothesis-table row.
2. **Retest recoveries** — a unit that passes on retest is *evidence* (contact, intermittent,
   marginal, or NFF), not an embarrassment to hide. Log every insertion.
3. **Order-of-operations evidence destruction** — decap before C-SAM erases delamination;
   baking a unit erases moisture history; re-testing at high V can convert ESD damage into
   EOS-looking damage. The gates exist for this.
4. **Mixed mechanisms** — e.g., delamination (assembly) *enabling* corrosion (field). If
   physical evidence spans two mechanisms, report the chain, not just the end state.
5. **Popcorn during FA itself** — baking/reflow steps in the lab can create the delamination
   you then "find". Record moisture handling of samples.
6. **Single-unit certainty** — one unit supports "consistent with", never a population claim.
7. **The blame trap** — see Operating rule 5.

## Scripts quick reference

```bash
pip install -r requirements.txt   # numpy, pandas, matplotlib only

python scripts/technique_selector.py \
    --symptom-class {hard_fail|parametric|marginal|intermittent|nff} \
    --package-type {wirebond-plastic|wirebond-bga|flipchip-bga|wlcsp|ceramic-hermetic|bare-die|module-sip} \
    --sample-count N \
    [--powered-signature short|open|leakage|functional|speed|unknown] \
    [--suspected esd,eos,tddb,em,latchup,hci,wirebond,delam,solder,corrosion,diecrack,underfill] \
    [--after-burnin] [--after-reflow] [--customer-return] \
    [--budget low|medium|high] [--urgency routine|expedite|emergency] \
    [--output plan.json] [--json]
# or drive it from a case file carrying a "selector_input" block:
python scripts/technique_selector.py --case-file case.json [--output plan.json]

python scripts/bin_signature.py --die-results die_results.csv \
    [--tests tests.csv] [--bin 42] [--outdir out/] \
    [--permutations 200] [--seed 7] [--no-plots] [--json]

python scripts/fa_report.py --evidence case.json --format {8d|fa} [--out report.md] [--strict]

python scripts/gen_sample_case.py --case {1|2|3|4|5|all} \
    --outdir ../../../sample-data/semi-failure-analysis/ [--seed 17]
```

All scripts: `--help` for full usage; deterministic; inputs are CSV/JSON; they compute, you
interpret. `fa_report.py` never invents content — every field you did not supply is rendered as
an explicit gap marker and the report is labelled a DRAFT until they are closed (`--strict`
exits non-zero on any gap).

## Sample data, golden cases, and the eval suite

Five worked cases ship with the skill: EOS from a hot-plug transient · TDDB emerging at burn-in ·
intermittent wire-bond NSOP in temperature cycling · ESD (HBM) pin-leakage after a tooling
change · MSL popcorn delamination after reflow.

| What | Where |
|---|---|
| Intake evidence JSON + case-4 wafer-sort CSVs | `sample-data/semi-failure-analysis/` |
| True mechanism and the discriminating technique per case | `evals/semi-failure-analysis/golden/` |
| Recorded eval results and honest status | `evals/semi-failure-analysis/EVALS.md` |
| Re-run the suite | `python evals/semi-failure-analysis/run_evals.py` |

The intake files deliberately do **not** contain the answer: `suspected` carries the requester's
belief, which is wrong in cases 1, 3 and 4. Use them to rehearse the flow, not to look it up.

## References index

| File | Load when |
|------|-----------|
| `references/failure-mechanisms.md` | Building/updating the hypothesis table |
| `references/technique-matrix.md` | Choosing or explaining any technique; reviewing selector output |
| `references/esd-eos-discrimination.md` | Before writing "ESD" or "EOS" anywhere |
| `references/bin-signature-analysis.md` | Reading datalogs, bins, Shmoo, populations |
| `references/report-templates.md` | Writing the 8D / FA report |

*Grounding: methodology aligned with public FA practice as described in EDFAS-community
literature, JEDEC JESD671-style guidance, and 2026 agentic-FA research (SemiFA,
arXiv:2604.13236; LLM planning agents for FA, arXiv:2506.15567) — all summarized in our own
words; no standard text is reproduced.*
