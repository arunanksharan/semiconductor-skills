#!/usr/bin/env python3
"""Run the semi-failure-analysis eval suite and print a pass/fail scorecard.

Checks, in order:
  1. every script in skills/semi-failure-analysis/scripts/ compiles and answers --help
  2. technique_selector.py on each of the 5 golden cases:
       - the case's discriminating technique(s) appear in an EARLY phase (P0/N0/N1/N2)
       - every destructive step carries a gate reference, and the gate step precedes it
       - case-specific ordering constraints (e.g. C-SAM strictly before any decap)
       - the single-sample preservation branch fires when sample_count == 1
  3. bin_signature.py on the case-4 wafer-sort data: the leakage bin must read spatially
     RANDOM and radially UNIFORM, must be confined to the post-tooling-change lot, and must
     be dominated by the I/O leakage test with a hard (far-outside-limit) excursion
  4. fa_report.py generates a complete 8D from the resolved case-1 record with zero gaps,
     and an incomplete case is correctly reported as a DRAFT with named gaps

Usage example:
  python run_evals.py
  python run_evals.py --json results.json

Exit codes: 0 all checks passed · 1 one or more checks failed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "semi-failure-analysis" / "scripts"
SAMPLES = ROOT / "sample-data" / "semi-failure-analysis"
WORK = Path(__file__).resolve().parent / "_run"

EARLY = {"P0", "N0", "N1", "N2"}

CASES = {
    "case1_eos_hotplug": {
        "label": "EOS from a hot-plug transient on a supply pin",
        "early": ["curve_trace", "external_visual"],
        "present": ["internal_optical", "fib_cross_section", "lock_in_thermography"],
        "single_sample": True,
        "before": [],
    },
    "case2_tddb_burnin": {
        "label": "TDDB gate-oxide failure emerging at burn-in",
        "early": ["burnin_delta_review", "emmi_backside"],
        "present": ["tem_lamella"],
        "single_sample": False,
        "before": [],
    },
    "case3_nsop_tempcycle": {
        "label": "Intermittent wire-bond NSOP surfacing in temperature cycling",
        "early": ["contact_elimination", "in_situ_tc_monitoring", "xray_2d"],
        "present": ["wire_pull_ball_shear", "mechanical_cross_section", "decap_plasma"],
        "single_sample": False,
        "before": [],
    },
    "case4_esd_hbm_cluster": {
        "label": "ESD (HBM) pin-leakage cluster after a probe-card / handling change",
        "early": ["bin_signature_analysis", "curve_trace", "emmi_frontside"],
        "present": ["fib_cross_section"],
        "single_sample": False,
        "before": [],
    },
    "case5_msl_popcorn": {
        "label": "MSL popcorn delamination after board reflow",
        "early": ["csam", "xray_2d"],
        "present": ["mechanical_cross_section"],
        "single_sample": False,
        "before": [("csam", "decap_chemical"), ("csam", "decap_plasma"),
                   ("csam", "decap_laser_assisted")],
    },
}

results: list[dict] = []


def check(name: str, ok: bool, detail: str) -> bool:
    results.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


# ------------------------------------------------------------------ 1. scripts
def check_scripts() -> None:
    print("\n== 1. scripts compile and answer --help ==")
    for p in sorted(SCRIPTS.glob("*.py")):
        c = run([sys.executable, "-m", "py_compile", str(p)])
        check(f"py_compile {p.name}", c.returncode == 0,
              "clean" if c.returncode == 0 else c.stderr.strip()[:200])
        h = run([sys.executable, str(p), "--help"])
        ok = h.returncode == 0 and "usage:" in h.stdout
        check(f"--help {p.name}", ok,
              f"{len(h.stdout.splitlines())} lines of usage" if ok else h.stderr.strip()[:200])


# ---------------------------------------------------------------- 2. selector
def check_selector() -> None:
    print("\n== 2. technique_selector.py on the 5 golden cases ==")
    WORK.mkdir(parents=True, exist_ok=True)
    for case, spec in CASES.items():
        print(f"\n-- {case}: {spec['label']}")
        out = WORK / f"{case}.plan.json"
        c = run([sys.executable, str(SCRIPTS / "technique_selector.py"),
                 "--case-file", str(SAMPLES / f"{case}.json"), "--output", str(out)])
        if not check(f"{case}: selector runs", c.returncode == 0, c.stderr.strip()[:200] or "exit 0"):
            continue
        plan = json.loads(out.read_text())
        steps = [s for s in plan["plan"] if s["kind"] == "technique"]
        phase_of = {s["id"]: s["phase"] for s in steps}
        order_of = {s["id"]: s["order"] for s in steps}

        for tid in spec["early"]:
            ph = phase_of.get(tid)
            check(f"{case}: '{tid}' present and EARLY",
                  ph in EARLY, f"phase={ph}" if ph else "NOT IN PLAN")
        for tid in spec["present"]:
            check(f"{case}: '{tid}' present in plan", tid in phase_of,
                  f"phase={phase_of.get(tid, 'ABSENT')}")

        destructive = [s for s in steps if s["destructive"] in ("D", "D-term")]
        ungated = [s["id"] for s in destructive if not s.get("requires_gate")]
        check(f"{case}: every destructive step is gated", not ungated,
              f"{len(destructive)} destructive step(s), {len(ungated)} ungated"
              + (f" -> {ungated}" if ungated else ""))

        gates = {s["id"]: s["order"] for s in plan["plan"] if s["kind"] == "gate"}
        bad = []
        for s in destructive:
            gid = f"GATE_{s['requires_gate']}"
            if gid not in gates or gates[gid] > s["order"]:
                bad.append(s["id"])
        check(f"{case}: gate step precedes each destructive step", not bad,
              f"gates={sorted(gates)} · violations={bad or 'none'}")

        for a, b in spec["before"]:
            if b in order_of:
                check(f"{case}: '{a}' strictly before '{b}'",
                      a in order_of and order_of[a] < order_of[b],
                      f"{a}@{order_of.get(a, '-')} vs {b}@{order_of[b]}")

        mode = plan["sample_plan"]["mode"]
        if spec["single_sample"]:
            check(f"{case}: single-sample preservation branch fires",
                  mode == "single_sample_preservation", f"mode={mode}")
            p0 = [s for s in plan["plan"] if s["phase"] == "P0"]
            check(f"{case}: P0 preservation steps emitted", len(p0) >= 5, f"{len(p0)} P0 steps")
        else:
            check(f"{case}: population sample plan chosen",
                  mode in ("small_population", "population"), f"mode={mode}")

        check(f"{case}: no plan-integrity defect reported",
              not any("PLAN DEFECT" in w for w in plan["warnings"]),
              f"{len(plan['warnings'])} warning(s), {len(plan['excluded'])} excluded technique(s)")


# ------------------------------------------------------------- 3. bin_signature
def check_bin_signature() -> None:
    print("\n== 3. bin_signature.py on the case-4 wafer-sort data ==")
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / "case4_bins"
    c = run([sys.executable, str(SCRIPTS / "bin_signature.py"),
             "--die-results", str(SAMPLES / "case4_die_results.csv"),
             "--tests", str(SAMPLES / "case4_tests.csv"),
             "--outdir", str(out)])
    if not check("case4: bin_signature runs", c.returncode == 0, c.stderr.strip()[:300] or "exit 0"):
        return
    res = json.loads((out / "bin_signature.json").read_text())

    b42 = next((b for b in res["bins"] if b["soft_bin"] == 42), None)
    if not check("case4: soft bin 42 analysed", b42 is not None, "leakage bin found"):
        return
    lots = sorted({w["lot_id"] for w in b42["per_wafer"]})
    check("case4: bin 42 confined to the post-change lot", lots == ["L2604"], f"lots={lots}")

    verdicts = [w["clustering"]["verdict"] for w in b42["per_wafer"]]
    check("case4: bin 42 spatially RANDOM (not clustered)",
          all(v == "random" for v in verdicts), f"verdicts={verdicts}")
    radial = [w["radial"]["verdict"] for w in b42["per_wafer"]]
    check("case4: bin 42 radially UNIFORM (no edge/center bias)",
          all(v == "uniform" for v in radial), f"verdicts={radial}")

    tests = b42.get("test_correlation", {}).get("tests", [])
    top = tests[0] if tests else None
    check("case4: bin 42 dominated by the I/O leakage test",
          bool(top) and top["test_num"] == 1050,
          f"top test = {top['test_num']} '{top['test_name']}' on "
          f"{top['dies_failing_this_test']}/{b42['test_correlation']['dies_with_test_data']} dies"
          if top else "no out-of-limit tests found")
    check("case4: leakage excursion reads HARD (far outside limit)",
          bool(top) and top["median_excursion_x_limit_range"] > 1.0,
          f"median excursion = {top['median_excursion_x_limit_range']}x the limit range · "
          f"{top['character']}" if top else "-")

    # Control bin: the assertion that matters is that the seeded background defectivity is never
    # mistaken for a spatial signature. Its per-wafer fail count is low enough that the adjacency
    # statistic legitimately returns `inconclusive_low_power` on some wafers - that is the power
    # guard working, and it must be accepted rather than silently called "random".
    b51 = next((b for b in res["bins"] if b["soft_bin"] == 51), None)
    if b51:
        v = [w["clustering"]["verdict"] for w in b51["per_wafer"]]
        r = [w["radial"]["verdict"] for w in b51["per_wafer"]]
        check("case4: background bin 51 never reads as a spatial signature (control)",
              all(x in ("random", "inconclusive_low_power", "dispersed") for x in v)
              and all(x == "uniform" for x in r),
              f"clustering={v} · radial={r}")

    kinds = {f["kind"] for f in res["findings"]}
    check("case4: ranked findings produced", len(res["findings"]) >= 3,
          f"{len(res['findings'])} findings, kinds={sorted(kinds)}")
    check("case4: PNG bin maps written", len(list(out.glob('binmap_*.png'))) == 4,
          f"{len(list(out.glob('binmap_*.png')))} maps")


# ------------------------------------------------------------------ 4. fa_report
def check_fa_report() -> None:
    print("\n== 4. fa_report.py ==")
    WORK.mkdir(parents=True, exist_ok=True)
    resolved = SAMPLES / "case1_eos_hotplug_resolved.json"
    for fmt in ("8d", "fa"):
        out = WORK / f"case1_{fmt}.md"
        c = run([sys.executable, str(SCRIPTS / "fa_report.py"), "--evidence", str(resolved),
                 "--format", fmt, "--out", str(out), "--strict"])
        body = out.read_text() if out.exists() else ""
        check(f"case1 resolved -> {fmt} report is complete (--strict exit 0)",
              c.returncode == 0, f"exit {c.returncode} · {len(body.splitlines())} lines")
        check(f"case1 {fmt}: no unfilled gap markers in the body",
              "NOT PROVIDED" not in body, "clean" if "NOT PROVIDED" not in body
              else f"{body.count('NOT PROVIDED')} gap marker(s)")
    d8 = (WORK / "case1_8d.md").read_text()
    for sec in ("## D0", "## D1", "## D2", "## D3", "## D4", "## D5", "## D6", "## D7", "## D8"):
        check(f"case1 8D: section {sec.strip('# ')} present", sec in d8, "found" if sec in d8 else "MISSING")
    check("case1 8D: escape point (second leg of root cause) rendered",
          "Escape point" in d8, "present")

    # an incomplete case must be reported as a draft, not silently filled in
    out = WORK / "case5_8d_draft.md"
    c = run([sys.executable, str(SCRIPTS / "fa_report.py"),
             "--evidence", str(SAMPLES / "case5_msl_popcorn.json"),
             "--format", "8d", "--out", str(out), "--strict"])
    body = out.read_text() if out.exists() else ""
    check("intake-only case is flagged DRAFT with named gaps (--strict exit 3)",
          c.returncode == 3 and "DRAFT" in body,
          f"exit {c.returncode} · {body.count('NOT PROVIDED')} gap markers named")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full results list to this path")
    args = ap.parse_args(argv)

    check_scripts()
    check_selector()
    check_bin_signature()
    check_fa_report()

    n = len(results)
    failed = [r for r in results if not r["pass"]]
    print("\n" + "=" * 70)
    print(f"RESULT: {n - len(failed)}/{n} checks passed")
    for r in failed:
        print(f"  FAILED: {r['check']} - {r['detail']}")
    print("=" * 70)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
