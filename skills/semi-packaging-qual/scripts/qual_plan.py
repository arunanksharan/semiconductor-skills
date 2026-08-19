#!/usr/bin/env python3
"""Package qualification test-matrix generator (JEDEC / AEC-Q100 style).

Device class + package family + novelty + MSL target -> a reliability test matrix with
standard references, conditions, durations, readpoints, sample sizes, lot requirements and
pass criteria, emitted as markdown and/or JSON.

Every LTPD figure in the matrix is computed by scripts/sample_size.py (exact binomial), not
quoted from a table. Conditions and durations are INDUSTRY-TYPICAL TEMPLATES: the emitted
plan always carries a `verify` block listing the standards whose current revision governs.
Rows whose applicability the author could not confirm are marked applicability=conditional
with a TODO in the note - do not silently promote them to "required".

Usage examples:
  python qual_plan.py --device-class automotive_grade1 --package qfn \\
      --novelty derivative --msl 2 --format both --out plan.md --json-out plan.json
  python qual_plan.py --device-class consumer --package wlcsp --novelty new_package \\
      --msl 1 --handheld
  python qual_plan.py --scenario ../../../sample-data/semi-packaging-qual/consumer_wlcsp_new.json
  python qual_plan.py --list-packages
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sample_size import ltpd as _ltpd  # noqa: E402  (local sibling module)

SCHEMA_VERSION = "0.1.0"

# --------------------------------------------------------------------------------------
# Device-class / mission-profile escalation table.
#
# Consumer + industrial follow JESD47-style defaults. The automotive rows follow AEC-Q100
# grade ambients (grade 0 <=150 C, 1 <=125 C, 2 <=105 C, 3 <=85 C, 4 <=70 C ambient) and
# escalate condition + duration + lot count with grade. EXACT AEC letter conditions and
# cycle counts differ by AEC-Q100 revision - each automotive row carries a verify string.
# --------------------------------------------------------------------------------------
DEVICE_CLASSES: dict[str, dict] = {
    "consumer": dict(
        label="Consumer", automotive=False, ambient_max_c=70, aec_grade=None,
        tc_condition="Condition G, -40/+125 C (air-to-air; record ramp and dwell)",
        tc_cycles=500, tc_readpoints=[250, 500],
        htsl_c=150, htsl_hours=500, htsl_readpoints=[250, 500],
        hast_hours=96, uhast_hours=96, thb_hours=500,
        lots_floor=1, env_n=77, mech_n=45,
        ptc=False, auto_mech_suite=False,
        verify="JESD47 current rev for the default stress set and durations",
    ),
    "industrial": dict(
        label="Industrial", automotive=False, ambient_max_c=85, aec_grade=None,
        tc_condition="Condition B, -55/+125 C (air-to-air; record ramp and dwell)",
        tc_cycles=1000, tc_readpoints=[500, 1000],
        htsl_c=150, htsl_hours=1000, htsl_readpoints=[500, 1000],
        hast_hours=96, uhast_hours=96, thb_hours=1000,
        lots_floor=1, env_n=77, mech_n=45,
        ptc=False, auto_mech_suite=False,
        verify="JESD47 current rev; confirm TC condition vs the product mission profile",
    ),
    "automotive_grade3": dict(
        label="Automotive AEC-Q100 grade 3 (ambient -40 to +85 C)", automotive=True,
        ambient_max_c=85, aec_grade=3,
        tc_condition="Condition G, -40/+125 C (AEC tables may specify a wider swing)",
        tc_cycles=1000, tc_readpoints=[500, 1000],
        htsl_c=150, htsl_hours=1000, htsl_readpoints=[500, 1000],
        hast_hours=96, uhast_hours=96, thb_hours=1000,
        lots_floor=3, env_n=77, mech_n=45,
        ptc=True, auto_mech_suite=True,
        verify="AEC-Q100 current rev, package-integrity table, grade 3 column",
    ),
    "automotive_grade2": dict(
        label="Automotive AEC-Q100 grade 2 (ambient -40 to +105 C)", automotive=True,
        ambient_max_c=105, aec_grade=2,
        tc_condition="Condition B, -55/+125 C",
        tc_cycles=1000, tc_readpoints=[500, 1000],
        htsl_c=150, htsl_hours=1000, htsl_readpoints=[500, 1000],
        hast_hours=96, uhast_hours=96, thb_hours=1000,
        lots_floor=3, env_n=77, mech_n=45,
        ptc=True, auto_mech_suite=True,
        verify="AEC-Q100 current rev, package-integrity table, grade 2 column",
    ),
    "automotive_grade1": dict(
        label="Automotive AEC-Q100 grade 1 (ambient -40 to +125 C)", automotive=True,
        ambient_max_c=125, aec_grade=1,
        tc_condition="Condition B, -55/+125 C (grade 1 programmes often run -50/+150 C)",
        tc_cycles=1000, tc_readpoints=[500, 1000],
        htsl_c=150, htsl_hours=1000, htsl_readpoints=[500, 1000],
        hast_hours=96, uhast_hours=96, thb_hours=1000,
        lots_floor=3, env_n=77, mech_n=45,
        ptc=True, auto_mech_suite=True,
        verify="AEC-Q100 current rev, package-integrity table, grade 1 column",
    ),
    "automotive_grade0": dict(
        label="Automotive AEC-Q100 grade 0 (ambient -40 to +150 C)", automotive=True,
        ambient_max_c=150, aec_grade=0,
        tc_condition="Condition C, -65/+150 C (grade 0 severity; confirm letter vs AEC table)",
        tc_cycles=2000, tc_readpoints=[500, 1000, 1500, 2000],
        htsl_c=175, htsl_hours=1000, htsl_readpoints=[500, 1000],
        hast_hours=96, uhast_hours=96, thb_hours=1000,
        lots_floor=3, env_n=77, mech_n=45,
        ptc=True, auto_mech_suite=True,
        verify="AEC-Q100 current rev, package-integrity table, grade 0 column; "
               "confirm 175 C HTSL vs mold-compound Tg and datasheet Tj",
    ),
}

# --------------------------------------------------------------------------------------
# Package families. `area_array` drives board-level content; the interconnect flags drive
# bond/attach integrity content.
# --------------------------------------------------------------------------------------
PACKAGES: dict[str, dict] = {
    "qfn": dict(label="QFN / DFN (wire-bond, exposed pad)", interconnect="wirebond",
                area_array=False, balls=False, wirebond=True, flipchip=False,
                underfill=False, formed_leads=False, bare_die=False, bespoke=False,
                typical_msl="1-2",
                risks=["Exposed-pad solder voiding on the board erodes the thermal spec",
                       "Cut-copper lead flanks: solderability and AOI of the side wall",
                       "Mold-to-leadframe delamination (moisture path to the wires)"]),
    "dfn": dict(label="DFN (wire-bond, exposed pad)", interconnect="wirebond",
                area_array=False, balls=False, wirebond=True, flipchip=False,
                underfill=False, formed_leads=False, bare_die=False, bespoke=False,
                typical_msl="1-2",
                risks=["Exposed-pad solder voiding on the board",
                       "Lead-flank solderability after singulation",
                       "Mold-to-leadframe delamination"]),
    "qfp": dict(label="QFP / TQFP (wire-bond, gull-wing leads)", interconnect="wirebond",
                area_array=False, balls=False, wirebond=True, flipchip=False,
                underfill=False, formed_leads=True, bare_die=False, bespoke=False,
                typical_msl="2-3",
                risks=["Long-wire sweep at mold; wire-to-wire shorting",
                       "Lead coplanarity and handling damage -> corner-lead opens",
                       "Mold-to-leadframe delamination"]),
    "pbga": dict(label="PBGA (wire-bond on organic substrate)", interconnect="wirebond",
                 area_array=True, balls=True, wirebond=True, flipchip=False,
                 underfill=False, formed_leads=False, bare_die=False, bespoke=False,
                 typical_msl="3",
                 risks=["Mold-to-substrate delamination; substrate moisture (MSL 3 typical)",
                        "Via-in-pad outgassing voids in the ball joint",
                        "Ball-joint fatigue in board-level thermal cycling"]),
    "fcbga": dict(label="FCBGA (flip chip on organic substrate, underfilled)",
                  interconnect="flipchip",
                  area_array=True, balls=True, wirebond=False, flipchip=True,
                  underfill=True, formed_leads=False, bare_die=False, bespoke=False,
                  typical_msl="3-4",
                  risks=["Die-corner low-k / ULK delamination under CTE stress",
                         "Dynamic warpage -> head-in-pillow / non-wet at board mount",
                         "Bump fatigue vs underfill Tg/CTE selection; lid-adhesive delam"]),
    "fccsp": dict(label="FCCSP (flip-chip chip-scale, underfilled)", interconnect="flipchip",
                  area_array=True, balls=True, wirebond=False, flipchip=True,
                  underfill=True, formed_leads=False, bare_die=False, bespoke=False,
                  typical_msl="3",
                  risks=["Underfill voids / incomplete fillet",
                         "Die-corner delamination",
                         "Board-level thermal fatigue of fine-pitch balls"]),
    "wlcsp": dict(label="WLCSP (bare die, bumps direct to board)", interconnect="wlcsp_bump",
                  area_array=True, balls=True, wirebond=False, flipchip=False,
                  underfill=False, formed_leads=False, bare_die=True, bespoke=False,
                  typical_msl="1",
                  risks=["Board-level thermal fatigue and drop are THE wear-out modes",
                         "UBM / RDL cracking; polymer repassivation adhesion",
                         "Backside chipping and die strength from thin-wafer handling"]),
    "fowlp": dict(label="Fan-out WLP (RDL over reconstituted mold)", interconnect="rdl",
                  area_array=True, balls=True, wirebond=False, flipchip=False,
                  underfill=False, formed_leads=False, bare_die=False, bespoke=False,
                  typical_msl="1-3",
                  risks=["Mold-to-RDL delamination; RDL cracking at the die edge",
                         "Reconstituted-wafer warpage -> coplanarity",
                         "Board-level thermal fatigue at large fan-out ratios"]),
    "interposer_2p5d": dict(label="2.5D interposer / 3D stack", interconnect="flipchip",
                            area_array=True, balls=True, wirebond=False, flipchip=True,
                            underfill=True, formed_leads=False, bare_die=False,
                            bespoke=True, typical_msl="3-4",
                            risks=["Microbump / hybrid-bond integrity under thermal cycling",
                                   "Interposer cracking; stacked-die thermal gradients",
                                   "Known-good-die economics drive the sampling plan"]),
}
PACKAGE_ALIASES = {"bga": "pbga", "csp": "fccsp", "tqfp": "qfp", "lqfp": "qfp",
                   "wlp": "wlcsp", "fo": "fowlp", "fowlp_info": "fowlp",
                   "2.5d": "interposer_2p5d", "3d": "interposer_2p5d"}

# J-STD-020 soak conditions per level (own-words digest; current revision governs).
MSL_SOAK = {
    "1": ("85 C / 85 %RH, 168 h", "unlimited floor life at <=30 C / 85 %RH"),
    "2": ("85 C / 60 %RH, 168 h", "1 year floor life at <=30 C / 60 %RH"),
    "2a": ("30 C / 60 %RH, 696 h", "4 weeks floor life at <=30 C / 60 %RH"),
    "3": ("30 C / 60 %RH, 192 h", "168 h floor life at <=30 C / 60 %RH"),
    "4": ("30 C / 60 %RH, 96 h", "72 h floor life at <=30 C / 60 %RH"),
    "5": ("30 C / 60 %RH, 72 h", "48 h floor life at <=30 C / 60 %RH"),
    "5a": ("30 C / 60 %RH, 48 h", "24 h floor life at <=30 C / 60 %RH"),
}

NOVELTY = {
    "new_package": dict(label="New package family / new materials set / new assembly site",
                        lots=3, similarity_allowed=False,
                        note="Full qualification. 3 non-consecutive assembly lots."),
    "derivative": dict(label="Derivative of an already-qualified package",
                       lots=1, similarity_allowed=True,
                       note="1 lot PLUS a written similarity justification. Similarity is "
                            "NOT allowed if any of: new mold compound or die-attach "
                            "material, new assembly site, die-to-pad ratio outside the "
                            "qualified envelope, finer wire/ball pitch, new wire or ball "
                            "metallurgy, thinner die than qualified. Any of those -> "
                            "re-run as new_package."),
    "process_change": dict(label="Process / material change on a qualified package",
                           lots=2, similarity_allowed=True,
                           note="Delta qualification. The matrix below is the MAXIMUM "
                                "scope: prune it against a documented change-impact "
                                "analysis (which mechanism can the change touch?) and "
                                "keep the pruning rationale in the plan."),
}

GROUP_ORDER = ["Preconditioning", "Environmental stress", "Board-level reliability",
               "Bond and attach integrity", "Mechanical robustness",
               "Package integrity and inspection"]

ELECTRICAL_PASS = ("All units pass the full datasheet electrical test (hot/cold/room) at "
                   "every readpoint; parametric drift within the limits declared in the plan")
CSAM_PASS = ("No NEW delamination on a critical interface vs the same unit's time-zero C-SAM "
             "(active die face, wire-bonded periphery, and any interface the construction "
             "makes a thermal/electrical path)")


ROW_FIELDS = ["id", "test", "group", "standard", "condition", "duration", "readpoints",
              "n_per_lot", "lots", "total_units", "accept", "ltpd_pct_at_90", "sample_note",
              "pass_criteria", "covers", "note", "applicability", "verify"]


def _normalise(rows: list[dict]) -> list[dict]:
    """Sort by stress group then insertion order, and give every row the same key set.

    Built in plain Python on purpose: routing these dicts through a DataFrame turns the
    missing optional keys into NaN, and NaN is truthy, which silently corrupts the
    sample-size cell. pandas is used below for aggregation and CSV only.
    """
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    ordered = sorted(rows, key=lambda r: (order[r["group"]], r["order"]))
    out = []
    for r in ordered:
        out.append({k: r.get(k) for k in ROW_FIELDS})
    return out


def _leg(n_per_lot: int | None, lots: int) -> dict:
    """Sample-size block with an exact-binomial LTPD, or a descriptive block."""
    if n_per_lot is None:
        return {"n_per_lot": None, "lots": lots, "total_units": None,
                "accept": 0, "ltpd_pct_at_90": None}
    return {"n_per_lot": n_per_lot, "lots": lots, "total_units": n_per_lot * lots,
            "accept": 0, "ltpd_pct_at_90": round(_ltpd(n_per_lot, 0, 0.90) * 100, 2)}


def build_matrix(cfg: dict) -> dict:
    """Assemble the plan dict for a resolved config."""
    dc = DEVICE_CLASSES[cfg["device_class"]]
    pk = PACKAGES[cfg["package"]]
    nov = NOVELTY[cfg["novelty"]]
    msl = cfg["msl"]
    soak, floor_life = MSL_SOAK[msl]

    lots = max(nov["lots"], dc["lots_floor"])
    env_n, mech_n = dc["env_n"], dc["mech_n"]
    rows: list[dict] = []
    notes: list[str] = []

    def add(**kw):
        kw.setdefault("applicability", "required")
        kw.setdefault("order", len(rows))
        rows.append(kw)

    # ---------------- Preconditioning -------------------------------------------------
    add(id="precon", test="Preconditioning (MSL {} + 3x reflow)".format(msl),
        group="Preconditioning", standard="JESD22-A113 (level per J-STD-020)",
        condition="Bake dry -> moisture soak {} -> 3x Pb-free reflow at the classified "
                  "peak (run msl_advisor.py for the peak) -> flux clean".format(soak),
        duration="Single pass; soak {}".format(soak.split(", ")[-1]),
        readpoints="Time-zero electrical + C-SAM before soak; electrical + C-SAM after "
                   "the 3rd reflow",
        **_leg(env_n, lots),
        pass_criteria="No external crack, no electrical fail, and " + CSAM_PASS,
        covers="Popcorn cracking and moisture-driven delamination from board mount",
        note="Gateway, not a standalone leg: the SAME units then feed TC / HAST / uHAST / "
             "HTSL. A precon fail stops the plan - triage before any stress leg starts.",
        verify="J-STD-020 current rev (soak table + classification peak); JESD22-A113")

    # ---------------- Environmental stress --------------------------------------------
    tc_cycles = dc["tc_cycles"]
    tc_rp = list(dc["tc_readpoints"])
    htsl_hours = dc["htsl_hours"]
    htsl_rp = list(dc["htsl_readpoints"])
    if cfg["novelty"] == "new_package":
        # House rule, not a standard: a family with no history needs wear-out data, not a
        # 500-cycle pass/fail gate. Stated as a house rule in the plan notes.
        if tc_cycles < 1000:
            tc_cycles, tc_rp = 1000, sorted(set(tc_rp + [1000]))
        if htsl_hours < 1000:
            htsl_hours, htsl_rp = 1000, sorted(set(htsl_rp + [1000]))
        notes.append("HOUSE RULE (not a standard requirement): a NEW package family is run "
                     "to at least 1000 TC cycles and 1000 h HTSL even when the device class "
                     "default is shorter - a family with no field history needs a wear-out "
                     "curve, not a pass/fail gate. Drop back to the class default only with "
                     "a written rationale.")
    if dc["automotive"] and cfg["novelty"] == "new_package" and tc_cycles < 2000:
        tc_cycles = 2000
        tc_rp = sorted(set(tc_rp + [1500, 2000]))
        notes.append("Automotive + new package family: TC extended to 2000 cycles "
                     "(wear-out margin, not just a pass/fail gate).")
    add(id="tc", test="Temperature cycling (TC)", group="Environmental stress",
        standard="JESD22-A104", condition=dc["tc_condition"],
        duration="{} cycles".format(tc_cycles),
        readpoints=", ".join("{} cyc".format(r) for r in tc_rp),
        **_leg(env_n, lots),
        pass_criteria=ELECTRICAL_PASS + "; " + CSAM_PASS,
        covers="CTE-mismatch fatigue: wire heel/neck, die attach, underfill, die-corner "
               "delamination, passivation cracking",
        note="Record soak mode / ramp with the letter condition - dwell drives solder creep "
             "and is not implied by the letter alone. Runs after precon.",
        verify="JESD22-A104 current rev; " + dc["verify"])

    add(id="uhast", test="Unbiased HAST (uHAST)", group="Environmental stress",
        standard="JESD22-A118",
        condition="Condition A, 130 C / 85 %RH (Condition B 110 C / 85 %RH is the longer "
                  "alternative)",
        duration="{} h".format(dc["uhast_hours"]),
        readpoints="End point (add an interim read if the leg is extended)",
        **_leg(env_n, lots),
        pass_criteria=ELECTRICAL_PASS + "; " + CSAM_PASS,
        covers="Moisture ingress, adhesion loss, galvanic/chemical corrosion without bias",
        note="Preferred over legacy autoclave / PCT (JESD22-A102), which is harsher on some "
             "compounds and prone to condensation artifacts. Runs after precon.",
        verify="JESD22-A118 current rev")

    hast_note = ("Bias per the device spec, chosen to maximise field without self-heating - "
                 "more than ~10 C junction rise invalidates the humidity exposure. "
                 "Runs after precon.")
    if pk["wirebond"]:
        hast_note += (" Cu or Pd-coated-Cu wire on Al pads: this leg is the one that finds "
                      "halide-driven IMC corrosion - do not waive it or shorten it.")
    add(id="hast", test="Biased HAST", group="Environmental stress", standard="JESD22-A110",
        condition="Condition A, 130 C / 85 %RH, ~230 kPa, biased",
        duration="{} h".format(dc["hast_hours"]),
        readpoints="End point (interim read at 48 h if equipment allows)",
        **_leg(env_n, lots),
        pass_criteria=ELECTRICAL_PASS + "; no corrosion or dendrite growth at bond "
                                        "pads/traces on decapsulated audit units",
        covers="Electrochemical corrosion and migration: Al pad corrosion, Cu-Al IMC halide "
               "attack, substrate dendrites",
        note=hast_note, verify="JESD22-A110 current rev")

    add(id="thb", test="Temperature humidity bias (THB) - alternative to HAST",
        group="Environmental stress", standard="JESD22-A101",
        condition="85 C / 85 %RH, biased",
        duration="{} h".format(dc["thb_hours"]),
        readpoints=", ".join("{} h".format(r) for r in
                             sorted({min(500, dc["thb_hours"]), dc["thb_hours"]})),
        **_leg(env_n, lots),
        pass_criteria=ELECTRICAL_PASS,
        covers="Same mechanisms as biased HAST on a longer, unaccelerated clock",
        applicability="alternative",
        note="Run HAST OR THB, not both. Choose THB when historical data or a customer spec "
             "demands 85/85, or when HAST pressure is a risk for the construction.",
        verify="JESD22-A101 current rev")

    add(id="htsl", test="High-temperature storage life (HTSL)", group="Environmental stress",
        standard="JESD22-A103",
        condition="{} C, unbiased".format(dc["htsl_c"]),
        duration="{} h".format(htsl_hours),
        readpoints=", ".join("{} h".format(r) for r in htsl_rp),
        **_leg(env_n, lots),
        pass_criteria=ELECTRICAL_PASS + (
            "; wire pull / ball shear sample at each readpoint stays above the plan limit"
            if pk["wirebond"] else ""),
        covers="Pure thermal aging: Au-Al IMC growth and Kirkendall voiding, mold-compound "
               "embrittlement, solder-joint coarsening",
        note=("Wire-bond packages: pull and shear a sample AT the readpoints, not only at "
              "end of life - IMC degradation shows in mechanical data long before it shows "
              "electrically." if pk["wirebond"] else
              "No wire bonds in this family: HTSL here targets die attach, underfill and "
              "ball/UBM aging."),
        verify="JESD22-A103 current rev; " + dc["verify"])

    if dc["ptc"] or cfg["power_cycling"]:
        add(id="ptc", test="Power temperature cycling (PTC)", group="Environmental stress",
            standard="JESD22-A105",
            condition="Device powered to its rated junction temperature, cycled to the "
                      "class ambient limit ({} C)".format(dc["ambient_max_c"]),
            duration="1000 cycles",
            readpoints="500, 1000 cycles",
            **_leg(mech_n, lots),
            pass_criteria=ELECTRICAL_PASS + "; thermal resistance (RthJA/RthJC) drift within "
                                            "the declared limit",
            covers="Self-heating thermal gradients across the die-attach / exposed-pad "
                   "thermal path that passive TC does not reproduce",
            applicability="conditional",
            note="Required for power devices and normal practice for automotive. TODO: "
                 "confirm applicability and cycle count for this specific device against "
                 "the current AEC-Q100 revision and the customer's mission profile.",
            verify="JESD22-A105 current rev; " + (dc["verify"] or ""))

    # ---------------- Board-level reliability -----------------------------------------
    want_bl_tc = (pk["area_array"] or dc["automotive"] or cfg["board_level"]) \
        and not cfg["suppress_board_level"]
    want_drop = (cfg["handheld"] or (pk["area_array"] and cfg["device_class"] == "consumer")
                 or cfg["board_level"]) and not cfg["suppress_board_level"]

    if want_drop:
        add(id="board_drop", test="Board-level drop", group="Board-level reliability",
            standard="JESD22-B111 (board and component layout per the standard)",
            condition="1500 G / 0.5 ms half-sine, condition B; daisy-chain components on the "
                      "standard drop board, continuously monitored",
            duration="30 drops (or to failure, recording cycles-to-fail)",
            readpoints="Continuous event detection; resistance check every 5 drops",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note=">=5 daisy-chain boards x 15 components per board "
                        "(JESD22-B111 board definition) = >=75 components",
            pass_criteria="No daisy-chain discontinuity (>1 us event) through the specified "
                          "drop count; Weibull characteristic life reported vs the "
                          "reference package",
            covers="Solder-joint and UBM cracking under handheld drop shock - the dominant "
                   "field risk for CSP/WLCSP/BGA in portable products",
            note="Mandatory for handheld/wearable end products. Report cycles-to-failure "
                 "distribution, not just pass/fail - the margin is the deliverable.",
            verify="JESD22-B111 current rev (board stack-up, component population, "
                   "drop condition letter)")

    if want_bl_tc:
        bl_cycles = "1000 cycles minimum; 3000 for a wear-out characterisation" \
            if not dc["automotive"] else "1000 cycles minimum; extend to wear-out for a " \
                                         "mission-profile-based life prediction"
        add(id="board_tc", test="Board-level thermal cycling (BLR TC)",
            group="Board-level reliability",
            standard="IPC-9701 practice (JEDEC has no single component-agnostic BLR TC "
                     "number - TODO: confirm the class/condition the customer requires)",
            condition="-40/+125 C, daisy-chain components on a representative board "
                      "stack-up and pad design (NSMD/SMD as built)",
            duration=bl_cycles,
            readpoints="Continuous event detection; Weibull fit at 63.2 % failure",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note=">=30 daisy-chained components (IPC-9701 practice); TODO verify the "
                        "minimum sample and class against the current revision",
            pass_criteria="Characteristic life exceeds the field requirement derived from "
                          "the mission profile with the agreed acceleration factor; no "
                          "early (infant) failures",
            covers="Solder-joint fatigue of the BOARD joint - the wear-out mode component-"
                   "level TC cannot see",
            applicability="required" if pk["area_array"] else "conditional",
            note="Board design (pad type, stack-up, via-in-pad) changes the answer as much "
                 "as the package does - qualify against the customer's real board, and say "
                 "which board the data came from.",
            verify="IPC-9701 current rev; acceleration model and field profile agreed in "
                   "writing with the customer")
    elif cfg["suppress_board_level"]:
        notes.append("Board-level tests suppressed by --suppress-board-level. This needs a "
                     "written justification in the plan (e.g. board-level data already "
                     "exists for an identical joint geometry on the same board design).")

    # ---------------- Bond and attach integrity ---------------------------------------
    if pk["wirebond"]:
        add(id="wire_pull", test="Wire pull", group="Bond and attach integrity",
            standard="MIL-STD-883 Method 2011 (industry practice; TODO confirm whether the "
                     "customer requires a JEDEC-numbered equivalent)",
            condition="Hook pull at mid-span, post-mold destructive decap on audit units",
            duration="Time-zero, plus after HTSL and TC readpoints",
            readpoints="t0, HTSL {} h, TC end".format(htsl_rp[-1]),
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="5 units x 30 wires per lot per readpoint (house practice)",
            pass_criteria="Mean and minimum pull force above the plan limit; failure-mode "
                          "distribution free of ball lift and cratering",
            covers="Heel/neck integrity, NSOP escapes, IMC degradation with thermal aging",
            note="Track the FAILURE MODE distribution, not only the force. A passing force "
                 "with a shifting mode (mid-span break -> ball lift) is a process signal.",
            verify="MIL-STD-883 M2011 current rev; pull limits vs wire diameter")
        add(id="ball_bond_shear", test="Ball bond shear",
            group="Bond and attach integrity", standard="JESD22-B116",
            condition="Shear tool at the ball bond after decap",
            duration="Time-zero and after HTSL",
            readpoints="t0, HTSL {} h".format(htsl_rp[-1]),
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="5 units x 30 balls per lot per readpoint (house practice)",
            pass_criteria="Shear strength above the plan limit; IMC coverage above the "
                          "declared minimum with no interfacial (ball lift) mode",
            covers="Ball-bond IMC coverage and strength; cratering risk on the pad stack",
            verify="JESD22-B116 current rev")
        add(id="die_shear", test="Die shear (die-attach strength)",
            group="Bond and attach integrity",
            standard="MIL-STD-883 Method 2019 (TODO confirm the customer's preferred method "
                     "number for plastic packages)",
            condition="Shear the die from the pad after decap",
            duration="Time-zero and after HTSL",
            readpoints="t0, HTSL {} h".format(htsl_rp[-1]),
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="5 units per lot per readpoint",
            pass_criteria="Shear strength above the area-scaled limit; cohesive (not "
                          "interfacial) failure mode",
            covers="Die-attach adhesion and its degradation with thermal aging",
            applicability="conditional",
            verify="MIL-STD-883 M2019 current rev")
    if pk["balls"]:
        add(id="ball_shear", test="Solder ball shear", group="Bond and attach integrity",
            standard="JESD22-B117",
            condition="Shear speed and shear height per the standard; report failure mode",
            duration="Time-zero, and after precon + TC for a brittle-mode check",
            readpoints="t0, post-precon, TC end",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="5 units x 10 balls per lot per readpoint",
            pass_criteria="Shear force above the plan limit with a ductile bulk-solder "
                          "failure mode; brittle IMC/pad-lift modes are a fail regardless "
                          "of force",
            covers="Ball-attach integrity, brittle IMC and ENIG black-pad exposure",
            note="Failure MODE is the real acceptance criterion here - a high-force brittle "
                 "interfacial fracture is worse than a lower-force ductile one.",
            verify="JESD22-B117 current rev")
    if pk["flipchip"]:
        add(id="bump_integrity", test="Bump shear / cold bump pull",
            group="Bond and attach integrity",
            standard="TODO verify standard number - JESD22-B117 covers solder ball shear; "
                     "Cu-pillar-specific methods are often supplier/customer specs",
            condition="Per the agreed method; report force and failure mode",
            duration="Time-zero and post-TC",
            readpoints="t0, TC end",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="3 units per lot, bump map sampled at corners and centre",
            pass_criteria="Force above the plan limit; no UBM/ULK lift-off mode",
            covers="First-level interconnect integrity and die-side ULK stack robustness",
            applicability="conditional",
            note="TODO: agree the method and limits with the OSAT before the build - this is "
                 "the row most likely to be missing a citable standard.",
            verify="Method and limits agreed in writing with the OSAT and the customer")
    if pk["underfill"] or pk["flipchip"]:
        add(id="corner_csam", test="Die-corner C-SAM audit (underfill / ULK)",
            group="Bond and attach integrity", standard="Plan-defined (see Workflow 5)",
            condition="High-frequency pulse-echo gated at the underfill/die interface, "
                      "focused on die corners",
            duration="t0 and every TC readpoint",
            readpoints="t0, each TC readpoint",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="Serialize 10 units per lot and scan the SAME units every time",
            pass_criteria="No new corner delamination vs the same unit's time-zero scan",
            covers="Die-corner ULK delamination, the leading FCBGA/FCCSP wear-out precursor",
            note="Serialization is the whole point: 'delamination grew' is only claimable "
                 "against the same unit's t0 scan.",
            verify="Internal work instruction; scan settings (MHz, gate, gain) recorded")

    # ---------------- Mechanical robustness -------------------------------------------
    if dc["auto_mech_suite"]:
        add(id="mech_shock", test="Mechanical shock", group="Mechanical robustness",
            standard="JESD22-B104",
            condition="Condition per the AEC table (commonly 1500 G / 0.5 ms, 5 pulses in "
                      "each of 6 orientations)",
            duration="Single sequence",
            readpoints="Electrical + external visual after the full sequence; C-SAM audit "
                       "on 5 units per lot",
            **_leg(mech_n, lots),
            pass_criteria=ELECTRICAL_PASS + "; no external damage; no new C-SAM delamination",
            covers="Handling and in-vehicle shock: die cracks, wire damage, lead damage",
            note="Usually run as a sequence with vibration on the same units - state the "
                 "sequence, since the order changes what the data means.",
            verify="JESD22-B104 current rev; " + dc["verify"])
        add(id="vibration", test="Variable-frequency vibration",
            group="Mechanical robustness", standard="JESD22-B103",
            condition="Condition per the AEC table (commonly 20 G, 20 Hz - 2 kHz sweeps, "
                      "4 sweeps in each of 3 orientations)",
            duration="Single sequence",
            readpoints="Electrical + external visual after the full sequence",
            **_leg(mech_n, lots),
            pass_criteria=ELECTRICAL_PASS + "; no external damage",
            covers="Resonance-driven wire, lead and die-attach fatigue",
            note="Same units as mechanical shock in the standard automotive sequence.",
            verify="JESD22-B103 current rev; " + dc["verify"])
        add(id="const_accel", test="Constant acceleration", group="Mechanical robustness",
            standard="MIL-STD-883 Method 2001",
            condition="Y1 orientation, level per the AEC table",
            duration="Single exposure",
            readpoints="Electrical after exposure; X-ray/C-SAM audit on any suspect unit",
            **_leg(mech_n, lots),
            pass_criteria=ELECTRICAL_PASS + "; no die-attach or wire separation",
            covers="Gross die-attach and wire-bond attachment weakness",
            applicability="conditional",
            note="TODO: historically a cavity/hermetic-package test. Confirm whether the "
                 "current AEC-Q100 revision requires it for this overmolded plastic family "
                 "before budgeting units for it.",
            verify="AEC-Q100 current rev - applicability to overmolded plastic packages")
        add(id="solvent", test="Resistance to solvents (mark permanency)",
            group="Mechanical robustness", standard="JESD22-B107",
            condition="Solvent set per the standard; laser mark and ink mark handled "
                      "separately",
            duration="Single exposure",
            readpoints="Visual after each solvent exposure",
            n_per_lot=None, lots=1, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="15 units total (typical)",
            pass_criteria="Marking remains legible and complete after exposure",
            covers="Traceability survival through board assembly cleaning",
            verify="JESD22-B107 current rev")
    if pk["formed_leads"]:
        add(id="lead_integrity", test="Lead integrity", group="Mechanical robustness",
            standard="JESD22-B105",
            condition="Lead bend / lead pull per the standard, condition per lead type",
            duration="Single sequence",
            readpoints="Visual + dimensional after the sequence",
            n_per_lot=None, lots=1, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="15 units, all leads tested (typical)",
            pass_criteria="No lead fracture or lead-to-body separation at the specified "
                          "condition",
            covers="Formed-lead handling robustness and lead-to-body seal",
            verify="JESD22-B105 current rev")

    # ---------------- Package integrity and inspection --------------------------------
    add(id="solderability", test="Solderability", group="Package integrity and inspection",
        standard="J-STD-002 (JESD22-B102 is the legacy reference)",
        condition="Steam age (or the agreed accelerated age) then dip-and-look / SMT "
                  "simulation per the terminal type",
        duration="Single sequence",
        readpoints="After aging; re-run after any cumulative bake beyond the plan limit",
        n_per_lot=None, lots=1, total_units=None, accept=0, ltpd_pct_at_90=None,
        sample_note="15 units total, all terminals evaluated (typical)",
        pass_criteria=">=95 % wetted area per terminal with no dewetting or non-wetting",
        covers="Finish wetting after storage; the first thing to re-run after a long bake",
        note=("QFN/DFN: include the cut-copper lead FLANK in the evaluation - it is the "
              "usual failure surface and the reason wettable-flank options exist."
              if cfg["package"] in ("qfn", "dfn") else
              "Re-verify after any cumulative bake over ~96 h at 125 C."),
        verify="J-STD-002 current rev; agreed accelerated-aging condition")
    add(id="phys_dim", test="Physical dimensions", group="Package integrity and inspection",
        standard="JESD22-B100", condition="Measure against the registered outline (MO-xxx) "
                                          "or the customer drawing",
        duration="Single measurement",
        readpoints="Time-zero on each assembly lot",
        n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
        sample_note="10 units per lot",
        pass_criteria="All dimensions within the drawing tolerance",
        covers="Outline conformance; the cheapest test that stops a board-fit surprise",
        verify="JESD22-B100 current rev; the registered outline number for this body")
    add(id="visual", test="External visual", group="Package integrity and inspection",
        standard="MIL-STD-883 Method 2009-style external visual",
        condition="Post-stress inspection at the specified magnification",
        duration="At every readpoint",
        readpoints="t0 and every stress readpoint",
        n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
        sample_note="All stressed units",
        pass_criteria="No cracks, no exposed die/wire, marking legible, no lead damage",
        covers="Popcorn cracks and handling damage that electricals can miss",
        verify="Customer workmanship spec; MIL-STD-883 M2009 current rev")
    if pk["area_array"]:
        add(id="warpage", test="Package warpage vs temperature (shadow moire)",
            group="Package integrity and inspection", standard="JESD22-B112",
            condition="Room temperature to reflow peak and back, reported at the profile's "
                      "key temperatures",
            duration="Single characterisation",
            readpoints="Room temp, 150 C, 217 C (solder melt), peak, and on cool-down",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="5 units per lot",
            pass_criteria="Coplanarity and dynamic warpage within the class limit for the "
                          "ball pitch (agree the limit with the board assembler)",
            covers="Head-in-pillow / non-wet opens at board mount - a yield problem that "
                   "looks like a reliability problem",
            applicability="required" if cfg["package"] in ("pbga", "fcbga", "fowlp",
                                                           "interposer_2p5d")
                          else "conditional",
            note="Dynamic (at-temperature) warpage is the number that matters; room-"
                 "temperature coplanarity alone does not predict HIP." + (
                     "" if cfg["package"] in ("pbga", "fcbga", "fowlp", "interposer_2p5d")
                     else " TODO: small CSP/WLCSP bodies rarely warp enough to cause HIP - "
                          "decide with the board assembler whether to keep this row (keep it "
                          "if they have seen non-wets on comparable bodies, or if the body "
                          "exceeds ~8 mm) and record the decision."),
            verify="JESD22-B112 current rev; HIP risk limits agreed with the assembler")
    if pk["bare_die"]:
        add(id="die_strength", test="Die strength monitor (3-point bend)",
            group="Package integrity and inspection",
            standard="Plan-defined; no single JEDEC method - TODO agree the method with the "
                     "OSAT (3-point bend or ball-on-ring)",
            condition="Post-backgrind and post-singulation samples, Weibull-fitted",
            duration="Per assembly lot",
            readpoints="Post-backgrind and post-singulation",
            n_per_lot=None, lots=lots, total_units=None, accept=0, ltpd_pct_at_90=None,
            sample_note="30 die per lot per condition (Weibull needs the population)",
            pass_criteria="Weibull characteristic strength and slope within the qualified "
                          "envelope",
            covers="Thin-die handling cracks that surface as infant TC failures",
            applicability="conditional",
            verify="Method and limits agreed with the OSAT")

    # ---------------- Declared out of scope -------------------------------------------
    out_of_scope = [
        {"test": "HTOL (operating life)", "standard": "JESD22-A108",
         "why": "Qualifies the DIE, not the package. Include in a full product qual; state "
                "explicitly that this package-level plan does not cover it."},
        {"test": "Early life failure rate (ELFR)", "standard": "AEC-Q100-008",
         "why": "Die-level infant mortality. Required for an automotive PRODUCT qual; not a "
                "package-integrity test."},
        {"test": "ESD (HBM/CDM) and latch-up",
         "standard": "AEC-Q100-002 / -011 / -004 (JS-001, JS-002)",
         "why": "Die/IO-level robustness. Package pin capacitance can matter for CDM - flag "
                "it if the pinout or body size changed materially."},
    ]

    if cfg["novelty"] == "derivative":
        notes.append("Derivative: the plan is only defensible with a written similarity "
                     "justification - list what is IDENTICAL (materials set, assembly site, "
                     "design rules, die-to-pad ratio, wire/ball metallurgy and pitch) and "
                     "what CHANGED, with the argument for why the change adds no new "
                     "failure mechanism.")
    if dc["automotive"] and cfg["novelty"] != "new_package":
        notes.append("Automotive lot floor applied: {} lots (grade {} programmes expect 3 "
                     "non-consecutive assembly lots even for derivatives). Any reduction "
                     "below this needs documented customer agreement.".format(
                         lots, dc["aec_grade"]))
    if pk["bespoke"]:
        notes.append("2.5D/3D construction: this matrix is a scaffold only. Microbump / "
                     "hybrid-bond, interposer and stacked-die thermal qualification is "
                     "bespoke and must be built with the OSAT and the customer.")
    if cfg["package"] in ("qfn", "dfn") and dc["automotive"]:
        notes.append("Automotive QFN/DFN: add board-level solder-joint void limits (X-ray) "
                     "and consider a wettable-flank terminal so the customer's AOI can see "
                     "the fillet - both are common automotive line-side rejects.")
    if cfg["package"] == "wlcsp":
        notes.append("WLCSP: the board joint IS the package joint. Board-level drop and "
                     "board-level TC are not optional extras here - they are the "
                     "qualification.")

    matrix = _normalise(rows)

    # pandas does the roll-up (and feeds --csv-out); the matrix itself stays plain dicts.
    df = pd.DataFrame(matrix)
    df["group"] = pd.Categorical(df["group"], categories=GROUP_ORDER, ordered=True)
    units = df.assign(total_units=df["total_units"].fillna(0)) \
              .groupby("group", observed=True)["total_units"].sum()
    total_env = sum(r["total_units"] or 0 for r in matrix
                    if r["group"] == "Environmental stress"
                    and r["applicability"] != "alternative")
    summary = {
        "rows": len(matrix),
        "rows_required": sum(1 for r in matrix if r["applicability"] == "required"),
        "rows_conditional": sum(1 for r in matrix if r["applicability"] == "conditional"),
        "rows_alternative": sum(1 for r in matrix if r["applicability"] == "alternative"),
        "lots": lots,
        "env_leg_n_per_lot": env_n,
        "env_leg_units_total": int(total_env),
        "env_leg_ltpd_pct_at_90": round(_ltpd(env_n, 0, 0.90) * 100, 2),
        "units_by_group": {str(k): int(v) for k, v in units.items()},
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "inputs": cfg,
        "device_class": {"key": cfg["device_class"], "label": dc["label"],
                         "ambient_max_c": dc["ambient_max_c"], "aec_grade": dc["aec_grade"]},
        "package": {"key": cfg["package"], "label": pk["label"],
                    "interconnect": pk["interconnect"], "area_array": pk["area_array"],
                    "typical_msl": pk["typical_msl"]},
        "novelty": {"key": cfg["novelty"], "label": nov["label"], "lots": lots,
                    "rule": nov["note"]},
        "msl": {"level": msl, "soak": soak, "floor_life": floor_life},
        "summary": summary,
        "matrix": matrix,
        "package_risks": pk["risks"],
        "plan_notes": notes,
        "out_of_scope": out_of_scope,
        "verify_block": [
            "JEDEC standards are free downloads (jedec.org, registration). Confirm the "
            "CURRENT revision of every standard cited above before committing hardware.",
            "AEC-Q100 (aecouncil.com): confirm the grade column - conditions, cycle counts "
            "and required tests move between revisions." if dc["automotive"] else
            "JESD47: confirm the default stress set and durations against the current rev.",
            "Every condition, duration and sample size emitted here is an industry-typical "
            "TEMPLATE. Nothing in this file has been verified against a copy of the "
            "standard by the generator.",
            "Rows marked applicability=conditional carry a TODO - resolve each one with the "
            "OSAT and the customer before the plan is baselined.",
        ],
    }


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def _md_escape(s: str | None) -> str:
    return "" if s is None else str(s).replace("|", "\\|").replace("\n", " ")


def _sample_cell(r: dict) -> str:
    if r.get("n_per_lot"):
        return "{} / lot x {} lots = {} (accept {}; LTPD {} % @90 %)".format(
            r["n_per_lot"], r["lots"], r["total_units"], r["accept"], r["ltpd_pct_at_90"])
    return "{} (x {} lot{})".format(r.get("sample_note", "per plan"), r["lots"],
                                    "s" if r["lots"] > 1 else "")


def render_markdown(plan: dict) -> str:
    inp, dc, pk, nov, msl = (plan["inputs"], plan["device_class"], plan["package"],
                             plan["novelty"], plan["msl"])
    L: list[str] = []
    L.append("# Package qualification plan - {} / {}".format(pk["label"], dc["label"]))
    L.append("")
    L.append("Generated {} by `qual_plan.py` v{}. **Template conditions - see the verify "
             "block before committing hardware.**".format(plan["generated"], SCHEMA_VERSION))
    L.append("")

    L.append("## 1. Scope")
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append("| Device class | {} |".format(dc["label"]))
    L.append("| Max ambient (class) | {} C |".format(dc["ambient_max_c"]))
    L.append("| Package family | {} |".format(pk["label"]))
    L.append("| First-level interconnect | {} |".format(inp["interconnect"]))
    L.append("| Novelty | {} |".format(nov["label"]))
    L.append("| Assembly lots | {} |".format(nov["lots"]))
    L.append("| MSL target | {} (soak {}) |".format(msl["level"], msl["soak"]))
    L.append("| Floor life at target MSL | {} |".format(msl["floor_life"]))
    L.append("| Handheld end product | {} |".format("yes" if inp["handheld"] else "no"))
    L.append("| Board-level content | {} |".format(
        "suppressed (justification required)" if inp["suppress_board_level"]
        else "included" if any(r["group"] == "Board-level reliability" for r in plan["matrix"])
        else "not applicable to this family"))
    if inp.get("change"):
        L.append("| Declared change | {} |".format(_md_escape(inp["change"])))
    if inp.get("device"):
        L.append("| Device | {} |".format(_md_escape(inp["device"])))
    L.append("")
    L.append("**Lot rule:** {}".format(nov["rule"]))
    L.append("")

    L.append("## 2. Test matrix")
    L.append("")
    L.append("| # | Test | Standard | Condition | Duration | Readpoints | Sample size | "
             "Accept | Pass criteria |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(plan["matrix"], 1):
        flag = {"required": "", "conditional": " *(conditional - see note)*",
                "alternative": " *(alternative - run this OR the HAST row)*"}[r["applicability"]]
        L.append("| {} | **{}**{} | {} | {} | {} | {} | {} | {} | {} |".format(
            i, _md_escape(r["test"]), flag, _md_escape(r["standard"]),
            _md_escape(r["condition"]), _md_escape(r["duration"]),
            _md_escape(r["readpoints"]), _md_escape(_sample_cell(r)),
            r["accept"], _md_escape(r["pass_criteria"])))
    L.append("")

    L.append("### Matrix by stress group")
    L.append("")
    L.append("| Group | Tests | Units budgeted |")
    L.append("|---|---|---|")
    groups: dict[str, list] = {}
    for r in plan["matrix"]:
        groups.setdefault(r["group"], []).append(r)
    for g in GROUP_ORDER:
        if g in groups:
            units = sum(r["total_units"] or 0 for r in groups[g])
            L.append("| {} | {} | {} |".format(g, len(groups[g]),
                                               units if units else "see sample notes"))
    L.append("")
    s = plan["summary"]
    L.append("Environmental legs total **{} units**, excluding the THB row (THB *replaces* "
             "biased HAST, it does not add to it). {} per lot x {} lots per leg, accept 0, "
             "demonstrating {} % LTPD at 90 % confidence per leg - recompute with "
             "`sample_size.py` if the leg size changes.".format(
                 s["env_leg_units_total"], s["env_leg_n_per_lot"], nov["lots"],
                 s["env_leg_ltpd_pct_at_90"]))
    L.append("")
    L.append("Rows counted: {} required, {} conditional (TODO to resolve), {} alternative."
             .format(s["rows_required"], s["rows_conditional"], s["rows_alternative"]))
    L.append("")

    L.append("## 3. Row notes")
    L.append("")
    for r in plan["matrix"]:
        if r.get("note") or r.get("covers"):
            L.append("- **{}** - covers: {}{}".format(
                r["test"], r.get("covers", "-"),
                " _Note:_ " + r["note"] if r.get("note") else ""))
    L.append("")

    L.append("## 4. Package risks this matrix must cover")
    L.append("")
    for risk in plan["package_risks"]:
        L.append("- {}".format(risk))
    L.append("")
    L.append("Cross-check each risk against the matrix. A risk with no covering row is an "
             "open risk - add a test, never delete the risk.")
    L.append("")

    if plan["plan_notes"]:
        L.append("## 5. Plan notes")
        L.append("")
        for n in plan["plan_notes"]:
            L.append("- {}".format(n))
        L.append("")

    L.append("## 6. Global pass criteria")
    L.append("")
    L.append("- {}".format(ELECTRICAL_PASS))
    L.append("- {}".format(CSAM_PASS))
    L.append("- Accept number 0 on every environmental leg: one failure in the leg is a "
             "failure of the leg. Fail-analyse, fix, re-run - a single fail is never argued "
             "away against the sample size.")
    L.append("- A readpoint failure stops that leg's clock. Triage before restarting.")
    L.append("- Post-stress C-SAM is compared against the SAME unit's time-zero scan; "
             "serialize the units before precon.")
    L.append("")

    L.append("## 7. Declared out of scope (say this explicitly, do not silently omit)")
    L.append("")
    L.append("| Test | Standard | Why it is not in this matrix |")
    L.append("|---|---|---|")
    for o in plan["out_of_scope"]:
        L.append("| {} | {} | {} |".format(o["test"], o["standard"], o["why"]))
    L.append("")

    L.append("## 8. Verify block (mandatory - do not present this plan without it)")
    L.append("")
    for v in plan["verify_block"]:
        L.append("- {}".format(v))
    L.append("")
    L.append("Per-row standards to confirm:")
    L.append("")
    for r in plan["matrix"]:
        L.append("- `{}` -> {}".format(r["id"], _md_escape(r.get("verify", "-"))))
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def resolve_package(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    key = PACKAGE_ALIASES.get(key, key)
    if key not in PACKAGES:
        raise SystemExit("unknown package '{}'. Known: {} (aliases: {})".format(
            name, ", ".join(sorted(PACKAGES)), ", ".join(sorted(PACKAGE_ALIASES))))
    return key


def build_config(args: argparse.Namespace, scenario: dict | None) -> dict:
    src = dict(scenario or {})
    def pick(key, cli_val, default=None):
        return cli_val if cli_val is not None else src.get(key, default)

    device_class = pick("device_class", args.device_class)
    package = pick("package", args.package)
    novelty = pick("novelty", args.novelty)
    msl = pick("msl", args.msl)
    missing = [k for k, v in [("device-class", device_class), ("package", package),
                              ("novelty", novelty), ("msl", msl)] if v is None]
    if missing:
        raise SystemExit("missing required input(s): {} (pass on the command line or in "
                         "--scenario)".format(", ".join(missing)))
    if device_class not in DEVICE_CLASSES:
        raise SystemExit("unknown device class '{}'. Known: {}".format(
            device_class, ", ".join(DEVICE_CLASSES)))
    msl = str(msl).lower()
    if msl not in MSL_SOAK:
        raise SystemExit("unknown MSL '{}'. Known: {}".format(msl, ", ".join(MSL_SOAK)))
    if novelty not in NOVELTY:
        raise SystemExit("unknown novelty '{}'. Known: {}".format(novelty, ", ".join(NOVELTY)))
    package = resolve_package(package)

    interconnect = pick("interconnect", args.interconnect, "auto")
    if interconnect == "auto":
        interconnect = PACKAGES[package]["interconnect"]
    return {
        "device_class": device_class,
        "package": package,
        "novelty": novelty,
        "msl": msl,
        "interconnect": interconnect,
        "handheld": bool(pick("handheld", True if args.handheld else None, False)),
        "board_level": bool(pick("board_level", True if args.board_level else None, False)),
        "suppress_board_level": bool(pick("suppress_board_level",
                                          True if args.suppress_board_level else None, False)),
        "power_cycling": bool(pick("power_cycling",
                                   True if args.power_cycling else None, False)),
        "change": pick("change", args.change),
        "device": pick("device", args.device),
        "scenario_name": src.get("scenario_name"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-class", choices=sorted(DEVICE_CLASSES),
                    help="mission profile / market")
    ap.add_argument("--package", help="package family (see --list-packages)")
    ap.add_argument("--novelty", choices=sorted(NOVELTY),
                    help="what is being qualified relative to existing data")
    ap.add_argument("--msl", help="MSL target: " + ", ".join(MSL_SOAK))
    ap.add_argument("--board-level", action="store_true",
                    help="force board-level drop + board-level TC into the matrix")
    ap.add_argument("--suppress-board-level", action="store_true",
                    help="drop auto-included board-level rows (requires written "
                         "justification in the plan)")
    ap.add_argument("--handheld", action="store_true",
                    help="handheld/wearable end product -> board-level drop is mandatory")
    ap.add_argument("--power-cycling", action="store_true",
                    help="force power temperature cycling (power devices)")
    ap.add_argument("--interconnect",
                    choices=["auto", "wirebond", "flipchip", "wlcsp_bump", "rdl"],
                    default=None, help="override the family's default interconnect label")
    ap.add_argument("--change", help="free text: what changed (process_change novelty)")
    ap.add_argument("--device", help="free text: device description for the plan header")
    ap.add_argument("--scenario", help="JSON file with any of the above keys "
                                       "(underscored names); CLI flags win")
    ap.add_argument("--format", choices=["markdown", "json", "both"], default="markdown")
    ap.add_argument("--out", help="write markdown here instead of stdout")
    ap.add_argument("--json-out", help="write JSON here")
    ap.add_argument("--csv-out", help="write the matrix as CSV here")
    ap.add_argument("--list-packages", action="store_true",
                    help="print the package families and exit")
    args = ap.parse_args(argv)

    if args.list_packages:
        rows = [{"key": k, "label": v["label"], "interconnect": v["interconnect"],
                 "area_array": v["area_array"], "typical_msl": v["typical_msl"]}
                for k, v in PACKAGES.items()]
        print(pd.DataFrame(rows).to_string(index=False))
        print("\naliases: " + ", ".join("{} -> {}".format(a, t)
                                        for a, t in sorted(PACKAGE_ALIASES.items())))
        return 0

    scenario = None
    if args.scenario:
        with open(args.scenario) as fh:
            scenario = json.load(fh)
        scenario = scenario.get("inputs", scenario)

    cfg = build_config(args, scenario)
    plan = build_matrix(cfg)

    md = render_markdown(plan)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(md)
    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(plan, fh, indent=2)
    if args.csv_out:
        pd.DataFrame(plan["matrix"]).to_csv(args.csv_out, index=False)

    if args.format in ("markdown", "both") and not args.out:
        print(md)
    if args.format in ("json", "both") and not args.json_out:
        print(json.dumps(plan, indent=2))
    if args.out or args.json_out or args.csv_out:
        written = [p for p in (args.out, args.json_out, args.csv_out) if p]
        print("wrote: " + ", ".join(written), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
