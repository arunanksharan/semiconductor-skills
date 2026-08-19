# Semiconductor Skills — Build Brief

**Created:** 2026-08-20 · **Owner:** Arunank (Kuzushi Labs)
**Purpose:** hand this file to a fresh Claude Code session to BUILD Claude Code skills for
semiconductor **wafer fabrication, packaging, failure analysis, and yield monitoring**.
The research below was done on 2026-08-20 — do not redo it; execute against it.

---

## How to use this file (instructions for the executing session)

1. Start Claude Code in this folder (`~/kuzushi_labs/semiconductor-skills/`).
2. Kickoff prompt (paste as-is):
   > Read BUILD_BRIEF.md fully. Build Skill 1 (`semi-yield-monitor`) end-to-end per §5.1:
   > scaffold, references, scripts with real parsers, sample data, and evals. Test it by
   > invoking the skill against the sample data. Stop and report before starting Skill 2.
3. Build order is §5: yield → failure analysis → packaging → fab process. One skill per
   session-block; each must pass its acceptance criteria before the next starts.
4. Rules of the road are §6 (licensing, no-NDA, verification duties). They are not optional.

---

## 1. Mission

Build a set of production-quality Claude Code skills that give an agent real judgment in
semiconductor manufacturing workflows. Two uses, in order:

1. **Portfolio/services asset for Kuzushi Labs** — "we build private Claude Code skills for
   semiconductor manufacturing teams" is an open, uncontested services offering (see §2:
   nobody has published these). Public repo = credibility + demo; private forks per client.
2. **Working tools** — each skill must actually run: parse real file formats, produce real
   analyses, not just talk methodology.

House precedent: `~/kuzushi_labs/robotics-hardware/.claude/skills/` already uses this exact
pattern for robotics (ISO-standard checklist-reviewers and builders, e.g.
`iso15066-biomechanical-limits-checklist-reviewer`, `robot-cell-layout-builder`). Mirror that
style: standards-grounded, reviewer/builder pairs, step-gated.

---

## 2. Research findings (2026-08-20) — the landscape

Verified via web search + GitHub code search over all public `SKILL.md` files
(~414 mention "wafer", ~3,776 mention "semiconductor").

**Verdict: green field.** No public Claude Code skill exists for wafer fab process
engineering, packaging/OSAT, or yield monitoring. Exactly one real failure-analysis skill
exists. Zero public SKILL.md files mention STDF, KLARF, wafer maps, or SECS/GEM.

| Domain | Public skill? | Closest existing thing |
|---|---|---|
| Wafer fab | ❌ | [industrial-laser-principles](https://github.com/victorzhu-eng/industrial-laser-principles) — step-gated DOE skills for laser ablation/dicing. **Best structural model to imitate.** |
| Packaging/OSAT | ❌ | Nothing (persona prompts only) |
| Failure analysis | ⚠️ one | `semiconductor-failure-analysis` in [zuohuadong/volt-gui](https://github.com/zuohuadong/volt-gui) (`.voltui/skills/semiconductor-failure-analysis/SKILL.md`) — solid symptom→mechanism→hypothesis→lab-flow framework; no scripts/parsers. Use as *structural reference only*; write our own content (license unverified). |
| Yield monitoring | ❌ | Generic SPC/Cpk skills ([asgard-ai algo-mfg-spc](https://github.com/asgard-ai-platform/skills), RBraga01 Quality-Engineering-Skills) — reusable substrate |

Adjacent signals worth knowing:
- **Anthropic is targeting this vertical** — [Claude Code for Semiconductor Teams AMA](https://www.anthropic.com/webinars/claude-code-for-semiconductor-teams) (Applied AI hardware team). Their pitch is MCP into engineering environments; skills on top is the open gap.
- Design/EDA-side skills exist and work ([vibe-ic](https://github.com/vibeic/vibe-ic) LVS triage, signoff loops) — proof the pattern holds for silicon workflows.
- Research blueprints (2026): [LLM planning agents for semiconductor FA](https://arxiv.org/abs/2506.15567) and [SemiFA — agentic multi-modal FA report generation](https://arxiv.org/html/2604.13236v1). Key design lesson from both: **the LLM produces plans, deterministic tools produce numbers.**
- The "semiconductor skills" that do exist are supply-chain *investing* analysts
  ([serenity-skill](https://github.com/BillyLu365/serenity-skill) family) and datasheet
  registries ([claude-skill-registry](https://github.com/majiayu000/claude-skill-registry)) —
  not competitors.
- Generic [FMEA skill](https://github.com/ddunnock/claude-plugins) (AIAG-VDA) exists — link to it, don't rebuild FMEA.

---

## 3. Skill anatomy (the three-layer rule)

Every skill here is three layers, with progressive disclosure:

```
skills/<skill-name>/
  SKILL.md          # frontmatter (name, description w/ trigger vocabulary) + the DECISION
                    # PROCEDURE — workflows, gates, output formats. Target < 500 lines.
  references/       # distilled domain knowledge, loaded on demand — taxonomies,
                    # technique matrices, standards digests. One topic per file.
  scripts/          # deterministic Python the agent RUNS — parsers, stats, renderers,
                    # report generators. Each with --help and a docstring example.
```

Design principles (non-negotiable):
- **Encode judgment, not textbook prose.** Value = decision procedures ("bin-7 spike confined
  to edge dies after chamber PM → check clamp ring / edge purge first"), selection matrices,
  ordered workflows with stop-gates. If a paragraph could be retrieved from Wikipedia, cut it.
- **Numbers come from scripts, never from the model.** The model chooses the analysis; Python
  computes it.
- **Step-gated:** destructive/expensive steps (in FA especially) require explicit confirmation
  of prior non-destructive evidence, mirroring the industrial-laser-principles pattern.
- **Every skill ships with sample data + an eval** (§5 per-skill). A skill without an eval is
  a draft.

---

## 4. Repo layout to create

```
semiconductor-skills/
  BUILD_BRIEF.md          # this file
  README.md               # public-facing: what these skills are, install, demo GIFs later
  skills/
    semi-yield-monitor/
    semi-failure-analysis/
    semi-packaging-qual/
    semi-fab-process/
  sample-data/            # synthetic STDF, sample wafer maps, KLARF snippets, WM-811K subset
  evals/                  # golden cases + EVALS.md scorecard per skill
```

Install for testing: symlink `skills/*` into `~/.claude/skills/`. Keep the repo the source
of truth. `git init` on day one; MIT license.

---

## 5. Build order & per-skill specs

### 5.1 Skill 1 — `semi-yield-monitor` (BUILD FIRST: public data, deterministic, clear value)

**Description/triggers:** yield analysis, wafer maps, bin pareto, STDF, KLARF, defect density,
commonality analysis, low-yield lot triage, SPC on yield.

**SKILL.md must encode:**
- Yield triage workflow: overall yield → bin pareto → wafer-level spread → spatial signature →
  lot/wafer/site commonality → parametric correlation → suspect-step shortlist.
- Wafer-map spatial-signature taxonomy → likely-cause table (edge ring → edge processes /
  clamp / bevel; scratch → handling/CMP; center cluster → dispense/spin; donut → chuck /
  temperature profile; repeating reticle pattern → litho/mask; random → baseline defectivity).
- Yield models and when each applies: Poisson, Murphy, negative binomial (cluster factor);
  die-size normalization; D0 extraction.
- SPC on yield: which chart for which metric, western-electric rules, when a shift is real.

**references/:** `wafer-map-signatures.md` · `yield-models.md` · `commonality-analysis.md` ·
`spc-for-yield.md` · `stdf-format-notes.md` (record types actually needed: FAR/MIR/PIR/PRR/
PTR/HBR/SBR/WIR/WRR).

**scripts/:** `stdf_summary.py` (lot/wafer/bin paretos from STDF), `wafermap_render.py`
(map → PNG + zonal stats), `spatial_signature.py` (rule-based zonal classifier v1; ML
optional later), `yield_models.py` (D0 fits, model comparison), `spc_charts.py`.
STDF parser: verify at build time and pick from `pystdf` / Semi-ATE `STDF` / alternatives —
whichever installs clean on Python 3.12+ (do not trust this brief; test).

**Data/evals:** WM-811K public dataset (811K labeled wafer maps, MIR Lab, mirrored on
Kaggle as `LSWMD.pkl`) — pull a stratified ~500-map subset into `sample-data/`; generate
synthetic STDF for at least 3 seeded scenarios (edge-ring lot, scratch wafer, healthy lot).
**Acceptance:** invoking the skill on each seeded scenario names the correct signature and
plausible cause; spatial classifier ≥80% on the WM-811K subset's labeled classes; all scripts
run from `--help` with zero setup beyond `pip install -r requirements.txt`.

### 5.2 Skill 2 — `semi-failure-analysis`

**Triggers:** failure analysis, FA request, bin signature, curve trace, EMMI, OBIRCH, decap,
RMA/customer return, 8D, root cause (electrical/package).

**SKILL.md must encode:** symptom intake template (what to ask for: ATE datalog, bin, Shmoo,
conditions, history) → failure-mechanism taxonomy (EOS/ESD, EM, TDDB, HCI/NBTI, latch-up,
opens/shorts, package-level: delam, wire, solder) → hypothesis table with evidence-for/against
→ **technique-selection matrix ordered by cost & destructiveness** (bench/curve trace → X-ray →
C-SAM → EMMI/OBIRCH/TDR → decap → FIB/SEM cross-section) with hard gates before each
destructive step → containment-vs-root-cause distinction → 8D / FA report generator.
Use the volt-gui skill and the SemiFA paper (§2) as structural references; write original text.

**scripts/:** `bin_signature.py` (shares STDF lib with skill 1), `fa_report.py` (evidence →
8D/FA markdown report), `technique_selector.py` (symptom class + package type → ordered plan).

**Evals:** ≥5 written case studies (from public FA literature, anonymized) as golden cases —
skill must produce the documented mechanism in its top-2 hypotheses.

### 5.3 Skill 3 — `semi-packaging-qual`

**Triggers:** package qualification, JEDEC, MSL, reliability test plan, wire bond, flip chip,
WLCSP, fan-out, delamination, C-SAM.

**SKILL.md must encode:** package-family selection tradeoffs → assembly flow + defect catalog
per step (dicing chipping, die-attach voiding, wire sweep, mold delam, NSOP/NSOL) → qual-plan
builder driven by JEDEC (JESD47 qual flows; JESD22-A104 TC, A110 HAST, A103 HTSL, A118 uHAST;
J-STD-020 MSL) → C-SAM/X-ray image interpretation checklist → MSL decision tree.
**JEDEC standards are free to download (registration)** — distill them into `references/`
digests (own words, cite clause numbers; do not copy text wholesale).

**scripts/:** `qual_plan.py` (device class + package + market → test matrix w/ sample sizes),
`msl_advisor.py`, `sample_size.py` (LTPD/AQL tables).

**Evals:** 3 seeded qual scenarios (automotive QFN, consumer WLCSP, industrial BGA) with
known-correct JEDEC test lists to match.

### 5.4 Skill 4 — `semi-fab-process` (LAST — most NDA-bound; ship the generic core only)

**Triggers:** process excursion, DOE, litho/etch/dep/implant/CMP issue, FDC, chamber matching,
SPC OOC on a tool parameter.

**SKILL.md must encode:** excursion-triage runbook (confirm metrology → scope lots/tools/time
→ commonality → hold decision → containment → root cause) → per-module common failure modes
(generic, textbook-grade: May & Spanos level) → DOE builder (screening → RSM; factor
selection discipline; confounding checks) → chamber-matching methodology.
**Explicit boundary note in the skill:** recipe- and tool-specific knowledge is fab-proprietary;
this skill carries methodology, the client fork carries their BKMs. This is the services hook.

**scripts/:** `doe_builder.py` (statsmodels/pyDOE3 — verify lib), `spc_charts.py` (shared),
`commonality.py` (lots × tools × time pivot from a CSV of lot history).

**Evals:** 2 seeded excursion scenarios (single-chamber etch drift; metrology false alarm) —
skill must scope correctly and NOT recommend a hold in the false-alarm case.

---

## 6. Guardrails (binding)

1. **No proprietary/NDA content, ever.** Public sources only: JEDEC (free), textbooks
   (May & Spanos *Fundamentals of Semiconductor Manufacturing and Process Control*; Sze),
   arXiv, vendor app notes. SEMI and the EDFAS Desk Reference are **paywalled — summarize
   concepts from secondary sources; never reproduce.**
2. **License hygiene:** volt-gui skill = structural inspiration only (license unverified);
   WM-811K — check and honor its dataset license before redistributing any subset in-repo
   (if redistribution is disallowed, ship a `fetch_wm811k.py` downloader instead).
3. **Verify every library and dataset claim in this brief at build time** (STDF parsers,
   pyDOE3, WM-811K location). The brief is a map, not ground truth.
4. **Each skill ends with its eval passing and a one-paragraph honest status** (what's solid,
   what's thin, what needs a domain expert pass). Arunank reviews between skills.
5. Skills must also degrade gracefully: with no data files provided, they interview the user
   and produce a plan — never fabricate numbers.

## 7. Definition of done (first session)

- [ ] Repo scaffolded per §4, git initialized, MIT license, README stub
- [ ] `semi-yield-monitor` complete per §5.1 acceptance criteria
- [ ] `evals/EVALS.md` records the eval run with actual numbers
- [ ] Status report: solid / thin / needs-expert, and what Skill 2 needs from Arunank
