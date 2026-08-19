# Failure mechanism catalog — signature, appearance, and the lookalike it must beat

A hypothesis-generation aid for the Step 4 table, not a verdict list. Every mechanism name below
is a **hypothesis until physical evidence confirms it**, and every row you copy into the table
must leave with a discriminating next test attached (technique IDs and costs:
`technique-matrix.md`). Figures marked *(rough — verify)* are industry-typical anchors only;
confirm against the current revision of the cited standard before any of them reaches a report.
Standard numbers are given for lookup, not as a claim about their current scope.

---

# A. Electrical / die-level mechanisms

## A1. Event-driven overstress and parasitic conduction

Compact rows only — the full morphology, energy-reasoning, and pin-pattern treatment lives in
`esd-eos-discrimination.md`, which you must read before writing "ESD" or "EOS" anywhere.

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **EOS** | Sustained current/voltage past SOA from a supply-backed source · hot-plug · sequencing violation · regulator fault · rework · ATE hot-switch · µs to seconds | Gross short or open · low-impedance path to a rail · multiple pins/nets · large ΔI on `curve_trace` | Wide melt spanning tens of µm · fused/balled metal · cracked dielectric · charred or bulged package · often visible pre-decap | Damaged volume exceeds what any component-level ESD model can supply · melt path traces to a supply, not a clamp |
| **ESD — HBM** (JS-001 · JESD22-A114) | Person/tool discharge into a pin · ~100 ns–1 µs through ~1.5 kΩ *(rough — verify)* · energy bounded by the body | Pin-referenced leakage on one or a few pins · often still partly functional | µm-scale melt filament confined to the pad's protection device or first junction · contact spiking | Site sits **on** the pad's ESD path · single-pin or adjacent-pin pattern · energy bounded |
| **ESD — CDM** (JS-002 · JESD22-C101) | Package self-charges, then discharges through a pin · sub-ns rise, ~1 ns *(rough — verify)* · automated handling, tape/reel, board build | Gate leakage · IDDQ shift · subtle parametric · damage frequently at **internal** nodes (receivers, clock/reset, domain crossings) | Sub-micron oxide puncture, minimal surrounding melt · often invisible optically, needs `emmi` / `tem_lamella` | Internal/gate-oxide site with the **primary clamp intact** · smallest damage volume of any model · maps to an automated step, not a human touch point |
| **ESD — MM** | Charged fixture/machine discharge · low series R · ns-scale oscillatory · high peak current | Like HBM but harsher — more likely to make a hard short · damage may run past the clamp into the driver | Melt at pad/clamp larger than HBM · evidence on **both polarities** of a structure from the ringing | Morphology overlaps HBM badly — separate by the **tooling audit** (charged fixture vs person), not by the die. MM is largely retired as a qualification model *(verify whether the customer still requires it)*; treat "MM" as a shop-floor hypothesis about a fixture |
| **Latch-up** (JESD78) | Parasitic PNPN (SCR) triggered by injection — I/O driven past a rail · supply overshoot · transient · particle strike · hot-plug sequencing; **sustained by the supply** | Sudden ICC jump that persists until power cycle · value set by the external current limit · **full recovery on power-down if caught in time** | Nothing at all if caught early · otherwise melt along the well/substrate path between adjacent structures — morphologically indistinguishable from EOS | Power-cycle recovery plus a **reproducible trigger** on a good unit under current limit. EOS never heals |

### Confusions

- **EOS vs ESD** → damage volume and thermal extent. Full treatment: `esd-eos-discrimination.md`.
- **HBM vs CDM** → CDM damages internal gates with the primary clamp untouched; HBM damages the
  pad's protection path. Locate the site before choosing the model.
- **MM vs HBM** → the die will not tell you. The handling/tooling audit will.
- **Latch-up vs EOS** → power-cycle behaviour and trigger reproducibility.
- **Latch-up vs CDM** → latch-up needs a live supply; CDM needs none at all — an unpowered part in
  a tube can take CDM damage, which is why "it was never powered" does not exclude ESD.
- **Any of these vs test-induced damage** → compliance limits, hot-switching, probe slips make
  real overstress damage in your own lab. Standing row in every hypothesis table.

## A2. Interconnect wearout and opens

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **Electromigration (EM)** | Sustained **unidirectional** current density × temperature · Black-type MTTF ∝ J⁻ⁿ·exp(Ea/kT), n≈2 and Ea ~0.5–0.7 eV (Al) / ~0.8–1.0 eV (Cu damascene) *(rough — verify vs JEP122)* | Progressive resistance rise → open · speed-path or rail-droop degradation first · late-life · lands on nets with sustained DC (power, ground, clock buffers), never a low-duty signal net | Void at the **cathode** end of a line, at a via bottom, or at the Cu/cap interface · hillock or extrusion at the anode (Al) · mass accumulation downstream | Void **plus** matching anode-side accumulation · site consistent with current direction · rate accelerates with both J and T |
| **Stress-induced voiding (SIV / stress migration)** | Tensile stress gradient from CTE/process mismatch driving vacancy migration · **no current required** · worst in a mid-temperature window (often quoted ~150–200 °C *(rough — verify)*) where stress and vacancy mobility coexist | Resistance rise or open appearing during **unbiased** bake/storage (JESD22-A103) · no correlation with current · geometry-specific (wide metal plate feeding one narrow via) | Slit or via-bottom void, typically under a via fed by a large metal reservoir · **no anode-side hillock or accumulation** | It happens with zero current and leaves no anode signature. Geometry correlation (large plate → single small via) is the second confirmer |
| **Soft / resistive opens** (high-R vias, marginal contacts) | Process marginality — via etch residue, incomplete fill, barrier discontinuity, misalignment, silicide gap · a partly-formed interface, not a wearout | Path conducts but with excess R · speed/timing fails at low V or high T · Shmoo shrink · DC continuity passes while function fails · often present at the **first** electrical test | Thin or partial via fill, residue layer, void — or nothing resolvable; needs high-res `sem_edx`, `tem_lamella`, or `nanoprobing` | Measure R vs known-good **and its temperature coefficient**: metal-like positive TCR reads differently from a barrier/tunnelling interface. A resistance that is stable from t=0 is a process escape, not a wearout |

### Confusions

- **EM vs SIV** → current dependence, and the anode. SIV appears unbiased and leaves no
  hillock/extrusion; EM's void always has a mass-conservation partner downstream.
- **EM vs resistive via** → the time trend. Pull the earliest datalog: if R was already off at
  t=0 the mechanism is a process escape and EM is a bystander (see the chain in §Chains).
- **SIV vs EM in a qual matrix** → the unbiased leg. SIV shows up in HTS; EM cannot.
- **On-die resistive open vs package interconnect open** → do not choose from electricals.
  Localize first: `tdr` / `xray_2d` / `dye_and_pry` separate package from die.

## A3. Dielectric and transistor degradation

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **TDDB — intrinsic** (SBD → progressive → HBD) | Field across the dielectric × time × temperature · competing acceleration models (E, 1/E, power-law Vⁿ) — the **model choice dominates the extrapolation** · Ea often quoted ~0.6–0.9 eV *(rough — verify vs JEP122; Ea extraction per JESD91)* | **SBD:** small stochastic step in gate leakage, RTN-like noise, device still functions. **Progressive:** Ig grows in discrete jumps. **HBD:** low-R gate-to-channel/well short → IDDQ jump, functional fail | Nanoscale percolation filament through the oxide · HBD leaves a visible melt spot · SBD is physically invisible | The **history**: monotonic, stepwise leakage growth over accumulated field-time, appearing after burn-in/HTOL in a cohort at similar stress hours |
| **Gate-oxide pinhole — extrinsic** | Process defect: particle, thin spot, contamination, plasma-charging/antenna damage. Kills at a field far below intrinsic breakdown | Gate-to-channel/substrate short **at or near t=0** or after very short burn-in · no growth history · random die position | Local oxide rupture/melt at the defect · sometimes a visible particle or thinning at TEM · **identical to HBD under SEM** | Timing plus the distribution: extrinsic failures form a separate early-life Weibull mode *(shape parameter is process-specific — `TODO(verify)` against your own line's data)*, carry lot/wafer commonality, and do **not** track mission-profile V/T. Call it "extrinsic dielectric breakdown", not TDDB |
| **HCI** | High lateral channel field at high Vds; energetic carriers damage the interface/oxide · AC/switching-activity dependent · **worse at low temperature** | Vt shift, gm/Idsat loss, drive-current degradation → speed fails that appear **cold and clear up hot** · drain-side asymmetric (direction-dependent) | None. Trapped charge and interface states — an electrical-only mechanism | The triple: negative temperature dependence + drain-side asymmetry + **no recovery** when stress is removed |
| **NBTI (pMOS) / PBTI (nMOS, high-k)** | Gate bias at elevated temperature · interface-trap generation plus oxide charge trapping · **worse hot** · time exponent and Ea vary widely by extraction method — `TODO(verify)`, do not quote a single number | \|Vt\| increase, Idsat loss → slow speed paths, Fmax degradation · **partially recovers** when bias is removed, which corrupts the measurement itself (measure-stress-measure delay changes the answer) | None. Electrical-only | **Recovery on bias removal** plus the measurement-delay sensitivity, plus positive temperature dependence. Recovery is the separator |

### Confusions

- **Intrinsic TDDB vs extrinsic pinhole** → timeline and Weibull mode, never the SEM image. Same
  picture, different population. If it shorted at first test, it is not wearout.
- **HCI vs NBTI/PBTI** → temperature sign and recovery. Cold-and-permanent vs hot-and-recovering.
- **BTI/HCI vs a resistive open** → both give speed fails. BTI/HCI show a Vt/Idsat shift on
  characterization structures and degrade with accumulated use; a resistive via is there at t=0.
- **HBD vs ESD gate rupture (CDM)** → stress hours and population. See `esd-eos-discrimination.md`.
- **SBD vs measurement noise** → repeat with the identical delay and bias history. SBD is a
  persistent step; noise is scatter.

---

# B. Package / assembly mechanisms

## B1. Wire bond and first-level interconnect

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **NSOP / NSOL** | Pad or lead contamination (epoxy bleed, Al/Cu oxide, fab F-residue, plating issue) · or bonder parameter drift (US power, force, time, stage temperature) | Hard, **stable** open on a specific pin at t=0 · caught at final test · not intermittent | Missing ball/wire, or an unbonded ball lying loose · **pad surface intact, no bond footprint, no IMC witness marks** | Pad witness. No footprint at all = it never stuck |
| **Ball lift** | Insufficient IMC coverage · contamination under a formed bond · TC shear · or later IMC/Kirkendall degradation | Open, often **intermittent** under temperature or mechanical stress · may appear only after TC/precon or in the field | Ball separated at the ball/pad interface · residual IMC islands and a clear bond footprint on the pad | Pad shows a previous bond. Then `wire_pull_ball_shear` (JESD22-B116 · MIL-STD-883 method 2011) failure mode and IMC coverage % decide "never bonded well" vs "degraded later" *(coverage acceptance limits are product/OSAT-specific — `TODO(verify)`)* |
| **Cratering** | Excess ultrasonic energy/force · hard Cu free-air-ball · weak or low-k ILD under the pad · bond-over-active layout | Open, leakage, or a parametric shift depending on what broke underneath · may pass at t=0 and fail after TC | Silicon/ILD chunk pulled out **beneath** the pad metal · radial ILD cracks around the footprint · only visible after ball and pad metal removal | Damage is **below** an otherwise intact pad. That points at bonder energy or pad-stack design, never at contamination |
| **Cu–Al IMC growth + Kirkendall voiding** (± halide corrosion) | Temperature × time, diffusion-limited (thickness ~ √t; Ea in the ~0.8–1.0 eV region, phase-dependent *(rough — verify)*) · corrosion accelerant: Cl⁻/Br⁻ from mold compound with bias + humidity (JESD22-A101 THB · A110/A118 HAST) | Gradual contact-R rise then open · late-life, or after HTSL/HAST readpoints · frequently **several bonds in the same package** | Layered IMC bands at the interface · Kirkendall voids in a plane parallel to it · corroded IMC instead looks porous and eaten-away, attacked from the bond perimeter | `sem_edx` for Cl/Br **plus** void geometry: a clean void plane with no halide = thermal Kirkendall; perimeter porous attack with halide = corrosion following a moisture path |

### Confusions

- **NSOP vs ball lift** → the pad witness mark. Highest-yield package call in this file.
- **Ball lift vs IMC/Kirkendall degradation** → timing and morphology: low IMC coverage at
  t=0/precon vs a full IMC layer plus a void plane late-life.
- **Cratering vs die crack** → the crater stays inside the bond footprint; a die crack runs away
  from any bond, usually from an edge, corner, or point load.
- **Cu–Al corrosion vs pure Kirkendall** → halide EDX.
- **NSOL vs a board-level or lead-finish open** → localize with `xray_2d` and electricals before
  the bonder gets blamed.

## B2. Interfaces, moisture, and mechanical integrity

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **Delamination** (die-attach · die-face/mold · substrate/leadframe) | Adhesion loss from contamination, absorbed moisture, CTE mismatch, TC (JESD22-A104), reflow · usually present long before any electrical symptom | Often **none** initially. Later: thermal-resistance rise and a hot-running part (die-attach delam) · stress opens at bonds · or an enabling path for corrosion | `csam` is the tool — interface echo polarity inversion, mapped by area **and location** | `csam` **before** decap — decap destroys the evidence permanently. A delam call is worthless without a location: die-attach ≠ die-face in consequence. Separate pre-existing from stress-grown by comparing `csam` at t=0 vs post-stress **on the same unit** |
| **Popcorn cracking / MSL failure** (J-STD-020 · J-STD-033) | Absorbed moisture flashing to steam at reflow peak — floor-life exceeded, failed bake, or reflow above rated peak | Opens or intermittents after board reflow · frequently several units from the **same reflow event** · sometimes no electrical symptom at all | Package crack running from a delaminated interface (usually the die paddle) out to the surface or edge · internal delam radiating from the paddle | The crack maps to a **reflow event** and the delam radiates from the paddle. Corroborate with the MSL/floor-life record; if that record is clean, question the profile before the package |
| **Underfill voids → flip-chip bump failure** | Dispense pattern, flow-front merge, moisture at the interface, cure profile, filler settling · the void itself is not the failure — it removes bump support and concentrates CTE strain | Open or high-R bump appearing **after** TC, drop, or board bend — not at t=0 · lands at high-DNP positions (die corners) | Void in `csam` · bump fatigue crack or low-k/ULK corner delamination ("white bump") at `fib_cross_section` | Void location and failing-bump location must **coincide**, and the bump must be at a high-DNP position. A failing bump elsewhere is not caused by that void — say so in the report |
| **Die crack** (dicing-origin · handling · TC-driven) | Dicing chipping and subsurface micro-cracks · point loads from pick-place, ejector pins, board flex, screw mount · or cyclic CTE stress | Opens, leakage, or nothing · strong mechanical dependence (fails change with board flex or press) · often intermittent | Fractography names the origin: dicing = die edge/street with chipping, chevrons pointing back to the sidewall · handling = point-load origin (backside scratch, ejector mark, corner impact), conchoidal features · TC = origin at a stress concentrator (die corner, die-attach void edge, thick-metal corner) | Find the **origin** first, then match it to the three candidates — and cross-check the timing (t=0 assembly vs growth across TC readpoints) |

### Confusions

- **Delamination vs popcorn crack** → delam is an interface separation with no through-path;
  popcorn adds a crack that breaches the package, and it maps to a reflow event.
- **Popcorn vs handling die crack** → moisture story and crack origin (paddle-radiating delam vs
  point load).
- **Underfill-void bump crack vs non-wet / head-in-pillow** → timing and fracture surface: non-wet
  is a t=0 reflow open with a ball-and-socket signature; a void-enabled crack is a post-cycling
  fatigue surface.
- **TC die crack vs dicing crack** → origin location: street/edge with chipping = dicing.
- **Die-attach delam vs die crack on a "hot part"** → Rth rise with an intact die = delam.
- **FA-induced delamination** → your own bake or reflow can create what you then find. Record the
  moisture handling of every sample (SKILL edge case 5).

## B3. Metallurgy and environment

| Mechanism | Driving stress | Electrical signature | Physical appearance | Discriminating evidence |
|---|---|---|---|---|
| **Solder-joint thermal fatigue** | Cyclic shear from package/board CTE mismatch × ΔT × cycles · Coffin-Manson-type Nf ∝ Δγ⁻ⁿ with a Norris-Landzberg-style frequency/Tmax correction — **exponents are alloy- and model-specific, `TODO(verify)`; never reuse a SnPb exponent for SAC** (board-level TC practice: IPC-9701) | Intermittent open appearing late in life · often only detectable under temperature or board flex · corner/DNP-max joints first · resistance spikes in `in_situ_tc_monitoring` | Crack through **bulk** solder near but not at the IMC, with a rough recrystallized grain band · `dye_and_pry` shows dye entering from the joint perimeter | The crack path. Bulk recrystallized crack + DNP-max location + cycle-count correlation = fatigue. A flat shiny crack **at** the IMC = brittle interfacial fracture (shock/drop, or a bad finish such as ENIG black pad) |
| **Tin whiskers** (JESD201) | Compressive stress in pure/matte Sn plating — Cu–Sn IMC growth at the interface, mechanical or thermal stress, oxide · grows over months to years at room temperature, and does **not** accelerate the way most mechanisms do | Intermittent or hard short between adjacent leads/terminals · may fuse open and become an NFF · often unreproducible after handling | Single high-aspect-ratio Sn filament growing **out of the plating** (not out of a solder joint) · `sem_edx` shows essentially pure Sn | SEM at the lead plus the finish spec (pure Sn vs Sn-Pb vs a Ni underlayer). Practical tell: a short that **disappears when the part is removed** for analysis is a whisker suspect — image before disturbing anything |
| **Corrosion** | Moisture + ionic contamination (Cl⁻, Br⁻, flux residue) + a galvanic couple · bias optional | Rising resistance → open (metal consumed) · or leakage · parametric drift · strongly location-dependent | Metal **removed**, porous corrosion product, discoloration · `sem_edx` shows halide and oxygen · attack follows a moisture ingress path (crack, delam, package edge, exposed pad) | Metal is consumed at the site, and the ingress path is traceable. Corrosion is almost always the **second** link in a chain — find the first |
| **Dendrite growth / ECM** | Bias + a continuous moisture film + ionic residue between two conductors at different potential · metal dissolves at the anode and plates at the cathode | Progressive leakage between two nets, growing with biased humid time · may drop again when the dendrite fuses · classic THB / HAST fail mode | Branched, tree-like metallic growth bridging conductors, advancing cathode → anode · visible optically at a surface or under a delaminated interface | A **bridge** between two different potentials that grew under bias, and may fuse open. Requires bias; corrosion does not |

### Confusions

- **Fatigue vs brittle interfacial fracture** → crack path (bulk recrystallized vs flat at IMC).
- **Fatigue vs assembly non-wet** → cycles vs t=0, and the fracture surface.
- **Whisker vs dendrite** → whisker is a single filament out of plating needing neither bias nor
  moisture; dendrite is branched, needs both, and bridges two potentials.
- **Corrosion vs ECM** → corrosion removes metal at one site; ECM deposits metal to build a bridge.
- **Whisker short vs contamination/test-induced short** → whisker shorts often vanish on handling.
  Photograph and SEM before anyone touches the leads.

---

# Reading the time-to-failure signal

The single most informative input you have before any physical work. Match the *when*, then let
it set priors — up and down — and take the first move before proposing anything destructive.

| When the failure appears | Raises | Lowers | First discriminating move |
|---|---|---|---|
| **t=0 at wafer sort** | Extrinsic gate-oxide pinhole · particle shorts/opens · resistive vias & contacts · design marginality | All wearout (EM, TDDB, BTI, HCI — no accumulated stress) · every package mechanism · anything needing moisture or cycles | Wafer-map spatial character via `bin_signature.py` — clustered vs edge vs random |
| **t=0 at final test** (passed sort) | NSOP/NSOL · cratering · die crack (dicing/handling) · bump non-wet · CDM from handling · probe/handler damage | Die process escapes that sort would have caught · all field mechanisms | Sort-vs-final datalog delta on the **same die** — the delta is assembly |
| **t=0 at board/system** (passed final) | Popcorn/MSL · solder non-wet/HIP · CDM at board build · board-level EOS at power-up | Die process escapes · die wearout | `xray_2d` + `csam` on an as-received unit, plus the reflow profile and floor-life records |
| **After burn-in / early life** | Extrinsic dielectric breakdown · weak or partial vias · marginal bonds (low IMC coverage) · latent overstress damage walking out | Intrinsic wearout (too early) · pure fatigue | Pre/post burn-in datalog delta on the same unit — **which parameter moved** |
| **Random through life, isolated, no trend** | EOS · ESD in the field or at repair · latch-up · single-unit handling damage · whisker short | Population wearout · process excursion (absent commonality) | Population rate check (1-of-millions vs cohort) + `curve_trace` pin map vs known-good |
| **Late-life, rate rising with hours** | Intrinsic TDDB · EM · SIV · BTI/HCI speed fails · Cu–Al IMC/Kirkendall · solder fatigue | Assembly escape · ESD/EOS event | Plot cumulative failures vs hours: is the hazard rate increasing? Then compare actual mission-profile T/J/ΔT against the design and qual assumptions |
| **Only after TC / thermal shock readpoints** | Solder fatigue · TC-driven die crack · delamination growth · corner bump / ULK crack · ball lift from IMC degradation | Field ESD/EOS · dielectric wearout | `csam` + `xray_2d` at **each** readpoint on the same unit — the growth curve names it |
| **Only after reflow / precon** | Popcorn/MSL · delamination · non-wet/HIP · die crack | Electrical wearout of any kind | MSL/floor-life audit + `csam` before vs after precon |
| **Only after biased humidity (THB/HAST/uHAST)** | Dendrite/ECM · Cu–Al bond corrosion (halide) · pad/passivation corrosion through a moisture path | Thermal-only mechanisms · mechanical mechanisms | `sem_edx` for halides at the site; check bias polarity against which conductor was consumed and which grew |
| **Only after unbiased HTS/HTSL** | SIV · IMC growth and Kirkendall voiding · metallurgical/contact change | EM (no current) · HCI/BTI (no bias) · ECM (no bias, no moisture) | The biased-vs-unbiased split itself is the discriminator — say so explicitly |
| **Only after HTOL (biased, hot)** | Intrinsic TDDB · EM · BTI · extrinsic escapes riding early | Mechanical · moisture · assembly | Split the population: an early cluster is extrinsic, the distribution body is intrinsic. Fit two modes, not one bad line |
| **Only after shock / drop / board flex** | Brittle IMC fracture at joints · die crack · pre-existing cratering revealed · bond lift | Everything time-dependent | `dye_and_pry` (board joints) + fractography for the origin |
| **Intermittent, tracks temperature or touch** | Resistive/soft open · solder fatigue crack · ball lift · whisker · **socket/contact artifact** | Nothing yet — this class is dominated by artifacts | `contact_elimination` first (SKILL §2a). Most "intermittents" end here, and that is a finding |

Two rules that come with this table. First, **the timing evidence must come from a record, not a
recollection** — the datalog sequence, the readpoint log, the floor-life sheet. Second, "it only
failed after stress X" is only meaningful if a control leg did *not* fail; a single-leg result
raises a prior, it does not confirm a mechanism.

# Bathtub-curve placement

| Region | Mechanisms | What you are actually hunting |
|---|---|---|
| **Infant mortality (extrinsic)** | Gate-oxide pinhole and extrinsic dielectric BD · resistive/partial vias · particle shorts · NSOP/NSOL · weak bonds · bump non-wet · assembly die crack | A **process escape plus a screen gap**. Corrective action is split: fix the excursion, and explain why burn-in / precon / outgoing test did not catch it. Commonality by lot, date code, tool, site |
| **Random / event** | EOS · ESD (HBM, CDM, MM) · latch-up · handling damage · board events · whisker short | An **event and its source** — a handling step, a hot-plug, an ESD control, a fixture. Corrective action is a procedure or hardware control, not a wafer fix. Expect a flat rate, not a rising one |
| **Wearout (intrinsic)** | Intrinsic TDDB · EM · SIV · HCI · NBTI/PBTI · Cu–Al IMC/Kirkendall · solder thermal fatigue · tin whiskers · delamination growth | A **design or mission-profile margin problem**: actual J, T, ΔT, cycle count, bias, and duty vs what design and qual (JESD47 / JEP001 stress set) assumed. If the profile matches the assumption, the model or its acceleration factor is wrong |

SIV and tin whiskers sit awkwardly here: both are time-dependent wearout that need neither
current nor bias. Treat them as stress-state wearout, and do not expect a bias-driven
acceleration factor to work on them.

Placement is a claim about the **rate curve**, not about a unit. With one failure you cannot see
the curve, so inferring placement from the mechanism and then the mechanism from the placement is
circular — flag it and use the placement only where a rate exists. Mixed modes are the norm: an
extrinsic population riding under an intrinsic distribution shows up as a two-slope Weibull, and
fitting one line through it produces a confident, wrong life projection.

# One-unit vs population

| What you have | Prior up | Prior down | Action |
|---|---|---|---|
| 1 fail from millions shipped, no cohort | Event (EOS, ESD, latch-up, handling) · extreme-tail extrinsic escape | Process excursion · design margin | Chain of custody + life history + `curve_trace` pin map. Report "consistent with"; a single unit can never support a rate claim |
| 1 fail, and it is the only unit ever tested (NPI, low volume) | Nothing is excluded — the prior is the design's own risk list | — | Get the denominator before ranking anything. Refuse to rank without it |
| Cluster in one lot / date code | Process or material excursion · assembly step · material lot | Random event | Commonality matrix first: tool · material lot · date window · operator · site. A defect that follows a **material** date code is a material problem regardless of which tool flagged it |
| Cluster on one tester/handler/site, spread across date codes | Test-induced · handling · CDM · socket/probe damage | Process excursion | Swap tester and socket, retest, audit the handler's ESD controls |
| Spatial cluster on the wafer (edge, ring, centre) | Process escape with a specific spatial cause | Random event | `bin_signature.py` for spatial character; details in `bin-signature-analysis.md` |
| Spatially random single-die fails on one leakage test | Extrinsic defect density — particles, pinholes | Systematic process shift | Defect-density trend by lot; compare with inline defect data if available |
| Rate rising with field hours across many lots | Wearout · mission-profile margin | Bad-lot theories · one-off event | Stop hunting a lot. Get the use conditions |
| Rate flat and low across all lots and hours | Steady background: random events, steady defect level | A change point | Do not chase a change that is not in the data. Say the rate is unchanged |

Population sets the prior **before** physical evidence and is overturned by one good
cross-section. Its real job is deciding **which** cross-section is worth cutting.

# Mechanism chains

When physical evidence spans two mechanisms, report the chain in order with evidence per link.
The end state is what you see; the first link is what the corrective action must attach to.

| Chain | Usual first link | End state that misleads | Evidence that proves the chain, not just the end |
|---|---|---|---|
| Delamination → moisture path → bond/pad corrosion → open | Adhesion loss at mold/die-face or leadframe (assembly) | "Corrosion — blame the mold compound" | `csam` delam that physically connects the failing site to an ingress path · halide `sem_edx` at the site · delam present on siblings that have not failed yet |
| Die crack → passivation breach → contamination at metal → leakage/corrosion → open | Dicing, handling, or TC | "Leaky net" or "corrosion" | Fractographic origin · contamination confined to the crack path · cracked-but-not-yet-leaky siblings |
| EM void → current crowding → Joule heating → adjacent dielectric damage | Current-density design margin | Dielectric damage read as TDDB | Cathode void on the same net · damage **adjacent to the void**, not at a maximum-field gate · direction consistency |
| Popcorn crack → delam + crack → wire/ball stress or moisture ingress → open/corrosion | Floor-life or reflow profile | "Bond failure" | Reflow-event correlation · crack path traced from a delaminated paddle |
| Underfill void → unsupported corner bump → CTE strain → bump/ULK crack → open | Underfill dispense or cure | "Bump fatigue" | Void coincident with the failing high-DNP bump · growth across TC readpoints |
| IMC/Kirkendall void → contact-R rise → local heating at the bond → accelerated degradation → open | Mission-profile temperature | "Wire bond open" | R-trend before the open · layered IMC plus a void plane at x-section |
| Latch-up trigger → sustained supply current → EOS-scale melt | An I/O overvoltage or supply transient | "EOS — customer's fault" | Damage follows the well/SCR path · the trigger reproduces on a good unit and recovers under current limit |
| Resistive via (process escape) → local heating → EM acceleration at that via → open | Via process marginality | "Electromigration wearout" | R was already high in the **earliest** datalog |

Containment attaches to the **last** link (the detectable signature); corrective action attaches
to the **first**. Report only the end state and the action lands on the wrong owner — which is the
most common way a technically correct FA report still fails. Write the chain into the two-legged
root cause (mechanism leg + escape leg) rather than flattening it: `report-templates.md`.

# Do not confuse — quick reference

| Pair | The one observation that separates them |
|---|---|
| ESD vs EOS | Damage volume and thermal extent. Read `esd-eos-discrimination.md` before writing either word |
| HBM vs CDM | CDM damages internal gates with the primary clamp intact; HBM damages the pad's protection path |
| Latch-up vs EOS | Power-cycle recovery plus a reproducible trigger. EOS never heals |
| EM vs SIV | Current dependence and the anode: SIV occurs unbiased and leaves no hillock or accumulation |
| Intrinsic TDDB vs extrinsic pinhole | Timeline and Weibull mode — the SEM image is identical, so never call it from the picture |
| HCI vs NBTI/PBTI | HCI is worse cold and permanent; BTI is worse hot and recovers on bias removal |
| NSOP vs ball lift | Pad witness: no bond footprint = never bonded; footprint or IMC residue = bonded, then released |
| Cratering vs die crack | The crater stays under the bond footprint; a die crack runs away from bond sites |
| Kirkendall voiding vs bond corrosion | Halide (Cl/Br) at `sem_edx`, plus clean void plane vs porous perimeter attack |
| Solder fatigue vs brittle interfacial fracture | Crack path: recrystallized bulk solder (cycles) vs a flat crack at the IMC (shock, or bad pad finish) |
| Whisker vs dendrite vs corrosion | Whisker = filament from plating, no bias/moisture · dendrite = branched bridge between two potentials under bias · corrosion = metal removed, nothing built |
| Real failure vs test-induced artifact | Reseat, swap socket and tester, confirm program revision — before any destructive step, every time |

---

*Grounding: mechanism physics and discrimination practice summarized in our own words from
general EDFAS-community failure-analysis literature and public reliability-engineering practice.
Standards cited by number only (JEP122, JESD91, JESD47, JEP001, JESD78, JESD22-A101/A103/A104/
A110/A114/A118, JESD22-B116, JESD22-C101, JESD201, ANSI/ESDA/JEDEC JS-001 and JS-002,
IPC/JEDEC J-STD-020 and J-STD-033, IPC-9701, MIL-STD-883 method 2011); no standard text is
reproduced or paraphrased. Every numeric anchor here is rough and must be verified against the
current revision and against the process's own data before it enters a report.*
