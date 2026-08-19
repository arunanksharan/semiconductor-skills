#!/usr/bin/env python3
"""Write the three eval scenario input files for semi-packaging-qual.

Each file is a scenario record: a short narrative a human can read, plus an `inputs` block
that `qual_plan.py --scenario <file>` consumes directly. The golden expectations that these
scenarios are graded against live in evals/semi-packaging-qual/golden/.

Scenarios:
  1. automotive_qfn_g1_derivative - automotive QFN, AEC-Q100 grade 1, derivative package
  2. consumer_wlcsp_new          - consumer WLCSP, new package family, MSL 1 target
  3. industrial_bga_derivative   - industrial PBGA, derivative package

Usage examples:
  python gen_scenarios.py                        # writes to the repo's sample-data/ dir
  python gen_scenarios.py --out-dir /tmp/scen --force
  python gen_scenarios.py --list
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.abspath(
    os.path.join(HERE, "..", "..", "..", "sample-data", "semi-packaging-qual"))

SCENARIOS: list[dict] = [
    {
        "scenario_name": "automotive_qfn_g1_derivative",
        "title": "Automotive QFN, AEC-Q100 grade 1, derivative package",
        "narrative": (
            "A qualified 5x5 mm QFN-32 motor pre-driver is being re-spun with a shrunk die "
            "(same pad count, same pad pitch, same leadframe design, same OSAT, same mold "
            "compound and die-attach lots). The customer is a tier-1 automotive supplier at "
            "AEC-Q100 grade 1 (ambient up to 125 C, under-hood adjacent). Pd-coated Cu wire "
            "on Al pads. Exposed pad soldered to a copper pour on the customer's board. "
            "The programme wants to leverage the existing family qualification."),
        "expected_judgement": (
            "Derivative, so a similarity justification carries the lot argument - but the "
            "automotive floor of 3 non-consecutive assembly lots still applies. Cu-alloy "
            "wire on Al pads makes biased HAST the leg that matters. QFN is not an area-"
            "array package, so board-level DROP does not belong in the plan; board-level "
            "thermal cycling of the exposed-pad joint does, as a conditional row."),
        "inputs": {
            "device_class": "automotive_grade1",
            "package": "qfn",
            "novelty": "derivative",
            "msl": "2",
            "handheld": False,
            "board_level": False,
            "suppress_board_level": False,
            "power_cycling": False,
            "device": "QFN-32, 5x5x0.9 mm, exposed pad, Pd-coated Cu wire on Al pads, "
                      "motor pre-driver",
            "change": None,
        },
    },
    {
        "scenario_name": "consumer_wlcsp_new",
        "title": "Consumer WLCSP, new package family, MSL 1 target",
        "narrative": (
            "A power-management IC is moving to WLCSP for the first time: 2.6x2.6 mm, "
            "36 bumps at 0.4 mm pitch, 300 um final die thickness, polymer repassivation "
            "over the RDL. The end product is a wearable. Marketing wants MSL 1 so the "
            "assembler can skip dry-pack handling. No prior WLCSP experience on this "
            "product line and a new bump/RDL supplier."),
        "expected_judgement": (
            "New package family: 3 non-consecutive lots, full stress set. WLCSP has no wire "
            "bonds and no die attach, so wire pull, ball-bond shear and die shear must NOT "
            "appear. The board joint IS the package joint, so board-level drop (handheld) "
            "and board-level thermal cycling are the core of the qualification, not "
            "optional extras. Thin die means a die-strength monitor belongs in the plan."),
        "inputs": {
            "device_class": "consumer",
            "package": "wlcsp",
            "novelty": "new_package",
            "msl": "1",
            "handheld": True,
            "board_level": False,
            "suppress_board_level": False,
            "power_cycling": False,
            "device": "WLCSP-36, 2.6x2.6 mm, 0.4 mm bump pitch, 300 um die, PMIC for a "
                      "wearable",
            "change": None,
        },
    },
    {
        "scenario_name": "industrial_bga_derivative",
        "title": "Industrial PBGA, derivative package",
        "narrative": (
            "A 23x23 mm 484-ball PBGA (wire-bond on a 4-layer organic substrate, 1.2 mm "
            "body) already qualified for an industrial controller is being reused for a "
            "derivative device: same substrate design and same ball map, larger die, same "
            "assembly site, same materials set. Industrial mission profile, cabinet-mounted, "
            "no drop exposure. Currently shipped at MSL 3."),
        "expected_judgement": (
            "Derivative on a non-automotive part: 1 lot plus a written similarity "
            "justification - but the larger die changes the die-to-pad ratio, which is one "
            "of the named similarity disqualifiers, so the plan must call that out. "
            "Wire-bond construction keeps wire pull / ball-bond shear / die shear in scope. "
            "Area array keeps board-level thermal cycling and warpage in scope; there is no "
            "drop exposure, so board-level drop stays out."),
        "inputs": {
            "device_class": "industrial",
            "package": "pbga",
            "novelty": "derivative",
            "msl": "3",
            "handheld": False,
            "board_level": False,
            "suppress_board_level": False,
            "power_cycling": False,
            "device": "PBGA-484, 23x23x1.2 mm, 1.0 mm ball pitch, wire bond on 4-layer "
                      "organic substrate, industrial controller",
            "change": None,
        },
    },
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=DEFAULT_OUT,
                    help="directory to write the scenario files into (default: %(default)s)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--list", action="store_true",
                    help="print the scenario names and titles, write nothing")
    args = ap.parse_args(argv)

    if args.list:
        for s in SCENARIOS:
            print("{:<32} {}".format(s["scenario_name"], s["title"]))
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    written, skipped = [], []
    for s in SCENARIOS:
        path = os.path.join(args.out_dir, s["scenario_name"] + ".json")
        if os.path.exists(path) and not args.force:
            skipped.append(path)
            continue
        with open(path, "w") as fh:
            json.dump(s, fh, indent=2)
            fh.write("\n")
        written.append(path)

    for p in written:
        print("wrote   {}".format(p))
    for p in skipped:
        print("skipped {} (exists; use --force)".format(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
