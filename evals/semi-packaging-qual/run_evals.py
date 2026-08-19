#!/usr/bin/env python3
"""Eval harness for semi-packaging-qual: diff qual_plan.py output against golden expectations.

For each golden file in golden/*.expected.json this:
  1. runs `qual_plan.py --scenario <sample-data scenario> --format json` as a SUBPROCESS
     (so the real CLI is under test, not an importable shortcut),
  2. checks the emitted test-id set against expected_test_ids and forbidden_test_ids,
  3. checks scalar plan fields (dotted paths) against expected_plan_fields,
  4. checks per-row conditions (standard/condition/duration/readpoints substrings, sample
     size, lot count, accept number, applicability) against expected_rows,
  5. checks plan-note and out-of-scope keywords.

It also runs `sample_size.py --self-check` so the LTPD numbers underneath the sample-size
column are verified in the same pass.

Exit code 0 only if every scenario and the LTPD self-check pass.

Usage examples:
  python run_evals.py
  python run_evals.py --verbose
  python run_evals.py --scenario consumer_wlcsp_new --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPTS = os.path.join(REPO, "skills", "semi-packaging-qual", "scripts")
SAMPLE_DATA = os.path.join(REPO, "sample-data", "semi-packaging-qual")
GOLDEN_DIR = os.path.join(HERE, "golden")


def dotted(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return KeyError(path)
        cur = cur[part]
    return cur


def run_plan(scenario_file: str) -> dict:
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "qual_plan.py"),
         "--scenario", scenario_file, "--format", "json"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("qual_plan.py failed ({}):\n{}".format(proc.returncode, proc.stderr))
    return json.loads(proc.stdout)


def check_scenario(golden: dict) -> dict:
    scenario_path = os.path.join(SAMPLE_DATA, golden["scenario_file"])
    failures: list[str] = []
    checks = 0

    if not os.path.exists(scenario_path):
        return {"scenario": golden["scenario"], "pass": False, "checks": 0,
                "failures": ["scenario input file missing: " + scenario_path],
                "produced_test_ids": []}

    plan = run_plan(scenario_path)
    ids = [r["id"] for r in plan["matrix"]]
    rows = {r["id"]: r for r in plan["matrix"]}

    # 1. expected / forbidden test ids
    for tid in golden["expected_test_ids"]:
        checks += 1
        if tid not in ids:
            failures.append("MISSING expected test '{}'".format(tid))
    for tid in golden["forbidden_test_ids"]:
        checks += 1
        if tid in ids:
            failures.append("FORBIDDEN test '{}' appeared in the matrix".format(tid))
    extra = sorted(set(ids) - set(golden["expected_test_ids"]))
    checks += 1
    if extra:
        failures.append("UNEXPECTED test id(s) not in the golden set: {}".format(extra))

    # 2. scalar plan fields
    for path, want in golden.get("expected_plan_fields", {}).items():
        checks += 1
        got = dotted(plan, path)
        if isinstance(got, KeyError):
            failures.append("field '{}' not present in the plan".format(path))
        elif got != want:
            failures.append("field '{}': expected {!r}, got {!r}".format(path, want, got))

    # 3. per-row conditions
    for tid, want in golden.get("expected_rows", {}).items():
        if tid not in rows:
            continue  # already reported as MISSING above
        row = rows[tid]
        for key, expect in want.items():
            checks += 1
            if key.endswith("_contains"):
                field = key[: -len("_contains")]
                actual = row.get(field) or ""
                if expect.lower() not in str(actual).lower():
                    failures.append(
                        "row '{}' field '{}' does not contain {!r} (got {!r})".format(
                            tid, field, expect, str(actual)[:110]))
            else:
                if row.get(key) != expect:
                    failures.append("row '{}' field '{}': expected {!r}, got {!r}".format(
                        tid, key, expect, row.get(key)))

    # 4. plan notes / out-of-scope keywords
    notes_blob = " ".join(plan.get("plan_notes", [])).lower()
    for kw in golden.get("expected_note_keywords", []):
        checks += 1
        if kw.lower() not in notes_blob:
            failures.append("plan notes never mention {!r}".format(kw))
    oos_blob = json.dumps(plan.get("out_of_scope", [])).lower()
    for kw in golden.get("expected_out_of_scope_keywords", []):
        checks += 1
        if kw.lower() not in oos_blob:
            failures.append("out-of-scope section never mentions {!r}".format(kw))

    # 5. structural invariants every plan must satisfy
    checks += 1
    if not plan.get("verify_block"):
        failures.append("plan has no verify block (SKILL.md operating rule 2)")
    checks += 1
    if any(r["applicability"] == "conditional" and "todo" not in
           ((r.get("note") or "") + (r.get("standard") or "")).lower()
           for r in plan["matrix"]):
        bad = [r["id"] for r in plan["matrix"] if r["applicability"] == "conditional"
               and "todo" not in ((r.get("note") or "") + (r.get("standard") or "")).lower()]
        failures.append("conditional row(s) without a TODO to resolve: {}".format(bad))

    return {"scenario": golden["scenario"], "title": golden["title"],
            "pass": not failures, "checks": checks, "failures": failures,
            "produced_test_ids": ids,
            "lots": plan["novelty"]["lots"],
            "env_units": plan["summary"]["env_leg_units_total"],
            "ltpd_pct": plan["summary"]["env_leg_ltpd_pct_at_90"],
            "rows": plan["summary"]["rows"]}


def run_ltpd_selfcheck() -> dict:
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "sample_size.py"), "--self-check", "--json"],
        capture_output=True, text=True)
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {"pass": False, "checks": []}
    payload["returncode"] = proc.returncode
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", help="run only this scenario name")
    ap.add_argument("--verbose", action="store_true", help="print the produced test-id list")
    ap.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = ap.parse_args(argv)

    goldens = []
    for path in sorted(glob.glob(os.path.join(GOLDEN_DIR, "*.expected.json"))):
        with open(path) as fh:
            g = json.load(fh)
        if args.scenario and g["scenario"] != args.scenario:
            continue
        goldens.append(g)
    if not goldens:
        print("no golden files matched", file=sys.stderr)
        return 2

    results = [check_scenario(g) for g in goldens]
    ltpd = run_ltpd_selfcheck()
    overall = all(r["pass"] for r in results) and bool(ltpd.get("pass"))

    if args.json:
        print(json.dumps({"pass": overall, "scenarios": results, "ltpd_self_check": ltpd},
                         indent=2))
        return 0 if overall else 1

    print("=" * 78)
    print("semi-packaging-qual eval run")
    print("=" * 78)
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        print("\n[{}] {}  -  {}".format(mark, r["scenario"], r.get("title", "")))
        print("      checks: {}   rows: {}   lots: {}   env units: {}   leg LTPD: {} %".format(
            r["checks"], r.get("rows"), r.get("lots"), r.get("env_units"), r.get("ltpd_pct")))
        if args.verbose:
            print("      produced: {}".format(", ".join(r["produced_test_ids"])))
        for f in r["failures"]:
            print("      - {}".format(f))

    print("\n[{}] sample_size.py LTPD self-check ({} checks)".format(
        "PASS" if ltpd.get("pass") else "FAIL", len(ltpd.get("checks", []))))
    for c in ltpd.get("checks", []):
        got = c.get("computed_pct", c.get("computed"))
        exp = c.get("expected_pct", c.get("expected"))
        print("      [{}] {:<40} expected {}  computed {}".format(
            "PASS" if c["pass"] else "FAIL", c["check"], exp, got))

    print("\n" + "=" * 78)
    print("OVERALL: {}  ({}/{} scenarios passed)".format(
        "PASS" if overall else "FAIL",
        sum(1 for r in results if r["pass"]), len(results)))
    print("=" * 78)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
