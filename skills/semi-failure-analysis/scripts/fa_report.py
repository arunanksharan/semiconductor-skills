#!/usr/bin/env python3
"""Render an 8D or FA lab report (markdown) from a case evidence JSON.

The script NEVER invents content. Any field you did not supply is rendered as an explicit
gap marker and listed in the completeness audit at the end of the report and on stdout.
Section semantics: references/report-templates.md.

Evidence JSON schema (all keys optional; unknown keys are ignored):

{
  "case_id": "FA-2026-0142",
  "title": "...",
  "status": "open|closed",
  "opened": "2026-08-05", "closed": "2026-08-19",
  "requester": {"name": "...", "org": "...", "contact": "..."},
  "device": {"part_number": "...", "description": "...", "package": "...",
             "date_code": "...", "assembly_lot": "...", "wafer_lot": "...",
             "assembly_site": "...", "test_program_rev": "..."},
  "samples": [{"serial": "...", "role": "sequence|archive|confirmation|reference",
               "condition_as_received": "...", "disposition": "..."}],
  "chain_of_custody": [{"date": "...", "from": "...", "to": "...",
                        "action": "...", "operator": "..."}],
  "complaint": "requester's description, verbatim",
  "problem": {"what": "", "is_not": "", "where": "", "when": "",
              "how_many": "", "since": ""},
  "symptoms": {"symptom_class": "", "failure_rate": "", "conditions": ""},
  "selector_input": { ... consumed by technique_selector.py ... },
  "observations": [{"phase": "N0", "technique": "curve_trace", "unit": "SN0007",
                    "conditions": "...", "result": "...", "interpretation": "...",
                    "date": "...", "image": "fig1.png"}],
  "hypotheses": [{"hypothesis": "", "evidence_for": "", "evidence_against": "",
                  "discriminating_test": "", "status": "active|retired|confirmed",
                  "cost": "low / ND"}],
  "mechanism": {"primary": "", "confidence": "high|medium|low", "basis": "",
                "secondary": "", "not_determined": ""},
  "escape_point": "why the existing test/inspection did not catch it",
  "team": [{"name": "", "role": ""}],
  "d0_emergency_response": "...",
  "containment": [{"action": "", "owner": "", "due": "", "status": "",
                   "verification": ""}],
  "corrective_actions": [{"action": "", "owner": "", "due": "", "verification": ""}],
  "validation": ["evidence the fix works"],
  "prevention": ["systemic / read-across actions"],
  "recommendations": ["..."],
  "limitations": ["what could not be determined and why"],
  "images": [{"file": "", "unit": "", "technique": "", "scale": "", "caption": ""}]
}

Usage example:
  python fa_report.py --evidence case1_eos_hotplug.json --format 8d --out 8d_report.md
  python fa_report.py --evidence case1_eos_hotplug.json --format fa --out fa_report.md

Exit codes: 0 report written · 2 bad input · 3 --strict and required content missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

VERSION = "0.1.0"

GAP = "**NOT PROVIDED** - required before this report can be issued."

# section key -> (human label, which format requires it)
REQUIRED = {
    "case_id": ("case identifier", "both"),
    "device": ("device / traceability block", "both"),
    "complaint": ("requester's complaint", "both"),
    "samples": ("sample inventory", "both"),
    "observations": ("analysis sequence with results", "both"),
    "hypotheses": ("competing hypothesis table", "both"),
    "mechanism": ("mechanism call with confidence and basis", "both"),
    "problem": ("D2 is / is-not problem description", "8d"),
    "team": ("D1 team", "8d"),
    "containment": ("D3 interim containment", "8d"),
    "escape_point": ("D4 escape point (second leg of root cause)", "8d"),
    "corrective_actions": ("D5 permanent corrective actions", "8d"),
    "validation": ("D6 implementation and validation evidence", "8d"),
    "prevention": ("D7 systemic prevention / read-across", "8d"),
    "limitations": ("what could not be determined and why", "fa"),
}

CONFIDENCE_RUBRIC = {
    "high": "physical evidence at a localized site, consistent with the electrical signature, "
            "and competing hypotheses retired with named evidence",
    "medium": "physical or strong electrical evidence, but at least one competing hypothesis "
              "is not fully excluded",
    "low": "circumstantial or electrical evidence only; no confirming physical observation",
}


# ---------------------------------------------------------------- small helpers
def g(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur or cur[k] in (None, "", [], {}):
            return default
        cur = cur[k]
    return cur


def val(x, gap=GAP):
    if x in (None, "", [], {}):
        return gap
    return x


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return [f"> {GAP}", ""]
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") if c not in (None, "") else "-"
                 for c in r]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return out


def bullets(items, gap=GAP) -> list[str]:
    if not items:
        return [f"> {gap}", ""]
    out = []
    for it in items:
        out.append(f"- {it}" if not isinstance(it, dict) else
                   "- " + " · ".join(f"**{k}**: {v}" for k, v in it.items() if v))
    out.append("")
    return out


def audit(ev: dict, fmt: str) -> list[str]:
    gaps = []
    for key, (label, applies) in REQUIRED.items():
        if applies not in ("both", fmt):
            continue
        if not ev.get(key):
            gaps.append(f"{key} - {label}")
    return gaps


# ------------------------------------------------------------------ traceability
def traceability_block(ev: dict) -> list[str]:
    dev = ev.get("device") or {}
    req = ev.get("requester") or {}
    rows = [
        ["Case ID", val(ev.get("case_id"))],
        ["Title", val(ev.get("title"))],
        ["Status", val(ev.get("status"), "open")],
        ["Opened / closed", f"{val(ev.get('opened'), '-')} / {val(ev.get('closed'), '-')}"],
        ["Requester", " · ".join(x for x in [req.get("name"), req.get("org"), req.get("contact")] if x)
         or GAP],
        ["Part number", val(dev.get("part_number"))],
        ["Description", val(dev.get("description"), "-")],
        ["Package", val(dev.get("package"))],
        ["Date code / assembly lot", f"{val(dev.get('date_code'), '-')} / "
                                     f"{val(dev.get('assembly_lot'), '-')}"],
        ["Wafer lot", val(dev.get("wafer_lot"), "-")],
        ["Assembly site", val(dev.get("assembly_site"), "-")],
        ["Test program rev", val(dev.get("test_program_rev"), "-")],
        ["Report generated", date.today().isoformat()],
    ]
    return table(["Field", "Value"], rows)


def samples_block(ev: dict) -> list[str]:
    rows = [[s.get("serial", "-"), s.get("role", "-"),
             s.get("condition_as_received", "-"), s.get("disposition", "-")]
            for s in (ev.get("samples") or [])]
    out = table(["Serial", "Role", "Condition as received", "Disposition"], rows)
    n = len(ev.get("samples") or [])
    if n == 1:
        out.append("> Single-sample case: the preservation protocol was in force. Imagery is the "
                   "archive; every destructive step below was irreversible for the whole "
                   "investigation.")
        out.append("")
    return out


def custody_block(ev: dict) -> list[str]:
    rows = [[c.get("date", "-"), c.get("from", "-"), c.get("to", "-"),
             c.get("action", "-"), c.get("operator", "-")]
            for c in (ev.get("chain_of_custody") or [])]
    if not rows:
        return ["> No chain-of-custody log supplied. For a customer return this is a gap that "
                "must be closed before the report is issued.", ""]
    return table(["Date", "From", "To", "Action", "Operator"], rows)


def observations_block(ev: dict) -> list[str]:
    obs = ev.get("observations") or []
    rows = [[i, o.get("phase", "-"), o.get("technique", "-"), o.get("unit", "-"),
             o.get("conditions", "-"), o.get("result", "-"), o.get("interpretation", "-")]
            for i, o in enumerate(obs, 1)]
    out = table(["#", "Phase", "Technique", "Unit", "Conditions", "Observed result",
                 "Interpretation"], rows)
    destructive = [o for o in obs if str(o.get("phase", "")).startswith("D")]
    if destructive:
        out.append(f"> {len(destructive)} destructive step(s) were performed. Each required its "
                   f"gate to be cleared and its expected outcomes pre-registered "
                   f"(see references/technique-matrix.md).")
        out.append("")
    nulls = [o for o in obs if "no anomaly" in str(o.get("result", "")).lower()
             or "not detected" in str(o.get("result", "")).lower()]
    if nulls:
        out.append(f"> {len(nulls)} technique(s) returned a null result. Null results are reported, "
                   f"not omitted - they retire hypotheses.")
        out.append("")
    return out


def hypotheses_block(ev: dict) -> list[str]:
    hyps = ev.get("hypotheses") or []
    rows = [[h.get("hypothesis", "-"), h.get("status", "-"), h.get("evidence_for", "-"),
             h.get("evidence_against", "-"), h.get("discriminating_test", "-")]
            for h in hyps]
    out = table(["Hypothesis", "Status", "Evidence for", "Evidence against",
                 "Discriminating test"], rows)
    if hyps and len(hyps) < 2:
        out.append("> Only one hypothesis was recorded. A single-hypothesis narrative is a report "
                   "anti-pattern; record the strongest alternative and the evidence that retired it.")
        out.append("")
    retired = [h for h in hyps if h.get("status") == "retired"]
    if hyps and not retired:
        out.append("> No hypothesis was retired in writing. State which evidence killed each "
                   "alternative, or the conclusion is unfalsifiable.")
        out.append("")
    return out


def mechanism_block(ev: dict) -> list[str]:
    m = ev.get("mechanism") or {}
    conf = (m.get("confidence") or "").lower()
    out = []
    out.append(f"**Failure mechanism (primary):** {val(m.get('primary'))}")
    out.append("")
    out.append(f"**Confidence:** {val(conf, GAP)}"
               + (f" - rubric: {CONFIDENCE_RUBRIC[conf]}" if conf in CONFIDENCE_RUBRIC else ""))
    out.append("")
    out.append(f"**Basis (evidence chain):** {val(m.get('basis'))}")
    out.append("")
    if m.get("secondary"):
        out.append(f"**Secondary / contributing:** {m['secondary']}")
        out.append("")
    if m.get("not_determined"):
        out.append(f"**Not determined:** {m['not_determined']}")
        out.append("")
    out.append("*Language note: \"observed\" marks direct evidence, \"consistent with\" marks "
               "inference. Mechanism is what this lab can determine; commercial attribution is "
               "not an FA conclusion.*")
    out.append("")
    return out


def images_block(ev: dict) -> list[str]:
    rows = [[im.get("file", "-"), im.get("unit", "-"), im.get("technique", "-"),
             im.get("scale", "-"), im.get("caption", "-")]
            for im in (ev.get("images") or [])]
    out = table(["File", "Unit", "Technique", "Scale / mag", "Caption"], rows)
    missing = [im for im in (ev.get("images") or [])
               if not im.get("scale") or not im.get("unit")]
    if missing:
        out.append(f"> {len(missing)} image(s) lack a unit serial or a scale bar. Both are required "
                   f"before issue.")
        out.append("")
    return out


# ------------------------------------------------------------------- renderers
def render_fa(ev: dict) -> str:
    L: list[str] = []
    L.append(f"# Failure Analysis Report - {val(ev.get('case_id'), 'CASE ID NOT PROVIDED')}")
    L.append("")
    L.append(f"*{val(ev.get('title'), 'title not provided')}*")
    L.append("")
    L.append("## 1. Traceability")
    L += traceability_block(ev)
    L.append("## 2. Samples received")
    L += samples_block(ev)
    L.append("## 3. Chain of custody")
    L += custody_block(ev)
    L.append("## 4. Request / complaint (as received)")
    L.append(f"> {val(ev.get('complaint'))}")
    L.append("")
    s = ev.get("symptoms") or {}
    L += table(["Field", "Value"], [
        ["Symptom class", val(s.get("symptom_class"))],
        ["Failure rate / population", val(s.get("failure_rate"))],
        ["Conditions at failure", val(s.get("conditions"))],
    ])
    L.append("## 5. Summary of findings")
    L += mechanism_block(ev)
    L.append("## 6. Analysis sequence and results")
    L.append("Performed in order. Non-destructive work precedes destructive work; each destructive "
             "step sat behind its gate.")
    L.append("")
    L += observations_block(ev)
    L.append("## 7. Competing hypotheses")
    L += hypotheses_block(ev)
    L.append("## 8. Imagery inventory")
    L += images_block(ev)
    L.append("## 9. What could not be determined")
    L += bullets(ev.get("limitations"),
                 gap="No limitations recorded. Every FA has them - state them, or the report "
                     "overclaims.")
    L.append("## 10. Recommendations")
    L += bullets(ev.get("recommendations"))
    L.append("## 11. Sample disposition")
    disp = [f"{s.get('serial','?')}: {s.get('disposition','disposition not recorded')}"
            for s in (ev.get("samples") or [])]
    L += bullets(disp)
    L.append("## Appendix - completeness audit")
    L += audit_block(ev, "fa")
    return "\n".join(L)


def render_8d(ev: dict) -> str:
    L: list[str] = []
    L.append(f"# 8D Report - {val(ev.get('case_id'), 'CASE ID NOT PROVIDED')}")
    L.append("")
    L.append(f"*{val(ev.get('title'), 'title not provided')}*")
    L.append("")
    L += traceability_block(ev)

    L.append("## D0 - Symptom and emergency response")
    L.append(f"**Reported symptom:** {val(ev.get('complaint'))}")
    L.append("")
    s = ev.get("symptoms") or {}
    L += table(["Field", "Value"], [
        ["Symptom class", val(s.get("symptom_class"))],
        ["Failure rate / population", val(s.get("failure_rate"))],
        ["Conditions at failure", val(s.get("conditions"))],
    ])
    L.append(f"**Emergency response actions:** {val(ev.get('d0_emergency_response'), 'None recorded.')}")
    L.append("")

    L.append("## D1 - Team")
    L += table(["Name", "Role"],
               [[t.get("name", "-"), t.get("role", "-")] for t in (ev.get("team") or [])])

    L.append("## D2 - Problem description (is / is-not, with quantities)")
    p = ev.get("problem") or {}
    L += table(["Dimension", "IS", "IS NOT"], [
        ["What", val(p.get("what")), val(p.get("is_not"), "-")],
        ["Where", val(p.get("where"), "-"), "-"],
        ["When", val(p.get("when"), "-"), "-"],
        ["How many", val(p.get("how_many"), "-"), "-"],
        ["Since", val(p.get("since"), "-"), "-"],
    ])
    L.append("> D2 is quantified or it is not D2. A problem description without counts, dates and "
             "a boundary (what does NOT fail) cannot scope containment.")
    L.append("")

    L.append("## D3 - Interim containment")
    L.append("Containment needs only the failure **signature**, not the mechanism. It is not a "
             "root cause and must never be reported as one.")
    L.append("")
    L += table(["Action", "Owner", "Due", "Status", "Verification"],
               [[c.get("action", "-"), c.get("owner", "-"), c.get("due", "-"),
                 c.get("status", "-"), c.get("verification", "-")]
                for c in (ev.get("containment") or [])])

    L.append("## D4 - Root cause (two legs)")
    L.append("### 4a. Failure mechanism - why the part failed")
    L += mechanism_block(ev)
    L.append("### 4b. Escape point - why it was not caught")
    L.append(f"> {val(ev.get('escape_point'))}")
    L.append("")
    L.append("### 4c. Evidence")
    L += observations_block(ev)
    L.append("### 4d. Competing hypotheses considered")
    L += hypotheses_block(ev)

    L.append("## D5 - Chosen permanent corrective actions")
    L += table(["Action", "Owner", "Due", "Verification of effectiveness"],
               [[c.get("action", "-"), c.get("owner", "-"), c.get("due", "-"),
                 c.get("verification", "-")] for c in (ev.get("corrective_actions") or [])])
    L.append("> Each action must address a leg of D4. An action that maps to neither the mechanism "
             "nor the escape point is housekeeping, not corrective action.")
    L.append("")

    L.append("## D6 - Implementation and validation")
    L += bullets(ev.get("validation"),
                 gap="No validation evidence supplied. D6 closes on evidence, not on intent.")

    L.append("## D7 - Prevention and read-across")
    L += bullets(ev.get("prevention"),
                 gap="No systemic action recorded. D7 asks what ELSE in the system carries this "
                     "weakness - other products, sites, packages, or test programs.")

    L.append("## D8 - Closure")
    L.append(f"**Status:** {val(ev.get('status'), 'open')}  ·  "
             f"**Closed:** {val(ev.get('closed'), '-')}")
    L.append("")
    L += bullets(ev.get("recommendations"), gap="No closing recommendations recorded.")
    L.append("### Sample disposition")
    L += bullets([f"{s.get('serial','?')}: {s.get('disposition','disposition not recorded')}"
                  for s in (ev.get("samples") or [])])
    L.append("### Limitations")
    L += bullets(ev.get("limitations"),
                 gap="No limitations recorded. State what could not be determined and why.")

    L.append("## Appendix - chain of custody")
    L += custody_block(ev)
    L.append("## Appendix - imagery inventory")
    L += images_block(ev)
    L.append("## Appendix - completeness audit")
    L += audit_block(ev, "8d")
    return "\n".join(L)


def audit_block(ev: dict, fmt: str) -> list[str]:
    gaps = audit(ev, fmt)
    out = []
    if not gaps:
        out.append("All required sections are populated. Content quality still needs a human "
                   "reviewer - completeness is not correctness.")
        out.append("")
    else:
        out.append(f"**{len(gaps)} required section(s) are empty. This report is a DRAFT and must "
                   f"not be issued to a customer until they are closed:**")
        out.append("")
        out += [f"- `{gp}`" for gp in gaps]
        out.append("")
    out.append(f"*Generated by fa_report.py v{VERSION} from the supplied evidence JSON. No content "
               f"was inferred or invented; every empty field is marked above.*")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--evidence", required=True, help="case evidence JSON path")
    ap.add_argument("--format", choices=("8d", "fa"), default="8d",
                    help="8d = customer-facing 8D container · fa = FA lab report (default 8d)")
    ap.add_argument("--out", help="write markdown here (default: stdout)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 3 if any required section is missing")
    args = ap.parse_args(argv)

    try:
        ev = json.loads(Path(args.evidence).read_text())
    except Exception as e:  # noqa: BLE001
        print(f"error: cannot read --evidence: {e}", file=sys.stderr)
        return 2
    if not isinstance(ev, dict):
        print("error: evidence JSON must be an object", file=sys.stderr)
        return 2

    md = render_8d(ev) if args.format == "8d" else render_fa(ev)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md + "\n")
        print(f"wrote {p} ({len(md.splitlines())} lines, format={args.format})")
    else:
        print(md)

    gaps = audit(ev, args.format)
    if gaps:
        print(f"\ncompleteness audit: {len(gaps)} required section(s) missing:", file=sys.stderr)
        for gp in gaps:
            print(f"  - {gp}", file=sys.stderr)
        if args.strict:
            return 3
    else:
        print("\ncompleteness audit: all required sections populated "
              "(completeness is not correctness - a human must review the content).",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
