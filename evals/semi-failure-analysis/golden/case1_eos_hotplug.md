# Golden case 1 — EOS from a hot-plug transient on a supply pin

| | |
|---|---|
| **Intake input** | `sample-data/semi-failure-analysis/case1_eos_hotplug.json` |
| **Completed record** (8D generator input) | `sample-data/semi-failure-analysis/case1_eos_hotplug_resolved.json` |
| **True mechanism** | Electrically induced physical damage on the VDD supply path, consistent with **sustained electrical overstress (EOS)** sourced by the application supply during live hot-swap — **not** the ESD the customer asserted |
| **Discriminating technique that must surface early** | `curve_trace` (pin-by-pin I-V vs known-good), phase **N0** |
| **Confirming technique** | `internal_optical` after decap (damage-area measurement), then `fib_cross_section` |
| **Edge cases exercised** | N = 1 (single-sample preservation) · customer return / chain of custody · requester asserts the wrong mechanism |

## Why this case exists

It is the ESD-vs-EOS misdiagnosis in its most commercially loaded form: the customer has already
named the mechanism ("this is ESD from our handling"), the named mechanism points the finger at
their own line, and accepting it would close the case with the wrong corrective action. The case
tests whether the skill reasons from damage energy rather than from the requester's framing.

It also tests the hardest sample constraint: **one unit, no siblings, and it is a customer
return.** Every destructive step ends the investigation, not just the unit.

## The intake picture

The input file contains only what an FA lab would hold at Step 1: a complaint, a package and
date code, a single unit with an open custody log, one external-visual observation (faint mold
discoloration over the pin-7 corner), and `suspected: ["esd"]` — which is the *requester's*
belief, deliberately wrong. There is **no** `mechanism` block and **no** hypothesis table in the
input. The answer lives only in this file.

## True mechanism

A sustained overstress event on the VDD rail during live-backplane hot-swap fused metal-1 on the
supply bus, creating a re-solidified metallic path into the substrate through cracked ILD. The
measured 2.8 Ω VDD-GND short is that fused path.

The correct verdict wording is neutral: *"electrically induced physical damage, most consistent
with a sustained supply-sourced overstress"* — with **medium** confidence, because the
application transient was never measured and latch-up was never positively excluded. A run that
returns "EOS, high confidence" is overclaiming and is scored down.

## Discriminating evidence, in the order it should appear

1. **`curve_trace`, N0.** VDD-GND is 2.8 Ω, linear and symmetric in both polarities; all 28 I/O
   pins match the known-good envelope. Two facts fall out immediately: the damage is a *metallic*
   path (not a degraded junction), and it is on the *supply* path (not on a pin protection
   device). A pin-level ESD event damages the clamp it fires through; here every clamp is intact.
2. **`datalog_review`, N0.** The unit passed final test with normal margin — no test escape, so
   the defect was created after manufacture.
3. **`csam` + `xray_2d`, N1.** Both null. They retire the popcorn/delamination and wire-short
   chains, and — critically — they are run *before* decap, which would have destroyed what
   C-SAM sees regardless of whether it found anything.
4. **`lock_in_thermography`, N2.** Localizes the site to the pin-7 die corner **without opening
   the package**. On a single-sample case this is what makes GATE D2 clearable later; a cut
   plane must come from a localization, not a guess.
5. **`internal_optical`, D1.** ~60 × 40 µm melt with displaced metal spanning the VDD bus and
   supply clamp. **The area measurement is the argument**: that volume needs orders of magnitude
   more energy than a human-body-model event can deliver through ~1.5 kΩ.
6. **`fib_cross_section` + `sem_edx`, D2.** Metal fused through full thickness; no Cl/Br/S above
   the reference site, retiring corrosion.

## What a correct plan must contain

- `curve_trace` in **N0**, before any imaging — it is the cheapest discriminator in the case.
- The **single-sample preservation branch** (phase P0): imagery is the archive, gates need
  written pre-registered expectations plus a second reviewer, FIB preferred over mechanical
  section, and no destructive population tests (wire pull / ball shear) on the only unit.
- **Chain of custody opened and as-received photography before any electrical test**, because
  `customer_return` is set.
- `csam` **before** any decap step.
- A `GATE D1` step before decap and a `GATE D2` step before the cross-section, each demanding
  explicit user confirmation.
- `magnetic_current_imaging` offered as the near-non-destructive option — this is exactly the
  case (hard short, N = 1) where its cost is justified.

## What a wrong run looks like

- Accepting "ESD" because the customer said it, or writing "the customer caused EOS" — both are
  the blame trap. The FA lab determines *mechanism*; commercial attribution is a business call.
- Recommending decap or cross-section before the curve trace and thermography.
- Reporting high confidence from one unit.
- Failing to note that the customer's own DMM check applied power to an already-damaged part and
  could in principle have extended the damage.
- Closing D4 with only the mechanism leg and no escape point. The escape here is *not* a test
  escape (the part was good at manufacture) — it is the application-review gap: hot-swap usage
  was never reviewed against the device's transient limits.

## Grounding

Composed for this repository from classic overstress-discrimination reasoning in the general
electronic-device-failure-analysis literature (EDFAS/ISTFA community practice) and the
component-level ESD model definitions in ANSI/ESDA/JEDEC JS-001 and JS-002. No real customer,
part number, or case is depicted; all part numbers, serials, dates and organizations are
invented. No standard text is reproduced.
