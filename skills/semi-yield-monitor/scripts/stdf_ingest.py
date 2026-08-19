#!/usr/bin/env python3
"""STDF v4 -> canonical die_results.csv, with a data-integrity report.

STDF parsing needs an OPTIONAL third-party library. This script tries, in
order, pystdf then Semi-ATE STDF, and if neither is importable it prints
install hints and the CSV schema to export instead. It never raises on a
missing library and it never invents data.

Records consumed (see references/data-formats.md):
  FAR  file/CPU/version header — endianness sanity
  MIR  lot id, part type, job (test program) name and revision, tester, temp
  WIR  wafer id + start time     WRR  wafer summary counts (the reconciliation key)
  PIR  part start                PRR  part result: X, Y, HARD_BIN, SOFT_BIN, PART_FLG
  PTR  parametric test result (optional --ptr-out)
  HBR  hard-bin summary          SBR  soft-bin summary

The integrity report is the gate for Workflow 1 step 1. It checks:
  * PRR count vs WRR PART_CNT, and PRR passes vs WRR GOOD_CNT, per wafer
  * PRR-derived hard-bin counts vs the HBR summary records
  * PART_FLG fail bit vs the "hard bin 1 == pass" convention (disagreement
    means one of the two is lying; find out which before trusting any yield)
  * repeated (wafer, x, y) coordinates, i.e. retest/rebin in the datalog
  * dies with no wafer context (PRR outside any WIR/WRR pair)

Exit codes: 0 ok · 2 usage/parse error · 3 no STDF backend installed.

Usage examples:
  python stdf_ingest.py --check
  python stdf_ingest.py --input lot.stdf --out die_results.csv
  python stdf_ingest.py --input lot.stdf --out die_results.csv --ptr-out params.csv
  python stdf_ingest.py --input lot.stdf --lot-id L1234 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

WANTED = {"FAR", "MIR", "WIR", "WRR", "PIR", "PRR", "PTR", "HBR", "SBR", "MRR"}

NO_BACKEND_MSG = """\
No STDF parsing library is available in this Python environment.

FIX 1 — install a parser (either one works; both are pure Python, MIT/GPL-compatible
licenses, and neither is required by the rest of this skill):

    pip install pystdf                 # import pystdf         (verified 1.3.4)
    pip install Semi-ATE-STDF          # import Semi_ATE.STDF  (verified)

Then re-run this script unchanged.

FIX 2 — skip STDF entirely. Every other script in this skill reads a plain CSV.
Export from your test-data system (Examinator, yieldWerx, Galaxy, TDR, or your
tester's own datalog converter) and save one row per die with EXACTLY these
columns and this header:

    lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag

    lot_id     string, the lot identifier (STDF MIR.LOT_ID)
    wafer_id   string, unique within the lot (STDF WIR.WAFER_ID)
    die_x      integer column index (STDF PRR.X_COORD)
    die_y      integer row index    (STDF PRR.Y_COORD)
    hard_bin   integer (STDF PRR.HARD_BIN); 1 = pass by convention
    soft_bin   integer (STDF PRR.SOFT_BIN)
    pass_flag  1 = passing die, 0 = failing die

Rules for a clean export: one row per probed die, no aggregation, keep failing
dies (a map with only passing dies is useless), keep the original bin numbers
(do not remap), and state whether retests were collapsed to the final result.

Then run: python yield_summary.py --input die_results.csv
"""


# ---------------------------------------------------------------- backends

def _try_pystdf():
    try:
        from pystdf.IO import Parser  # noqa: F401
    except ImportError:
        return None

    def parse(path, max_parts=None):
        from pystdf.IO import Parser
        recs = []
        stop = {"n": 0}

        class Sink:
            def after_send(self, data_source, data):
                rec_type, fields = data
                name = rec_type.name.split(".")[-1].upper()
                if name not in WANTED:
                    return
                if name == "PRR":
                    stop["n"] += 1
                    if max_parts and stop["n"] > max_parts:
                        return
                recs.append((name, dict(zip(rec_type.fieldNames, fields))))

        with open(path, "rb") as fh:
            p = Parser(inp=fh)
            p.addSink(Sink())
            p.parse()
        return recs

    return ("pystdf", parse)


def _try_semi_ate():
    try:
        from Semi_ATE.STDF.utils import records_from_file  # noqa: F401
    except ImportError:
        return None

    def parse(path, max_parts=None):
        from Semi_ATE.STDF.utils import records_from_file
        recs, n_prr = [], 0
        for rec in records_from_file(str(path)):
            name = str(getattr(rec, "id", type(rec).__name__)).upper()
            if name not in WANTED:
                continue
            if name == "PRR":
                n_prr += 1
                if max_parts and n_prr > max_parts:
                    continue
            fields = {}
            for fname in rec.fields:
                if fname in ("REC_LEN", "REC_TYP", "REC_SUB"):
                    continue
                try:
                    fields[fname] = rec.get_value(fname)
                except Exception:
                    fields[fname] = None
            recs.append((name, fields))
        return recs

    return ("Semi-ATE-STDF", parse)


def pick_backend():
    for probe in (_try_pystdf, _try_semi_ate):
        got = probe()
        if got:
            return got
    return None


# ---------------------------------------------------------------- helpers

def bitfield(v) -> int:
    """Normalize a B1 field to an int. pystdf gives an int; Semi-ATE gives an
    8-char MSB-first bit list."""
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, (bytes, bytearray)):
        return v[0] if v else 0
    if isinstance(v, (list, tuple)) and len(v) == 8:
        return int("".join(str(b) for b in v), 2)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def text(v, default="") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def num(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- reduction

def reduce_records(recs, lot_override):
    st = {
        "backend_records": Counter(),
        "far": {}, "mir": {},
        "hbr": {}, "sbr": {},
        "wafers": {},            # wafer_id -> {"wrr": {...}, "n_prr": int, "n_pass": int}
        "rows": [],              # canonical die rows
        "ptrs": [],
        "orphan_prr": 0,
        "flag_bin_disagree": 0,
        "invalid_bin_flag": 0,
    }
    wafer = None
    pending_ptr = []

    for name, f in recs:
        st["backend_records"][name] += 1
        if name == "FAR":
            st["far"] = {"cpu_type": num(f.get("CPU_TYPE")), "stdf_ver": num(f.get("STDF_VER"))}
        elif name == "MIR":
            st["mir"] = {k.lower(): text(f.get(k)) for k in
                         ("LOT_ID", "PART_TYP", "JOB_NAM", "JOB_REV", "TSTR_TYP",
                          "NODE_NAM", "TST_TEMP", "SBLOT_ID", "OPER_NAM", "PROC_ID")}
        elif name == "WIR":
            wafer = text(f.get("WAFER_ID"), f"W{len(st['wafers']) + 1}")
            st["wafers"].setdefault(wafer, {"wrr": {}, "n_prr": 0, "n_pass": 0})
        elif name == "WRR":
            wid = text(f.get("WAFER_ID"), wafer or "")
            ent = st["wafers"].setdefault(wid, {"wrr": {}, "n_prr": 0, "n_pass": 0})
            ent["wrr"] = {k.lower(): num(f.get(k)) for k in
                          ("PART_CNT", "GOOD_CNT", "RTST_CNT", "ABRT_CNT", "FUNC_CNT")}
            wafer = None
        elif name == "PTR":
            pending_ptr.append(f)
        elif name == "PRR":
            if wafer is None:
                st["orphan_prr"] += 1
                wafer = "UNKNOWN"
                st["wafers"].setdefault(wafer, {"wrr": {}, "n_prr": 0, "n_pass": 0})
            hb = num(f.get("HARD_BIN"))
            sb = num(f.get("SOFT_BIN"), hb)
            x, y = num(f.get("X_COORD")), num(f.get("Y_COORD"))
            flg = bitfield(f.get("PART_FLG"))
            failed_flag = bool(flg & 0x08)
            if flg & 0x10:                       # bit 4: bin data invalid
                st["invalid_bin_flag"] += 1
            failed_bin = (hb != 1) if hb is not None else failed_flag
            if failed_flag != failed_bin:
                st["flag_bin_disagree"] += 1
            pf = 0 if failed_flag else 1
            lot = lot_override or text(st["mir"].get("lot_id"), "LOT1")
            st["rows"].append((lot, wafer, x, y, hb, sb, pf))
            ent = st["wafers"][wafer]
            ent["n_prr"] += 1
            ent["n_pass"] += pf
            for p in pending_ptr:
                st["ptrs"].append((lot, wafer, x, y, num(p.get("TEST_NUM")),
                                   text(p.get("TEST_TXT")), p.get("RESULT"),
                                   text(p.get("UNITS")), p.get("LO_LIMIT"), p.get("HI_LIMIT")))
            pending_ptr = []
        elif name == "PIR":
            pending_ptr = []
        elif name in ("HBR", "SBR"):
            key = "HBIN_NUM" if name == "HBR" else "SBIN_NUM"
            cnt = "HBIN_CNT" if name == "HBR" else "SBIN_CNT"
            head = num(f.get("HEAD_NUM"), 255)
            b, c = num(f.get(key)), num(f.get(cnt), 0)
            if b is None:
                continue
            # head 255 is the all-heads summary; prefer it, else accumulate per head
            tgt = st["hbr"] if name == "HBR" else st["sbr"]
            if head == 255:
                tgt[b] = c
            else:
                tgt[b] = tgt.get(b, 0) + c
    return st


def integrity(st) -> list[dict]:
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    ver = st["far"].get("stdf_ver")
    add("FAR present and v4", ver == 4,
        f"STDF_VER={ver}, CPU_TYPE={st['far'].get('cpu_type')}" if st["far"] else "no FAR record")
    add("MIR lot id present", bool(st["mir"].get("lot_id")),
        f"lot_id={st['mir'].get('lot_id')!r} job={st['mir'].get('job_nam')!r} "
        f"rev={st['mir'].get('job_rev')!r}")

    add("MRR present (file closed cleanly)", st["backend_records"].get("MRR", 0) > 0,
        "MRR found" if st["backend_records"].get("MRR") else
        "no MRR — the datalog was never closed. Truncated or aborted file; counts below "
        "may cover only part of the lot.")

    no_wrr = [w for w, e in st["wafers"].items() if not e["wrr"]]
    add("every wafer has a WRR summary", not no_wrr,
        "all wafers have WRR" if not no_wrr else
        f"no WRR for {no_wrr} — nothing to reconcile these wafers against")

    bad = [w for w, e in st["wafers"].items()
           if e["wrr"].get("part_cnt") not in (None, e["n_prr"])]
    add("PRR count == WRR.PART_CNT", not bad,
        "all wafers reconcile" if not bad else
        "; ".join(f"{w}: {st['wafers'][w]['n_prr']} PRR vs PART_CNT "
                  f"{st['wafers'][w]['wrr'].get('part_cnt')}" for w in bad))

    badg = [w for w, e in st["wafers"].items()
            if e["wrr"].get("good_cnt") not in (None, e["n_pass"])]
    add("PRR passes == WRR.GOOD_CNT", not badg,
        "all wafers reconcile" if not badg else
        "; ".join(f"{w}: {st['wafers'][w]['n_pass']} pass vs GOOD_CNT "
                  f"{st['wafers'][w]['wrr'].get('good_cnt')}" for w in badg))

    if st["hbr"]:
        obs = Counter(r[4] for r in st["rows"])
        diff = {b: (obs.get(b, 0), c) for b, c in st["hbr"].items() if obs.get(b, 0) != c}
        add("PRR hard bins == HBR summary", not diff,
            "all bins reconcile" if not diff else
            "; ".join(f"bin {b}: {o} PRR vs {c} HBR" for b, (o, c) in sorted(diff.items())))
    else:
        add("PRR hard bins == HBR summary", True, "no HBR records to compare (not an error)")

    add("PART_FLG agrees with 'hard bin 1 == pass'", st["flag_bin_disagree"] == 0,
        f"{st['flag_bin_disagree']} PRR(s) disagree. Resolve before trusting any yield "
        "number: either the pass bin is not 1 on this program, or PART_FLG is unset."
        if st["flag_bin_disagree"] else "0 disagreements")

    add("no 'bin data invalid' flags", st["invalid_bin_flag"] == 0,
        f"{st['invalid_bin_flag']} PRR(s) have PART_FLG bit 4 set")

    dup = Counter((r[1], r[2], r[3]) for r in st["rows"])
    ndup = sum(1 for k, v in dup.items() if v > 1)
    add("no repeated (wafer, x, y)", ndup == 0,
        f"{ndup} coordinate(s) appear more than once — retest/rebin is in this datalog. "
        "Decide first-pass vs final-result before computing yield."
        if ndup else "every die appears once")

    add("every PRR inside a WIR/WRR pair", st["orphan_prr"] == 0,
        f"{st['orphan_prr']} PRR(s) with no wafer context" if st["orphan_prr"]
        else "wafer context complete")
    return checks


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", help="STDF v4 file to read")
    ap.add_argument("--out", help="write canonical die_results.csv here")
    ap.add_argument("--ptr-out", help="write parametric (PTR) results to this CSV")
    ap.add_argument("--lot-id", help="override MIR.LOT_ID in the output")
    ap.add_argument("--max-parts", type=int, help="stop after N parts (quick look)")
    ap.add_argument("--check", action="store_true",
                    help="report which STDF backend is available, then exit")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    backend = pick_backend()

    if args.check:
        if backend:
            print(f"STDF backend available: {backend[0]}")
        else:
            print("STDF backend available: NONE\n")
            print(NO_BACKEND_MSG)
        return 0

    if not args.input:
        ap.error("--input is required (or use --check)")
    if backend is None:
        print(NO_BACKEND_MSG, file=sys.stderr)
        return 3

    name, parse = backend
    try:
        recs = parse(args.input, args.max_parts)
    except FileNotFoundError:
        print(f"ERROR: no such file: {args.input}", file=sys.stderr)
        return 2
    except Exception as exc:                       # a bad STDF must not traceback
        print(f"ERROR: {name} failed to parse {args.input}: "
              f"{type(exc).__name__}: {exc}\n"
              "The file may be truncated, gzipped, or not STDF v4. Check the first "
              "four bytes for a FAR record, and try the other backend "
              "(pip install Semi-ATE-STDF / pip install pystdf).", file=sys.stderr)
        return 2

    st = reduce_records(recs, args.lot_id)
    if not st["rows"]:
        print(f"ERROR: {args.input} parsed but contained no PRR records — no die results "
              "to extract. Confirm this is a wafer-sort datalog, not a summary-only file.",
              file=sys.stderr)
        return 2

    checks = integrity(st)
    n = len(st["rows"])
    n_pass = sum(r[6] for r in st["rows"])
    wafers = {w: {"dies": e["n_prr"], "passed": e["n_pass"],
                  "yield_pct": round(100 * e["n_pass"] / e["n_prr"], 2) if e["n_prr"] else None,
                  "wrr": e["wrr"]}
              for w, e in st["wafers"].items()}

    if args.out:
        with open(args.out, "w") as fh:
            fh.write("lot_id,wafer_id,die_x,die_y,hard_bin,soft_bin,pass_flag\n")
            for r in st["rows"]:
                fh.write(",".join("" if v is None else str(v) for v in r) + "\n")
    if args.ptr_out:
        with open(args.ptr_out, "w") as fh:
            fh.write("lot_id,wafer_id,die_x,die_y,test_num,test_txt,result,units,"
                     "lo_limit,hi_limit\n")
            for r in st["ptrs"]:
                fh.write(",".join("" if v is None else str(v) for v in r) + "\n")

    out = {
        "backend": name, "input": args.input,
        "records": dict(sorted(st["backend_records"].items())),
        "mir": st["mir"], "far": st["far"],
        "dies": n, "passed": n_pass, "yield_pct": round(100 * n_pass / n, 2),
        "wafers": wafers,
        "hard_bin_counts": dict(sorted(Counter(r[4] for r in st["rows"]).items(),
                                       key=lambda kv: -kv[1])),
        "hbr_summary": dict(sorted(st["hbr"].items())),
        "sbr_summary": dict(sorted(st["sbr"].items())),
        "integrity": checks,
        "integrity_ok": all(c["status"] == "PASS" for c in checks),
        "die_results_csv": args.out, "ptr_csv": args.ptr_out,
        "ptr_rows": len(st["ptrs"]),
    }
    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"backend: {name}   file: {args.input}")
    print(f"records: {out['records']}")
    print(f"lot {out['mir'].get('lot_id')!r}  part {out['mir'].get('part_typ')!r}  "
          f"program {out['mir'].get('job_nam')!r} rev {out['mir'].get('job_rev')!r}  "
          f"tester {out['mir'].get('tstr_typ')!r}  temp {out['mir'].get('tst_temp')!r}")
    print(f"dies {n}  passed {n_pass}  yield {out['yield_pct']}%")
    print(f"\n{'wafer':<12}{'dies':<8}{'passed':<9}{'yield%':<9}WRR part/good")
    for w, e in wafers.items():
        wrr = e["wrr"]
        print(f"{w:<12}{e['dies']:<8}{e['passed']:<9}{e['yield_pct']:<9}"
              f"{wrr.get('part_cnt')}/{wrr.get('good_cnt')}")
    print("\nDATA-INTEGRITY REPORT (Workflow 1 step 1 gate):")
    for c in checks:
        print(f"  [{c['status']}] {c['check']}: {c['detail']}")
    if not out["integrity_ok"]:
        print("\nAt least one check FAILED. Do not report a yield number from this file "
              "until the failure is explained — a reconciliation error means the datalog "
              "and the summary records disagree about what happened.")
    if args.out:
        print(f"\nwrote {args.out} ({n} rows)")
    if args.ptr_out:
        print(f"wrote {args.ptr_out} ({len(st['ptrs'])} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
