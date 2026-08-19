#!/usr/bin/env python3
"""Generate the five golden FA case inputs used by evals/semi-failure-analysis/.

Each case writes an INTAKE evidence JSON - the information an FA lab would actually hold at
Step 1, before any physical work. The intake files deliberately do NOT contain the answer:
`suspected` carries what the requester believes (which is wrong in cases 1, 3 and 4), and no
`mechanism` block is present. The true mechanism lives only in the golden markdown files under
evals/semi-failure-analysis/golden/.

  case 1  EOS from a hot-plug transient on a supply pin      -> case1_eos_hotplug.json
          plus the completed post-analysis record used to    -> case1_eos_hotplug_resolved.json
          exercise the full 8D generator
  case 2  TDDB gate-oxide failure emerging at burn-in        -> case2_tddb_burnin.json
  case 3  Intermittent wire-bond NSOP surfacing in temp cyc. -> case3_nsop_tempcycle.json
  case 4  ESD (HBM) pin-leakage cluster after a probe-card / -> case4_esd_hbm_cluster.json
          handling change, with wafer-sort data                 case4_die_results.csv
                                                                case4_tests.csv
  case 5  MSL popcorn delamination after board reflow        -> case5_msl_popcorn.json

The case-4 CSVs are synthesized: two lots on a 40x40 circular die grid, background defectivity
in both, plus a spatially RANDOM leakage population present only in the lot processed after the
tooling change. Seeded, so bin_signature.py results are reproducible.

Usage example:
  python gen_sample_case.py --case all --outdir ../../../sample-data/semi-failure-analysis/
  python gen_sample_case.py --case 4 --outdir out/ --seed 11

Exit codes: 0 files written · 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

VERSION = "0.1.0"

# =============================================================================== case 1
CASE1_INTAKE = {
    "case_id": "FA-2026-0117",
    "title": "Single field return, dead short VDD-to-GND, 48 V industrial gateway line card",
    "status": "open",
    "opened": "2026-08-05",
    "requester": {"name": "Quality engineering", "org": "Customer A - industrial gateway",
                  "contact": "via distributor RMA desk"},
    "device": {"part_number": "KL-8842-QFN32", "description": "24 V-tolerant transceiver, "
               "internal LDO, 32-pin QFN", "package": "QFN32 wire-bond plastic",
               "date_code": "2548", "assembly_lot": "AS-24-8871", "wafer_lot": "W24-1129",
               "assembly_site": "OSAT-2", "test_program_rev": "TP-8842 rev D"},
    "samples": [
        {"serial": "SN-0416", "role": "sequence",
         "condition_as_received": "de-soldered from customer board by the customer's CM; "
                                  "package intact, no external discoloration visible at 10x; "
                                  "pin 7 (VDD) solder residue present",
         "disposition": "in FA lab, unpowered, ESD bag, custody log open"}
    ],
    "chain_of_custody": [
        {"date": "2026-08-01", "from": "Customer A field site", "to": "Customer A quality lab",
         "action": "unit removed from installed gateway, bagged", "operator": "cust. tech"},
        {"date": "2026-08-03", "from": "Customer A quality lab", "to": "Distributor RMA",
         "action": "shipped with RMA form; board not included", "operator": "cust. QE"},
        {"date": "2026-08-05", "from": "Distributor RMA", "to": "FA lab",
         "action": "received, photographed as-received before any handling", "operator": "FA-01"},
    ],
    "complaint": "Unit went dead in the field after approximately 400 hours of service. Customer "
                 "reports the gateway is hot-swapped into a live 48 V backplane during "
                 "maintenance. Customer's own bench check found VDD shorted to GND. Customer "
                 "states 'this is ESD from our handling' and has asked us to confirm.",
    "symptoms": {
        "symptom_class": "hard_fail",
        "failure_rate": "1 unit; no other returns from this customer or this date code to date. "
                        "Installed base on this platform approximately 12,000 units.",
        "conditions": "Failure discovered in service. Customer bench check: VDD-GND resistance "
                      "measured at approximately 3 ohms with a DMM. No other pin checked.",
    },
    "life_history": {
        "burn_in": "no",
        "board_reflow": "standard Pb-free reflow at the CM, 2025-11, no rework recorded on this unit",
        "field_hours": "approximately 400",
        "environment": "indoor cabinet, 20-40 C",
        "application_notes": "hot-swap into a live 48 V backplane during maintenance; on-board "
                             "buck converter feeds the 3.3 V rail; customer has not supplied the "
                             "schematic or the power-sequencing detail yet",
    },
    "selector_input": {
        "symptom_class": "hard_fail",
        "package_type": "wirebond-plastic",
        "sample_count": 1,
        "powered_signature": "short",
        "suspected": ["esd"],
        "after_burnin": False,
        "after_reflow": False,
        "customer_return": True,
        "budget": "medium",
        "urgency": "expedite",
    },
    "observations": [
        {"phase": "N0", "technique": "external_visual", "unit": "SN-0416",
         "conditions": "10x and 50x stereo, as received, before any electrical test",
         "result": "No cracking or bulging. Faint darkening of the mold compound over the corner "
                   "nearest pin 7 visible at 50x under oblique light; not visible at 10x.",
         "interpretation": "Observation only. Localized mold discoloration is a lead, not a "
                           "conclusion.", "date": "2026-08-05", "image": "fig1_external.png"},
    ],
    "hypotheses": [],
    "open_questions": [
        "Application power-sequencing and hot-swap inrush behaviour on the 3.3 V rail - requested "
        "from customer, not yet received.",
        "Whether the customer's bench check itself applied power to a damaged part.",
        "Whether any sibling units from date code 2548 are available from the same installation.",
    ],
}

CASE1_RESOLVED = {
    "case_id": "FA-2026-0117",
    "title": "Single field return, dead short VDD-to-GND, 48 V industrial gateway line card",
    "status": "closed",
    "opened": "2026-08-05",
    "closed": "2026-08-19",
    "requester": CASE1_INTAKE["requester"],
    "device": CASE1_INTAKE["device"],
    "samples": [
        {"serial": "SN-0416", "role": "sequence",
         "condition_as_received": CASE1_INTAKE["samples"][0]["condition_as_received"],
         "disposition": "consumed - decapped and cross-sectioned; mount retained in case file"},
        {"serial": "SN-0417 (reference)", "role": "reference",
         "condition_as_received": "known-good unit, same date code, pulled from customer spares",
         "disposition": "returned to customer, non-destructive imaging only"},
    ],
    "chain_of_custody": CASE1_INTAKE["chain_of_custody"] + [
        {"date": "2026-08-08", "from": "FA lab bench", "to": "FA lab X-ray",
         "action": "2D X-ray, unit returned to bag same day", "operator": "FA-02"},
        {"date": "2026-08-12", "from": "FA lab", "to": "FA lab decap bench",
         "action": "GATE D1 cleared and signed; wet chemical decap of SN-0416",
         "operator": "FA-01 / reviewed FA-03"},
        {"date": "2026-08-15", "from": "FA lab", "to": "FA lab FIB",
         "action": "GATE D2 cleared and signed; FIB cross-section at the localized site",
         "operator": "FA-03"},
    ],
    "complaint": CASE1_INTAKE["complaint"],
    "symptoms": CASE1_INTAKE["symptoms"],
    "problem": {
        "what": "One returned KL-8842-QFN32 exhibits a low-resistance short between VDD (pin 7) "
                "and GND; measured 2.8 ohms on the curve tracer at 100 mV, symmetric in both "
                "polarities.",
        "is_not": "Not present on any signal pin: all 28 I/O pins curve-trace within the "
                  "known-good envelope. Not a package crack (X-ray and C-SAM clean). Not present "
                  "in any other returned unit - zero further returns from date code 2548.",
        "where": "Customer A industrial gateway platform, field-installed units subject to "
                 "hot-swap maintenance into a live 48 V backplane.",
        "when": "After approximately 400 service hours; discovered during a maintenance visit.",
        "how_many": "1 of approximately 12,000 units in the installed base on this platform "
                    "(0.008%); 1 of 1 units received for analysis.",
        "since": "First and only report; RMA received 2026-08-05.",
    },
    "d0_emergency_response": "No line stop. Date code 2548 was placed on ship-hold for 48 hours "
                             "while the returns database was queried for related signatures; hold "
                             "released once no second occurrence was found.",
    "team": [
        {"name": "FA-01", "role": "FA lab lead, case owner"},
        {"name": "FA-03", "role": "Physical analysis (decap, FIB, SEM)"},
        {"name": "QE-02", "role": "Customer quality interface"},
        {"name": "DE-05", "role": "Product design - ESD/EOS protection network owner"},
        {"name": "AE-01", "role": "Applications engineering - customer board and sequencing"},
    ],
    "selector_input": CASE1_INTAKE["selector_input"],
    "observations": [
        {"phase": "N0", "technique": "external_visual", "unit": "SN-0416",
         "conditions": "10x and 50x stereo, as received, before any electrical test",
         "result": "Faint mold discoloration over the die corner nearest pin 7 at 50x oblique; "
                   "no cracking, no bulging, no rework marks.",
         "interpretation": "Consistent with localized internal heating. Not diagnostic alone.",
         "date": "2026-08-05", "image": "fig1_external.png"},
        {"phase": "N0", "technique": "curve_trace", "unit": "SN-0416 vs SN-0417",
         "conditions": "Pin-by-pin I-V, +/-1 V sweep, compliance limited to 1 mA to avoid "
                       "altering the damage",
         "result": "VDD (pin 7) to GND: 2.8 ohms, linear and symmetric in both polarities. All "
                   "28 I/O pins and their protection diodes match the reference unit envelope. "
                   "No leakage on any signal pin.",
         "interpretation": "Observed: a resistive, non-rectifying short on the supply path only. "
                           "A metallic (fused/melted) path, not a degraded junction.",
         "date": "2026-08-06", "image": "fig2_curvetrace.png"},
        {"phase": "N0", "technique": "datalog_review", "unit": "SN-0416",
         "conditions": "Final-test datalog retrieved by serial from the 2548 date code archive",
         "result": "Unit passed all final-test parameters at manufacture with normal margin, "
                   "including IDDQ and all I/O leakage tests.",
         "interpretation": "Retires the escape-at-final-test hypothesis for a pre-existing "
                           "defect of this magnitude.", "date": "2026-08-06"},
        {"phase": "N1", "technique": "xray_2d", "unit": "SN-0416",
         "conditions": "2D transmission, 0 and 45 degree projections",
         "result": "All 32 bond wires intact and correctly placed; no wire sweep, no shorting, "
                   "no foreign metal, die-attach void area visually below the 10% device limit.",
         "interpretation": "Retires wire-short and gross-assembly hypotheses. Null result, "
                           "reported.", "date": "2026-08-08", "image": "fig3_xray.png"},
        {"phase": "N1", "technique": "csam", "unit": "SN-0416",
         "conditions": "Immersion C-SAM, die face and die-attach interfaces; performed before any "
                       "decap or bake",
         "result": "No delamination detected at the die face, die attach, or leadframe "
                   "interfaces. No popcorn crack.",
         "interpretation": "Null result. Retires the moisture/popcorn chain; run before decap "
                           "because decap would have destroyed the evidence either way.",
         "date": "2026-08-08"},
        {"phase": "N2", "technique": "lock_in_thermography", "unit": "SN-0416",
         "conditions": "50 mA forced through the VDD-GND short, 3 Hz modulation, through-mold",
         "result": "A single hot spot located over the die corner adjacent to the pin-7 bond, "
                   "coincident with the external mold discoloration.",
         "interpretation": "Failure site localized to a sub-millimetre region without opening the "
                           "package. This localization is what cleared GATE D2 later.",
         "date": "2026-08-11", "image": "fig4_lit.png"},
        {"phase": "D1", "technique": "decap_chemical", "unit": "SN-0416",
         "conditions": "GATE D1 cleared 2026-08-12: all N0-N2 complete, C-SAM and X-ray done, "
                       "single-sample protocol acknowledged, expected outcomes pre-registered, "
                       "customer approval on file. Wet acid decap, window over the pin-7 corner.",
         "result": "Die exposed with bonds intact.",
         "interpretation": "Enabling step; no diagnostic content of its own.",
         "date": "2026-08-12"},
        {"phase": "D1", "technique": "internal_optical", "unit": "SN-0416",
         "conditions": "100x-500x, before any re-biasing of the die",
         "result": "A molten region approximately 60 x 40 micrometres spanning the VDD bus metal "
                   "and the adjacent supply clamp, with visibly displaced and re-solidified "
                   "metal and cracked dielectric at the perimeter. The pad-side I/O protection "
                   "structures are undamaged and identical to the reference die.",
         "interpretation": "Observed: a large-area melt on the supply path. The scale and metal "
                           "displacement are far beyond what a human-body-model event can supply, "
                           "and the I/O ESD network is intact.",
         "date": "2026-08-13", "image": "fig5_internal.png"},
        {"phase": "D2", "technique": "fib_cross_section", "unit": "SN-0416",
         "conditions": "GATE D2 cleared 2026-08-15: site localized by thermography and optical, "
                       "all prior imagery archived, expected outcomes pre-registered. FIB cut "
                       "through the centre of the melt.",
         "result": "Metal fully fused through the full metal-1 thickness over approximately 12 "
                   "micrometres, with re-solidified metal bridging into the substrate through a "
                   "cracked ILD.",
         "interpretation": "Observed: a metal-to-substrate fused path - the physical short "
                           "measured on the curve tracer.", "date": "2026-08-15",
         "image": "fig6_fib.png"},
        {"phase": "D2", "technique": "sem_edx", "unit": "SN-0416",
         "conditions": "SEM at the cut face; EDX at the melt and at a clean reference site 200 um "
                       "away",
         "result": "Al and Si intermixed within the melt; no Cl, Br, or S above the reference "
                   "site; no foreign material.",
         "interpretation": "Retires corrosion and contamination hypotheses. Consistent with a "
                           "purely thermal/electrical event.", "date": "2026-08-16"},
    ],
    "hypotheses": [
        {"hypothesis": "ESD (HBM) during customer handling - the customer's stated cause",
         "status": "retired",
         "evidence_for": "Customer handles boards during maintenance; no ESD control audit exists "
                         "for the field procedure.",
         "evidence_against": "Damage is on the supply path, not on a pin protection device; all "
                             "28 I/O protection structures are undamaged; the melt volume "
                             "(~60x40 um with displaced metal) exceeds the energy a human-body "
                             "event can deliver through ~1.5 kohm.",
         "discriminating_test": "curve_trace pin map plus internal_optical damage-area measurement",
         "cost": "low / ND then D"},
        {"hypothesis": "ESD (CDM) during board assembly", "status": "retired",
         "evidence_for": "CDM damage can appear on internal nodes rather than at pads.",
         "evidence_against": "CDM damage is sub-micron with minimal surrounding melt; the observed "
                             "site is three orders of magnitude larger in area and shows metal "
                             "displacement. Unit also passed 400 service hours after assembly.",
         "discriminating_test": "internal_optical damage morphology and scale", "cost": "low"},
        {"hypothesis": "EOS - sustained supply-sourced overstress on VDD during live hot-swap",
         "status": "confirmed",
         "evidence_for": "Melt confined to the VDD bus and supply clamp; metal fused over ~12 um; "
                         "mold discoloration above the site; energy required is only available "
                         "from a supply, not from a stored-charge model; application is "
                         "hot-swapped into a live 48 V backplane.",
         "evidence_against": "The customer has not supplied the schematic or inrush measurements, "
                             "so the specific transient path is inferred, not measured.",
         "discriminating_test": "Application inrush measurement on the customer's board during "
                                "hot-swap - requested, outstanding.",
         "cost": "low / customer action"},
        {"hypothesis": "Latch-up triggered by the hot-swap transient, sustained by the 3.3 V rail",
         "status": "active",
         "evidence_for": "Latch-up produces supply-sourced melt indistinguishable from EOS by "
                         "morphology, and a hot-swap transient is a plausible trigger.",
         "evidence_against": "The melt path runs through supply bus metal rather than through a "
                             "well-substrate diffusion path; no evidence of the parasitic "
                             "structure conducting was found in cross-section.",
         "discriminating_test": "Board-level transient capture plus a latch-up characterization "
                                "on fresh units per JESD78-style method - recommended, not yet run.",
         "cost": "medium / requires fresh units"},
        {"hypothesis": "Test-induced damage in this lab", "status": "retired",
         "evidence_for": "Standing hypothesis on every case.",
         "evidence_against": "The short was measured by the customer before receipt, and our first "
                             "curve trace ran at 1 mA compliance. Damage predates our handling.",
         "discriminating_test": "As-received custody log and the customer's own bench measurement",
         "cost": "none"},
    ],
    "mechanism": {
        "primary": "Electrically induced physical damage (EIPD) on the VDD supply path, most "
                   "consistent with a sustained electrical overstress (EOS) event rather than a "
                   "component-level ESD event.",
        "confidence": "medium",
        "basis": "Observed: 2.8 ohm symmetric VDD-GND short (curve trace); a ~60x40 um melt with "
                 "displaced metal spanning the VDD bus and supply clamp (internal optical); metal "
                 "fused through full metal-1 thickness with a re-solidified path into the "
                 "substrate through cracked ILD (FIB cross-section); no elemental contamination "
                 "(EDX). All 28 I/O protection structures undamaged, which is inconsistent with a "
                 "pin-level ESD event. The damaged volume requires more energy than component-level "
                 "ESD models can supply, and is consistent with a supply-sourced transient. "
                 "Confidence is medium rather than high because the application transient has not "
                 "been measured and latch-up has not been positively excluded.",
        "secondary": "Latch-up triggered by the same transient cannot be excluded on morphology "
                     "alone; the cross-section did not show a well-substrate conduction path, "
                     "which argues against it but does not eliminate it.",
        "not_determined": "The specific circuit path and magnitude of the hot-swap transient. "
                          "The customer has not supplied the board schematic or inrush "
                          "measurements, so the source of the overstress is inferred from the "
                          "damage and the stated application, not measured.",
    },
    "escape_point": "Two legs. (a) Manufacturing test cannot detect this failure because the "
                    "part was good at manufacture - the final-test datalog for SN-0416 shows "
                    "normal margin on every parameter including IDDQ and I/O leakage, so there is "
                    "no test escape. (b) The real escape is at the application-review stage: the "
                    "datasheet absolute-maximum and the recommended hot-swap sequencing were never "
                    "reviewed against this customer's live-backplane maintenance procedure, and no "
                    "inrush limiting is specified in our reference design for hot-swap use.",
    "containment": [
        {"action": "48-hour ship-hold on date code 2548 pending a returns-database query for "
                   "matching signatures (VDD-GND short).",
         "owner": "QE-02", "due": "2026-08-06", "status": "complete - released, no second case",
         "verification": "Returns database query across 18 months: zero further VDD-GND shorts on "
                         "this part number."},
        {"action": "Advisory to the customer: do not hot-swap this line card into a live "
                   "backplane until inrush behaviour on the 3.3 V rail has been characterized.",
         "owner": "AE-01", "due": "2026-08-07", "status": "complete",
         "verification": "Advisory acknowledged in writing by Customer A quality on 2026-08-07."},
        {"action": "Retain and quarantine any further returns from this platform unpowered, "
                   "without customer bench testing, to preserve the damage signature.",
         "owner": "QE-02", "due": "2026-08-07", "status": "in place",
         "verification": "RMA desk instruction updated; distributor confirmed."},
    ],
    "corrective_actions": [
        {"action": "Applications engineering to characterize hot-swap inrush on the customer's "
                   "board and publish a hot-swap application note with required inrush limiting "
                   "and rail sequencing for this device family.",
         "owner": "AE-01", "due": "2026-09-15",
         "verification": "Measured inrush waveform on the customer board, before and after the "
                         "recommended limiting, attached to the application note."},
        {"action": "Design review of the supply-clamp energy rating against the transient "
                   "environment implied by live-backplane hot-swap; decide whether the clamp is "
                   "adequately specified or the datasheet must state the limit explicitly.",
         "owner": "DE-05", "due": "2026-10-01",
         "verification": "Design review record with the clamp energy calculation and the "
                         "resulting datasheet or design change decision."},
        {"action": "Run a latch-up characterization on fresh units per a JESD78-style method to "
                   "positively include or exclude the latch-up leg of the mechanism.",
         "owner": "DE-05", "due": "2026-09-30",
         "verification": "Characterization report; result folded back into this case's mechanism "
                         "call before the case is treated as fully closed."},
    ],
    "validation": [
        "Returns-database query across 18 months and approximately 12,000 installed units found "
        "zero further VDD-GND short signatures - the failure is a single event, not a population "
        "trend. (Evidence: query export dated 2026-08-06 in the case file.)",
        "Customer acknowledged the hot-swap advisory in writing on 2026-08-07; no further returns "
        "from this platform as of case closure.",
        "PENDING: effectiveness of the corrective actions cannot be validated until the "
        "application note and the latch-up characterization are complete. This report records the "
        "actions as open, not as verified.",
    ],
    "prevention": [
        "Read-across: identify every other product family sold into hot-swap or live-insertion "
        "applications and check whether the datasheet states a hot-swap limitation. Owner DE-05.",
        "Process change: add 'live insertion / hot-swap present?' as a mandatory field in the "
        "application-review checklist for new design-ins. Owner AE-01.",
        "FA process: add the standing instruction that returned units are quarantined unpowered "
        "and are not bench-tested by the customer or the distributor before receipt, so that "
        "damage evidence is not altered en route. Owner QE-02.",
    ],
    "recommendations": [
        "Obtain the customer's board schematic and an inrush capture during hot-swap; without it "
        "the transient source remains inferred.",
        "Complete the latch-up characterization before treating the mechanism call as final.",
        "If a second unit with the same signature is ever received, run magnetic current imaging "
        "before opening it - a second sample is worth more intact than decapped.",
    ],
    "limitations": [
        "Single sample. Every conclusion is a 'consistent with' at the unit level and none of it "
        "supports a population claim.",
        "The customer measured the short with a DMM before shipping the unit; that measurement "
        "applied power to an already-damaged part and could in principle have extended the damage. "
        "The morphology does not suggest it did, but it cannot be excluded.",
        "The application transient was not measured. The source of the overstress is inferred from "
        "the damage character and the stated hot-swap usage.",
        "Latch-up was not positively excluded; the cross-section evidence argues against it but is "
        "not conclusive.",
        "No sibling units from date code 2548 were available for comparison.",
    ],
    "images": [
        {"file": "fig1_external.png", "unit": "SN-0416", "technique": "external_visual",
         "scale": "50x, 500 um bar", "caption": "Mold discoloration over the pin-7 die corner, "
                                                "oblique illumination, as received."},
        {"file": "fig2_curvetrace.png", "unit": "SN-0416 vs SN-0417", "technique": "curve_trace",
         "scale": "+/-1 V, 1 mA compliance",
         "caption": "VDD-GND I-V, failing unit (2.8 ohm, linear) overlaid on the reference unit."},
        {"file": "fig3_xray.png", "unit": "SN-0416", "technique": "xray_2d", "scale": "1 mm bar",
         "caption": "All 32 bond wires intact and correctly placed; no shorting or sweep."},
        {"file": "fig4_lit.png", "unit": "SN-0416", "technique": "lock_in_thermography",
         "scale": "1 mm bar, 50 mA / 3 Hz",
         "caption": "Single hot spot at the pin-7 die corner, coincident with the external "
                    "discoloration."},
        {"file": "fig5_internal.png", "unit": "SN-0416", "technique": "internal_optical",
         "scale": "500x, 20 um bar",
         "caption": "Molten region approx. 60 x 40 um across the VDD bus and supply clamp with "
                    "displaced metal; I/O protection structures intact."},
        {"file": "fig6_fib.png", "unit": "SN-0416", "technique": "fib_cross_section",
         "scale": "5 um bar", "caption": "Metal-1 fused through full thickness with a "
                                         "re-solidified path into the substrate through cracked ILD."},
    ],
}

# =============================================================================== case 2
CASE2 = {
    "case_id": "FA-2026-0121",
    "title": "Burn-in fallout on a 12 nm SoC: IDDQ and I/O leakage failures appearing only after "
             "the 168 h dynamic burn-in readpoint",
    "status": "open",
    "opened": "2026-08-07",
    "requester": {"name": "Reliability engineering", "org": "Internal - qual lot for automotive "
                  "grade 2 release", "contact": "REL-04"},
    "device": {"part_number": "KL-9310-FCBGA", "description": "12 nm automotive SoC, flip-chip",
               "package": "FCBGA 484, lidded", "date_code": "2612", "assembly_lot": "AS-26-0043",
               "wafer_lot": "W26-0210", "assembly_site": "OSAT-1",
               "test_program_rev": "TP-9310 rev B"},
    "samples": [
        {"serial": "SN-2210", "role": "sequence", "condition_as_received": "post burn-in, "
         "de-socketed, no visible damage", "disposition": "in FA lab"},
        {"serial": "SN-2214", "role": "archive", "condition_as_received": "post burn-in fail, "
         "untouched", "disposition": "archived unpowered"},
        {"serial": "SN-2231", "role": "confirmation", "condition_as_received": "post burn-in fail",
         "disposition": "held"},
        {"serial": "SN-2100", "role": "reference", "condition_as_received": "same lot, passed "
         "burn-in, full margin", "disposition": "held as known-good"},
    ],
    "complaint": "Qualification lot for automotive grade 2. 3 of 231 units failed at the 168 h "
                 "dynamic burn-in readpoint. All 231 units passed final test with normal margin "
                 "before burn-in. Failures are IDDQ elevation plus leakage on a core supply "
                 "domain; the units still function at nominal voltage. Reliability engineering "
                 "needs the mechanism before the qual can be released or re-run.",
    "symptoms": {
        "symptom_class": "parametric",
        "failure_rate": "3 of 231 (1.3%) at the 168 h readpoint. 0 of 231 at the 48 h readpoint. "
                        "0 fails at pre-burn-in final test.",
        "conditions": "Dynamic burn-in, elevated voltage and 125 C ambient per the internal "
                      "burn-in spec. Post-burn-in test at room temperature, nominal voltage: "
                      "IDDQ 40-90x the pre-burn-in value on the same serials; core-domain leakage "
                      "elevated; functional patterns still pass at nominal.",
    },
    "life_history": {
        "burn_in": "yes - 168 h dynamic burn-in, readpoints at 48 h and 168 h",
        "board_reflow": "n/a - units tested in sockets",
        "field_hours": "0",
        "environment": "lab",
        "application_notes": "qualification lot, no field exposure",
    },
    "selector_input": {
        "symptom_class": "parametric",
        "package_type": "flipchip-bga",
        "sample_count": 4,
        "powered_signature": "leakage",
        "suspected": [],
        "after_burnin": True,
        "after_reflow": False,
        "customer_return": False,
        "budget": "high",
        "urgency": "expedite",
    },
    "observations": [
        {"phase": "N0", "technique": "datalog_review", "unit": "SN-2210, SN-2214, SN-2231",
         "conditions": "full datalog, both readpoints, same program rev",
         "result": "All three units passed every parameter pre-burn-in with normal margin. "
                   "Post-168 h, IDDQ on the core domain is 40-90x the pre-burn-in value on the "
                   "same serials; all other parameters unchanged.",
         "interpretation": "Observed: a leakage-only shift that developed during stress, on units "
                           "that were good at t=0.", "date": "2026-08-07"},
    ],
    "hypotheses": [],
    "open_questions": [
        "Do the three failing units share a wafer, a reticle field, or a wafer position? "
        "Wafer-sort traceability requested.",
        "Was the burn-in board or socket implicated - are the three units from the same burn-in "
        "board position?",
        "Is the leakage voltage-accelerated in the way a dielectric mechanism would be, or "
        "temperature-accelerated in the way a junction mechanism would be?",
    ],
}

# =============================================================================== case 3
CASE3 = {
    "case_id": "FA-2026-0128",
    "title": "Intermittent open on a single I/O, appearing only in the cold half of temperature "
             "cycling, on a wire-bond PBGA",
    "status": "open",
    "opened": "2026-08-10",
    "requester": {"name": "Board-level reliability", "org": "Customer B - automotive tier 1",
                  "contact": "via account QE"},
    "device": {"part_number": "KL-7715-PBGA", "description": "CAN transceiver hub, wire-bond PBGA",
               "package": "PBGA 256, wire bond, Cu wire on Al pad", "date_code": "2604",
               "assembly_lot": "AS-26-0119", "wafer_lot": "W25-3380",
               "assembly_site": "OSAT-3", "test_program_rev": "TP-7715 rev C"},
    "samples": [
        {"serial": "U12-A", "role": "sequence", "condition_as_received": "still soldered to the "
         "customer's TC coupon board", "disposition": "in FA lab, board attached"},
        {"serial": "U12-B", "role": "archive", "condition_as_received": "sibling from the same "
         "assembly lot, never cycled", "disposition": "archived"},
        {"serial": "U12-C", "role": "confirmation", "condition_as_received": "second failing unit "
         "from the same TC coupon lot", "disposition": "held"},
        {"serial": "U12-D", "role": "confirmation", "condition_as_received": "second failing unit",
         "disposition": "held"},
        {"serial": "U12-E", "role": "reference", "condition_as_received": "cycled, still passing",
         "disposition": "held as cycled-good reference"},
    ],
    "complaint": "During board-level temperature cycling (-40 to +125 C) on a qualification "
                 "coupon, 3 of 40 assemblies showed intermittent loss of continuity on one I/O "
                 "net. The failure appears somewhere below about -10 C and clears on warm-up. "
                 "The units pass every test at room temperature. The customer's CM has looked at "
                 "the solder joints and believes it is a solder-joint crack; they want us to "
                 "confirm so they can change the reflow profile.",
    "symptoms": {
        "symptom_class": "intermittent",
        "failure_rate": "3 of 40 assemblies on the TC coupon; failures began appearing after "
                        "roughly 400 cycles. Zero failures at incoming electrical test and zero "
                        "at room temperature at any point.",
        "conditions": "Board-level TC -40 to +125 C, 2 cycles/hour. Failure is a continuity open "
                      "on one I/O net, present only in the cold portion of the cycle, and it "
                      "recovers completely on warm-up. Not reproducible at room temperature by "
                      "any means the customer tried.",
    },
    "life_history": {
        "burn_in": "no",
        "board_reflow": "standard Pb-free reflow, MSL 3 handling documented and within floor life",
        "field_hours": "0 - qualification coupon",
        "environment": "TC chamber",
        "application_notes": "board-level qual coupon, daisy-chained continuity monitoring "
                             "available on the customer's fixture",
    },
    "selector_input": {
        "symptom_class": "intermittent",
        "package_type": "wirebond-bga",
        "sample_count": 5,
        "powered_signature": "open",
        "suspected": ["solder"],
        "after_burnin": False,
        "after_reflow": False,
        "customer_return": True,
        "budget": "medium",
        "urgency": "routine",
    },
    "observations": [
        {"phase": "N0", "technique": "retest_matrix", "unit": "U12-A",
         "conditions": "5 insertions at room temperature, customer program rev",
         "result": "Passes all 5 insertions at room temperature. No parameter outside limits.",
         "interpretation": "Room-temperature testing cannot see this failure; the case cannot "
                           "proceed on room-temperature evidence.", "date": "2026-08-10"},
    ],
    "hypotheses": [],
    "open_questions": [
        "Does the open follow the package or the board? The customer has not yet re-tested the "
        "same package on a different board, or a different package on the same board site.",
        "Which specific net and which specific ball/wire - the customer reports 'one I/O net' but "
        "has not identified it by ball position.",
        "Is the assembly lot common across the three failures, and is it common with the "
        "37 passing assemblies?",
        "Cu wire on Al pad with an automotive mission profile - what does the OSAT's bond "
        "monitoring data for AS-26-0119 look like?",
    ],
}

# =============================================================================== case 4
CASE4 = {
    "case_id": "FA-2026-0133",
    "title": "Step increase in an I/O leakage bin at wafer sort, starting with the first lot "
             "probed after a probe-card and load-board change",
    "status": "open",
    "opened": "2026-08-12",
    "requester": {"name": "Product engineering", "org": "Internal - wafer sort",
                  "contact": "PE-07"},
    "device": {"part_number": "KL-6120 (die)", "description": "Mixed-signal controller die at "
               "wafer sort", "package": "bare die at probe (assembled later into QFN48)",
               "date_code": "n/a", "assembly_lot": "n/a", "wafer_lot": "L2551 (before), "
               "L2604 (after)", "assembly_site": "n/a", "test_program_rev": "TP-6120 rev F "
               "(unchanged across both lots)"},
    "samples": [
        {"serial": "20 dies inked from L2604", "role": "sequence",
         "condition_as_received": "picked from the reject bin after sort, in waffle pack",
         "disposition": "in FA lab"},
        {"serial": "5 dies from L2551", "role": "reference",
         "condition_as_received": "passing dies from the pre-change lot",
         "disposition": "held as known-good"},
    ],
    "complaint": "Soft bin 42 (I/O leakage) jumped from effectively zero to roughly 6% of dies, "
                 "starting with the first lot probed after a probe-card replacement and a "
                 "load-board swap on prober PR-03. The test program revision did not change. "
                 "Product engineering wants to know whether this is a real die problem, a test "
                 "artifact, or damage being caused at probe.",
    "symptoms": {
        "symptom_class": "parametric",
        "failure_rate": "Approximately 6% of dies in lot L2604 (first lot after the change); "
                        "effectively 0% in lot L2551 (last lot before the change). Background "
                        "defectivity bin unchanged in both lots.",
        "conditions": "Wafer sort at room temperature, prober PR-03, new probe card PC-118 and "
                      "load board LB-22 installed 2026-08-09. Failing dies show elevated input "
                      "leakage on one I/O pin pair; all other parameters normal.",
    },
    "data_files": {
        "die_results": "case4_die_results.csv",
        "tests": "case4_tests.csv",
        "note": "Canonical schemas: die_results.csv is lot_id,wafer_id,die_x,die_y,hard_bin,"
                "soft_bin,pass_flag · tests.csv is lot_id,wafer_id,die_x,die_y,test_num,"
                "test_name,value,lo_lim,hi_lim",
    },
    "life_history": {
        "burn_in": "no", "board_reflow": "no", "field_hours": "0", "environment": "sort floor",
        "application_notes": "dies have never been packaged; the only handling is the prober",
    },
    "selector_input": {
        "symptom_class": "parametric",
        "package_type": "bare-die",
        "sample_count": 20,
        "powered_signature": "leakage",
        "suspected": ["esd"],
        "after_burnin": False,
        "after_reflow": False,
        "customer_return": False,
        "budget": "medium",
        "urgency": "expedite",
    },
    "observations": [
        {"phase": "N0", "technique": "datalog_review", "unit": "L2604 population",
         "conditions": "full datalog, both lots, same program rev TP-6120 rev F",
         "result": "Failing dies fail test 1050 (IIL_IO2) far outside its limit; test 1051 "
                   "(IIH_IO2) also fails on a subset. All other tests, including IDDQ, remain "
                   "within limits.",
         "interpretation": "Observed: leakage confined to one I/O pin pair, not a general "
                           "leakage shift.", "date": "2026-08-12"},
    ],
    "hypotheses": [],
    "open_questions": [
        "Is the spatial pattern of bin 42 clustered (a process or wafer-level cause) or random "
        "(a per-touchdown event)? Run bin_signature.py before anything else.",
        "Does a failing die still fail when re-probed on a different prober with the old probe "
        "card, and does a passing die start failing after extra touchdowns?",
        "Was the new load board's ESD control verified - grounding, ionizer, and the discharge "
        "path through the probe card?",
        "Do the failing dies correlate with touchdown order, probe-card site, or wafer position?",
    ],
}

# =============================================================================== case 5
CASE5 = {
    "case_id": "FA-2026-0140",
    "title": "Functional failures appearing at the contract manufacturer immediately after board "
             "reflow, on a batch of QFN parts stored open on the line",
    "status": "open",
    "opened": "2026-08-14",
    "requester": {"name": "Contract manufacturer quality", "org": "Customer C CM",
                  "contact": "via account QE"},
    "device": {"part_number": "KL-5502-QFN64", "description": "Power management IC, wire-bond QFN",
               "package": "QFN64, wire bond, MSL 3 rated", "date_code": "2551",
               "assembly_lot": "AS-25-5510", "wafer_lot": "W25-2201", "assembly_site": "OSAT-2",
               "test_program_rev": "TP-5502 rev A"},
    "samples": [
        {"serial": "CM-01 .. CM-06", "role": "sequence",
         "condition_as_received": "6 failing units de-soldered from CM boards; 2 show a faint "
                                  "package bulge under raking light",
         "disposition": "in FA lab, bagged with desiccant, not baked"},
        {"serial": "CM-R1, CM-R2", "role": "reference",
         "condition_as_received": "2 units from the same reel, never reflowed, still in the "
                                  "original dry-pack",
         "disposition": "held sealed as the un-reflowed control"},
    ],
    "complaint": "The CM reports that 6 of 220 boards from one build failed in-circuit test "
                 "immediately after reflow. All 220 devices came from the same reel. The devices "
                 "were removed from their dry-pack for a partial build, the reel sat open on the "
                 "line over a long weekend, and the remainder were used in this build without a "
                 "bake. The CM says the devices are defective and is asking for credit. Our "
                 "account QE wants a mechanism, and wants to know whether the surviving 214 "
                 "boards are at risk.",
    "symptoms": {
        "symptom_class": "hard_fail",
        "failure_rate": "6 of 220 boards from one build (2.7%). Zero failures in the earlier "
                        "partial build that used devices from the same reel while it was still "
                        "within floor life.",
        "conditions": "Failures present at the first in-circuit test after reflow. Mixed "
                      "signatures across the 6 units: 4 show an open on one or more supply or "
                      "I/O nets, 2 are functionally dead. None passed at any point after reflow.",
    },
    "life_history": {
        "burn_in": "no",
        "board_reflow": "Pb-free reflow, peak reported as 245-250 C, single pass. Devices are "
                        "MSL 3 rated. Dry-pack opened 2026-07-30; the reel sat on the line "
                        "uncovered until 2026-08-05 (approximately 6 days, factory ambient "
                        "reported as 28-32 C and 60-70% RH). No bake was performed before this "
                        "build.",
        "field_hours": "0",
        "environment": "CM assembly line",
        "application_notes": "the earlier partial build from the same reel, run on 2026-07-30 "
                             "within floor life, produced zero failures",
    },
    "selector_input": {
        "symptom_class": "hard_fail",
        "package_type": "wirebond-plastic",
        "sample_count": 6,
        "powered_signature": "open",
        "suspected": [],
        "after_burnin": False,
        "after_reflow": True,
        "customer_return": True,
        "budget": "medium",
        "urgency": "expedite",
    },
    "observations": [
        {"phase": "N0", "technique": "external_visual", "unit": "CM-01 .. CM-06",
         "conditions": "10x and 50x stereo, raking light, as received",
         "result": "2 of 6 units show a faint convex bulge on the mold surface under raking "
                   "light. No cracks visible at 50x on any unit. No discoloration.",
         "interpretation": "Observation only. A bulge is a lead worth pursuing before any "
                           "handling that could alter the package.", "date": "2026-08-14"},
    ],
    "hypotheses": [],
    "open_questions": [
        "What is the actual floor-life allowance for this package at MSL 3, and how far did the "
        "6-day open exposure at 60-70% RH exceed it?",
        "Was the reflow profile within the device's rated peak temperature? The CM reports "
        "245-250 C - obtain the actual profile trace, not the setpoint.",
        "Are the surviving 214 boards at risk - i.e. is there latent delamination in units that "
        "currently pass?",
        "IMPORTANT: do not bake any received unit and do not decap anything before acoustic "
        "imaging. Baking erases the moisture state and decapsulation erases the interface "
        "evidence.",
    ],
}

CASES = {
    1: [("case1_eos_hotplug.json", CASE1_INTAKE),
        ("case1_eos_hotplug_resolved.json", CASE1_RESOLVED)],
    2: [("case2_tddb_burnin.json", CASE2)],
    3: [("case3_nsop_tempcycle.json", CASE3)],
    4: [("case4_esd_hbm_cluster.json", CASE4)],
    5: [("case5_msl_popcorn.json", CASE5)],
}

# ------------------------------------------------------------------- case 4 CSVs
GRID_N = 40          # matches the canonical grid used by semi-yield-monitor
LOTS = (("L2551", 2, False), ("L2604", 2, True))   # lot_id, wafers, after_tooling_change
P_BACKGROUND = 0.048          # random defectivity, soft bin 51
P_ESD = 0.060                 # added leakage population in the post-change lot, soft bin 42
PASSING_SAMPLE_RATE = 0.10    # fraction of passing dies that also get tests.csv rows

TEST_DEFS = {
    1010: ("CONT_IO2", -1.5, -0.2),
    1050: ("IIL_IO2", -1.0e-06, 1.0e-06),
    1051: ("IIH_IO2", -1.0e-06, 1.0e-06),
    2100: ("IDDQ_CORE", 0.0, 5.0e-06),
    4000: ("FUNC_SCAN_M1", 0.5, 1.5),
}


def wafer_sites(n=GRID_N):
    c = (n - 1) / 2.0
    return [(x, y) for x in range(n) for y in range(n)
            if math.hypot(x - c, y - c) <= c + 1e-9]


def gen_case4_csvs(outdir: Path, seed: int) -> list[Path]:
    rng = np.random.default_rng(seed)
    sites = wafer_sites()
    die_lines = ["lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag"]
    test_lines = ["lot_id,wafer_id,die_x,die_y,test_num,test_name,value,lo_lim,hi_lim"]
    stats = []

    def trow(lot, waf, x, y, tnum, value):
        name, lo, hi = TEST_DEFS[tnum]
        test_lines.append(f"{lot},{waf},{x},{y},{tnum},{name},{value:.6g},{lo:.6g},{hi:.6g}")

    for lot, n_waf, post_change in LOTS:
        for w in range(1, n_waf + 1):
            waf = f"W{w:02d}"
            n_esd = n_bg = 0
            for (x, y) in sites:
                is_esd = post_change and rng.random() < P_ESD
                is_bg = (not is_esd) and rng.random() < P_BACKGROUND
                if is_esd:
                    hb, sb, pf = 4, 42, 0
                    n_esd += 1
                elif is_bg:
                    hb, sb, pf = 5, 51, 0
                    n_bg += 1
                else:
                    hb, sb, pf = 1, 1, 1
                die_lines.append(f"{lot},{waf},{x},{y},{hb},{sb},{pf}")

                emit_tests = (pf == 0) or (rng.random() < PASSING_SAMPLE_RATE)
                if not emit_tests:
                    continue
                trow(lot, waf, x, y, 1010, -0.65 + rng.normal(0, 0.03))
                if is_esd:
                    # leakage far outside the limit on one I/O pin pair
                    trow(lot, waf, x, y, 1050, rng.uniform(2.0e-05, 4.0e-04))
                    if rng.random() < 0.6:
                        trow(lot, waf, x, y, 1051, rng.uniform(5.0e-06, 8.0e-05))
                    else:
                        trow(lot, waf, x, y, 1051, rng.normal(0, 1.5e-07))
                    trow(lot, waf, x, y, 2100, abs(rng.normal(2.6e-06, 4e-07)))
                    trow(lot, waf, x, y, 4000, 1.0)
                elif is_bg:
                    trow(lot, waf, x, y, 1050, rng.normal(0, 1.5e-07))
                    trow(lot, waf, x, y, 4000, 0.0)
                else:
                    trow(lot, waf, x, y, 1050, rng.normal(0, 1.5e-07))
                    trow(lot, waf, x, y, 1051, rng.normal(0, 1.5e-07))
                    trow(lot, waf, x, y, 2100, abs(rng.normal(1.9e-06, 3e-07)))
                    trow(lot, waf, x, y, 4000, 1.0)
            stats.append((lot, waf, len(sites), n_esd, n_bg, post_change))

    p_die = outdir / "case4_die_results.csv"
    p_tst = outdir / "case4_tests.csv"
    p_die.write_text("\n".join(die_lines) + "\n")
    p_tst.write_text("\n".join(test_lines) + "\n")
    print(f"  case 4 grid: {GRID_N}x{GRID_N} circular mask, {len(sites)} dies/wafer")
    print(f"  {'lot':<8}{'wafer':<7}{'dies':>6}{'bin42':>7}{'bin51':>7}  post-change")
    for lot, waf, nd, ne, nb, pc in stats:
        print(f"  {lot:<8}{waf:<7}{nd:>6}{ne:>7}{nb:>7}  {pc}")
    return [p_die, p_tst]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--case", default="all", help="1 | 2 | 3 | 4 | 5 | all (default all)")
    ap.add_argument("--outdir", default=".", help="output directory (default: current dir)")
    ap.add_argument("--seed", type=int, default=17, help="RNG seed for the case-4 CSVs (default 17)")
    args = ap.parse_args(argv)

    if args.case == "all":
        wanted = [1, 2, 3, 4, 5]
    else:
        try:
            wanted = [int(args.case)]
        except ValueError:
            print("error: --case must be 1-5 or 'all'", file=sys.stderr)
            return 2
        if wanted[0] not in CASES:
            print("error: --case must be 1-5 or 'all'", file=sys.stderr)
            return 2

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for c in wanted:
        for fname, payload in CASES[c]:
            p = outdir / fname
            p.write_text(json.dumps(payload, indent=2) + "\n")
            written.append(p)
        if c == 4:
            written += gen_case4_csvs(outdir, args.seed)

    for p in written:
        print(f"wrote {p} ({p.stat().st_size / 1024:.1f} KB)")
    print(f"\n{len(written)} file(s). The true mechanism for each case lives ONLY in "
          f"evals/semi-failure-analysis/golden/ - the intake files do not contain it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
