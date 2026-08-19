# Package families — selection tradeoffs and feasibility limits

Own-words engineering digest. Values marked *typical* are industry-common envelopes, not
vendor specs — confirm against the chosen OSAT's design rules.

## Feasibility quick-limits (eliminate families fast)

| Family | I/O envelope (typical) | Pitch floor (typical) | Power envelope | Body sizes |
|---|---|---|---|---|
| QFN/DFN | 8–100+ (peripheral) | 0.35–0.5 mm lead pitch | ≤~3 W (exposed pad, good board) | 1×1–12×12 mm |
| QFP | 32–256 (peripheral) | 0.4–0.8 mm | ≤~2 W (no pad) | 5×5–28×28 mm |
| PBGA (wire bond) | 100–~900 (area array) | 0.8–1.27 mm ball | ~2–5 W | 15–40 mm |
| FCBGA | 400–5000+ | 0.8–1.0 mm ball, bump pitch 100–150 µm (Cu pillar to ~40 µm) | 5–>200 W (lid/heat sink) | 15–75 mm |
| FCCSP | 50–400 | 0.4–0.5 mm ball | 1–3 W | ≤12 mm |
| WLCSP | die-limited (≤~200 practical) | 0.35–0.5 mm ball | ≤~1–2 W | = die size, practical ≤~6×6 mm |
| Fan-out (FOWLP/InFO-class) | 100–1000 | 0.35–0.4 mm ball, RDL L/S to 2/2 µm class | 1–5 W (higher with TIV/stacking) | die+fan-out ring |
| 2.5D (Si interposer) / 3D stack | 10k+ die-to-die | µbump 40–55 µm, hybrid bond <10 µm | high, but stacked-die thermal is the constraint | reticle-class interposers |

## Tradeoff matrix (expanded)

| Axis | QFN | QFP | PBGA | FCBGA | WLCSP | FOWLP | 2.5D/3D |
|---|---|---|---|---|---|---|---|
| Cost (relative) | 1 | 1.2 | 1.5 | 3–6 | 1 @small die | 2–3 | 8+ |
| Thermal (θJA class) | good w/ pad via farm | poor | fair (thermal balls) | best (die-back path) | fair (heat into board) | fair-good | hardest |
| Electrical (parasitics) | good (short wires) | worst (long leads/wires) | fair | excellent (bumps) | excellent | excellent (short RDL) | excellent |
| Board-level TC | excellent | good | good | fair (body CTE vs FR4) | weak beyond ~4–5 mm body | fair-good | fair |
| Drop (handheld) | excellent | good | good | fair | weakest — needs corner support/underfill data | fair | n/a usually |
| Inspectability of joints | X-ray needed (bottom pads) | visual (gull-wing) | X-ray | X-ray | X-ray | X-ray | X-ray |
| Rework on board | hard | easy | moderate | moderate-hard | hard | hard | practically no |
| Die shrink tolerance | high | high | high | medium (bump map redo) | **none** — new package each shrink, re-qual | medium (RDL absorbs) | high |
| Time-to-first-sample | days-weeks | days-weeks | weeks | months (substrate lead time) | weeks (wafer-level) | weeks-months | months |

## Family-specific risk lists (feed Workflow 3 risk coverage)

**QFN** — exposed-pad solder voiding on board (thermal spec erosion); pad delam if PCB pad
design poor; lead-flank solderability after singulation (cut copper face) → wettable-flank
option for automotive AOI. Cover with: board-level void X-ray spec, solderability J-STD-002,
precon + C-SAM.

**QFP** — long-wire sweep at mold, lead coplanarity/handling damage, corner-lead solder
opens. Cover: X-ray sweep metric, coplanarity scan, lead fatigue (bend) test.

**PBGA (wire bond)** — mold-to-substrate delam, via-in-pad outgassing voids, substrate
moisture (MSL 3+ typical), ball drop/shear. Cover: precon at target MSL + C-SAM interfaces,
ball shear (JESD22-B117), TC with readpoints.

**FCBGA** — bump fatigue vs underfill choice, die-corner ULK delam ("white bump" history at
assembly), substrate warpage → HIP/non-wet at board mount, lid adhesive delam (thermal path).
Cover: TC + C-SAM at die corners, shadow-moiré warpage vs temp, board-level TC, SAM of lid line.

**WLCSP** — board-level TC and drop are *the* wear-out modes (joint = full stress); UBM/RDL
cracking; backside chip from thin wafers; MSL1 typical (no organics to soak) but polymer
repassivation still audit-worthy. Cover: JESD22-B111 drop, board-level TC (IPC-9701-style),
die-strength monitor, ball shear.

**FOWLP** — die shift vs RDL alignment (yield, not reliability), mold-RDL delam, warpage of
reconstituted wafer → coplanarity, board-level TC of large fan-out ratios. Cover: precon +
C-SAM, board-level TC/drop if handheld, coplanarity.

**2.5D/3D** — µbump/hybrid-bond integrity under TC, interposer cracking, stacked-die thermal
gradients, known-good-die economics. Qual is bespoke — this skill's generic matrix is a
starting scaffold only; state that explicitly when asked.

## Selection interview (ask in this order)

1. I/O count and pitch after fanout? (kills/keeps half the table immediately)
2. Power and thermal path available on the board? (exposed pad? heatsink allowed?)
3. End product: handheld/wearable (drop), automotive (grade, vibration), infrastructure (lifetime)?
4. Die roadmap: shrink expected within package lifetime?
5. Cost ceiling per unit at volume? NRE tolerance (substrate design, new tooling)?
6. Board constraints: rework needed? visual inspection required (medical/aero often want leads)?
7. Schedule: substrate lead times acceptable?

Then write the decision record: constraints → surviving families → choice → top-3 risks +
covering tests.
