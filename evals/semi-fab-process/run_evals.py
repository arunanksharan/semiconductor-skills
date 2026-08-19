#!/usr/bin/env python3
"""Eval harness for semi-fab-process: re-runs the four acceptance criteria in EVALS.md.

Every script is invoked as a SUBPROCESS through its real CLI, so the interface documented
in SKILL.md is what is under test.

  (a) etch CD drift  -- commonality.py must rank the seeded chamber ETCH-02/C #1, both over
      the full history and over the scoped window, and must NOT flag the top suspect as a
      tie or as time-confounded.
  (b) metrology false alarm -- the process chart shows exactly one point beyond a control
      limit; the gauge's own monitor chart is OUT OF CONTROL from the calibration date while
      the second gauge stays in control; the re-measurements on the second tool remove the
      offset. Together these mean the runbook exits at Gate 0 with NO PROCESS HOLD.
  (c) doe_builder.py -- the printed 2^(5-2) defining relation, resolution and alias classes
      must match an independent derivation (contrast columns compared directly).
  (d) hygiene -- every script compiles and answers --help with exit code 0.

Sample data is regenerated into a temporary directory first, so the harness also proves the
generator is deterministic and that the eval does not depend on files lying around.

Exit code 0 only if every check passes.

Usage examples:
  python3 run_evals.py
  python3 run_evals.py --verbose
  python3 run_evals.py --json
  python3 run_evals.py --keep-data /tmp/fabdata   # keep the regenerated scenarios
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPTS = os.path.join(REPO, "skills", "semi-fab-process", "scripts")


def run(script: str, *args: str) -> str:
    """Run a skill script through its CLI and return stdout (raises on non-zero)."""
    cmd = [sys.executable, os.path.join(SCRIPTS, script), *args]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{script} exited {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def check(results: list, name: str, ok: bool, detail: str = "") -> bool:
    results.append({"check": name, "pass": bool(ok), "detail": detail})
    return bool(ok)


# ------------------------------------------------------------------ (a) etch drift
def eval_etch(data_root: str, results: list) -> None:
    d = os.path.join(data_root, "etch_cd_drift")
    hist, met = os.path.join(d, "history.csv"), os.path.join(d, "cd_by_lot.csv")

    for label, extra in (("full window", []), ("scoped since 2026-07-16", ["--since", "2026-07-16"])):
        out = json.loads(run("commonality.py", "--history", hist, "--metric", met,
                             "--metric-col", "cd_nm", "--json", *extra))
        top = out["top"]
        check(results, f"(a) top suspect is ETCH/ETCH-02/C [{label}]",
              top["label"] == "ETCH/ETCH-02/C",
              f"got {top['label']}  p_tail={top['p_tail']:.3g}  z={top['shift_z']:.2f}  "
              f"delta={top['delta']:+.3f}  flagged {top['flagged_in']}/{out['n_flagged']}")
        check(results, f"(a) top suspect is at CHAMBER level [{label}]",
              top["level"] == "chamber", f"level={top['level']}")
        check(results, f"(a) top suspect carries no TIE/TIME-CONFOUNDED flag [{label}]",
              not any(f.startswith("TIE") or f == "TIME-CONFOUNDED" for f in top["flags"]),
              f"flags={top['flags']}")
        runner = out["candidates"][1]
        check(results, f"(a) #1 separates from #2 [{label}]",
              top["p_tail"] < runner["p_tail"],
              f"#1 p_tail={top['p_tail']:.3g} vs #2 {runner['label']} "
              f"p_tail={runner['p_tail']:.3g}")

    # the fleet-level chart must see the excursion at all
    spc = json.loads(run("spc_charts.py", "--data", met, "--value", "cd_nm",
                         "--label", "lot_id", "--chart", "imr", "--baseline", "30",
                         "--usl", "46.5", "--lsl", "43.5", "--json"))
    check(results, "(a) fleet I-MR chart is OUT OF CONTROL",
          spc["verdict"] == "OUT OF CONTROL",
          f"{spc['verdict']}; UCL={spc['ucl']:.4f}; "
          f"rule-1 lots={[v['label'] for v in spc['violations'] if v['rule'] == 1]}")

    # split by the guilty chamber, every post-boundary lot is out
    spc_c = json.loads(run("spc_charts.py", "--data", met, "--value", "cd_nm",
                           "--label", "lot_id", "--chart", "imr", "--baseline", "6",
                           "--where", "etch_tool=ETCH-02", "--where", "etch_chamber=C",
                           "--json"))
    r1 = sorted({v["label"] for v in spc_c["violations"] if v["rule"] == 1})
    check(results, "(a) chamber-split chart flags all 4 post-boundary lots",
          r1 == ["L0032", "L0048", "L0058", "L0060"], f"rule-1 lots={r1}")


# ------------------------------------------------------- (b) metrology false alarm
def eval_metro(data_root: str, results: list) -> None:
    d = os.path.join(data_root, "metro_false_alarm")
    lots = os.path.join(d, "thickness_by_lot.csv")
    mon = os.path.join(d, "metro_monitor.csv")

    spc = json.loads(run("spc_charts.py", "--data", lots, "--value", "thickness_a",
                         "--label", "lot_id", "--chart", "imr", "--baseline", "30", "--json"))
    beyond = [v for v in spc["violations"] if v["rule"] == 1]
    check(results, "(b) exactly ONE lot beyond a control limit", len(beyond) == 1,
          f"{[(v['label'], v['value']) for v in beyond]}  UCL={spc['ucl']:.2f}")
    ooc_lot = beyond[0]["label"] if beyond else None

    met02 = json.loads(run("spc_charts.py", "--data", mon, "--value", "reading_a",
                           "--label", "date", "--chart", "imr", "--baseline", "30",
                           "--where", "tool=MET-02", "--json"))
    met01 = json.loads(run("spc_charts.py", "--data", mon, "--value", "reading_a",
                           "--label", "date", "--chart", "imr", "--baseline", "30",
                           "--where", "tool=MET-01", "--json"))
    post = sorted(v["label"] for v in met02["violations"]
                  if v["rule"] == 1 and v["label"] >= "2026-08-16")
    check(results, "(b) MET-02 gauge monitor OOC on every day from the cal date",
          met02["verdict"] == "OUT OF CONTROL" and len(post) >= 7,
          f"{met02['verdict']}; days beyond 3 sigma from 2026-08-16: {post}")
    check(results, "(b) MET-01 gauge monitor stays in control",
          met01["verdict"].startswith("IN CONTROL"), met01["verdict"])

    # the cal event exists in the gauge history on the step date
    ev = open(os.path.join(d, "metro_events.csv")).read()
    check(results, "(b) gauge event history contains the 2026-08-16 MET-02 CAL",
          bool(re.search(r"2026-08-16,MET-02,CAL", ev)), "metro_events.csv")

    # second-tool re-measurement removes the offset on every re-measured lot
    rows = [l.split(",") for l in
            open(os.path.join(d, "remeasure.csv")).read().strip().splitlines()[1:]]
    orig = {r[0]: float(r[4]) for r in rows if r[1] == "original"}
    second = {r[0]: float(r[4]) for r in rows if r[1] == "second_tool"}
    deltas = {k: second[k] - orig[k] for k in second if k in orig}
    check(results, "(b) every second-tool re-measure is 5-10 A LOWER than MET-02",
          bool(deltas) and all(-10.5 < v < -5.0 for v in deltas.values()),
          "; ".join(f"{k} {v:+.2f} A" for k, v in sorted(deltas.items())))
    check(results, "(b) the OOC lot itself comes back in family on the second tool",
          ooc_lot in second and second[ooc_lot] < spc["ucl"],
          f"{ooc_lot}: {orig.get(ooc_lot)} -> {second.get(ooc_lot)} (UCL {spc['ucl']:.2f})")

    # commonality over the post-cal window points at the metrology tool, not a process tool
    com = json.loads(run("commonality.py", "--history", os.path.join(d, "history.csv"),
                         "--metric", lots, "--metric-col", "thickness_a",
                         "--since", "2026-08-16", "--json"))
    check(results, "(b) post-cal commonality ranks METRO/MET-02 above every process tool",
          com["top"]["label"] == "METRO/MET-02",
          f"top={com['top']['label']} delta={com['top']['delta']:+.3f} "
          f"z={com['top']['shift_z']:.2f}; #2={com['candidates'][1]['label']}")
    check(results, "(b) verdict: NO PROCESS HOLD (gauge moved, process did not)",
          all(r["pass"] for r in results if r["check"].startswith("(b)")),
          "Gate 0 = FAIL -> false-alarm exit")


# --------------------------------------------------------------- (c) alias structure
def eval_doe(data_root: str, results: list) -> None:
    out = run("doe_builder.py", "--design", "fractional", "-k", "5", "-p", "2",
              "--alias-order", "2")
    check(results, "(c) resolution reported as III", "resolution III" in out, "")
    check(results, "(c) defining relation printed",
          "defining relation: I = ABD = ACE = BCDE" in out, "")

    printed = set()
    for line in out.splitlines():
        s = line.strip()
        if " = " in s and not s.startswith("defining") and re.fullmatch(r"[A-Z ={2,}=]+", s):
            printed.add(frozenset(w.strip() for w in s.split("=")))
    printed = {c for c in printed if all(re.fullmatch(r"[A-E]+", w) for w in c)}

    # independent derivation: group all 31 effects by their actual contrast column
    rows = []
    for i in range(8):
        a = 1 if i & 1 else -1
        b = 1 if (i >> 1) & 1 else -1
        c = 1 if (i >> 2) & 1 else -1
        rows.append({"A": a, "B": b, "C": c, "D": a * b, "E": a * c})
    classes: dict[tuple, list[str]] = {}
    for r in range(1, 6):
        for combo in itertools.combinations("ABCDE", r):
            col = tuple(int(eval("*".join(str(row[f]) for f in combo))) for row in rows)
            key = col if col[next(i for i, v in enumerate(col) if v)] > 0 else \
                tuple(-v for v in col)
            classes.setdefault(key, []).append("".join(combo))
    derived = {frozenset(v) for v in classes.values()}
    identity = frozenset(classes[tuple([1] * 8)])

    check(results, "(c) 8 distinct contrast columns (7 estimable + identity)",
          len(classes) == 8, f"got {len(classes)}")
    check(results, "(c) all 31 effects accounted for",
          sum(len(v) for v in classes.values()) == 31,
          f"got {sum(len(v) for v in classes.values())}")
    check(results, "(c) identity class == the defining relation",
          identity == frozenset({"ABD", "ACE", "BCDE"}), f"{sorted(identity)}")
    check(results, "(c) every printed alias class matches the independent derivation",
          printed and printed <= derived and len(printed) == 7,
          f"printed {len(printed)} classes; "
          f"mismatched: {[sorted(c) for c in printed - derived]}")

    # Lenth path on the unreplicated screen, t-test + curvature on the replicated design
    scr = os.path.join(data_root, "doe_etch", "screening_2_5_2_response.csv")
    a1 = json.loads(run("doe_analyze.py", "--data", scr, "--response", "CD_NM",
                        "--generators", "D=AB,E=AC", "--json"))
    eff = {e["effect"]: e for e in a1["effects"]}
    check(results, "(c) unreplicated design routes to Lenth's method",
          a1["method"]["kind"].startswith("Lenth"),
          f"{a1['method']['kind']}  PSE={a1['method']['PSE']:.4g} "
          f"ME={a1['method']['ME']:.4g} SME={a1['method']['SME']:.4g} m={a1['method']['m_effects']}")
    check(results, "(c) only 7 contrasts estimated (aliases collapsed)",
          len(a1["effects"]) == 7, f"got {len(a1['effects'])}")
    check(results, "(c) A and C exceed SME; D and E do not exceed ME",
          eff["A"]["significant_simultaneous"] and eff["C"]["significant_simultaneous"]
          and not eff["D"]["significant"] and not eff["E"]["significant"],
          f"A={eff['A']['value']:.3f} C={eff['C']['value']:.3f} B={eff['B']['value']:.3f} "
          f"D={eff['D']['value']:.3f} E={eff['E']['value']:.3f}")

    ch = os.path.join(data_root, "doe_etch", "characterisation_2_3_response.csv")
    a2 = json.loads(run("doe_analyze.py", "--data", ch, "--response", "CD_NM",
                        "--max-order", "3", "--json"))
    check(results, "(c) replicated design routes to t-tests on pure error",
          "t-test" in a2["method"]["kind"],
          f"{a2['method']['kind']} MSE={a2['method']['MSE']:.5g} "
          f"df={a2['method']['df_pure_error']}")
    check(results, "(c) curvature detected -> route to RSM",
          bool(a2["curvature"] and a2["curvature"].get("significant")),
          f"diff={a2['curvature']['difference']:+.4f} F={a2['curvature']['F']:.3f} "
          f"p={a2['curvature']['p']:.4g}")


# ------------------------------------------------------------------ (d) hygiene
def eval_hygiene(results: list) -> None:
    scripts = sorted(glob.glob(os.path.join(SCRIPTS, "*.py")))
    check(results, "(d) all five scripts present", len(scripts) == 5,
          ", ".join(os.path.basename(s) for s in scripts))
    for s in scripts:
        name = os.path.basename(s)
        c = subprocess.run([sys.executable, "-m", "py_compile", s],
                           capture_output=True, text=True)
        check(results, f"(d) py_compile {name}", c.returncode == 0,
              (c.stderr or c.stdout).strip()[:200])
        p = subprocess.run([sys.executable, s, "--help"], capture_output=True, text=True)
        check(results, f"(d) --help {name}", p.returncode == 0 and len(p.stdout) > 200,
              f"rc={p.returncode}, {len(p.stdout)} chars")
    shutil.rmtree(os.path.join(SCRIPTS, "__pycache__"), ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", action="store_true", help="print the detail line for passes too")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ap.add_argument("--keep-data", help="regenerate the scenarios here instead of a temp dir")
    ap.add_argument("--seed", type=int, default=20260820, help="generator seed (default 20260820)")
    args = ap.parse_args()

    tmp = None
    if args.keep_data:
        root = args.keep_data
        os.makedirs(root, exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = tmp.name

    results: list = []
    try:
        run("gen_excursion_data.py", "--outdir", root, "--scenario", "all",
            "--seed", str(args.seed))
        check(results, "(0) sample data regenerated from the shipped generator", True, root)
        eval_etch(root, results)
        eval_metro(root, results)
        eval_doe(root, results)
        eval_hygiene(results)
    except Exception as e:  # noqa: BLE001 - a harness failure is a FAIL, not a traceback
        check(results, "harness completed", False, f"{type(e).__name__}: {e}")
    finally:
        if tmp:
            tmp.cleanup()

    overall = all(r["pass"] for r in results)
    if args.json:
        print(json.dumps({"pass": overall, "n_checks": len(results),
                          "n_failed": sum(1 for r in results if not r["pass"]),
                          "results": results}, indent=2))
        return 0 if overall else 1

    width = max(len(r["check"]) for r in results)
    for r in results:
        print(f"[{'PASS' if r['pass'] else 'FAIL'}] {r['check']:<{width}}")
        if r["detail"] and (args.verbose or not r["pass"]):
            print(f"       {r['detail']}")
    print("\n" + "=" * 78)
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}  "
          f"({sum(1 for r in results if r['pass'])}/{len(results)} checks passed)")
    print("=" * 78)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
