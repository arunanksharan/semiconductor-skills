# Golden case 3 — intermittent wire-bond NSOP surfacing in temperature cycling

| | |
|---|---|
| **Intake input** | `sample-data/semi-failure-analysis/case3_nsop_tempcycle.json` |
| **True mechanism** | **Marginal first-bond adhesion (NSOP-class) on a Cu-wire ball bond**: partial intermetallic coverage that opens on thermal contraction in the cold half of the cycle and re-closes on warm-up — **not** the solder-joint crack the CM asserted |
| **Discriminating techniques that must surface early** | `contact_elimination` and `in_situ_tc_monitoring` (phase **N0**), then `xray_2d` (phase **N1**) |
| **Confirming techniques** | `decap_plasma` → `internal_optical` → `wire_pull_ball_shear` **on siblings**, then `mechanical_cross_section` through the suspect bond |
| **Edge cases exercised** | Intermittent (evidence evaporates) · requester asserts the wrong mechanism · destructive population test must not consume the subject unit · decap chemistry must not dissolve the evidence |

## Why this case exists

This is the case where the standing rule — *no destructive step until the failure is
reproducible on demand or the pin and condition window are nailed* — carries the whole
investigation. An intermittent that is destroyed before it is reproduced is a case that can
never be closed, and there is no second chance.

It also tests two quieter judgments that separate a real FA plan from a technique list:

- **Decap chemistry follows metallurgy.** The hypothesis lives *at* the Cu-wire/Al-pad
  interface. Wet acid decap dissolves exactly that interface. The plan must call for plasma
  decapsulation and say why.
- **Population evidence needs a population.** Wire pull and ball shear are destructive and their
  *failure mode* is the diagnosis — but running them on the failing unit destroys the bond you
  still need to cross-section. They belong on siblings.

## The intake picture

3 of 40 board-level TC assemblies (−40 to +125 °C) show an intermittent open on one I/O net,
appearing below roughly −10 °C after about 400 cycles and clearing on warm-up. Everything passes
at room temperature. `suspected: ["solder"]` is the CM's belief — they want to change the reflow
profile. Five units are available, including a never-cycled sibling and a cycled-but-passing
reference. The only observation on file is a 5-insertion room-temperature retest matrix: all
pass.

## True mechanism

Weak first-bond adhesion with incomplete intermetallic coverage. At room temperature the bond
makes contact; on cold contraction the marginal interface separates and the net opens; on
warm-up it re-closes. The board solder joints are sound — the failure is inside the package, one
level up the interconnect chain from where the CM was looking.

Correct wording is "consistent with a marginal ball-bond interface (NSOP-class)"; a confident
"NSOP" call needs the bond failure-mode histogram from sibling pull/shear testing plus the
cross-section, and even then the *escape point* (why the OSAT's bond monitoring did not catch
it) is a separate leg.

## Discriminating evidence, in the order it should appear

1. **`retest_matrix`, N0.** Already in the intake: room-temperature testing cannot see this
   failure. That is a finding, not a dead end — it defines the condition window.
2. **`contact_elimination`, N0.** Different socket, different tester, cleaned leads, gentle lead
   press. Most reported intermittents die here and turn out to be contact rather than silicon.
   Surviving this step is what earns the case its lab time.
3. **`in_situ_tc_monitoring`, N0.** The pivot of the case: continuous continuity monitoring
   through the cycle converts "intermittent" into a reproducible failure with a named net, a
   named ball position, and a temperature window. **Nothing destructive may happen before this
   succeeds.**
4. **`xray_2d` (and `xray_ct` for the suspect joint), N1.** Localizes to the interconnect level
   and — importantly — is the step that *retires the CM's solder hypothesis* non-destructively
   if the joints image clean. Also checks wire sweep, lifted wires and shorting.
5. **`tdr`, N1.** Distance-to-fault along the identified net separates a board/substrate
   discontinuity from one inside the package.
6. **`decap_plasma` → `internal_optical`, D1.** Plasma, not acid — see above.
7. **`wire_pull_ball_shear` on held siblings, D1.** The failure-mode histogram (pad lift vs heel
   break vs cratering vs neck break) against the OSAT's control data is the population evidence.
8. **`mechanical_cross_section`, D2.** Package-scale feature; a FIB's field of view is a
   liability here. The section plane comes from the localized ball position.

## What a correct plan must contain

- `contact_elimination` and `in_situ_tc_monitoring` in **N0**, ahead of everything physical.
- `xray_2d` promoted to a discriminator because a solder/interconnect hypothesis is live.
- `decap_plasma` selected **and `decap_chemical` explicitly excluded with the metallurgy
  reason** — a plan that silently picks acid decap here has thrown away the evidence.
- `wire_pull_ball_shear` scoped to sibling units, not to the subject.
- `dye_and_pry` present but sequenced late (it destroys the package and answers the board-level
  question, which is not the open question here).
- Both gates, with a `GATE D2` cut plane sourced from the in-situ localization.

## What a wrong run looks like

- Agreeing with the CM and recommending a reflow-profile change — that is a containment-shaped
  action attached to an unproven mechanism, and it would leave the real escape untouched.
- Cross-sectioning a unit whose failing net was never identified: a blind section through an
  unlocalized package is evidence destruction with a photograph attached.
- Running pull/shear on the failing unit.
- Concluding "no fault found" because the unit passes at room temperature.
- Reporting the mechanism without the escape point: the OSAT's bond-monitoring and the
  qualification that released this assembly lot both let a marginal-adhesion population through.

## Grounding

Composed for this repository. Bond-integrity failure modes and the use of failure-mode
classification (rather than raw strength numbers) follow general assembly-FA practice;
JESD22-B116-style ball shear and wire pull methods are cited by number only. No standard text is
reproduced and no strength thresholds are asserted. Part numbers, serials, dates and
organizations are invented.
