# FA report and 8D templates — what belongs in each section, and how to word it

Load at Step 7 of `SKILL.md`, when reviewing someone else's FA report, and before answering any customer
request for an 8D. `scripts/fa_report.py` renders these skeletons from an evidence JSON; this file is the
authority on what each section must contain and on the language rules. A section you cannot fill is
declared empty here, with a reason — it is never silently dropped.

## 1. Which container, and how they relate

| Deliverable | Audience | Contains | Owner |
|---|---|---|---|
| FA lab report | Engineering, internal quality, sometimes the customer's engineer | Evidence: what was received, what was done in what order, what was seen, what it means, what stayed unresolved | FA lab |
| 8D | Customer, supplier quality, automotive programs | The containment-and-correction narrative built around that evidence | Quality / program owner |

The FA lab report is **the evidence that fills D4**, not a substitute for the 8D; the 8D is the
customer-facing container, not a substitute for the analysis. Automotive customers ask for 8D by default
because their own problem-solving and corrective-action obligations (the problem-solving and
error-proofing requirements of IATF 16949, plus customer-specific requirements layered on top) push the
format down the supply chain. JEDEC JESD671 covers the same ground for component quality problems, and
VDA's 8D volume and the original Ford Global 8D / TOPS material are the usual reference points. Cite
them by name; do not reproduce them.

5-Why and Ishikawa are **tools used inside D4**, not the root cause itself: a 5-Why chain is only as good
as the physical evidence on each link, and an untested Ishikawa is a brainstorm. FMEA belongs to a
separate generic skill — reference it for the D7 prevention actions, do not rebuild it here.

## 2. The 8D disciplines

| D | What actually goes in it | Most common way it is done badly | Example line |
|---|---|---|---|
| D0 Symptom & emergency response | The reported symptom in measurable terms, when and where it surfaced, and any immediate action taken before a team existed | Skipped entirely, or used to record an early root-cause guess | "2026-06-10: customer incoming test reports 3/500 units of PN 1234 failing standby supply current. Emergency response: stop shipment of the two suspect date codes, request 5 failing + 5 passing units." |
| D1 Team | Named people with functions, the champion who can authorize action, and who signs | A list of departments with no names, no owner, and nobody from the failing process step | "FA lead (name) · product/test engineer (name) · OSAT assembly process owner (name) · quality champion (name) · customer SQE as recipient." |
| D2 Problem description | Is/is-not with quantities (§3) plus the failure signature from `bin-signature-analysis.md`, bounding the affected population | Repeating the customer's sentence back; "intermittent failures observed" with no counts, dates or boundaries | "12/4,800 units from date codes 2624–2626 fail test 1420 IDDQ_STBY at 25 C and 125 C; 2621–2623 and 2627+ do not; no functional or speed fails; first seen 2026-06-10." |
| D3 Interim containment | The action protecting the customer now, its effectivity point, its verification, and its exit criterion | Waiting for root cause before containing; containment with no effectivity date, no proof it works, no exit | "100 % IDDQ screen at 125 C at final test for date codes 2624–2626, effective lot AB1234; 3 escapes caught in 6,000 screened; exits when D6 validation closes." |
| D4 Root cause | Both legs (§4): the mechanism that made the part fail **and** the escape that let it ship | Only the mechanism, so the detection gap is never fixed; a 5-Why terminating at "operator error"; "consistent with" quietly promoted to "caused by" | "Occurrence: charged-device-model-type ESD event at handler insertion — EMMI site at the I/O pad-ring clamp, damage character per `esd-eos-discrimination.md`. Escape: IDDQ tested only at 25 C, where the path sits inside the limit." |
| D5 Chosen permanent corrective actions | The selected action for **each** leg, the alternatives rejected and why, and the predicted effect with how it will be measured | A wish list with no owners or dates; actions only for the occurrence leg; no decision record | "Occurrence: replace handler tray material and add a verified ground path at the insert. Escape: add hot IDDQ at final test, limit re-derived from post-change data. Rejected: screen-only — does not remove the source." |
| D6 Implement & validate | Implementation date and lot, plus evidence the action worked and introduced no new failure mode | "Implemented on <date>" with no data; validation run on the same units used to find the problem | "Implemented 2026-07-02 from lot AC0101. Validation: 5 consecutive lots, 0 hot IDDQ fails (n = 24,000); handler charge measurements within control limits across 3 audits." |
| D7 Prevent recurrence | Systemic reach — what else shares this weakness (products, lines, sites, package types) — and which document, checklist, FMEA or control plan changes | Closing with "operator retrained"; fixing one line while four others keep the same handler | "Same handler model runs 4 other products — audit all. Add handler ESD verification to the equipment-qual checklist; require hot IDDQ in the test-limit procedure; update the process FMEA detection ranking." |
| D8 Close & recognize | Formal closure with the customer, the archive pointer (case ID, imagery, raw data, remaining samples), and recognition of the team | Closed while D6 validation is still pending; evidence archived nowhere; sample disposition unrecorded | "Closed 2026-07-20 with customer acceptance. Evidence archived under FA-2026-0142; 2 units retained, 1 consumed, remainder returned 2026-07-18." |

Ordering discipline: D3 needs only the **signature**, so it starts while D4 is still open; D5 is not
written until D4 has both legs; D8 is not written until D6 has data. An 8D that reaches D8 in one sitting
is a form, not an investigation.

## 3. D2 — the is/is-not table

| Dimension | Is | Is not |
|---|---|---|
| What (part, rev, test, bin) | Failing part number, program rev, soft bin, first-failing test | Similar parts, other bins, the tests that pass |
| Where (step, site, pin, die location, customer plant) | Where it is detected and where on the device | Steps, sites and pins that see no fails |
| When (first seen, date codes, insertion, life stage) | The window containing all confirmed fails | The adjacent windows that are clean |
| How big (count, rate, DPPM, trend) | Quantities with denominators and a trend direction | The population that did not fail |
| How detected (who found it, at which insertion) | Customer incoming, final test, burn-in, field | The screens that should have caught it and did not — this feeds D4's escape leg |

The is-not column is the one that gets skipped, and it is where the discrimination lives: an "is"
without a matching "is not" leaves the problem unbounded, so containment over-scopes and root cause
under-tests. Fill the boundaries even where the honest entry is "not yet known" — written that way it
becomes a data request instead of a gap.

## 4. D4 — the two-legged root cause

| Leg | Question it answers | Evidence it needs | Cost of skipping it |
|---|---|---|---|
| Occurrence | Why did the part become defective? | The physical mechanism, localized and imaged where possible, plus the process, event or wearout path that produced it | Nothing is fixed; the defect keeps being made |
| Escape | Why did test, inspection or screening not catch it before shipment? | The specific coverage, limit, condition or sampling gap that let it through — measured, not assumed | You ship the next one even after the occurrence is fixed |

Each leg gets its own D5 action and its own D6 validation. Attach the §7 confidence level to the
mechanism call: if it is only "consistent with", say so in D4 and state what would raise it. An 8D built
on an over-claimed D4 collapses at the customer's first technical challenge.

## 5. FA lab report skeleton

| § | Section | Must contain |
|---|---|---|
| 1 | Header / traceability | Case ID · requester and organization · date opened · device part number and rev · date code / lot / wafer / assembly site · unit serials · quantity received · **sample condition as received** (packaging, ESD protection, loose or board-mounted, visible damage) · chain-of-custody log (§8) |
| 2 | Request / complaint | The requester's own words, verbatim and marked as verbatim, plus their stated conditions and application |
| 3 | Summary of findings | Three to eight lines: what failed, mechanism call with confidence, escape point if known, and what was not determined. Written last; must read standalone |
| 4 | Electrical verification | Did it reproduce — on what equipment, at what conditions, which program rev; the full insertion log including recoveries; curve-trace pin map versus known-good; Shmoo versus known-good |
| 5 | Analysis sequence | Every step **in the order performed**: technique · equipment and conditions (energy, magnification, chemistry, time, temperature — the parameters worth recording per technique are in `technique-matrix.md`) · unit serial · result, including steps that found nothing |
| 6 | Imagery inventory | Every figure numbered with the caption rule below; note which images were taken before each irreversible step |
| 7 | Conclusion | Primary mechanism + confidence + the evidence chain; secondary mechanism where honest; escape point where the data supports one |
| 8 | Not determined | What could not be established and **why** (sample consumed, no localization achieved, unit powered since failure, application conditions unavailable) |
| 9 | Sample disposition | Per serial: consumed · retained · returned · archived, with dates and storage location |
| 10 | Recommendations | Split into containment, corrective action, and further analysis; each marked as needing or not needing more evidence |
| 11 | Appendix | Raw datalogs, script outputs, full technique parameters, references consulted |

Caption rule for every image, no exceptions: **unit serial · technique · magnification or scale bar ·
what the reader should see**. An image without a scale is decoration; an image without a serial cannot be
tied to the case; an "after" image with no "before" of the same field documents nothing and destroyed
something.

## 6. Language discipline

| Intent | Wording | Requires |
|---|---|---|
| Direct evidence | "observed" · "measured" · "imaged" | The artifact exists and is in the report |
| Inference from evidence | "consistent with" · "indicates" | At least one alternative considered and addressed in the text |
| Alternative not excluded | "cannot be excluded" | You state what evidence would exclude it |
| Technique found nothing | "no anomaly detected by <technique> at <resolution/sensitivity>" | The detection limit is stated |
| Unwitnessed overstress | "electrically induced physical damage" — the neutral industry wording | Damage character and energy reasoning; see `esd-eos-discrimination.md` |
| Never | "caused by the customer" · "abuse" · "operator error" · "mishandled in the field" | Attribution is a commercial conclusion, not an FA one |

A negative result is a result. "C-SAM detected no delamination at the die attach or die front side at the
system's resolution" narrows the hypothesis set *and* proves the step was performed; deleting it implies
the technique was never run and invites the customer to ask for it again. Report the null, and report its
sensitivity so nobody reads it as stronger than it is.

Tense discipline: what was done in past tense, what is inferred in the present. Keep interpretation out of
§5 — results there, meaning in §7.

## 7. Confidence rubric

| Confidence | Evidence required | Allowed wording |
|---|---|---|
| High | Site localized by an independent technique · physical evidence imaged at that site · electrical signature matching the mechanism · competing hypotheses killed in writing · reproduced on ≥2 units or corroborated by a population signature | "The failure mechanism is X, observed at <site>" |
| Medium | Electrical signature plus a physical anomaly at a plausible site, but single unit, or site not independently localized, or one credible alternative still open | "consistent with X" — and name the open alternative |
| Low | Electrical signature only, or a physical anomaly that cannot be tied to the failing net | "the evidence is consistent with X and with Y; not resolved — resolving requires <test>" |
| None / NFF | Did not reproduce | "not reproduced under conditions A–N (matrix attached); no mechanism call" |

Single-unit cases cap at medium, always. One unit supports "consistent with"; it cannot support a
population statement, a failure rate, or any claim about the process that made it.

## 8. Customer returns and RMA specifics

Open the chain of custody at intake, before the first electrical test, and carry it as a table in §1:

| Date/time | From | To | Purpose | Condition & packaging | Operator |
|---|---|---|---|---|---|

**Photograph as received before anything else**: outer packaging, ESD bag and its condition, unit top and
bottom, markings and date code legible, leads/balls, and the board if the unit arrives mounted. Once a
unit has been powered, cleaned, desoldered or baked the as-received state is gone and cannot be
reconstructed — those photos are the only record that the damage was not created in your lab. Record
moisture handling for the same reason: baking a returned unit erases moisture history and can create the
delamination you later "find".

State plainly, in §9 and in the conclusion: which units were consumed, which destructive step was
performed on which serial, what remains, and where it is stored. A customer who sends parts back is
entitled to know exactly what happened to them.

Where the customer's application conditions could not be reproduced, write it as a bounded statement:
what was requested, what the lab could apply, what gap remains, and what that gap prevents you from
concluding. "Could not be reproduced" without that boundary reads as "the customer is wrong" — which is
unsupported, and the fastest way to lose access to the next data set you need.

## 9. Report anti-patterns

1. **Single-hypothesis narrative** — one story told forward, no alternatives considered or killed.
2. **Conclusion with no imaged or measured support** — a mechanism named in §7 that appears nowhere in §4–§6.
3. **Containment presented as root cause** — "we screened the suspect date codes" is D3, never D4.
4. **Blame** — any sentence assigning commercial fault (§6).
5. **Missing escape leg** — D4 explains the defect and never asks why test passed it.
6. **Photos without scale, serial or orientation**, or an "after" with no "before".
7. **A buried retest recovery** — recoveries belong in §4 with the insertion log, not in a footnote.
8. **Silent gaps** — sections dropped because they were empty instead of declared empty with a reason.
9. **Unbounded quantities** — percentages without denominators, "several units", "occasionally".

*Grounding: 8D structure as used across the automotive and component supply chain (VDA's 8D volume; the
Ford Global 8D / TOPS lineage; IATF 16949 problem-solving and error-proofing requirements) and JEDEC
JESD671 for component quality problem analysis and corrective action; FA reporting practice as described
in EDFAS-community literature and ISTFA proceedings. Summarized in our own words; no standard text is
reproduced, and every example line is invented for illustration.*
