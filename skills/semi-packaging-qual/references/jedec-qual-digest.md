# JEDEC-style qualification digest — test by test

Own-words digest for planning purposes. **Conditions below are industry-typical defaults —
the current revision of each standard governs.** JEDEC standards are free downloads
(jedec.org, registration required). Anything not re-verified against a current copy is a
template value; the emitted plan's `verify` block must say so.

JESD47 ("Stress-Test-Driven Qualification of Integrated Circuits") is the umbrella: it names
the stress set, default durations/sample sizes, and allows qualification-by-similarity for
derivatives. JESD94 covers knowledge-based/mission-profile tailoring when deviating from
defaults.

## Moisture / bias / temperature stress set

### Preconditioning — JESD22-A113 (+ J-STD-020 for the level definition)
- **Purpose:** simulate shipping + board mount before any other stress; all surface-mount
  reliability legs run *after* precon.
- **Flow:** electrical + time-zero C-SAM → bake dry → moisture soak at the target MSL's
  condition → 3× reflow at the classification peak (Pb-free profile per J-STD-020) → flux
  clean → electrical + C-SAM vs time zero.
- **Fails it precipitates:** popcorn cracking, mold/pad and die-attach delam, wire damage
  from body flex.
- **Gate:** any *new* delam on a critical interface or electrical fail = precon fail — stop,
  triage (Workflow 5), do not proceed to stress legs.

### Temperature cycling (TC) — JESD22-A104
- **Purpose:** CTE-mismatch fatigue — solder joints, wire heels/necks, die attach, underfill,
  passivation cracks.
- **Common letter conditions (Ta):** A −55/+85 · B −55/+125 · C −65/+150 · G −40/+125 ·
  J 0/+100 · N −40/+85 °C. Soak mode (dwell) matters for solder creep — record condition
  *and* soak/ramp, not the letter alone.
- **Typical durations:** consumer/industrial 500–1000 cycles (condition B or G); automotive
  1000–2000 cycles at harsher condition per grade (see aec-q100-mapping.md).
- **Readpoints:** 500 / 1000 (and 2000 if run); electrical + C-SAM sample at readpoints.
- **Signature fails:** ball/joint cracks (board-level version), wire neck/heel breaks,
  die-corner delam growth, die-attach fatigue.

### High-temperature storage life (HTSL) — JESD22-A103
- **Purpose:** pure thermal aging, no bias — IMC growth (Au-Al Kirkendall), mold compound
  outgassing/embrittlement, solder joint coarsening.
- **Conditions:** A 125 °C · B 150 °C · C 175 °C · D 200 °C. Typical: 150 °C/1000 h
  (consumer/industrial and automotive grade 1); 175 °C for grade 0 or as accelerated
  equivalent (with justification).
- **Readpoints:** 500 / 1000 h; wire-bond packages: bond pull/shear sample at readpoints,
  not just electrical.

### Biased HAST — JESD22-A110
- **Purpose:** accelerated humidity + bias → electrochemical corrosion/migration (Al pad
  corrosion, Cu-Al IMC halide attack, dendrites).
- **Conditions:** 130 °C/85 %RH/~230 kPa, bias per device spec, 96 h (condition A) or
  110 °C/85 %RH 264 h (condition B). Bias chosen to maximize field without self-heating
  (>~10 °C junction rise invalidates the humidity exposure — derate or pulse the bias).
- **Replaces THB when equipment allows.** THB — JESD22-A101: 85 °C/85 %RH biased 1000 h
  (same mechanisms, longer clock; readpoints 500/1000 h).

### Unbiased HAST (uHAST) — JESD22-A118 (successor to autoclave/PCT A102)
- **Purpose:** moisture ingress + galvanic/chemical corrosion without bias; adhesion loss.
- **Conditions:** A 130 °C/85 %RH 96 h · B 110 °C/85 %RH 264 h.
- **Note:** autoclave (121 °C saturated, A102) is legacy — harsher on some materials and
  prone to condensation artifacts; prefer uHAST unless matching historical data.

### Power temperature cycling (PTC) — JESD22-A105
- **Purpose:** TC with device self-heating — real power/thermal gradients (die attach,
  exposed-pad thermal path). Mostly automotive/power devices; 1000 cycles typical
  (grade-dependent).

### Early-life / operating-life (die-oriented, listed for completeness)
- HTOL (JESD22-A108) and ELFR (AEC-Q100-008) qualify the *die*, not the package — include in
  a full product qual, out of scope for a package-only delta qual. Say so explicitly rather
  than silently omitting.

## Mechanical / board-level set

| Test | Standard | Typical condition | What it catches |
|---|---|---|---|
| Board-level drop | JESD22-B111 | 1500 G/0.5 ms half-sine, 30 drops, daisy-chain boards | WLCSP/CSP/BGA joint & UBM cracks — mandatory for handheld end products |
| Board-level TC | IPC-9701-style (JEDEC has no single component-agnostic BLR TC number — plan per product) | −40/+125, 1000–3000 cycles, daisy-chain | Solder fatigue of the *board* joint (dominant WLCSP/large-BGA wear-out) |
| Solder ball shear | JESD22-B117 | shear speed & height per std | Ball attach integrity, brittle IMC (black pad) |
| Bond shear | JESD22-B116 | shear tool at ball | Ball-bond IMC coverage/strength |
| Wire pull | MIL-STD-883 Method 2011 (industry habit; JEDEC lacks a direct clone — TODO verify chosen spec) | hook pull mid-span | Heel/neck integrity, NSOP escapes |
| Solderability | J-STD-002 (JESD22-B102 legacy) | steam age + dip or SMT simulation | Finish wetting after storage |
| Physical dimensions | JESD22-B100 | — | Outline vs registered outline (MO-xxx) |
| Coplanarity | JESD22-B108 / B100 family | ≤0.1 mm typical BGA spec | Warpage at room temp |
| External visual | MIL-STD-883 M2009-style | — | Marking, damage, flash |

## Sample sizes & lots (defaults; compute exact numbers with `scripts/sample_size.py`)

- Default env-stress leg: **77 units/lot, accept 0** → demonstrates ≈3 % LTPD at 90 %
  confidence (exact minimum is 76; 77 is the entrenched industry/AEC table value — either is
  defensible, use 77 for compatibility).
- **New package / new materials / new site: 3 non-consecutive lots** per JESD47 practice.
- **Derivative:** 1 lot with written similarity justification (JESD47 allows generic data);
  see SKILL.md Workflow 3 step 5 for when similarity is *disallowed*.
- Mechanical tests: smaller n (e.g., 22–45, accept 0 → LTPD 10–5 %) is common; state the
  demonstrated LTPD next to any reduced n — never present reduced sampling silently.
- 0-fail philosophy: any fail = fail-analyze + fix + re-qualify the leg; "1 of 77" is not a
  pass under accept-0 no matter how it's argued.

## Plan-skeleton (emit plans in this structure)

```
1. Scope & device description (die, package, materials set, novelty declaration)
2. Similarity justification (derivatives only: identical vs changed, risk argument)
3. MSL target & preconditioning definition
4. Test matrix table: test | standard | condition | duration & readpoints |
   n/lot × lots | accept | covers-risk
5. Pass criteria: electrical to datasheet at every readpoint; no new critical-interface
   delam vs time-zero C-SAM; parametric drift limits if specified
6. Verify block: standards + revisions to confirm before build (rule 2 of SKILL.md)
7. Open risks not covered by the matrix, with rationale
```

## Readpoint & disposition discipline

- A readpoint fail **stops the leg clock**: triage (assembly-defects.md), FA the unit
  (`semi-failure-analysis`), disposition = fix-and-restart or waiver-with-data. Continuing
  the stress on a failed population wastes the leg.
- Post-stress C-SAM compares against **the same unit's** time-zero scan (serialize units).
- Keep survivors: post-qual units are the reference population for future field-return FA.
