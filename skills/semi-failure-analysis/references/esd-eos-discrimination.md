# ESD vs EOS — the discrimination that decides who pays

Load this **before writing the word ESD or EOS anywhere**: in a hypothesis table, an email, or a
report. The two get swapped constantly, and the swap is expensive: ESD points at handling and
controls (often inside the factory or the customer's line), EOS points at the application
circuit, the power sequencing, or a test/board event. The physics that separates them is
mostly *energy and duration*, and it is readable in the damage.

The honest default when the event was not witnessed is the neutral industry wording
**"electrically induced physical damage" (EIPD)** — describe the damage, state the energy
reasoning, name the most consistent model, and let the commercial conclusion follow from
evidence rather than from the FA report's vocabulary.

---

## 1. The one-paragraph physics

All of these are the same phenomenon at different points on the energy-vs-time curve: charge
moves through a path that was not designed to carry it, and something melts, punctures, or
fuses. What differs is **how much energy, delivered over how long, through what impedance**.

| Model | Rough duration | Rough source impedance | Energy delivered | Where the damage lands |
|---|---|---|---|---|
| CDM (charged device) | sub-ns to ~1 ns | very low (the package itself) | small total energy, enormous peak current | Thin, localized — gate oxide, thin dielectric, internal nodes; often *not* at the pad |
| MM (machine model) | ~ns to tens of ns, oscillatory | very low (charged metal) | moderate, ringing waveform | Pad and protection structures; damage can appear on both polarities from the ringing |
| HBM (human body) | ~100 ns to ~1 µs | ~1.5 kΩ (a person) | moderate, current-limited by the body resistance | Protection devices and the pad-side circuits — the ESD network doing its job, or failing at it |
| EOS (electrical overstress) | µs to seconds and beyond | low, and *sustained* — a supply can source amps indefinitely | large, sometimes unbounded | Wide melt, metal fusing, mold discoloration, package damage; anywhere the current path ran |
| Latch-up | sustained until power is removed | supply-limited | very large — the supply itself is the source | Diffusion/well melt, large power-path damage; often indistinguishable from EOS by morphology alone |

The single most useful consequence: **HBM/CDM/MM events are energy-limited by their source; EOS
is not.** An ESD event carries what was stored on a body, a machine, or the package. An EOS
event carries what the power supply is willing to give, for as long as the protection took to
act — which is why EOS damage tends to be *large*, and ESD damage tends to be *small and
specific*. Model waveform definitions are in ANSI/ESDA/JEDEC JS-001 (HBM) and JS-002 (CDM);
JEDEC JESD22-A114 and JESD22-C101 are the older component-level references. Cite them by number;
do not restate their waveform tables from memory.

---

## 2. Damage-site morphology — read the site, not the story

| Observation at the damage site | Reads as | Why |
|---|---|---|
| Sub-micron pinhole through gate oxide, minimal surrounding melt, no metal displacement | CDM (or intrinsic TDDB — see §6) | Huge peak current, almost no total energy: it punches through and stops |
| Small localized melt filament at a junction, ~µm scale, confined to the protection device | HBM | Energy dumped into the clamp, which is what it is for; the clamp reached its failure threshold |
| Localized damage with evidence on *both* polarities of the same structure, or multiple small sites | MM | Ringing waveform swings both ways |
| Wide molten region spanning tens of µm, metal balled up or displaced, dielectric cracked around it | EOS | Sustained current, thermal runaway with time to spread |
| Metal line fused open like a fuse, with resolidified beads | EOS (or a very high HBM level) | Requires enough I²t to vaporize a whole line, not just a junction |
| Mold compound discolored/charred, package bulged or cracked, leadframe darkened | EOS, high energy | Only sustained power reaches package materials |
| Large melt centered on the well/substrate current path between supply structures | Latch-up | The parasitic SCR conducts supply current until power cycles |
| Damage at a pad-side ESD clamp *and* a matching wide melt downstream | ESD-initiated then EOS-sustained, or a design margin issue | Chain — report the chain (§7) |

**Scale is the primary cue.** If you must remember one thing: *ESD damage is small and
surgical; EOS damage is big and messy.* The exception that keeps people honest is CDM, whose
peak current is the highest of all yet whose total energy is the lowest — CDM damage is the
smallest of all, which is why it hides from optical inspection and needs emission microscopy or
a TEM lamella through the oxide.

---

## 3. Energy-per-area reasoning (the argument you actually write down)

Do not assert a model from a photograph alone. Write the reasoning:

1. **Measure the damaged area** from the imagery (`sem_edx`, `internal_optical`), with a scale
   bar. Record it.
2. **Ask what it took to melt that.** Melting and vaporizing silicon, aluminium, or copper over
   that area requires an energy that scales with volume. A site tens of microns across with
   displaced metal is orders of magnitude more energy than a sub-micron oxide puncture.
3. **Compare against what each source can deliver.** A human-body event stores a bounded charge
   at a bounded voltage through ~1.5 kΩ; a device supply rail delivers amps for as long as
   nothing interrupts it. If the damage needs more than the ESD models can supply, the answer is
   EOS regardless of what the handling audit says.
4. **Check the path.** Follow the melt: which nets connect the damaged site to a pin? If the
   path runs pad → clamp → ground, that is the ESD network operating. If it runs from a supply
   rail through core metal, a supply was the source.
5. **State the conclusion as an inference**: "the damaged volume is inconsistent with the energy
   available from a human-body-model event and is consistent with a sustained supply-sourced
   overstress" — with the measurement that supports it.

`TODO(verify)` — if you want to quote actual joules-to-melt figures or clamp failure thresholds
in a report, derive them for the specific metal stack and geometry, or get them from the design
team's ESD simulation. Do not carry rules of thumb into a customer document.

---

## 4. Pin patterns — where the damage sits tells you which model

| Pin pattern | Most consistent with | Reasoning |
|---|---|---|
| Damage on a **power/ground pin** or the supply rail structures | EOS or latch-up | Supplies are the only source with unlimited energy |
| Damage on **one signal pin's protection device**, everything else clean | HBM | A person touched a pin; the clamp took it |
| Damage on **two adjacent pins** or pins sharing a package edge | HBM/MM during handling (tray, socket, tweezers), or a board-level event | Adjacency implicates physical contact geometry |
| Damage on **internal nodes with clean pads and clean clamps** | CDM | The package discharged through itself; the pad never saw the peak |
| Damage on **corner pins / high-capacitance pins** | CDM | Charge distribution in the package concentrates the discharge there |
| Leakage on a **repeated pin position across many units** | Systematic — a handler, socket, tester, or board node touches that pin | This is a process/handling finding, not a device weakness, until proven otherwise |
| Leakage on **random pins across units** | Ambient ESD control failure, or a genuine device weakness | Combine with `bin_signature_analysis` before choosing |
| Damage on **the pin the application hot-plugs, connects to a connector, or drives a load through** | EOS from the application | Ask for the schematic and the sequencing |

The pin-position histogram across multiple failing units is the cheapest and most persuasive
evidence in this entire file, and it costs nothing but a spreadsheet. Build it early.

---

## 5. What the application circuit tells you (ask before you cut)

For any suspected overstress, request and read:

| Ask for | What it rules in or out |
|---|---|
| Power-up/power-down **sequencing** between rails | Forward-biasing an I/O into an unpowered rail is a classic EOS path; a sequencing violation makes the FA nearly conclusive |
| **Hot-plug / hot-swap** on any connector | Inrush transients and connector pin-mating order routinely overstress supply and I/O pins |
| **Inductive loads** (motors, relays, solenoids) on any pin | Flyback transients; check for clamp diodes in the application |
| Cable-facing or off-board pins | System-level ESD (IEC 61000-4-2 class events) rather than component-level HBM/CDM |
| Supply **decoupling and rail impedance**, bulk capacitance | Determines how much energy a rail event can deliver |
| Board **rework or probing** history | Soldering-iron leakage and probe slips are a real, common, under-reported EOS source |
| ESD control audit at the **handler, tray, socket, operator station** | Ionizer status, grounding, tray material change, humidity — this is the HBM/CDM containment story |
| Whether the failure appeared **after a change** (new tray, new tester, new site, new board rev) | A change point is the strongest circumstantial evidence in either direction |

If the application is a customer's and they will not share the schematic, say so explicitly in
the report as a limitation; do not fill the gap with a guess.

---

## 6. The lookalikes that are neither ESD nor EOS

| Lookalike | How it mimics | The discriminator |
|---|---|---|
| **Intrinsic TDDB** | Produces a gate-oxide breakdown path that looks like CDM damage | Population and timing: TDDB appears after stress hours (burn-in, life test) and rises with time/voltage/temperature; CDM appears at t=0 and correlates with a handling step. A TDDB unit usually passed a prior test that a CDM unit would have failed. See `failure-mechanisms.md` |
| **Latch-up** | Melt indistinguishable from EOS | The *trigger* is the tell: latch-up needs an injection event (overvoltage on a pin, a transient, particle strike) and is cleared by power cycling. Ask whether the failure survived a power cycle before it became permanent, and check for the parasitic path between well and substrate structures |
| **Electromigration** | Metal void/extrusion damage | EM is progressive, current-density and temperature driven, appears late, and lands at known geometry stress points (vias, corners, current crowding). Overstress is a single-event morphology with melt, not a slow void |
| **Test-induced damage** | Real overstress damage — because it *is* one, just created in your lab | Curve tracer compliance set too high, hot-switching, an ATE force/sense fault, probe slip. Check the equipment log and whether the damage matches a probe/pin position rather than a circuit node |
| **Assembly/EOS at the OSAT or board house** | Damage indistinguishable from field EOS | Traceability: which units, which line, which date, which step. Population beats morphology here |

Rule: **never diagnose CDM without ruling out TDDB, and never diagnose EOS without ruling out
latch-up.** Both pairs are morphologically close and diverge on timing, population, and trigger.

---

## 7. Chains — when the answer is "both"

Real cases often are:

- **ESD weakens, EOS finishes.** A marginal clamp damaged by an ESD event later fails to protect
  a normal transient; the visible damage is the second, larger event. Look for a small site
  *plus* a large site.
- **EOS initiated by an application transient that ESD protection was never specified for.**
  A design-margin finding, not a handling finding. This is why the ESD spec level and the
  application transient environment both belong in D4 of the 8D (`report-templates.md`).
- **Latch-up triggered by an ESD-scale transient, then sustained by the supply.** The trigger is
  ESD; the damage is EOS-scale. Report both legs.
- **Retest converted the evidence.** A leakage-damaged part re-tested at elevated voltage can be
  driven into a full melt, turning ESD damage into an EOS-looking site. This is why the retest
  log and the datalog sequence matter (`bin-signature-analysis.md`).

When the evidence spans two mechanisms, report the chain in order with the evidence for each
link. A chain reported as a single mechanism will produce the wrong corrective action.

---

## 8. Discrimination checklist (run this before naming a model)

1. Damage area measured with a scale bar? Recorded in the report?
2. Is the site at a pad/clamp, an internal node, or a supply structure?
3. Pin-position histogram across all failing units built?
4. Does the timing fit an event (t=0, or a specific handling step) or a wearout (post-burn-in,
   hours-dependent)?
5. Was there a change point — new tray, tester, socket, operator, board rev, assembly site?
6. Application sequencing, hot-plug, and inductive loads asked about and answered?
7. Latch-up excluded (trigger + power-cycle behaviour)?
8. TDDB excluded (prior test history + population + time dependence)?
9. Could your own lab have caused it (compliance limits, hot switching, probe)?
10. Is the wording in the draft report "consistent with", not "was caused by"?

If any of 1–8 is unanswered, the model name in your hypothesis table is a placeholder, not a
conclusion.

---

## 9. Wording that survives review

| Do not write | Write instead |
|---|---|
| "The customer caused EOS." | "The damage is consistent with a sustained overstress on the VDD pin; the energy required exceeds what component-level ESD models supply. Application power sequencing and hot-plug conditions have been requested to identify the source." |
| "This is ESD." | "The damage is consistent with a human-body-model ESD event at the pin-2 protection device, based on the ~X µm localized melt confined to the clamp and the absence of supply-path damage." |
| "No defect found, must be handling." | "No anomaly was detected by [techniques]. Handling remains a hypothesis but is unsupported by physical evidence; the discriminating next step is [X]." |
| "Root cause: ESD." | "Failure mechanism: electrically induced physical damage, most consistent with CDM. Root cause requires identifying the discharge event; the escape point is [test coverage / control gap]." |

Mechanism is what the FA lab can determine. Root cause requires the event and the escape point —
see the two-legged root cause in `report-templates.md`.

---

*Grounding: model definitions cited by standard number only (ANSI/ESDA/JEDEC JS-001, JS-002;
JEDEC JESD22-A114, JESD22-C101; IEC 61000-4-2 for system level). Morphology and discrimination
practice summarized in our own words from the general EDFAS-community failure-analysis
literature and vendor application notes; no standard or desk-reference text is reproduced. All
quantitative energy reasoning must be derived per-device — no thresholds are asserted here.*
