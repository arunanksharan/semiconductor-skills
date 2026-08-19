# EVALS — `semi-fab-process`

Every number below was produced by running the shipped scripts against the shipped sample
data on the date recorded, and pasted from the actual stdout. Nothing here is estimated.

**Environment:** macOS (darwin 24.6.0), Python 3.11.12, numpy 2.2.6, pandas 2.3.3,
scipy 1.17.1, matplotlib 3.10.8. Run date 2026-08-20.

**Data:** all synthetic, regenerated deterministically by
`skills/semi-fab-process/scripts/gen_excursion_data.py --outdir sample-data/semi-fab-process`
(default seed 20260820). 12 files, **64 KB total** (limit 200 KB). Never present it as
measured fab data.

Paths below are relative to the repo root. Prefix scripts with
`skills/semi-fab-process/scripts/` and data with `sample-data/semi-fab-process/`.

## Scoreboard

| # | Eval | Acceptance criterion | Result |
|---|---|---|---|
| a | Etch CD drift seeded to ONE chamber | `commonality.py` ranks the guilty chamber **#1**; runbook concludes in a **targeted chamber hold** | **PASS** — ETCH-02/C ranked #1 on both the full window (p_tail 0.00351) and the scoped window (p_tail 0.000985, z 7.14); targeted hold on 4 lots |
| b | Metrology false alarm | Runbook exits at "re-measure / verify metrology" with **no process hold** | **PASS** — Gate 0 FAIL; gauge monitor chart steps +7.4 Å on the cal date; second tool reads 8.4 Å lower; NO HOLD |
| c | `doe_builder.py` 2^(5-2) | Correct alias structure, printed and verified | **PASS** — I = ABD = ACE = BCDE, resolution III, 7 alias classes; independently reproduced by a second method |
| d | All scripts | `python -m py_compile` and `--help` pass | **PASS** — 5/5 and 5/5 |

---

## Eval (a) — etch CD drift confined to one chamber

**Seeded ground truth** (`gen_excursion_data.py --scenario etch`): 60 lots over 2026-07-01 to
2026-07-30, four steps (LITHO 3 tools · ETCH 2 tools × 3 chambers · CMP 2 tools · METRO 2
tools). Post-etch CD target 45.0 nm, LSL 43.5 / USL 46.5. **Chamber ETCH-02/C** drifts high
starting 2026-07-16 (ramp to +2.2 nm over ~6 days, then flat). Every other tool and chamber is
healthy (offsets ≤ 0.1 nm). `events.csv` carries a **PART_CHANGE on ETCH-02/C dated
2026-07-15**: "focus ring + upper liner replaced; short season, qual on 1 monitor wafer".

### GATE 0 — metrology verification: PASS

The three flagged lots were **not** measured by a single metrology tool:

| lot | date | etch tool/chamber | metro tool | CD (nm) |
|---|---|---|---|---|
| L0048 | 2026-07-24 | ETCH-02/C | MET-01 | 46.586 |
| L0058 | 2026-07-29 | ETCH-02/C | MET-02 | 46.787 |
| L0060 | 2026-07-30 | ETCH-02/C | MET-02 | 47.256 |

Both gauges report the excursion, so a single-gauge bias cannot explain it. The only metrology
event in the window is a routine MET-01 CD-SEM magnification cal on 2026-07-22 with the
monitor unchanged — it post-dates the first drifted lot (L0032, 2026-07-16) and only touches
one of the two tools. Gate 0 → **PASS, continue**. (In a real fab this gate would also require
a repeat measurement and the gauge's own monitor chart; the scenario does not ship one for the
CD-SEM, so the gate is recorded as passed on the two-tool agreement plus event history —
weaker evidence, and honest about it.)

### 1. Confirm the signal

```bash
python3 skills/semi-fab-process/scripts/spc_charts.py \
  --data sample-data/semi-fab-process/etch_cd_drift/cd_by_lot.csv \
  --value cd_nm --label lot_id --chart imr --baseline 30 --usl 46.5 --lsl 43.5
```
```
limits     : CL 44.9803   UCL 46.0466   LCL 43.9140   sigma_hat 0.3554   (from first 30 points)
capability : Cp=1.407  Cpk=1.388
VERDICT    : OUT OF CONTROL
rule  point                value       z
1     L0048              46.5860   +4.52   point beyond 3 sigma
1     L0058              46.7870   +5.08   point beyond 3 sigma
1     L0060              47.2560   +6.40   point beyond 3 sigma
2     L0060              47.2560   +6.40   2 of 3 consecutive beyond 2 sigma, same side
```

Three scattered rule-1 points, no clean run — because five of six chambers are healthy and the
chart mixes them. **This is the lesson: a fleet-level chart under-reports a single-chamber
drift.** Max deviation 47.256 nm is 0.756 nm above USL 46.5, so there *is* material risk.

### 2. Scope

Time: first bad point L0048 (2026-07-24) on the fleet chart, but the boundary from the drifted
chamber's own chart is **2026-07-16** (L0032). Material: 3 flagged lots of 60. Route: post-etch
CD is set by LITHO and ETCH, so both are in scope. Sampling: every lot measured, so there is no
invisible population in this scenario (called out because in most real cases there is).

### 3. Commonality — the guilty chamber ranks #1

**Full window (all 60 lots):**
```bash
python3 skills/semi-fab-process/scripts/commonality.py \
  --history sample-data/semi-fab-process/etch_cd_drift/history.csv \
  --metric sample-data/semi-fab-process/etch_cd_drift/cd_by_lot.csv \
  --metric-col cd_nm --top 6
```
```
flagged lots  : 3  (L0048, L0058, L0060)
ranking key   : TAIL (hypergeometric over-representation among flagged lots)
direction     : excursion is HIGH
global drift  : Spearman r(metric, time) = +0.174 (p=0.183)

#  candidate               lvl      n_in n_out   mean_in    delta  shift_z  flag_in    p_tail      d       t
1  ETCH/ETCH-02/C          chamber    10    50    45.489   +0.451     3.28      3/3   0.00351   0.86    1.32
2  ETCH/ETCH-02            tool       30    30    45.183   +0.140     1.37      3/3     0.119   0.26    0.99
3  LITHO/LITH-02           tool       17    43    45.285   +0.239     2.10      2/3     0.191   0.44    1.22
4  CMP/CMP-02              tool       36    24    45.155   +0.104     1.00      3/3     0.209   0.19    0.76
5  METRO/MET-02            tool       36    24    45.111   -0.006    -0.06      2/3      0.65  -0.01   -0.04
6  LITHO/LITH-01           tool       19    41    44.921   -0.282    -2.56      1/3     0.688  -0.53   -1.97
```
**ETCH-02/C is #1 with p_tail = 0.00351** (all 3 flagged lots in a group holding 10 of 60
lots), 34× smaller than the runner-up's 0.119. No TIE and no TIME-CONFOUNDED flag on the top
suspect. Note that its Welch t is only **1.32** and its Cohen's d only **0.86** — a mean-shift
statistic would rank it *fourth*, because 6 of its 10 lots ran before the drift started and
inflate its within-group variance. This is exactly why the script ranks a partial excursion by
tail over-representation and reports t/d as secondary information.

**Scoped to the window since the drift started:**
```bash
python3 skills/semi-fab-process/scripts/commonality.py \
  --history sample-data/semi-fab-process/etch_cd_drift/history.csv \
  --metric sample-data/semi-fab-process/etch_cd_drift/cd_by_lot.csv \
  --metric-col cd_nm --since 2026-07-16 --top 6
```
```
#  candidate               lvl      n_in n_out   mean_in    delta  shift_z  flag_in    p_tail      d       t
1  ETCH/ETCH-02/C          chamber     4    26    46.657   +1.628     7.14      3/3  0.000985   4.36    6.05
2  ETCH/ETCH-02            tool       13    17    45.508   +0.461     2.95      3/3    0.0704   0.72    1.76
3  CMP/CMP-02              tool       18    12    45.380   +0.335     2.12      3/3     0.201   0.51    1.47
4  LITHO/LITH-02           tool        9    21    45.531   +0.407     2.40      2/3     0.207   0.62    1.28
```
Scoping sharpens every statistic: delta +0.451 → **+1.628 nm**, z 3.28 → **7.14**, d 0.86 →
**4.36**, t 1.32 → **6.05**, p_tail 0.00351 → **0.000985**.

**When did it start** (top suspect vs the rest, scoped run):

| bucket | from | to | n_in | mean_in | n_out | mean_out | delta |
|---|---|---|---|---|---|---|---|
| 0 | 2026-07-16 | 2026-07-19 | 1 | 46.000 | 7 | 45.090 | +0.910 |
| 1 | 2026-07-20 | 2026-07-23 | 0 | – | 7 | 44.988 | – |
| 2 | 2026-07-23 | 2026-07-26 | 1 | 46.586 | 6 | 44.978 | +1.608 |
| 3 | 2026-07-27 | 2026-07-30 | 2 | 47.022 | 6 | 45.058 | +1.964 |

Growing delta = a drift with a start date, not a chamber that was always different. On the
full-window run the same table reads −0.361 / −0.313 / +0.961 / +1.859, i.e. the chamber was
*below* average before 2026-07-16 and above it after — a clean boundary at the part change.

### 4. Chamber-only chart confirms the boundary

```bash
python3 skills/semi-fab-process/scripts/spc_charts.py \
  --data sample-data/semi-fab-process/etch_cd_drift/cd_by_lot.csv \
  --value cd_nm --label lot_id --chart imr \
  --where etch_tool=ETCH-02 --where etch_chamber=C --baseline 6
```
```
limits : CL 44.7105  UCL 45.3281  LCL 44.0929  sigma_hat 0.2059  (from first 6 points)
VERDICT: OUT OF CONTROL
1  L0032  46.0000   +6.26      1  L0048  46.5860   +9.11
1  L0058  46.7870  +10.09      1  L0060  47.2560  +12.37
NOTE: baseline of 6 points is thin; limits from <20-25 points are themselves uncertain
```
Split by chamber, **every** post-2026-07-16 lot is out — including L0032, which the fleet chart
missed (46.000 vs a fleet UCL of 46.047). The script's own thin-baseline warning fires, and it
should: 6 points is not a real baseline, so this chart confirms a boundary rather than proving
a magnitude.

### 5. Independent confirmation (FDC) — required before acting

`fdc_etch.csv`, ETCH-02/C endpoint time: **61.41 s** before 2026-07-16, **64.35 s** after;
the other five chambers over the same period sit at **62.12 ± 0.65 s** (n=50). The post-drift
chamber is ~3.4σ off the fleet on a parameter nobody was charting.

```bash
python3 skills/semi-fab-process/scripts/spc_charts.py \
  --data sample-data/semi-fab-process/etch_cd_drift/fdc_etch.csv \
  --value endpoint_time_s --label lot_id --chart ewma \
  --where tool=ETCH-02 --where chamber=C --baseline 6 --lambda 0.2
```
→ EWMA out of limits at L0048, L0058, L0060. Chamber pressure is flat (29.5–30.5 mTorr
throughout), so the mechanism is not pressure control. Endpoint time lengthening after a focus
ring + liner replacement with only a short season points at chamber condition / part
configuration, per `references/process-modules.md` (etch: consumable and part-change modes),
**not** at seasoning — seasoning decays, and this grows and then holds.

### 6. Runbook conclusion — TARGETED CHAMBER HOLD (branch 3)

| Field | Value |
|---|---|
| Gate 0 | PASS (both metrology tools see it; no gauge event explains it) |
| Signal | Sustained shift on ETCH-02/C from 2026-07-16; 3 lots beyond the fleet UCL, max 47.256 nm (USL 46.5) |
| Scope | ETCH step, chamber ETCH-02/C, 2026-07-16 onward |
| Commonality | ETCH-02/C #1, p_tail 0.000985 scoped; no tie, no time confounding |
| Confirmation | FDC endpoint time +2.9 s vs its own history, +2.2 s vs the fleet |
| Change match | PART_CHANGE ETCH-02/C 2026-07-15 (focus ring + upper liner, short season, 1-wafer qual) |
| **Hold** | **TARGETED: the 4 lots that ran ETCH-02/C on or after 2026-07-16 — L0032, L0048, L0058, L0060 — plus a dispatch block on ETCH-02/C** |
| Explicitly NOT held | The other 26 lots in the window, including the 26 that ran ETCH-01 (all chambers) and ETCH-02/A and /B: they are in family, and holding them buys nothing while costing WIP |
| Release criteria | Re-measure held lots; disposition against USL 46.5; L0032 (46.000) is in spec and may release on measurement alone; L0048/L0058/L0060 exceed USL and need a device-level disposition |
| Root cause (hypothesis) | Part change without adequate season/requal; the 1-monitor-wafer qual criterion did not detect the offset |
| Systemic fix | Requal criterion after a part change, and RF-hours-based rather than calendar-based part scheduling |
| Fix verification | Monitor wafers on ETCH-02/C vs a reference chamber, paired design (`references/chamber-matching.md`), before returning it to dispatch |
| Limit review | Deferred to close-out. The fleet-level chart is the real weakness — see below |

**Why not a broad hold:** the affected population is fully identifiable (chamber-level history
exists, boundary is sharp, commonality is clean and independently confirmed), which is
precisely branch 3 of the hold decision tree. A full-lot hold would have held 30 lots instead
of 4 for no additional protection.

### Bonus finding — rational subgrouping, demonstrated

Charting the same data as X̄-R with **sites-within-a-lot as the subgroup** (n=15):

```bash
python3 skills/semi-fab-process/scripts/spc_charts.py \
  --data sample-data/semi-fab-process/etch_cd_drift/cd_sites.csv \
  --value cd_nm --subgroup-col lot_id --chart xbar-r --baseline 30
```
```
limits : CL 45.0016  UCL 45.1492  LCL 44.8540  sigma_hat 0.1906
rule-1 points: 8 / 60  (L0022, L0029, L0032, L0037, L0044, L0048, L0058, L0060)
```
σ̂ collapses from 0.3554 (I-MR, lot-to-lot) to **0.1906** (within-lot site scatter), the limits
close to ±0.15 nm, and **8 of 60 lots** alarm — 5 of them perfectly healthy. This is the
subgrouping failure described in `references/fdc-spc.md §3`, reproduced with real numbers.

---

## Eval (b) — metrology false alarm: no process hold

**Seeded ground truth** (`gen_excursion_data.py --scenario metro`): 44 lots of film thickness,
2026-08-01 to 2026-08-22, steps DEP (2 tools × 2 chambers), RTP (2 tools), METRO (2 tools).
Target 1000 Å. A **calibration on MET-02 dated 2026-08-16** puts a **+7.0 Å bias** on
everything MET-02 measures afterwards. **The process is unchanged.** Exactly one lot crosses
the control limit (the generator searches seeds until that is true).

### The trigger

```bash
python3 skills/semi-fab-process/scripts/spc_charts.py \
  --data sample-data/semi-fab-process/metro_false_alarm/thickness_by_lot.csv \
  --value thickness_a --label lot_id --chart imr --baseline 30 --usl 1030 --lsl 970
```
```
limits     : CL 1000.2727  UCL 1010.3488  LCL 990.1965  sigma_hat 3.3587  (first 30 points)
capability : Cp=2.977  Cpk=2.950
VERDICT    : OUT OF CONTROL
1  F0044  1015.8400  +4.63   point beyond 3 sigma
2  F0040  1007.1700  +2.05   2 of 3 consecutive beyond 2 sigma, same side
3  F0040 / F0042            4 of 5 consecutive beyond 1 sigma, same side
4  F0042 / F0043 / F0044    8 consecutive on one side of the centre line
```
One point beyond 3σ (F0044) plus run rules. Read naively this is "a shift with a confirmed
excursion" and the reflex is a hold on the DEP step.

### GATE 0 — metrology verification: **FAIL**

| Check | Data (`remeasure.csv`, `metro_events.csv`, `metro_monitor.csv`) | Read |
|---|---|---|
| **Repeat measurement**, same wafers, same tool | F0044 original **1015.84** → repeat **1016.54** (Δ +0.70) | Repeatable. This is not a flyer read — and it does **not** clear a bias |
| **Second metrology tool** | Same wafers on MET-01: **1007.45** (Δ **−8.39** vs original) | The number is tool-specific |
| **Gauge event history** | `metro_events.csv`: **2026-08-16, MET-02, CAL — "calibration after light-source service; reference-wafer check skipped"** | A change to the gauge, on the right date, with the verification step skipped |
| **SPC on the gauge itself** | Reference wafer REF-STD-07, MET-02, limits frozen on 30 pre-event points: CL 1000.08, UCL 1003.88, σ̂ 1.26. **Seven consecutive points beyond 3σ, 2026-08-16 through 2026-08-22, at +5.81σ to +8.22σ** (1007.43–1010.48 vs a CL of 1000.08) | The gauge stepped ~+7.4 Å on the cal date and stayed there |
| Control gauge | Same chart for MET-01: **IN CONTROL** (supplementary run rules only) | The other gauge did not move |

Corroboration that the bias is on every MET-02 lot, not just the OOC one:

| lot | MET-02 reading | MET-01 re-measure | delta |
|---|---|---|---|
| F0044 (the OOC lot) | 1015.84 | 1007.45 | −8.39 |
| F0040 | 1007.17 | 1000.13 | −7.04 |
| F0042 | 1003.99 | 995.63 | −8.36 |
| F0044 post-recal on MET-02 | — | 1008.90 | −6.94 vs original |

Mean offset ≈ **−7.7 Å**, against a seeded bias of −7.0 Å plus measurement noise. Population
means tell the same story: pre-cal all lots **1000.27**, post-cal MET-01 lots **1001.99**,
post-cal MET-02 lots **1006.51**.

Supporting (not decisive) commonality over the post-cal window:
```bash
python3 skills/semi-fab-process/scripts/commonality.py \
  --history sample-data/semi-fab-process/metro_false_alarm/history.csv \
  --metric sample-data/semi-fab-process/metro_false_alarm/thickness_by_lot.csv \
  --metric-col thickness_a --since 2026-08-16 --top 5
```
```
flagged lots  : 1  (F0044)
ranking key   : SHIFT (robust two-sample z)   [only 1 flagged lot < --min-flagged 3: the tail test has no power here]
1  METRO/MET-02   tool   7   7  1006.513  +4.524   2.50   1/1   0.5   1.14   2.13
     flags: MIRROR-of METRO/MET-01
2  RTP/RTP-02     tool   2  12  1007.030  +3.242   1.25   0/1     1   0.72   2.38
3  DEP/DEP-01/B   chamber 4 10  1005.452  +1.682   0.84   0/1     1   0.37   0.73
```
The metrology tool outranks every process candidate (+4.52 Å, z 2.50), and the script correctly
degrades to the SHIFT key because a single flagged lot gives the tail test no power. It also
flags the MIRROR: a two-tool step cannot distinguish "MET-02 is high" from "MET-01 is low" —
which is why the *monitor-wafer chart*, not the commonality, is the decisive evidence.

### Runbook conclusion — FALSE-ALARM EXIT, **NO PROCESS HOLD**

| Field | Value |
|---|---|
| Gate 0 | **FAIL** — the measurement moved, the process did not |
| **Hold** | **NONE.** No lot hold, no DEP chamber hold, no recipe change |
| Data quarantine | Every MET-02 measurement from 2026-08-16 onward: 7 lots (F0032, F0034, F0036, F0038, F0040, F0042, F0044), plus any non-lot measurement on that tool |
| Re-measure | Done for F0040, F0042, F0044 on MET-01 → all in family. Remaining 4 lots to be re-measured before their data is released |
| Process verdict | In control across the window once the gauge offset is removed. Pre-cal mean 1000.27 vs post-cal MET-01 mean 1001.99 — a 1.7 Å difference on a σ of 3.36 |
| Metrology CA | Recalibrate MET-02 against REF-STD-07 (done: F0044 post-recal reads 1008.90, i.e. −6.94 vs the biased value); requalify; the gauge R&R logged as "scheduled, not yet run" on 2026-08-20 must actually run |
| Escape analysis | The cal procedure allowed the **post-cal reference-wafer check to be skipped**, and the monitor chart was not reviewed for 6 days. Both are the systemic fix |
| Decisions to revert | None were taken in this scenario — but this is the step that matters most: a recipe re-centre made against the biased data would have written −7 Å into the process |
| Close-out | Blameless. Recorded as "measurement verified, process confirmed in control", not as "no issue found" |

**What would have happened without Gate 0:** a hold on the DEP step (44 lots in the window),
an investigation into DEP-01/B (the top process candidate at +1.68 Å, z 0.84 — noise), and a
material risk of re-centring the deposition recipe by −7 Å against a biased gauge.

**Honest caveat:** the MET-02 monitor chart also shows one isolated pre-cal point on 2026-08-13
at −3.02σ. It is a single point inside the baseline window with no run structure; per the
runbook's single-point-vs-sustained branch it is an event/noise, not the step change, which
begins cleanly on 2026-08-16 and persists for seven consecutive points.

---

## Eval (c) — `doe_builder.py` 2^(5-2) alias structure

```bash
python3 skills/semi-fab-process/scripts/doe_builder.py --design fractional -k 5 -p 2 --alias-order 2
```
```
design      : fractional
factors (5): A,B,C,D,E
runs        : 8 total  (8 factorial, 0 axial, 0 centre)
generators  : D=AB, E=AC
fraction    : 2^(5-2) = 1/4 fraction, resolution III
defining relation: I = ABD = ACE = BCDE

ALIAS STRUCTURE (classes containing effects up to order 2):
  A = BD = CE = ABCDE
  B = AD = CDE = ABCE
  C = AE = BDE = ABCD
  D = AB = BCE = ACDE
  E = AC = BCD = ABDE
  BC = DE = ABE = ACD
  BE = CD = ABC = ADE

  WARNING resolution III: main effects are aliased with 2-factor interactions.
```

### Verification (independent of the script's algebra)

`doe_builder.py` derives this from group algebra on words (symmetric difference over the
defining subgroup). It was checked against a **different method**: build the 8-run design
matrix, form the contrast column for all 31 non-empty effects of a 5-factor design, and group
effects by identical (up to sign) columns.

| Check | Expected | Observed |
|---|---|---|
| Distinct contrast columns | 8 (7 estimable + the identity column) | **8** |
| Effects enumerated | 2⁵ − 1 = 31 | **31** |
| Estimable alias classes | 7 (= runs − 1) | **7**, identical to the printed list, member for member |
| Identity class | the defining relation | **ABD = ACE = BCDE**, matching `I = ABD = ACE = BCDE` |
| Resolution | shortest defining word = 3 → III | **III** |
| Class size | 2^p = 4 members each | 4 members each |

Design matrix produced (standard order, coded):

| Std | A | B | C | D=AB | E=AC |
|---|---|---|---|---|---|
| 1 | −1 | −1 | −1 | +1 | +1 |
| 2 | +1 | −1 | −1 | −1 | −1 |
| 3 | −1 | +1 | −1 | −1 | +1 |
| 4 | +1 | +1 | −1 | +1 | −1 |
| 5 | −1 | −1 | +1 | +1 | −1 |
| 6 | +1 | −1 | +1 | −1 | +1 |
| 7 | −1 | +1 | +1 | −1 | −1 |
| 8 | +1 | +1 | +1 | +1 | +1 |

Blocking check — `--block-on BC` on the same design correctly reports the whole alias class as
consumed: `2 blocks; CONFOUNDED with blocks (NOT estimable): BC = DE = ABE = ACD`.

### `doe_analyze.py` on that design — Lenth's method

Seeded truth for `doe_etch/screening_2_5_2_response.csv`: coefficients A −1.30, C +0.95,
B +0.35, D +0.02, E −0.05, noise σ 0.10 nm (so true *effects* are A −2.60, C +1.90, B +0.70).

```bash
python3 skills/semi-fab-process/scripts/doe_analyze.py \
  --data sample-data/semi-fab-process/doe_etch/screening_2_5_2_response.csv \
  --response CD_NM --generators "D=AB,E=AC" --half-normal-out hn.csv --plot hn.png
```
```
contrasts : 7 estimated (design supports at most 7 independent contrasts)
method    : Lenth PSE (unreplicated)
            PSE = 0.111  ME = 0.4178  SME = 0.9999  (m=7 effects, d=2.33 df)

effect           value        coef  >ME  >SME  alias
A              -2.5237     -1.2619   *     *   BD = CE = ABCDE
C               1.8167      0.9084   *     *   AE = BDE = ABCD
B               0.7498      0.3749   *         AD = CDE = ABCE
BC              0.1103      0.0551             DE = ABE = ACD
E              -0.1013     -0.0506             AC = BCD = ABDE
BE             -0.0467     -0.0234             CD = ABC = ADE
D               0.0077      0.0039             AB = BCE = ACDE
```
Recovered effects **−2.52 / +1.82 / +0.75** against seeded **−2.60 / +1.90 / +0.70**; D and E
correctly inert. A and C clear both ME and SME; **B clears ME but not SME** — the textbook-
correct outcome for a factor whose true effect (0.70) sits between the two bars, and the reason
B goes into the next experiment rather than into the recipe. The script collapses aliased terms
onto one contrast (m = 7, not 15), without which Lenth's PSE would be computed over duplicated
values.

### Characterisation design — t-tests and curvature

Seeded truth for `characterisation_2_3_response.csv` (2³, 2 replicates, 4 centre points):
A −1.28, C +0.92, B +0.30, AC −0.41, curvature +0.62 nm at the centre, σ 0.16.
```
method    : t-test on pure error;  MSE = 0.023771 on 11 df,  se(effect) = 0.07709
A_pressure              -2.7462  t=-35.62  p=0.0000  *
C_rf_power               1.7418  t= 22.59  p=0.0000  *
A_pressure*C_rf_power   -0.8310  t=-10.78  p=0.0000  *
B_gap                    0.5503  t=  7.14  p=0.0000  *
A_pressure*B_gap*C_rf_power  0.1587  t=2.06  p=0.0639
curvature : factorial mean 44.9548 vs centre mean 45.5080 (diff -0.5532)
            F = 41.205 on 1,11 df, p = 0.0000  -> CURVATURE PRESENT: go to RSM/CCD
```
All four real terms significant, the two inert 2fi and the 3fi not; the curvature test fires
and routes correctly to RSM. Note the script switched significance path on its own (pure error
available → t-tests) — the choice is made by the design, not by the user.

---

## Eval (d) — script hygiene

```
py_compile OK  doe_builder.py          --help rc=0  (62 lines)
py_compile OK  doe_analyze.py          --help rc=0  (44 lines)
py_compile OK  commonality.py          --help rc=0  (83 lines)
py_compile OK  spc_charts.py           --help rc=0  (48 lines)
py_compile OK  gen_excursion_data.py   --help rc=0  (34 lines)
```
5/5 compile, 5/5 `--help` exit 0. Every chart type exercised on real data (I-MR, X̄-R, EWMA);
every design type exercised (full factorial with blocking/centre points/replicates/real units,
2^(k-p) fractional, rotatable CCD). Dependencies: numpy, pandas, scipy, matplotlib only.
Data footprint 64 KB of 200 KB.

---

## Known limitations — what a domain expert should check

1. **The data is synthetic and generous.** Real excursions are messier: multiple simultaneous
   causes, missing history rows, chamber IDs that change meaning after a rebuild, metrology
   sampling that changes mid-window. The eval proves the *procedure and the tooling* work; it
   does not prove they survive dirty data.
2. **Gate 0 in eval (a) is only partly exercised** — the scenario has no CD-SEM monitor-wafer
   chart, so the gate passes on two-tool agreement plus event history rather than on the full
   four-check set. A fab fork should add gauge monitor data to that scenario.
3. **The commonality ranking keys are a judgement call.** TAIL-then-SHIFT with a `--min-flagged`
   switch handles the two excursion shapes in these scenarios; a fab with different sampling and
   different excursion shapes may want CUSUM-style change-point detection or a per-wafer model
   instead. The thresholds (`--flag-k 3.0`, `--min-flagged 3`, `--tie-tol 0.15`,
   `--time-confound-r 0.5`) are defaults, not standards.
4. **Hold thresholds and disposition authority are deliberately absent.** The decision tree
   names the branches; which deviation size triggers which branch, and who signs, is fab policy.
5. **The DOE generator catalogue** covers (k,p) up to k=8. Entries are standard resolution-
   maximising choices and the script always computes and prints the resolution it actually
   achieves, but minimum-aberration optimality beyond the listed cases has not been proven here
   — **TODO(verify)** against a published catalogue if you extend it.
6. **Power/sample-size guidance is a rule of thumb**, not a script. A `power.py` that sizes a
   DOE from a historical σ and a target detectable effect is the obvious next addition.
7. **No FDC trace-level tooling.** The skill describes trace summarisation and multivariate
   distance; the scripts only chart pre-summarised features. Real FDC integration needs the
   fab's trace store and is fork territory.
