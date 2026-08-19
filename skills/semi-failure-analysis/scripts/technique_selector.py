#!/usr/bin/env python3
"""Build an ordered, gated failure-analysis technique plan.

Turns a symptom class + package type + sample count + budget/urgency into an ordered
technique sequence: non-destructive before destructive, cheap before expensive, with an
explicit GATE step in front of every destructive step, and a sample-preservation plan.

Technique IDs match references/technique-matrix.md row for row.

Usage example:
  python technique_selector.py --symptom-class parametric --package-type wirebond-plastic \
      --sample-count 12 --powered-signature leakage --suspected esd --customer-return \
      --budget medium --urgency expedite --output plan.json

  # or drive it from a case file that carries a "selector_input" block:
  python technique_selector.py --case-file ../../../sample-data/semi-failure-analysis/case1_eos_hotplug.json

Exit codes: 0 plan produced · 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "0.1.0"

SYMPTOM_CLASSES = ("hard_fail", "parametric", "marginal", "intermittent", "nff")
PACKAGE_TYPES = (
    "wirebond-plastic", "wirebond-bga", "flipchip-bga", "wlcsp",
    "ceramic-hermetic", "bare-die", "module-sip",
)
SIGNATURES = ("short", "open", "leakage", "functional", "speed", "unknown")
SUSPECTS = (
    "esd", "eos", "tddb", "em", "latchup", "hci", "wirebond", "delam",
    "solder", "corrosion", "diecrack", "underfill", "none",
)
BUDGETS = ("low", "medium", "high")
URGENCIES = ("routine", "expedite", "emergency")

MOLDED = ("wirebond-plastic", "wirebond-bga", "module-sip")
BACKSIDE_ACCESS = ("flipchip-bga", "wlcsp")
SUBSTRATE_PACKAGES = ("wirebond-bga", "flipchip-bga", "wlcsp", "module-sip")
WIREBONDED = ("wirebond-plastic", "wirebond-bga", "module-sip", "ceramic-hermetic")

PHASES = (
    ("P0", "Preservation & custody", "non-destructive"),
    ("N0", "Electrical characterization & records", "non-destructive"),
    ("N1", "Package imaging", "non-destructive"),
    ("N2", "Localization without opening", "non-destructive / sample-altering"),
    ("D1", "Package opening & die-level access", "DESTRUCTIVE"),
    ("D2", "Sectioning & analytical microscopy", "DESTRUCTIVE - TERMINAL"),
)

# id -> (display name, default phase, destructive code, cost 1-5, turnaround)
CATALOG = {
    # --- N0 -----------------------------------------------------------------
    "external_visual":       ("External optical / stereo inspection as received", "N0", "ND", 1, "minutes"),
    "datalog_review":        ("Full ATE datalog re-analysis (no stop-on-first-fail)", "N0", "ND", 1, "minutes-hours"),
    "retest_matrix":         ("Structured retest matrix, every insertion logged", "N0", "ND", 1, "hours"),
    "contact_elimination":   ("Contact elimination: new socket / tester / cleaned leads", "N0", "ND", 1, "hours"),
    "curve_trace":           ("Pin-by-pin curve trace (I-V) vs known-good unit", "N0", "ND", 1, "hours"),
    "shmoo":                 ("Shmoo vs known-good on the same setup", "N0", "ND", 2, "hours-1 day"),
    "bin_signature_analysis": ("Bin / population / spatial statistics (bin_signature.py)", "N0", "ND", 1, "minutes"),
    "burnin_delta_review":   ("Pre- vs post-burn-in datalog delta", "N0", "ND", 1, "hours"),
    "in_situ_tc_monitoring": ("In-situ monitoring through thermal cycling / vibration", "N0", "ND", 3, "days-weeks"),
    # --- N1 -----------------------------------------------------------------
    "xray_2d":               ("2D transmission X-ray", "N1", "ND", 2, "<1 day"),
    "xray_ct":               ("X-ray computed tomography (3D)", "N1", "ND", 3, "1-3 days"),
    "csam":                  ("C-mode scanning acoustic microscopy (C-SAM)", "N1", "ND", 2, "<1 day"),
    "hermeticity_pind":      ("Fine/gross leak + PIND (cavity packages)", "N1", "ND", 2, "<1 day"),
    "tdr":                   ("Time-domain reflectometry, distance-to-fault", "N1", "ND", 2, "<1 day"),
    "magnetic_current_imaging": ("Magnetic current imaging (SQUID/GMR)", "N1", "ND", 4, "days"),
    # --- N2 -----------------------------------------------------------------
    "lock_in_thermography":  ("Lock-in IR thermography", "N2", "ND", 3, "<1 day"),
    "emmi_backside":         ("Photoemission microscopy, backside", "N2", "ND*", 4, "1-3 days"),
    "obirch_backside":       ("OBIRCH / thermal laser stimulation, backside", "N2", "ND*", 4, "1-3 days"),
    # --- D1 -----------------------------------------------------------------
    "lid_removal":           ("Controlled lid removal (hermetic package)", "D1", "ND*", 2, "hours"),
    "decap_chemical":        ("Wet chemical decapsulation", "D1", "D", 2, "hours"),
    "decap_plasma":          ("Plasma decapsulation (Cu-wire / thin-pad safe)", "D1", "D", 3, "hours-1 day"),
    "decap_laser_assisted":  ("Laser-assisted decapsulation + finish etch", "D1", "D", 3, "hours"),
    "internal_optical":      ("Internal optical inspection of exposed die & wires", "D1", "D", 1, "hours"),
    "emmi_frontside":        ("Photoemission microscopy, frontside", "D1", "D", 3, "1 day"),
    "obirch_frontside":      ("OBIRCH / thermal laser stimulation, frontside", "D1", "D", 3, "1 day"),
    "pvc_sem":               ("Passive voltage contrast SEM", "D1", "D", 3, "1 day"),
    "wire_pull_ball_shear":  ("Wire pull / ball shear with failure-mode classification", "D1", "D", 2, "hours"),
    # --- D2 -----------------------------------------------------------------
    "mechanical_cross_section": ("Mechanical cross-section (mount, grind, polish)", "D2", "D-term", 2, "1-2 days"),
    "fib_cross_section":     ("FIB site-specific cross-section", "D2", "D-term", 4, "1-3 days"),
    "sem_edx":               ("SEM imaging + EDX elemental analysis", "D2", "D-term", 2, "1 day"),
    "delayering":            ("Sequential delayering with inter-layer imaging", "D2", "D-term", 4, "days"),
    "nanoprobing":           ("Nanoprobing of deprocessed die", "D2", "D-term", 5, "days"),
    "tem_lamella":           ("FIB lamella + TEM (+EELS/EDX)", "D2", "D-term", 5, "3-7 days"),
    "dye_and_pry":           ("Dye penetrant and pry (board-level joints)", "D2", "D-term", 2, "1-2 days"),
}

# Canonical within-phase execution order. Physical ordering wins over priority: you cannot
# inspect an exposed die before the decap that exposed it, however "critical" the inspection is.
SEQ = {tid: i for i, tid in enumerate((
    # N0 - desk work first (free), then bench, then long stress monitoring
    "external_visual", "datalog_review", "burnin_delta_review", "bin_signature_analysis",
    "retest_matrix", "contact_elimination", "curve_trace", "shmoo", "in_situ_tc_monitoring",
    # N1
    "hermeticity_pind", "xray_2d", "csam", "xray_ct", "tdr", "magnetic_current_imaging",
    # N2
    "lock_in_thermography", "emmi_backside", "obirch_backside",
    # D1 - open, then look, then stimulate, then destructively test bonds
    "lid_removal", "decap_plasma", "decap_chemical", "decap_laser_assisted",
    "internal_optical", "emmi_frontside", "obirch_frontside", "pvc_sem", "wire_pull_ball_shear",
    # D2 - terminal
    "mechanical_cross_section", "fib_cross_section", "sem_edx", "delayering",
    "tem_lamella", "nanoprobing", "dye_and_pry",
))}

GATE_TEXT = {
    "D1": [
        "All applicable N0-N2 techniques are done and logged, or ruled inapplicable with a reason.",
        "C-SAM and X-ray are complete for molded/laminate packages - decapsulation destroys what they see.",
        "The hypothesis table names which hypothesis this step discriminates, with a pre-registered "
        "expected observation for every surviving hypothesis.",
        "Failure site or at least the failing pin/net is localized as far as non-destructive work allows.",
        "Sample allocation reviewed: the serial being consumed is the designated sequence unit, not the archive.",
        "EXPLICIT USER CONFIRMATION in this conversation, after being shown: units consumed, "
        "information gained, information destroyed, and the no-go alternative.",
    ],
    "D2": [
        "All GATE D1 checks still hold and D1 results are logged in the hypothesis table.",
        "THE CUT PLANE COMES FROM A LOCALIZED SITE (EMMI / OBIRCH / thermography / PVC-SEM / "
        "magnetic current imaging / unambiguous optical or X-ray feature). A cross-section through an "
        "unlocalized die is evidence destruction, not analysis.",
        "Every image and datalog from earlier phases is archived - this step is terminal for the unit.",
        "The pre-registered expectation is written down: what each surviving hypothesis predicts at this plane.",
        "Sample allocation reviewed; a confirmation unit remains for an independent mechanism check "
        "(or the single-sample protocol is explicitly in force).",
        "EXPLICIT USER CONFIRMATION in this conversation.",
    ],
}


def _sig_is(sig, *vals):
    return sig in vals


def build_plan(inp: dict) -> dict:
    """Return the plan dict. Pure function of the input dict - no I/O."""
    sc = inp["symptom_class"]
    pkg = inp["package_type"]
    n = inp["sample_count"]
    sig = inp["powered_signature"]
    susp = set(inp["suspected"])
    budget = inp["budget"]
    urgency = inp["urgency"]
    after_bi = inp["after_burnin"]
    after_reflow = inp["after_reflow"]
    cust = inp["customer_return"]

    selected: dict[str, dict] = {}
    excluded: list[dict] = []
    warnings: list[str] = []
    data_requests: list[str] = []

    def add(tid, priority, rationale, phase=None, expect=None, seq=None, destructive=None):
        if tid in selected:
            # keep the strongest priority and merge rationales
            cur = selected[tid]
            rank = {"critical": 3, "standard": 2, "optional": 1}
            if rank[priority] > rank[cur["priority"]]:
                cur["priority"] = priority
            if rationale not in cur["rationale"]:
                cur["rationale"] += " · " + rationale
            return
        name, dphase, destr, cost, tat = CATALOG[tid]
        selected[tid] = {
            "kind": "technique", "id": tid, "name": name,
            "phase": phase or dphase, "destructive": destructive or destr,
            "cost_tier": cost, "typical_turnaround": tat,
            "priority": priority, "rationale": rationale,
            "expect": expect or "", "_seq": SEQ[tid] if seq is None else seq,
        }

    def drop(tid, reason):
        excluded.append({"technique": tid, "reason": reason})

    # ------------------------------------------------------------------ P0
    single = (n == 1)
    if single:
        warnings.append(
            "SINGLE-SAMPLE CASE (--sample-count 1): the preservation protocol in phase P0 is in force. "
            "Every destructive step is irreversible for the whole investigation, not just for one unit."
        )
    if cust:
        warnings.append(
            "CUSTOMER RETURN / RMA: chain of custody opens before the first electrical test. "
            "As-received photography precedes any handling, powering, cleaning, or bake."
        )

    # ------------------------------------------------------------------ N0
    add("external_visual", "critical",
        "Always first; free, and burn marks / cracks / rework evidence are lost once handling starts.",
        expect="Package damage, discoloration, cracked mold, bent or corroded leads, rework or probe marks.")
    add("datalog_review", "critical",
        "The electrical fingerprint. Request a full datalog - stop-on-first-fail hides the signature.",
        expect="First-failing test number and name, bin, measured value vs limit, margin.")
    if sc in ("intermittent", "nff"):
        add("retest_matrix", "critical",
            f"Symptom class '{sc}': reproducibility must be established before any physical step.",
            expect="Pass/fail per insertion with conditions; a reproducibility rate, not an anecdote.")
        add("contact_elimination", "critical",
            "Most reported intermittents die here - contact, socket, or tester rather than silicon. "
            "That outcome is a finding, not a failure of the FA.",
            expect="Failure follows the unit (real) or follows the socket/tester (test-induced).")
    else:
        add("retest_matrix", "standard",
            "Confirm the failure on your own setup and program rev before committing lab time.",
            expect="Failure reproduces on your setup with the requester's program revision.")
    add("curve_trace", "critical",
        "Highest information-per-dollar step in the flow: separates short / open / leakage and "
        "shows whether the damage sits on a protection device or the core. Set compliance LOW - a "
        "high-compliance curve trace is itself an overstress event.",
        expect="Pin-by-pin I-V deltas vs known-good; a named failing pin and a damage character.")
    if sc in ("marginal", "parametric", "nff") or _sig_is(sig, "functional", "speed"):
        add("shmoo", "critical" if sc == "marginal" else "standard",
            "Marginality has a shape; the shape names the parameter the failure tracks. "
            "Always against a known-good Shmoo on the same setup.",
            expect="Pass-region shape: uniform shrink, notch, V-only or T-only boundary shift.")
    add("bin_signature_analysis", "critical" if n >= 5 else "standard",
        "Population statistics set the mechanism prior before any physical work. Even for a single "
        "return, wafer-sort data for that die is often retrievable through traceability.",
        expect="Bin pareto, spatial clustering vs random, edge/center concentration, first-failing-test commonality.")
    if n < 3:
        data_requests.append(
            "die_results.csv (and tests.csv if available) for the failing unit's lot/wafer, pulled via "
            "traceability - bin_signature.py needs die-level data to say anything."
        )
    if after_bi:
        add("burnin_delta_review", "critical",
            "Failure emerged at or after burn-in: the pre/post delta datalog is the single highest-value "
            "artifact for early-life mechanisms (which units moved, which test, which direction).",
            expect="Units that passed pre-burn-in and failed after; the specific test that shifted and by how much.")
        data_requests.append("Pre-burn-in and post-burn-in datalogs for the same serial numbers.")
    if sc == "intermittent":
        add("in_situ_tc_monitoring", "critical",
            "Intermittent that survived contact elimination: convert it into a reproducible, "
            "pin-localized failure by monitoring continuously through thermal cycling or vibration. "
            "HARD RULE: no destructive step until the failure is reproducible on demand.",
            expect="Resistance or functional excursions correlated with temperature/mechanical phase, "
                   "localized to specific pin(s).")

    # ------------------------------------------------------------------ N1
    if pkg in MOLDED or pkg == "flipchip-bga":
        prio = "critical" if (after_reflow or "delam" in susp or "underfill" in susp) else "standard"
        add("csam", prio,
            "MANDATORY BEFORE ANY DECAP OR BAKE. Decap chemistry, laser heat and hot plates create or "
            "heal the delamination you were sent to find; the moisture/interface history is then "
            "unrecoverable." + (" Reflow / MSL history in this case makes it decisive." if after_reflow else ""),
            expect="Interface delamination maps (die face, die attach, substrate/leadframe), "
                   "popcorn cracks, mold and die-attach voids.")
    else:
        drop("csam", f"package '{pkg}' has no molded/laminate interfaces with useful acoustic contrast")
    add("xray_2d", "critical" if ("wirebond" in susp or "solder" in susp or _sig_is(sig, "open")) else "standard",
        "Nearly free and nearly always worth it. Remember it is a projection: a crack plane along the "
        "beam is invisible and voids can superimpose.",
        expect="Wire sweep/breaks/shorts, ball and bump voids, joint bridging or opens, die-attach voids, foreign metal.")
    ct_reason = None
    if pkg in ("module-sip", "flipchip-bga"):
        ct_reason = f"'{pkg}' stacks features through the beam path; 2D projection is not enough to disposition."
    elif _sig_is(sig, "open") or {"wirebond", "solder", "underfill", "diecrack"} & susp:
        ct_reason = "An open / interconnect hypothesis needs 3D confirmation before the package is opened."
    if ct_reason:
        add("xray_ct", "standard", ct_reason,
            expect="3D reconstruction of the suspect joint/wire: crack plane, void geometry, true standoff.")
    if pkg == "ceramic-hermetic":
        add("hermeticity_pind", "critical",
            "Cavity package: seal integrity and loose conductive particles are hypotheses no other "
            "technique addresses, and lid removal destroys both.",
            expect="Fine/gross leak rate vs spec; PIND noise indicating loose particles.")
    else:
        drop("hermeticity_pind", f"package '{pkg}' is not a cavity/hermetic package")
    if pkg in SUBSTRATE_PACKAGES and (_sig_is(sig, "open") or sc == "intermittent" or "solder" in susp):
        add("tdr", "standard",
            "Substrate/board-level nets with an open or intermittent signature: TDR gives distance-to-fault "
            "before anything is opened.",
            expect="Impedance discontinuity at a known distance along the net vs a known-good reference net.")
    if _sig_is(sig, "short") and (single or budget == "high"):
        add("magnetic_current_imaging", "standard",
            "A hard short plus a sample that must survive: magnetic current imaging traces the actual "
            "current path through an intact package. This is the technique that justifies its cost "
            "precisely when N=1.",
            expect="Current path mapped through the package; short location in x-y without opening it.")

    # ------------------------------------------------------------------ N2
    if _sig_is(sig, "short", "leakage") or {"esd", "eos", "latchup"} & susp:
        add("lock_in_thermography", "standard",
            "Signature is a current path: sub-milliwatt hot spots are locatable through mold compound "
            "or from the backside, with the package still intact.",
            expect="A localized thermal signature at the defect, in x-y, under the failing bias condition.")
    emission_first = _sig_is(sig, "short", "leakage") or {"esd", "eos", "tddb"} & susp
    thermal_first = _sig_is(sig, "open", "speed") or {"em", "wirebond"} & susp
    if pkg in BACKSIDE_ACCESS:
        if emission_first:
            add("emmi_backside", "critical",
                "Backside access without decapsulation. Emission finds LIGHT - junction leakage, "
                "gate-oxide breakdown, forward-biased junctions - which is what this electrical "
                "signature predicts.",
                expect="Emission site(s) localized on the die; compare against a known-good unit under the same bias.")
        if thermal_first or not emission_first:
            add("obirch_backside", "critical" if thermal_first else "optional",
                "Thermal laser stimulation finds RESISTANCE CHANGE - opens, voided lines, marginal "
                "contacts - which emit no light and are invisible to EMMI.",
                expect="Resistive anomaly localized on the die under bias with current monitoring.")
    elif pkg == "bare-die":
        drop("emmi_backside", "bare die: the active face is already exposed - use frontside emission "
                              "(listed in phase N2 for this package type, non-destructively)")
        drop("obirch_backside", "bare die: frontside thermal stimulation is directly available")
    else:
        drop("emmi_backside",
             f"'{pkg}' buries the die face; photoemission and OBIRCH only become available after decap "
             f"(see phase D1) and therefore sit behind GATE D1")
        drop("obirch_backside", "same access constraint as emmi_backside for this package type")

    # ------------------------------------------------------------------ D1
    if pkg == "bare-die":
        # Nothing to open: die-level optical/emission work is non-destructive here.
        add("internal_optical", "critical",
            "Bare die: the die face is already exposed, so this is non-destructive. Handling damage is "
            "the leading test-induced artifact - photo-document before and after every handling step.",
            phase="N2", seq=14.5, destructive="ND",
            expect="Melt sites, cratering, corrosion, foreign material, passivation and probe damage.")
        if emission_first:
            add("emmi_frontside", "critical", "Bare die - frontside emission needs no decapsulation, "
                "so it is non-destructive here and belongs before any gate.",
                phase="N2", seq=16.5, destructive="ND",
                expect="Emission site(s) on the die under the failing bias.")
        if thermal_first:
            add("obirch_frontside", "critical",
                "Bare die - frontside thermal stimulation needs no decapsulation, and it sees the "
                "resistive anomalies that emission cannot.",
                phase="N2", seq=16.6, destructive="ND",
                expect="Resistive site localized on the die under bias.")
        drop("decap_chemical", "bare die / KGD - there is nothing to decapsulate")
    elif pkg == "ceramic-hermetic":
        add("lid_removal", "critical",
            "Least destructive way into a cavity package, and near-reversible - but it voids hermeticity, "
            "so hermeticity and PIND must be complete first.",
            expect="Cavity interior, die face, wires and any loose particles, intact.")
        add("internal_optical", "critical", "Direct inspection of the exposed die and wires.",
            expect="Melt sites, cratering, corrosion, lifted balls, foreign material.")
    elif pkg == "wlcsp":
        add("internal_optical", "standard",
            "WLCSP has no mold to remove; die-face inspection is available directly, and board-level "
            "solder/die-corner damage dominates this package family.",
            phase="N2", seq=14.5, destructive="ND",
            expect="Die corner cracks, passivation/PI damage, bump and RDL condition.")
        drop("decap_chemical", "WLCSP has no mold compound to remove")
    else:
        # Molded packages: choose the decap chemistry from the metallurgy.
        cu_wire_risk = pkg in WIREBONDED and ({"wirebond", "corrosion"} & susp or sc == "intermittent")
        if cu_wire_risk:
            add("decap_plasma", "critical",
                "The hypothesis lives AT the bond interface. Aggressive acid decap dissolves Cu wire, "
                "Al pad and the intermetallic layer - the exact evidence this case depends on. "
                "Plasma costs more and takes longer; pay it.",
                expect="Mold removed with bonds and pad metallurgy intact and inspectable.")
            drop("decap_chemical",
                 "wet acid attacks Cu wire / Al pad / IMC, which is the evidence this case needs - "
                 "use decap_plasma")
        else:
            add("decap_chemical", "standard",
                "Standard mold removal for die-face access. Record the method in the report - an "
                "interface photograph cannot be judged without knowing what removed the compound.",
                expect="Die face and wires exposed for optical and emission work.")
            add("decap_laser_assisted", "optional",
                "Faster local window when only a known die region matters; watch the heat-affected zone.",
                expect="Local cavity over the region of interest.")
        add("internal_optical", "critical",
            "First look after opening, before any biasing - photograph everything before the die sees power again.",
            expect="Melt sites, cratering, corrosion, lifted balls, foreign material, passivation damage.")
        if emission_first:
            add("emmi_frontside", "critical",
                "Emission localization, only now available on this package type. This is the step "
                "decapsulation was performed FOR - if it is not in the plan, the decap was premature.",
                expect="Emission site(s) on the die under the failing bias vs known-good.")
        if thermal_first:
            add("obirch_frontside", "critical",
                "Resistive-anomaly localization on the exposed die; matches an open/speed signature "
                "that emission cannot see.",
                expect="Resistive site localized on the die.")
    if _sig_is(sig, "open", "functional") or "em" in susp:
        add("pvc_sem", "standard",
            "Passive voltage contrast answers 'is this net floating?' directly and screens a large area "
            "fast - underused for open/resistive hypotheses.",
            expect="Bright/dark contrast identifying floating vs grounded nets across the array.")
    if pkg in WIREBONDED and ({"wirebond"} & susp or sc == "intermittent"):
        if n >= 2:
            add("wire_pull_ball_shear", "critical",
                "Bond-strength testing with FAILURE-MODE classification - the mode (pad lift, heel break, "
                "cratering, neck break) is the diagnosis; the number alone is not. Run it on SIBLING units, "
                "never on the subject unit whose bond you still need to cross-section. "
                "Method definitions: JESD22-B116-style ball shear and wire pull.",
                expect="Strength distribution vs the OSAT's control data, and the failure-mode histogram.")
        else:
            drop("wire_pull_ball_shear",
                 "single-sample case: destructive bond testing is population evidence and would consume "
                 "the only bond available for cross-section. Request sibling units from the same date code")
            data_requests.append(
                "Sibling units from the same date code / assembly lot - destructive bond-strength testing "
                "needs a population, and the subject unit cannot supply it."
            )

    # ------------------------------------------------------------------ D2
    package_feature = bool({"wirebond", "delam", "solder", "diecrack", "underfill", "corrosion"} & susp) \
        or pkg == "module-sip" or after_reflow
    if package_feature:
        add("mechanical_cross_section", "critical",
            "The suspect feature is package-scale (bond, joint, die attach, mold, die edge) - mechanical "
            "sectioning is the right tool; a FIB's field of view is a liability at this scale."
            + (" A reflow/MSL history puts the crack path and the delaminated interface at package "
               "scale, and the section plane should be chosen from the C-SAM map." if after_reflow else ""),
            expect="The interface in cross-section: crack path, IMC layer, void, delamination gap, with a scale bar.")
    if not single or not package_feature:
        add("fib_cross_section", "critical" if not package_feature else "standard",
            "Site-specific and material-sparing: it consumes almost no die, so the rest of the sample "
            "stays available. Requires a site localized to roughly a micron - if nothing is localized, "
            "the next step is another localization technique, not a cut.",
            expect="The localized site in cross-section: void, breakdown path, contact or via defect.")
    add("sem_edx", "standard",
        "Morphology plus elements. Report elements detected vs a reference location - EDX gives elements "
        "in an interaction volume, not a stoichiometry you can quote, and light elements are unreliable.",
        expect="Damage morphology at high magnification; elemental deltas (e.g. Cl, S, Br) vs a clean reference site.")
    if "tddb" in susp or (after_bi and _sig_is(sig, "leakage")):
        add("tem_lamella", "critical",
            "A gate-oxide question is answered at the oxide, and only TEM resolves an oxide thickness and "
            "a breakdown path. Site must already be localized by emission and FIB.",
            expect="Oxide thickness and integrity at the emission site; breakdown filament / percolation path.")
    if _sig_is(sig, "functional", "speed") or {"hci", "tddb"} & susp:
        add("delayering", "standard",
            "Functional/speed failures without a DC anomaly usually need the layer identified before the "
            "device can be probed; compare against a reference die or the layout.",
            expect="The layer holding the defect; buried shorts/opens visible between layers.")
        add("nanoprobing", "optional" if budget == "low" else "standard",
            "Transistor- and net-level electrical characterization of the suspect device itself - the only "
            "technique that measures the failing device rather than imaging it.",
            expect="I-V of the suspect transistor/net vs a neighbouring good one on the same die.")
    if pkg in SUBSTRATE_PACKAGES and ("solder" in susp or (sc == "intermittent" and _sig_is(sig, "open"))):
        add("dye_and_pry", "standard",
            "The board-level answer: which joints were cracked BEFORE the pry, and how far the crack ran. "
            "Sequence it after die-level work or run it on a sibling - the pry destroys the package.",
            expect="Dye coverage on fracture surfaces = pre-existing crack; clean fracture = pry artifact.")

    # ------------------------------------------------------------- budget/urgency
    if budget == "low":
        for tid, step in list(selected.items()):
            if step["cost_tier"] >= 4 and step["priority"] != "critical":
                del selected[tid]
                drop(tid, "cost tier >=4 deferred at --budget low; request approval if the plan stalls")
        warnings.append(
            "--budget low: cost-tier 4-5 techniques are deferred unless they are the discriminating step. "
            "If the plan stalls at a gate, the honest answer is to request budget, not to cut earlier."
        )
    if budget == "high":
        warnings.append(
            "--budget high does NOT relax the gates. Money buys parallel non-destructive work and "
            "external-lab access; it does not buy an earlier cross-section."
        )
    if urgency == "emergency":
        warnings.append(
            "--urgency emergency: launch CONTAINMENT IN PARALLEL, now. Containment needs only the failure "
            "SIGNATURE, not the mechanism - screen/hold the suspect date codes while the FA runs. "
            "Do not compress the flow by skipping gates; compress it by running N0/N1 in parallel and "
            "pre-booking the destructive slots."
        )
    elif urgency == "expedite":
        warnings.append(
            "--urgency expedite: run N0 and N1 in parallel across units rather than serially, and "
            "pre-book the localization tool. Gate order is unchanged."
        )

    # ---------------------------------------------------------------- assemble
    order_key = {p[0]: i for i, p in enumerate(PHASES)}
    steps = sorted(selected.values(), key=lambda s: (order_key[s["phase"]], s["_seq"]))
    for s in steps:
        s.pop("_seq", None)

    # P0 preservation steps
    p0: list[dict] = []

    def p0_step(text, why):
        p0.append({"kind": "note", "id": f"p0_{len(p0)+1}", "name": text, "phase": "P0",
                   "destructive": "ND", "cost_tier": 0, "typical_turnaround": "-",
                   "priority": "critical", "rationale": why, "expect": ""})

    if cust:
        p0_step("Open the chain-of-custody log: serials, requester, date/time received, condition as received.",
                "Customer-return evidence must be traceable through every transfer and every action.")
        p0_step("Photograph as received - all package faces, markings/date code, leads or balls, and the "
                "board if still attached - BEFORE any electrical test, cleaning, or bake.",
                "As-received condition is unrecoverable once anyone touches the part.")
    if single:
        p0_step("SINGLE-SAMPLE PROTOCOL IS IN FORCE: exhaust every applicable non-destructive technique "
                "before any gate is opened.",
                "There is no second unit; a destructive step ends the investigation, not just the unit.")
        p0_step("Archive every image, datalog and scan to the case folder before each irreversible step, "
                "and record the archive location in the report.",
                "The archived record is the only thing that survives a terminal step.")
        p0_step("Gates require WRITTEN pre-registered expected outcomes per surviving hypothesis, plus a "
                "second reviewer's sign-off.",
                "Pre-registration is what stops a cut from being rationalized after the fact.")
        p0_step("Prefer FIB over mechanical sectioning; prefer near-non-destructive external-lab "
                "localization (magnetic current imaging, lock-in thermography) over opening the package.",
                "Material-sparing techniques keep the remaining hypotheses testable.")
        p0_step("Do NOT run destructive population tests (wire pull, ball shear, dye-and-pry) on this unit. "
                "Request siblings from the same date code instead.",
                "Population evidence must come from a population.")
    else:
        p0_step(f"Designate sample roles now for the {n} units received, before any testing.",
                "Role assignment after testing is how the archive unit gets consumed by accident.")
        if not cust:
            p0_step("Photograph every unit as received and record serials against roles.",
                    "Baseline imagery, and it prevents serial confusion later in the flow.")

    if single:
        mode = "single_sample_preservation"
        alloc = {"archive": 0, "sequence": 1, "confirmation": 0, "held": 0}
        alloc_rules = [
            "The one unit is the sequence unit and there is no archive - imagery IS the archive.",
            "Known-good reference unit (different serial, same lot if possible) goes through the same "
            "non-destructive imaging for comparison, and never through a destructive step.",
        ]
    elif n <= 4:
        mode = "small_population"
        alloc = {"archive": 1, "sequence": 1, "confirmation": 0, "held": max(0, n - 2)}
        alloc_rules = [
            "1 unit archived untouched; 1 unit runs the sequence; the remainder are held for cross-check.",
            "Never run all units through the same destructive step.",
        ]
    else:
        mode = "population"
        alloc = {"archive": 1, "sequence": 1, "confirmation": 1, "held": n - 3}
        alloc_rules = [
            "1 archive (untouched), 1 sequence unit, 1 reserved to independently confirm the final "
            "mechanism call, remainder held or returned.",
            "Destructive population tests (bond pull/shear, dye-and-pry) run on held units, not on the "
            "sequence unit.",
            "A known-good reference unit runs the same non-destructive imaging for comparison only.",
        ]

    # Flat ordered plan with gates injected before each destructive phase
    plan: list[dict] = []
    order = 0

    def emit(step):
        nonlocal order
        order += 1
        s = dict(step)
        s["order"] = order
        plan.append(s)

    for s in p0:
        emit(s)

    gates_emitted = set()
    for s in steps:
        destructive = s["destructive"] in ("D", "D-term")
        gate = "D1" if s["phase"] == "D1" else ("D2" if s["phase"] == "D2" else None)
        if destructive and gate and gate not in gates_emitted:
            emit({
                "kind": "gate", "id": f"GATE_{gate}", "name": f"GATE {gate}",
                "phase": s["phase"], "destructive": "-", "cost_tier": 0,
                "typical_turnaround": "-", "priority": "critical",
                "rationale": "STOP. Every check below must be satisfied and stated in writing "
                             "before any step in this phase runs.",
                "expect": "", "checks": GATE_TEXT[gate],
            })
            gates_emitted.add(gate)
        s = dict(s)
        s["requires_gate"] = gate if destructive else None
        emit(s)

    phases_out = []
    for pid, ptitle, pnature in PHASES:
        psteps = [s for s in plan if s["phase"] == pid]
        if psteps:
            phases_out.append({"phase": pid, "title": ptitle, "nature": pnature, "steps": psteps})

    # Integrity check the plan enforces on itself.
    ungated = [s["id"] for s in plan
               if s["kind"] == "technique" and s["destructive"] in ("D", "D-term")
               and not s.get("requires_gate")]
    if ungated:
        warnings.append(f"PLAN DEFECT: destructive steps without a gate: {ungated}")

    discriminators = [s["id"] for s in plan if s["kind"] == "technique" and s["priority"] == "critical"]
    early = [s["id"] for s in plan
             if s["kind"] == "technique" and s["phase"] in ("N0", "N1", "N2")]

    return {
        "generated_by": "technique_selector.py",
        "version": VERSION,
        "inputs": inp,
        "sample_plan": {"mode": mode, "allocation": alloc, "rules": alloc_rules},
        "warnings": warnings,
        "data_requests": data_requests,
        "phases": phases_out,
        "plan": plan,
        "excluded": excluded,
        "summary": {
            "n_steps": len([s for s in plan if s["kind"] == "technique"]),
            "n_gates": len([s for s in plan if s["kind"] == "gate"]),
            "n_nondestructive": len([s for s in plan if s["kind"] == "technique"
                                     and s["destructive"].startswith("ND")]),
            "n_destructive": len([s for s in plan if s["kind"] == "technique"
                                  and s["destructive"] in ("D", "D-term")]),
            "critical_techniques": discriminators,
            "early_phase_techniques": early,
        },
    }


def render_text(plan: dict) -> str:
    L: list[str] = []
    inp = plan["inputs"]
    L.append("=" * 78)
    L.append("FA TECHNIQUE PLAN")
    L.append("=" * 78)
    L.append(f"symptom class : {inp['symptom_class']}")
    L.append(f"package       : {inp['package_type']}")
    L.append(f"samples       : {inp['sample_count']}")
    L.append(f"signature     : {inp['powered_signature']}")
    L.append(f"suspected     : {', '.join(inp['suspected']) or '-'}")
    flags = [k for k in ("after_burnin", "after_reflow", "customer_return") if inp[k]]
    L.append(f"flags         : {', '.join(flags) or '-'}")
    L.append(f"budget/urgency: {inp['budget']} / {inp['urgency']}")
    s = plan["summary"]
    L.append(f"plan          : {s['n_steps']} techniques ({s['n_nondestructive']} non-destructive, "
             f"{s['n_destructive']} destructive), {s['n_gates']} hard gates")
    L.append("")
    L.append("-- DISCRIMINATING TECHNIQUES (plan order; these are what the case turns on) " + "-" * 3)
    for tid in s["critical_techniques"]:
        st = next(x for x in plan["plan"] if x.get("id") == tid)
        tag = "EARLY/non-destructive" if st["phase"] in ("N0", "N1", "N2") else f"behind GATE {st['requires_gate']}"
        L.append(f"  * {tid:<26} [{st['phase']}] {tag}")
    L.append("")

    if plan["warnings"]:
        L.append("-- WARNINGS " + "-" * 66)
        for w in plan["warnings"]:
            L.append(f"  ! {w}")
        L.append("")

    sp = plan["sample_plan"]
    L.append("-- SAMPLE PLAN " + "-" * 63)
    L.append(f"  mode: {sp['mode']}")
    a = sp["allocation"]
    L.append(f"  allocation: archive={a['archive']} sequence={a['sequence']} "
             f"confirmation={a['confirmation']} held={a['held']}")
    for r in sp["rules"]:
        L.append(f"  - {r}")
    L.append("")

    for ph in plan["phases"]:
        L.append("=" * 78)
        L.append(f"PHASE {ph['phase']} - {ph['title']}  [{ph['nature']}]")
        L.append("=" * 78)
        for st in ph["steps"]:
            if st["kind"] == "gate":
                L.append("")
                L.append("  " + "#" * 70)
                L.append(f"  # {st['order']:>2}. {st['name']} - HARD STOP")
                L.append("  # " + st["rationale"])
                for i, c in enumerate(st["checks"], 1):
                    L.append(f"  #  {i}. {c}")
                L.append("  " + "#" * 70)
                L.append("")
            elif st["kind"] == "note":
                L.append(f"  {st['order']:>2}. [P0] {st['name']}")
                L.append(f"       why: {st['rationale']}")
            else:
                gate = f" behind GATE {st['requires_gate']}" if st.get("requires_gate") else ""
                L.append(f"  {st['order']:>2}. [{st['priority'].upper():<8}] {st['id']}"
                         f"  ({st['destructive']}{gate}, cost {st['cost_tier']}/5, {st['typical_turnaround']})")
                L.append(f"       {st['name']}")
                L.append(f"       why: {st['rationale']}")
                if st["expect"]:
                    L.append(f"       expect: {st['expect']}")
        L.append("")

    if plan["data_requests"]:
        L.append("-- DATA / SAMPLES TO REQUEST " + "-" * 49)
        for d in plan["data_requests"]:
            L.append(f"  - {d}")
        L.append("")
    if plan["excluded"]:
        L.append("-- NOT IN PLAN (with reason) " + "-" * 49)
        for e in plan["excluded"]:
            L.append(f"  - {e['technique']}: {e['reason']}")
        L.append("")
    L.append("This plan is an ordering, not a commitment. Update it after every result; a technique "
             "that returns nothing is a result too (see references/technique-matrix.md).")
    return "\n".join(L)


def normalize(raw: dict) -> dict:
    out = {
        "symptom_class": raw.get("symptom_class", "hard_fail"),
        "package_type": raw.get("package_type", "wirebond-plastic"),
        "sample_count": int(raw.get("sample_count", 1)),
        "powered_signature": raw.get("powered_signature") or "unknown",
        "suspected": [s for s in (raw.get("suspected") or []) if s and s != "none"],
        "after_burnin": bool(raw.get("after_burnin", False)),
        "after_reflow": bool(raw.get("after_reflow", False)),
        "customer_return": bool(raw.get("customer_return", False)),
        "budget": raw.get("budget") or "medium",
        "urgency": raw.get("urgency") or "routine",
    }
    errs = []
    if out["symptom_class"] not in SYMPTOM_CLASSES:
        errs.append(f"symptom_class must be one of {SYMPTOM_CLASSES}")
    if out["package_type"] not in PACKAGE_TYPES:
        errs.append(f"package_type must be one of {PACKAGE_TYPES}")
    if out["powered_signature"] not in SIGNATURES:
        errs.append(f"powered_signature must be one of {SIGNATURES}")
    for s in out["suspected"]:
        if s not in SUSPECTS:
            errs.append(f"suspected '{s}' not in {SUSPECTS}")
    if out["budget"] not in BUDGETS:
        errs.append(f"budget must be one of {BUDGETS}")
    if out["urgency"] not in URGENCIES:
        errs.append(f"urgency must be one of {URGENCIES}")
    if out["sample_count"] < 1:
        errs.append("sample_count must be >= 1")
    if errs:
        raise ValueError("; ".join(errs))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--case-file", help="JSON case file carrying a 'selector_input' block "
                                        "(CLI flags override its fields)")
    ap.add_argument("--symptom-class", choices=SYMPTOM_CLASSES,
                    help="hard_fail | parametric | marginal | intermittent | nff")
    ap.add_argument("--package-type", choices=PACKAGE_TYPES)
    ap.add_argument("--sample-count", type=int,
                    help="units available for analysis (1 triggers the preservation protocol)")
    ap.add_argument("--powered-signature", choices=SIGNATURES,
                    help="what the powered part does: short | open | leakage | functional | speed | unknown")
    ap.add_argument("--suspected", default="",
                    help=f"comma-separated mechanism suspicions from {','.join(SUSPECTS)}")
    ap.add_argument("--after-burnin", action="store_true",
                    help="failure appeared at or after burn-in / early life")
    ap.add_argument("--after-reflow", action="store_true",
                    help="failure appeared after board reflow / MSL exposure")
    ap.add_argument("--customer-return", action="store_true",
                    help="RMA / field return: chain of custody applies")
    ap.add_argument("--budget", choices=BUDGETS, help="relative budget (default medium)")
    ap.add_argument("--urgency", choices=URGENCIES, help="routine | expedite | emergency (default routine)")
    ap.add_argument("--output", help="write the plan JSON to this path")
    ap.add_argument("--json", action="store_true", help="print the plan JSON to stdout instead of the summary")
    args = ap.parse_args(argv)

    raw: dict = {}
    if args.case_file:
        try:
            case = json.loads(Path(args.case_file).read_text())
        except Exception as e:  # noqa: BLE001
            print(f"error: cannot read --case-file: {e}", file=sys.stderr)
            return 2
        raw.update(case.get("selector_input") or {})
    for key, val in (
        ("symptom_class", args.symptom_class), ("package_type", args.package_type),
        ("sample_count", args.sample_count), ("powered_signature", args.powered_signature),
        ("budget", args.budget), ("urgency", args.urgency),
    ):
        if val is not None:
            raw[key] = val
    if args.suspected:
        raw["suspected"] = [s.strip() for s in args.suspected.split(",") if s.strip()]
    for flag, key in ((args.after_burnin, "after_burnin"), (args.after_reflow, "after_reflow"),
                      (args.customer_return, "customer_return")):
        if flag:
            raw[key] = True
    if not raw.get("symptom_class") or not raw.get("package_type") or not raw.get("sample_count"):
        print("error: need --symptom-class, --package-type and --sample-count "
              "(or a --case-file that supplies them)", file=sys.stderr)
        return 2

    try:
        inp = normalize(raw)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    plan = build_plan(inp)
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(plan, indent=2) + "\n")
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(render_text(plan))
        if args.output:
            print(f"\n[plan JSON written to {args.output}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
