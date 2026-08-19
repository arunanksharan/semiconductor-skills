# Golden case 5 — MSL popcorn delamination after board reflow

| | |
|---|---|
| **Intake input** | `sample-data/semi-failure-analysis/case5_msl_popcorn.json` |
| **True mechanism** | **Moisture-induced popcorn cracking**: absorbed moisture flashed to steam during reflow, delaminating the die-attach and die-face interfaces and cracking the package, breaking bonds and lifting wires. Driven by a floor-life violation at the CM, not by a device defect |
| **Discriminating technique that must surface early** | `csam` (C-mode scanning acoustic microscopy), phase **N1** — and it must run **before any decap and before any bake** |
| **Confirming technique** | `mechanical_cross_section` through the delaminated interface, plane chosen from the C-SAM map |
| **Edge cases exercised** | Order-of-operations evidence destruction · the lab can *create* the failure it is looking for · a null control unit matters · latent risk in the surviving population |

## Why this case exists

This is the ordering case. Every other trap in the skill costs money; this one costs the answer.
Three routine lab actions destroy the evidence irreversibly:

- **Decapsulation before C-SAM** — decap chemistry, laser heat, and the hot plate all erase or
  create delamination at the interfaces you were sent to inspect.
- **Baking the received units** — a bake is the standard way to *fix* a moisture problem, and it
  erases the moisture state that is the entire root cause.
- **Any reflow or thermal step in the lab** — the lab can popcorn a unit itself and then "find"
  the delamination it just made.

The intake file states all three constraints explicitly in `open_questions`, and a correct run
has to honour them without being told twice.

## The intake picture

6 of 220 boards from one build failed in-circuit test immediately after reflow. All 220 devices
came from one reel of MSL 3 parts. The dry-pack was opened on 2026-07-30 for a partial build;
the reel then sat open on the line for about 6 days at 28–32 °C and 60–70 % RH; the remainder
were used in this build **without a bake**. The earlier partial build, run within floor life from
the same reel, produced zero failures. Two of the six units show a faint convex bulge under
raking light. Two never-reflowed units from the same reel are held sealed as a control.
`suspected` is deliberately empty — the discriminator is reached through the `after_reflow` flag
and the history, not through a hint.

## True mechanism

Absorbed moisture in the mold compound vaporized at reflow peak temperature, generating internal
pressure that delaminated the die-attach and die-face interfaces and cracked the package
("popcorn"). Mixed electrical signatures across the six units — four opens, two functionally
dead — are exactly what a mechanical event of this kind produces: it breaks whatever it happens
to break.

The strongest single piece of evidence is the **contrast against the sealed control units**:
same reel, same lot, never reflowed, C-SAM clean. Delamination present only in the reflowed
population is the argument.

## Discriminating evidence, in the order it should appear

1. **`external_visual`, N0.** Already in the intake: 2 of 6 show a faint convex bulge under
   raking light. A lead, not a conclusion — but it is a lead that survives only if nobody
   handles the parts aggressively first.
2. **`csam`, N1 — the decisive step.** Delamination maps at the die face, die attach and
   leadframe interfaces, plus popcorn crack signatures. Run on all six failing units **and on the
   two sealed control units**. The comparison is the finding.
3. **`xray_2d`, N1.** Broken or lifted wires, ball/joint condition — the mechanical consequence
   that produced the electrical opens.
4. **`curve_trace`, N0/N1.** Maps which nets are open on each unit, and confirms the mixed
   signature is mechanical rather than a single repeatable circuit fault.
5. **`decap_*` → `internal_optical`, D1, gated** — only after C-SAM. Lifted balls, cracked die
   surface, separated interfaces.
6. **`mechanical_cross_section`, D2, gated.** Package-scale feature; the section plane comes
   from the C-SAM delamination map, not from a guess. FIB is the wrong tool at this scale.

## What a correct plan must contain

- `csam` **strictly before** every `decap_*` step. The eval asserts this ordering directly.
- `csam` flagged as a discriminator (the `after_reflow` flag is what promotes it).
- `mechanical_cross_section` in D2, not FIB, because the feature is package-scale.
- Both gates present, `GATE D1` naming C-SAM completion as a precondition.
- An explicit instruction not to bake the received units, and a statement that the lab's own
  thermal handling of the samples is recorded.
- The sealed control units used as a comparison, never consumed destructively.
- Containment reasoning about the **surviving 214 boards**: latent delamination can exist in
  units that currently pass, so the population question ("are the survivors at risk?") is a
  separate deliverable from the mechanism, and it needs C-SAM on a sample of passing boards.

## What a wrong run looks like

- Decapsulating first and reporting the delamination that decap itself may have caused.
- Baking the units "to be safe" before analysis, destroying the moisture evidence.
- Accepting the CM's "the devices are defective" framing and issuing credit — the device is MSL 3
  rated and the earlier build from the same reel was clean; the floor-life exposure is the
  differentiator.
- Blaming the CM in the report. The FA lab reports the mechanism and the conditions that produce
  it; whether a floor-life violation occurred and who owns it is a commercial conclusion drawn
  from the record, not an FA verdict.
- Closing on the 6 failed units without addressing the 214 survivors.
- Asserting a floor-life number from memory. The allowance for this package at this MSL must be
  read from the current revision of the applicable standard (IPC/JEDEC J-STD-020 for
  classification, J-STD-033 for handling) and from the device's own label — not quoted from a
  model's recollection.

## Grounding

Composed for this repository. Moisture-sensitivity concepts and the popcorn mechanism follow
general packaging-reliability practice; IPC/JEDEC J-STD-020 (MSL classification) and J-STD-033
(handling, packing, shipping and use of moisture-sensitive devices) are cited by number only, no
text reproduced, and **no floor-life durations, bake schedules or peak-temperature limits are
asserted anywhere in this file** — those are `TODO(verify)` against the current standard
revisions and the device label. Part numbers, serials, dates and organizations are invented.
