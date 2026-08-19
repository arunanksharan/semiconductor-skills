#!/usr/bin/env python3
"""Moisture-sensitivity-level advisor (J-STD-020 / J-STD-033 framework).

Takes package family, body geometry, die-to-package ratio hints and the customer's actual
reflow peak, and returns:
  * the Pb-free CLASSIFICATION reflow peak from the J-STD-020 thickness x volume table,
  * a conflict check against the customer's real process peak,
  * a starting-point MSL (family baseline adjusted by construction risk factors),
  * floor life and soak condition for the target level,
  * bake-out guidance (J-STD-033 practice) including the carrier constraint,
  * the re-classification triggers that void an existing MSL.

An MSL is EARNED by running the classification flow (soak + 3x reflow + C-SAM/electrical),
never assigned from a table. Everything here is a starting point for that experiment and is
labelled as such in the output.

Usage examples:
  python msl_advisor.py --package pbga --body-thickness-mm 1.2 --body-volume-mm3 800 \\
      --target-msl 3 --reflow-peak-c 260
  python msl_advisor.py --package wlcsp --body-thickness-mm 0.5 --body-size-mm 3x3 \\
      --target-msl 1
  python msl_advisor.py --package fcbga --body-thickness-mm 2.8 --body-volume-mm3 3000 \\
      --reflow-peak-c 260 --carrier tray --json
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

# J-STD-020 Pb-free classification reflow peak, own-words digest of the
# thickness x volume table. Current revision governs.
THICKNESS_BANDS = [(1.6, "<1.6 mm"), (2.5, "1.6-2.5 mm"), (float("inf"), ">=2.5 mm")]
VOLUME_BANDS = [(350, "<350 mm3"), (2000, "350-2000 mm3"), (float("inf"), ">2000 mm3")]
PBFREE_PEAK = {
    "<1.6 mm":   {"<350 mm3": 260, "350-2000 mm3": 260, ">2000 mm3": 260},
    "1.6-2.5 mm": {"<350 mm3": 260, "350-2000 mm3": 250, ">2000 mm3": 245},
    ">=2.5 mm":  {"<350 mm3": 250, "350-2000 mm3": 245, ">2000 mm3": 245},
}
SNPB_PEAK = {
    "<1.6 mm":   {"<350 mm3": 240, "350-2000 mm3": 225, ">2000 mm3": 225},
    "1.6-2.5 mm": {"<350 mm3": 240, "350-2000 mm3": 225, ">2000 mm3": 225},
    ">=2.5 mm":  {"<350 mm3": 240, "350-2000 mm3": 225, ">2000 mm3": 225},
}
SNPB_NOTE = ("SnPb classification bands are coarser than the Pb-free table and only matter "
             "for legacy lines - TODO verify the exact SnPb cell against a current copy of "
             "J-STD-020 before quoting it to a customer.")

# Level -> (soak condition, floor life, floor-life environment)
LEVELS = {
    "1":  ("85 C / 85 %RH, 168 h", "unlimited", "<=30 C / 85 %RH"),
    "2":  ("85 C / 60 %RH, 168 h", "1 year", "<=30 C / 60 %RH"),
    "2a": ("30 C / 60 %RH, 696 h", "4 weeks", "<=30 C / 60 %RH"),
    "3":  ("30 C / 60 %RH, 192 h", "168 h", "<=30 C / 60 %RH"),
    "4":  ("30 C / 60 %RH, 96 h", "72 h", "<=30 C / 60 %RH"),
    "5":  ("30 C / 60 %RH, 72 h", "48 h", "<=30 C / 60 %RH"),
    "5a": ("30 C / 60 %RH, 48 h", "24 h", "<=30 C / 60 %RH"),
    "6":  ("per label", "mandatory bake before use; mount within the time on the label",
           "<=30 C / 60 %RH"),
}
LEVEL_ORDER = ["1", "2", "2a", "3", "4", "5", "5a", "6"]

# Family baselines: (starting MSL index into LEVEL_ORDER, rationale)
FAMILY_BASELINE = {
    "wlcsp": ("1", "Bare die with only a repassivation polymer - almost no organic bulk to "
                   "absorb moisture."),
    "qfn": ("2", "Small leadframe body, thin mold cap, no organic substrate."),
    "dfn": ("2", "Small leadframe body, thin mold cap, no organic substrate."),
    "qfp": ("3", "Larger mold volume and long mold-to-leadframe interfaces."),
    "pbga": ("3", "Organic substrate is the moisture reservoir; mold-to-substrate interface "
                  "is the popcorn path."),
    "fccsp": ("3", "Organic substrate plus an underfill interface."),
    "fcbga": ("3", "Large organic substrate, large interfaces, high thermal mass."),
    "fowlp": ("2", "Mold-over-RDL with no organic substrate, but the mold/RDL interface is "
                   "the risk - construction-dependent, classify it."),
    "interposer_2p5d": ("3", "Substrate + interposer + underfill stack; bespoke - classify."),
}
ALIASES = {"bga": "pbga", "csp": "fccsp", "tqfp": "qfp", "lqfp": "qfp", "wlp": "wlcsp",
           "fo": "fowlp", "2.5d": "interposer_2p5d", "3d": "interposer_2p5d"}


def band(value: float, bands) -> str:
    for edge, label in bands:
        if value < edge:
            return label
    return bands[-1][1]


def classification_peak(thickness_mm: float, volume_mm3: float, solder: str) -> dict:
    t_band = band(thickness_mm, THICKNESS_BANDS)
    v_band = band(volume_mm3, VOLUME_BANDS)
    table = PBFREE_PEAK if solder == "pbfree" else SNPB_PEAK
    return {"thickness_band": t_band, "volume_band": v_band,
            "classification_peak_c": table[t_band][v_band],
            "table": "J-STD-020 Pb-free" if solder == "pbfree" else "J-STD-020 SnPb (legacy)"}


def worsen(level: str, steps: int) -> str:
    i = min(LEVEL_ORDER.index(level) + steps, len(LEVEL_ORDER) - 1)
    return LEVEL_ORDER[i]


def starting_msl(package: str, thickness_mm: float, die_pkg_ratio: float | None,
                 volume_mm3: float) -> dict:
    base, rationale = FAMILY_BASELINE[package]
    steps = 0
    factors = []
    # Thickness and volume are strongly correlated - penalise the PAIR once, not twice,
    # or a large thick FCBGA lands two levels below where the industry actually classifies it.
    geometry_hit = False
    if thickness_mm >= 2.0:
        geometry_hit = True
        factors.append("body >= 2.0 mm: more absorbed water and a longer vapour path")
    if volume_mm3 > 2000:
        geometry_hit = True
        factors.append("body volume > 2000 mm3: large interfaces and high thermal mass")
    if geometry_hit:
        steps += 1
        factors.append("geometry penalty applied once (thickness and volume are correlated): "
                       "one level worse")
    if package == "wlcsp":
        # The die IS the package: ratio ~1 by construction, and there is no mold cap for a
        # high ratio to thin. Applying the mold-cap penalty here would be nonsense.
        factors.append("bare-die construction: the die/package ratio is ~1 by definition and "
                       "carries no mold-cap penalty; the moisture risk is the repassivation "
                       "polymer and any RDL dielectric, so audit those materials instead")
    elif die_pkg_ratio is not None:
        if die_pkg_ratio >= 0.70:
            steps += 1
            factors.append("die/package area ratio >= 0.70: thin mold cap and little "
                           "adhesion area around the die -> one level worse")
        elif die_pkg_ratio >= 0.50:
            factors.append("die/package area ratio 0.50-0.70: watch the mold cap thickness "
                           "over the die; no level penalty applied, but this is the first "
                           "thing to blame if classification fails")
        else:
            factors.append("die/package area ratio < 0.50: comfortable mold cap and "
                           "adhesion area")
    else:
        factors.append("die/package ratio not supplied - supply it; a high ratio is the most "
                       "common reason a package classifies a level worse than its family")
    if package == "fowlp":
        factors.append("fan-out construction varies enormously (mold cap thickness, RDL "
                       "dielectric, backside protection) - treat the baseline as a coin "
                       "flip and classify early")
    steps = min(steps, 2)  # heuristic, not a standard: never move more than two levels
    return {"family_baseline_msl": base, "family_rationale": rationale,
            "risk_factors": factors, "starting_msl": worsen(base, steps),
            "levels_worsened": steps}


def bake_guidance(thickness_mm: float, carrier: str, level: str) -> dict:
    if thickness_mm <= 1.4:
        std = "125 C for 24 h (typical for bodies <= 1.4 mm)"
    elif thickness_mm <= 2.0:
        std = "125 C for 24-48 h (typical for bodies > 1.4 mm and <= 2.0 mm)"
    else:
        std = "125 C for 48 h or longer (thick bodies; use the standard's duration table)"
    carrier_rule = {
        "tray": "Confirm the tray is marked high-temperature (135 C class) before a 125 C "
                "bake. Standard trays deform and become an unloadable mess.",
        "tape_reel": "Tape-and-reel does NOT survive 125 C. Transfer to high-temp trays, or "
                     "use a low-temperature bake (e.g. 40 C at <=5 %RH) with the standard's "
                     "much longer duration.",
        "tube": "Confirm the tube material's temperature rating; most are not 125 C rated.",
        "unknown": "Carrier not declared - resolve this BEFORE scheduling a bake. The carrier "
                   "decides whether a 125 C bake is even possible.",
    }[carrier]
    return {
        "standard_recovery": std,
        "low_temperature_alternative": "40 C at <=5 %RH (days-to-weeks) or 90 C at <=5 %RH; "
                                       "use the J-STD-033 duration tables, do not "
                                       "interpolate by feel",
        "carrier_constraint": carrier_rule,
        "cumulative_bake_gate": "Bakes grow intermetallics and oxidise finishes. Track "
                                "CUMULATIVE bake time; beyond about 96 h at 125 C "
                                "(tighter for pure-Sn finishes) re-verify solderability to "
                                "J-STD-002 before board mount.",
        "after_bake": "Reset the floor-life clock, re-bag with fresh desiccant and a humidity "
                      "indicator card, and verify the moisture-barrier-bag seal.",
        "level_note": ("MSL 6 parts are baked immediately before every use - there is no "
                       "floor life to manage." if level == "6" else
                       "Floor life pauses in a <10 %RH dry cabinet; log in/out times."),
    }


RECLASS_TRIGGERS = [
    "Mold compound, die-attach, substrate or underfill material change",
    "Body thickness or volume change that crosses a J-STD-020 table cell",
    "Customer raises the process reflow peak above the classified peak (e.g. 245 -> 260 C)",
    "Assembly site transfer (conservative practice: re-run precon at the target level)",
    "Die size / die-to-package ratio change that thins the mold cap",
    "Lead finish or ball alloy change that changes the reflow profile",
]


def advise(package: str, thickness_mm: float, volume_mm3: float, die_pkg_ratio: float | None,
           reflow_peak_c: float | None, target_msl: str | None, solder: str,
           carrier: str) -> dict:
    cls = classification_peak(thickness_mm, volume_mm3, solder)
    start = starting_msl(package, thickness_mm, die_pkg_ratio, volume_mm3)
    level = target_msl or start["starting_msl"]
    soak, floor, env = LEVELS[level]

    conflict = None
    if reflow_peak_c is not None:
        if reflow_peak_c > cls["classification_peak_c"]:
            conflict = {
                "status": "CONFLICT",
                "detail": "Customer process peak {} C exceeds the {} C classification peak "
                          "for this body. The part must be re-classified AT the higher peak "
                          "(or the customer must lower the profile). Shipping against the "
                          "lower classification is a latent popcorn risk.".format(
                              reflow_peak_c, cls["classification_peak_c"]),
            }
        elif reflow_peak_c < cls["classification_peak_c"] - 10:
            conflict = {"status": "HEADROOM",
                        "detail": "Customer process peak {} C sits {} C below the {} C "
                                  "classification peak - margin, and an argument for a "
                                  "better MSL if the classification is re-run.".format(
                                      reflow_peak_c, cls["classification_peak_c"] - reflow_peak_c,
                                      cls["classification_peak_c"])}
        else:
            conflict = {"status": "OK",
                        "detail": "Customer process peak {} C is at or just under the {} C "
                                  "classification peak.".format(
                                      reflow_peak_c, cls["classification_peak_c"])}

    flow = [
        "Sample from >= 1 assembly lot (3 lots for a new package family); SERIALIZE the units.",
        "Time-zero: full electrical + C-SAM of every critical interface.",
        "Bake dry (125 C, 24 h typical) and record the dry weight.",
        "Moisture soak at the candidate level: {}.".format(soak),
        "Three reflow passes at {} C within the standard's timing envelope.".format(
            cls["classification_peak_c"]),
        "Post: full electrical + C-SAM vs the SAME unit's time-zero scan + external visual.",
        "Pass -> the part is that level (try one level better if you want the margin). "
        "Fail -> drop one level and start again with FRESH samples (soaked units are spent).",
    ]
    fail_def = ("External crack, electrical failure, or a delamination CHANGE on a critical "
                "interface (active die face, wire-bonded periphery, and - for products that "
                "use the pad as a thermal or electrical path - the die attach).")

    return {
        "inputs": {"package": package, "body_thickness_mm": thickness_mm,
                   "body_volume_mm3": volume_mm3, "die_package_area_ratio": die_pkg_ratio,
                   "reflow_peak_c": reflow_peak_c, "target_msl": target_msl,
                   "solder": solder, "carrier": carrier},
        "classification": cls,
        "process_peak_check": conflict,
        "msl_recommendation": {
            "starting_msl": start["starting_msl"],
            "family_baseline_msl": start["family_baseline_msl"],
            "family_rationale": start["family_rationale"],
            "levels_worsened_by_construction": start["levels_worsened"],
            "risk_factors": start["risk_factors"],
            "evaluated_level": level,
            "evaluated_level_is_target": bool(target_msl),
        },
        "floor_life": {"level": level, "soak_condition": soak, "floor_life": floor,
                       "environment": env},
        "classification_flow": flow,
        "fail_definition": fail_def,
        "bake_out": bake_guidance(thickness_mm, carrier, level),
        "reclassification_triggers": RECLASS_TRIGGERS,
        "caveats": [
            "MSL is EARNED by running the flow above - this output is a starting point and a "
            "handling guide, not a classification.",
            "Conditions here are an own-words digest; the current revisions of J-STD-020 and "
            "J-STD-033 govern.",
        ] + ([SNPB_NOTE] if solder == "snpb" else []),
    }


def render_text(rep: dict) -> str:
    i, c, m, f, b = (rep["inputs"], rep["classification"], rep["msl_recommendation"],
                     rep["floor_life"], rep["bake_out"])
    L = ["MSL advisory - {} , body {} mm thick, {} mm3".format(
        i["package"], i["body_thickness_mm"], i["body_volume_mm3"]), ""]
    L.append("CLASSIFICATION REFLOW PEAK ({})".format(c["table"]))
    L.append("  thickness band {}  x  volume band {}  ->  {} C".format(
        c["thickness_band"], c["volume_band"], c["classification_peak_c"]))
    if rep["process_peak_check"]:
        L.append("  process peak check [{}]: {}".format(
            rep["process_peak_check"]["status"], rep["process_peak_check"]["detail"]))
    L.append("")
    L.append("MSL RECOMMENDATION (starting point for the classification run)")
    L.append("  family baseline    : MSL {} - {}".format(
        m["family_baseline_msl"], m["family_rationale"]))
    for rf in m["risk_factors"]:
        L.append("    - {}".format(rf))
    L.append("  starting MSL       : {}{}".format(
        m["starting_msl"],
        " (worsened {} level(s) by construction)".format(m["levels_worsened_by_construction"])
        if m["levels_worsened_by_construction"] else ""))
    L.append("  level evaluated    : {}{}".format(
        m["evaluated_level"], " (user target)" if m["evaluated_level_is_target"] else ""))
    L.append("")
    L.append("FLOOR LIFE AT MSL {}".format(f["level"]))
    L.append("  soak for classification : {}".format(f["soak_condition"]))
    L.append("  floor life              : {} at {}".format(f["floor_life"], f["environment"]))
    L.append("")
    L.append("CLASSIFICATION FLOW")
    for n, step in enumerate(rep["classification_flow"], 1):
        L.append("  {}. {}".format(n, step))
    L.append("  FAIL = {}".format(rep["fail_definition"]))
    L.append("")
    L.append("BAKE-OUT (floor life exceeded / HIC card expired)")
    L.append("  standard recovery  : {}".format(b["standard_recovery"]))
    L.append("  low-temp option    : {}".format(b["low_temperature_alternative"]))
    L.append("  carrier constraint : {}".format(b["carrier_constraint"]))
    L.append("  cumulative gate    : {}".format(b["cumulative_bake_gate"]))
    L.append("  after the bake     : {}".format(b["after_bake"]))
    L.append("  {}".format(b["level_note"]))
    L.append("")
    L.append("RE-CLASSIFICATION REQUIRED IF ANY OF")
    for t in rep["reclassification_triggers"]:
        L.append("  - {}".format(t))
    L.append("")
    L.append("CAVEATS")
    for cav in rep["caveats"]:
        L.append("  - {}".format(cav))
    return "\n".join(L)


def parse_size(s: str) -> tuple[float, float]:
    parts = s.lower().replace("mm", "").split("x")
    if len(parts) != 2:
        raise SystemExit("--body-size-mm must look like 5x5 or 12.5x12.5")
    return float(parts[0]), float(parts[1])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True,
                    help="package family: " + ", ".join(sorted(FAMILY_BASELINE)))
    ap.add_argument("--body-thickness-mm", type=float, required=True,
                    help="package BODY thickness in mm (not including balls/leads)")
    ap.add_argument("--body-volume-mm3", type=float,
                    help="package body volume in mm3 (or give --body-size-mm)")
    ap.add_argument("--body-size-mm", help="body footprint WxL in mm, e.g. 5x5; "
                                           "volume = W*L*thickness")
    ap.add_argument("--die-package-ratio", type=float,
                    help="die area / package footprint area, 0-1 (thin mold cap indicator)")
    ap.add_argument("--die-size-mm", help="die WxL in mm; used with --body-size-mm to "
                                          "compute the ratio")
    ap.add_argument("--reflow-peak-c", type=float,
                    help="the customer's ACTUAL process peak, for the conflict check")
    ap.add_argument("--target-msl", choices=LEVEL_ORDER,
                    help="level to evaluate floor life / soak for (default: the starting MSL)")
    ap.add_argument("--solder", choices=["pbfree", "snpb"], default="pbfree")
    ap.add_argument("--carrier", choices=["tray", "tape_reel", "tube", "unknown"],
                    default="unknown", help="shipping carrier (decides bake feasibility)")
    ap.add_argument("--levels-table", action="store_true",
                    help="print the level / soak / floor-life table and exit")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.levels_table:
        rows = [{"MSL": lv, "soak (classification)": LEVELS[lv][0],
                 "floor life": LEVELS[lv][1], "environment": LEVELS[lv][2]}
                for lv in LEVEL_ORDER]
        print(pd.DataFrame(rows).to_string(index=False))
        return 0

    pkg = ALIASES.get(args.package.lower().replace("-", "_"),
                      args.package.lower().replace("-", "_"))
    if pkg not in FAMILY_BASELINE:
        raise SystemExit("unknown package '{}'. Known: {}".format(
            args.package, ", ".join(sorted(FAMILY_BASELINE))))

    body_wl = parse_size(args.body_size_mm) if args.body_size_mm else None
    volume = args.body_volume_mm3
    if volume is None:
        if body_wl is None:
            raise SystemExit("give --body-volume-mm3 or --body-size-mm")
        volume = body_wl[0] * body_wl[1] * args.body_thickness_mm

    ratio = args.die_package_ratio
    if ratio is None and args.die_size_mm and body_wl:
        dw, dl = parse_size(args.die_size_mm)
        ratio = (dw * dl) / (body_wl[0] * body_wl[1])
    if ratio is not None and not (0 < ratio <= 1):
        raise SystemExit("--die-package-ratio must be in (0,1]")

    rep = advise(pkg, args.body_thickness_mm, volume,
                 round(ratio, 3) if ratio is not None else None,
                 args.reflow_peak_c, args.target_msl, args.solder, args.carrier)
    print(json.dumps(rep, indent=2) if args.json else render_text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
