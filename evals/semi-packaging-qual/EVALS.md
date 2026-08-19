# semi-packaging-qual — eval scorecard

**Run date:** 2026-08-20 · **Python:** 3.11.12 · **numpy:** 2.2.6 · **pandas:** 2.3.3 ·
**Platform:** macOS (darwin 24.6.0)

Reproduce with:

```bash
pip install -r skills/semi-packaging-qual/requirements.txt
python3 evals/semi-packaging-qual/run_evals.py --verbose
```

Every number below is copied from an actual run, not estimated.

---

## 1. Headline result

```
OVERALL: PASS  (3/3 scenarios passed)
```

| | Result |
|---|---|
| Golden scenarios passed | **3 / 3** |
| Assertions executed across the three scenarios | **258** |
| LTPD self-check assertions | **12 / 12 pass** |
| Scripts compiling (`python -m py_compile`) | **5 / 5** |
| Scripts with a working `--help` | **5 / 5** (exit 0) |
| Documented SKILL.md commands executed verbatim | **12 / 12 exit 0** |
| Extra edge-case invocations exercised | **4 / 4 exit 0** |

The harness runs `qual_plan.py` as a **subprocess** against each scenario file, so what is
graded is the real CLI surface, not an importable shortcut.

---

## 2. Per-scenario results

### 2.1 `automotive_qfn_g1_derivative` — automotive QFN, AEC-Q100 grade 1, derivative

**PASS** — 100 assertions.

Produced: 18 rows · 3 lots · 1059 environmental-leg units · 2.95 % leg LTPD.

```
precon, tc, uhast, hast, thb, htsl, ptc, board_tc, wire_pull, ball_bond_shear,
die_shear, mech_shock, vibration, const_accel, solvent, solderability, phys_dim, visual
```

What was actually checked and what came back:

| Expectation | Produced |
|---|---|
| TC escalated to the grade-1 class condition | `JESD22-A104`, Condition B −55/+125 °C, **1000 cycles**, readpoints 500 / 1000 |
| HTSL escalated to 1000 h | `JESD22-A103`, 150 °C, **1000 h**, readpoints 500 h / 1000 h |
| Automotive lot floor overrides the derivative rule | **3 lots** (novelty rule alone would have given 1); plan note states the override |
| Biased HAST present with a Cu-wire warning | `JESD22-A110`, 130 °C/85 %RH/230 kPa, 96 h; note calls out halide-driven Cu-Al IMC corrosion |
| Automotive mechanical suite present | `JESD22-B104` shock + `JESD22-B103` vibration as **required**; `MIL-STD-883 M2001` constant acceleration as **conditional with a TODO** |
| No board-level **drop** (leadframe package, no handheld exposure) | absent ✓ |
| No solder **ball shear** (QFN has no balls) | absent ✓ |
| No warpage / die-strength / bump rows | absent ✓ |
| Board-level TC present but honest about its status | `IPC-9701` row, **conditional**, TODO on the class/condition |
| Sample sizes | env legs 77/lot × 3 = 231 @ accept 0; mechanical legs 45/lot × 3 = 135 |
| QFN-specific judgement surfaced | solderability note demands the **cut-copper lead flank** be evaluated; plan note recommends board-level void limits + wettable flank |

### 2.2 `consumer_wlcsp_new` — consumer WLCSP, new package family, MSL 1

**PASS** — 81 assertions.

Produced: 14 rows · 3 lots · 924 environmental-leg units · 2.95 % leg LTPD.

```
precon, tc, uhast, hast, thb, htsl, board_drop, board_tc, ball_shear,
solderability, phys_dim, visual, warpage, die_strength
```

| Expectation | Produced |
|---|---|
| **No wire pull, no ball-bond shear, no die shear** on a bare-die package | all three absent ✓ — this is the hallucinated-test check and it passes |
| MSL 1 maps to the *harshest* soak, not the mildest | precon soak **85 °C / 85 %RH, 168 h**; floor life "unlimited at ≤30 °C / 85 %RH" ✓ |
| New family → 3 lots | **3 lots** ✓ |
| New family → wear-out duration, not a 500-cycle gate | TC **1000 cycles** (class default 500), HTSL **1000 h** (class default 500), both flagged in the plan notes as a **HOUSE RULE, not a standard requirement** |
| Board-level drop mandatory (wearable) | `JESD22-B111`, 1500 G / 0.5 ms, 30 drops, ≥5 daisy-chain boards × 15 components, **required** |
| Board-level TC required, not optional | `IPC-9701` row marked **required** for this family |
| Ball shear present, mode-based acceptance | `JESD22-B117`; note makes failure **mode** the acceptance criterion, not force alone |
| No automotive suite, no PTC | shock / vibration / constant-acceleration / solvents / PTC all absent ✓ |
| Thin-die risk covered | `die_strength` row (3-point bend, Weibull), **conditional** — no single JEDEC method to cite, TODO to agree with the OSAT |
| Small-body warpage handled honestly | `JESD22-B112` present but **conditional** with a TODO: a 2.6 mm body rarely warps enough to cause head-in-pillow |

### 2.3 `industrial_bga_derivative` — industrial PBGA, derivative

**PASS** — 77 assertions.

Produced: 15 rows · 1 lot · 308 environmental-leg units · 2.95 % leg LTPD.

```
precon, tc, uhast, hast, thb, htsl, board_tc, wire_pull, ball_bond_shear,
die_shear, ball_shear, solderability, phys_dim, visual, warpage
```

| Expectation | Produced |
|---|---|
| Derivative on a non-automotive part → **1 lot** + similarity justification | **1 lot**; plan note spells out what the justification must contain |
| Industrial escalation sits between consumer and automotive | TC Condition B −55/+125 °C **1000 cycles**; HTSL 150 °C **1000 h** |
| MSL 3 soak | precon **30 °C / 60 %RH, 192 h**, floor life 168 h ✓ |
| Wire-bond *and* ball-array construction → both interconnect suites | wire pull + ball-bond shear + die shear **and** solder ball shear ✓ |
| Large organic body → warpage is required, not optional | `JESD22-B112` marked **required** ✓ |
| No drop, no PTC, no automotive mechanical suite | all absent ✓ |

---

## 3. LTPD numeric verification (the requested check)

`sample_size.py` implements the exact binomial acceptance function
`P_accept(p) = Σ_{k≤c} C(n,k) p^k (1−p)^(n−k)` in log space (`math.lgamma` + numpy), and
solves it by bisection. **No scipy.** `--self-check` grades it against known table anchors:

```
sample_size.py self-check (confidence 90%)
  [PASS] LTPD(n=77, c=0)                        expected 3.0   computed 2.9461
  [PASS] LTPD(n=45, c=0)                        expected 5.0   computed 4.9881
  [PASS] LTPD(n=22, c=0)                        expected 10.0  computed 9.9372
  [PASS] LTPD(n=32, c=0)                        expected 7.0   computed 6.9428
  [PASS] min_n(LTPD=10.0%, c=0) exact           expected 22    computed 22
  [PASS] min_n(LTPD=5.0%, c=0) exact            expected 45    computed 45
  [PASS] min_n(LTPD=3.0%, c=0) exact            expected 76    computed 76
  [PASS] min_n(LTPD=1.0%, c=0) exact            expected 230   computed 230
  [PASS] round-trip LTPD(min_n(10.0%, c=0))     expected <= 10.0  computed 9.9372
  [PASS] round-trip LTPD(min_n(5.0%, c=0))      expected <= 5.0   computed 4.9881
  [PASS] round-trip LTPD(min_n(3.0%, c=0))      expected <= 3.0   computed 2.9843
  [PASS] round-trip LTPD(min_n(1.0%, c=0))      expected <= 1.0   computed 0.9961
  OVERALL: PASS
```

**The two anchors the build asked for:**

| Plan | Computed LTPD @ 90 % confidence | Table value | Verdict |
|---|---|---|---|
| n = 77, c = 0 | **2.9461 %** | "3 %" | matches |
| n = 45, c = 0 | **4.9881 %** | "5 %" | matches |

Inverse direction, `--ltpd 3`:

```
  accept c | min n (exact binomial) | min n (Poisson table) | LTPD at exact n
         0 |                     76 |                    77 |         2.984 %
         1 |                    129 |                   130 |         2.982 %
         2 |                    176 |                   178 |         2.996 %
```

Full min-n table (`--table`), exact binomial at 90 % confidence:

```
  accept c |    10% |     7% |     5% |     3% |     2% |     1%
         0 |     22 |     32 |     45 |     76 |    114 |    230
         1 |     38 |     55 |     77 |    129 |    194 |    388
         2 |     52 |     75 |    105 |    176 |    265 |    531
```

**The 76-vs-77 discrepancy is real and is documented, not papered over.** The exact binomial
minimum for 3 % / accept-0 is **76**; the printed MIL-S-19500 / JEDEC tables say **77**
because they round through the Poisson (chi-square) approximation, which gives
`m/LTPD = 2.302585/0.03 = 76.75 → 77`. The script prints both columns and names which is
which. `qual_plan.py` uses 77 for compatibility with the entrenched industry value and
reports its *actual* demonstrated LTPD (2.95 %) rather than the nominal 3 %. The c = 1 (129)
and c = 2 (176) values also match the classic table entries, which is independent evidence
the implementation is right.

Also verified by hand during the build:
`LTPD(n, 0) = 1 − 0.1^(1/n)`; for n = 77 that is `1 − exp(ln(0.1)/77) = 0.029461` — identical
to the bisection result to 6 decimal places.

---

## 4. `msl_advisor.py` sanity cases (5 run, 5 sensible)

| # | Input | Classification peak | Starting MSL | Floor life | Peak check | Bake |
|---|---|---|---|---|---|---|
| A | WLCSP, 0.5 mm, 3×3 body, die = body, target MSL 1, customer peak 260 °C | 260 °C | **1** | unlimited | OK | 125 °C / 24 h |
| B | PBGA, 1.2 mm, 800 mm³, target MSL 3, peak 260 °C, tape-and-reel | 260 °C | **3** | 168 h | OK | 125 °C / 24 h + **tape-and-reel will not survive it** |
| C | FCBGA, 2.8 mm, 3000 mm³, peak 260 °C, tray, die/pkg 0.35 | **245 °C** | **4** | 72 h | **CONFLICT** | 125 °C / 48 h+ |
| D | QFN, 0.9 mm, 5×5 body, die/pkg 0.75, peak 245 °C, tape-and-reel | 260 °C | **2a** | 4 weeks | HEADROOM | 125 °C / 24 h |
| E | QFP, 2.2 mm, 1500 mm³, peak 250 °C | 250 °C | **4** | 72 h | OK | 125 °C / 48 h+ |

Case C is the one that matters: a 2.8 mm / 3000 mm³ body classifies at **245 °C**, so a
customer running a 260 °C profile gets a hard **CONFLICT** verdict with the reason spelled
out. Case D shows the die-to-package ratio doing real work — a 0.75 ratio pushes a QFN from
its family baseline of MSL 2 to MSL 2a on thin-mold-cap grounds. Case A shows the bare-die
guard: WLCSP has a ratio of ~1 by construction and correctly takes **no** mold-cap penalty
(an earlier build wrongly demoted it to MSL 2; the guard was added and the case re-run).

---

## 5. Script check list (all executed, all exit 0)

| Script | `py_compile` | `--help` | Functional run |
|---|---|---|---|
| `scripts/qual_plan.py` | PASS | PASS | 3 scenarios + 4 edge cases (grade 0 FCBGA, QFP process-change, FOWLP with `--suppress-board-level`, `--list-packages`) |
| `scripts/msl_advisor.py` | PASS | PASS | 5 sanity cases + `--levels-table` + `--json` |
| `scripts/sample_size.py` | PASS | PASS | `--n/--accept`, `--ltpd`, `--fails`, `--table`, `--self-check`, `--json` |
| `scripts/gen_scenarios.py` | PASS | PASS | wrote all 3 scenario files; `--list` works; re-run is idempotent (skips existing without `--force`) |
| `evals/…/run_evals.py` | PASS | PASS | full run, `--verbose`, `--json`, `--scenario` filter |

Edge-case behaviour confirmed:

- `--device-class automotive_grade0 --package fcbga --novelty new_package` → TC **2000
  cycles at −65/+150 °C**, HTSL **175 °C**, and the flip-chip-specific rows appear
  (`corner_csam` required, `bump_integrity` conditional) while all wire-bond rows stay out.
- `--suppress-board-level` removes the auto-included board-level rows **and** emits a plan
  note demanding a written justification — it cannot be used silently.
- `--novelty process_change` gives 2 lots and a note that the matrix is the *maximum* scope
  to be pruned against a documented change-impact analysis.

---

## 6. Structural invariants the harness enforces on every plan

Beyond the golden diffs, `run_evals.py` asserts two things about every emitted plan:

1. **A `verify_block` must exist** (SKILL.md operating rule 2 — no plan is presentable
   without it).
2. **Every `applicability: conditional` row must carry a TODO** in its note or standard
   string. This one *caught a real defect during the build*: the WLCSP `warpage` row was
   emitted as conditional with no TODO, so a reviewer had no way to know what decision was
   outstanding. Fixed by making the note state the decision and who owns it. The invariant
   stays in the harness to stop it regressing.

---

## 7. Honest notes for a domain-expert review

These are the things a package-reliability engineer should attack first. They are written as
open questions, not as defended positions.

**Highest priority — the automotive escalation table is the weakest thing here.**
`DEVICE_CLASSES` in `qual_plan.py` encodes grade→condition mappings (grade 0: −65/+150 °C
2000 cycles, HTSL 175 °C; grades 1–2: −55/+125 °C 1000 cycles, HTSL 150 °C; grade 3:
−40/+125 °C). These are **industry-typical templates assembled from general knowledge, not
transcribed from a copy of AEC-Q100**, and the AEC package-integrity table moves between
revisions. Several houses run grade 1 at −50/+150 °C rather than −55/+125 °C. Every
automotive row carries a `verify` string naming the grade column to confirm, and
`references/aec-q100-mapping.md` marks the gap as an explicit TODO — but an expert should
diff the whole table against a current download before any of this drives a real build.

**Standards whose number or applicability is genuinely uncertain (all marked TODO in-code):**

- **Constant acceleration** (`MIL-STD-883 M2001`) — historically a cavity/hermetic test.
  Emitted as *conditional* for automotive with a TODO asking whether the current AEC revision
  requires it for overmolded plastic. An expert should settle this yes/no.
- **Board-level TC** — cited as "IPC-9701 practice" because JEDEC has no single
  component-agnostic BLR TC number. The sample size (≥30 daisy-chained components) is house
  practice, not a verified minimum from the standard.
- **Wire pull** — cited as `MIL-STD-883 Method 2011`, which is what the industry actually
  uses, with a TODO on whether a JEDEC-numbered equivalent is expected.
- **Die shear** — cited as `MIL-STD-883 Method 2019` with a TODO on the preferred method
  number for plastic packages.
- **Cu-pillar bump shear / cold bump pull** — no standard cited at all, only a TODO to agree
  the method with the OSAT. This is the row most likely to be wrong and it says so.
- **SnPb classification peaks** in `msl_advisor.py` — the Pb-free thickness×volume table is
  the one that was reasoned through carefully; the legacy SnPb cells carry a TODO.

**Judgement calls that are defensible but arguable:**

- The **new-package duration floor** (≥1000 TC cycles, ≥1000 h HTSL even for consumer) is a
  house rule I introduced and labelled as one in the plan notes. A reviewer may want it gone
  for cost reasons on a consumer part.
- The **automotive 3-lot floor applied to derivatives** is conservative. AEC allows leveraging
  generic/family data; the generator makes you argue *down* from 3 rather than *up* from 1.
  That is a deliberate direction-of-error choice, not an accident.
- The **MSL starting-point heuristic** (family baseline, +1 level for a geometry hit, +1 for a
  die/package ratio ≥0.70, capped at +2, geometry counted once because thickness and volume
  are correlated) is engineering judgement with no standard behind it. It is a hypothesis
  generator for a classification run, and the tool says so in its own output — but the
  thresholds (2.0 mm, 2000 mm³, 0.70) deserve a second opinion.
- **Mechanical-leg sample size of 45/lot** (5 % LTPD) versus the 77/lot on environmental legs
  is common practice, but some houses run 22 or 32. The generator makes the demonstrated LTPD
  visible in the sample-size cell so the trade is explicit rather than buried.

**What is genuinely solid:**

- The LTPD/AQL math. It is exact binomial, it round-trips, and it reproduces four independent
  published table anchors including the c = 1 (129) and c = 2 (176) entries that a naive
  Poisson implementation would miss.
- The **structural** logic: which tests attach to which construction. No wire pull on bare
  die, no ball shear on a leadframe package, corner C-SAM and bump integrity only on
  flip-chip, board-level drop only where there is drop exposure, warpage only on area arrays.
  That is the part of the tool that encodes real judgement and it is what the golden
  forbidden-test lists are actually testing.
- The honesty plumbing: `verify_block`, `out_of_scope`, `applicability` and the TODO
  invariant. The tool is built so that an unverified claim is visible rather than confident.

**Not covered at all (by design, and declared in every plan):** HTOL, ELFR, ESD/latch-up —
die-level qualification, out of scope for a package plan. Also not covered: hermetic/ceramic
packages, power-module (IGBT/SiC) constructions, and anything optical or MEMS. 2.5D/3D is
present as a scaffold with an explicit "this is bespoke" warning, not as a usable matrix.

**No proprietary or NDA-derived content is used anywhere in this skill.** The JEDEC/AEC
digests are written in the author's own words with clause and document numbers only; no
standard text or table is reproduced verbatim.
