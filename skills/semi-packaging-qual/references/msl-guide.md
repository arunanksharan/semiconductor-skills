# MSL guide — classification, floor life, bake recovery

Framework: J-STD-020 (classification) + J-STD-033 (handling, packing, use). Own-words
digest; current revisions govern.

## Why MSL exists

Plastic packages absorb moisture. At reflow, absorbed water flashes to steam; vapor pressure
+ weakened adhesion → "popcorn" cracking and interface delamination. MSL = how long a package
may sit out of its dry-pack before mounting.

## Levels and floor life (J-STD-020 table, own words)

| MSL | Floor life (out of bag) | Condition |
|---|---|---|
| 1 | Unlimited | ≤30 °C / 85 %RH |
| 2 | 1 year | ≤30 °C / 60 %RH |
| 2a | 4 weeks | ≤30 °C / 60 %RH |
| 3 | 168 h | ≤30 °C / 60 %RH |
| 4 | 72 h | ≤30 °C / 60 %RH |
| 5 | 48 h | ≤30 °C / 60 %RH |
| 5a | 24 h | ≤30 °C / 60 %RH |
| 6 | Mandatory bake before use; mount within time-on-label | ≤30 °C / 60 %RH |

Floor-life clock starts at bag-open, pauses in dry storage (<10 %RH cabinet or re-bagged
with fresh desiccant), resets only after a qualified bake.

## Pb-free classification reflow peak (J-STD-020 thickness × volume table)

Package **body** thickness × volume → classification peak (the temp used in precon reflows):

| Thickness \ Volume | <350 mm³ | 350–2000 mm³ | >2000 mm³ |
|---|---|---|---|
| <1.6 mm | 260 °C | 260 °C | 260 °C |
| 1.6–2.5 mm | 260 °C | 250 °C | 245 °C |
| ≥2.5 mm | 250 °C | 245 °C | 245 °C |

(SnPb legacy table is lower — 220/225/240 °C class; only relevant for legacy lines.)
Classification is at the peak the *body* sees; tolerance per standard. If the customer's
process peak exceeds the classified peak → re-classify at the higher peak.

## Classification flow (new package or re-classification trigger)

1. Sample from ≥1 lot (3 lots for a new package family is better practice); serialize.
2. Electrical + time-zero C-SAM (all critical interfaces).
3. Bake dry (125 °C, 24 h typical) → weigh (dry weight).
4. Soak at candidate level: L1 85 °C/85 %RH 168 h · L2 85/60 168 h · L2a 30/60 696 h ·
   L3 30/60 192 h · L4 30/60 96 h · L5 30/60 72 h · L5a 30/60 48 h (accelerated-equivalent
   soaks exist in the standard — record which one was used).
5. 3× reflow at classification peak within the standard's timing envelope.
6. Electrical + C-SAM vs time zero + external visual (cracks).
7. Pass → that level (try the next-better level if desired). Fail → next level down, fresh
   samples.

**Fail definition:** external crack, electrical fail, or delamination change on critical
interfaces (active die face, wire-bonded periphery, any interface the standard flags for the
package construction). Die-attach delam judged per construction — thermal/electrical-path
products fail on it.

## Typical starting points by family (expectation-setting only — classify, don't assume)

| Family | Typical MSL |
|---|---|
| WLCSP (no organics beyond repassivation) | 1 |
| Small QFN/DFN | 1–2 |
| Large QFN, QFP | 2–3 |
| PBGA / FCCSP | 3 (2a achievable with compound choice) |
| Large FCBGA | 3–4 |
| Fan-out | 1–3 (construction-dependent) |

## Bake recovery (J-STD-033 rules of practice)

- Standard recovery: **125 °C — 24 h** (≥1.4 mm bodies often spec'd 48 h; thin bodies
  shorter). Low-temp alternatives (90 °C ≤5 %RH, or 40 °C long-duration) exist for
  moisture/temp-sensitive carriers — use the standard's duration tables.
- **Check the carrier first:** trays must be marked high-temp (135 °C class) for 125 °C bake;
  tape-and-reel almost never survives 125 °C → transfer to trays or low-temp bake.
- **Cumulative-bake gate:** bakes grow intermetallics and oxidize finishes. >96 h cumulative
  at 125 °C (house rule; tighter for Sn finishes) → re-verify solderability (J-STD-002)
  before board mount.
- After bake: reset floor-life clock, re-bag with fresh desiccant + HIC card + MBB seal
  verified.

## Re-classification triggers (any of these voids the existing MSL)

- Mold compound, die attach, substrate, or underfill material change
- Body thickness/volume change crossing a table cell
- Higher process peak at the customer (e.g., 245 → 260 °C)
- Assembly site transfer (practice varies — conservative houses re-run precon at target MSL)

## Line-handling checklist (what to tell a factory)

1. Log bag-open time on every MBB; label floor-life expiry on the reel/tray.
2. HIC card read at open: pink/expired indicator → bake regardless of clock.
3. Dry cabinet (<10 %RH) pauses the clock; document in/out times.
4. Expired floor life → bake per table above; never "just reflow it, it's probably fine."
5. MSL 6 parts: bake immediately before use, every time.
