# C-SAM / X-ray interpretation — signatures, artifact traps, quantification

For Workflow 5. C-SAM (a.k.a. SAT) sees **interfaces/air gaps**; X-ray sees **density**
(voids in solder/epoxy, wire positions, ball defects). They answer different questions —
pick the tool before arguing about the image.

## C-SAM physics you must apply, not recite

- Pulse-echo: sound reflects at acoustic-impedance boundaries. A solid interface returns a
  modest echo; an **air gap returns a near-total reflection with inverted phase**. Phase
  inversion is the delam call — amplitude alone is not.
- Frequency tradeoff: higher MHz → finer lateral/axial resolution, less penetration.
  15–30 MHz: through mold to leadframe/die-attach depth. 50–75 MHz: die-top interface in
  thin bodies. 100–230 MHz: WLCSP/underfill/near-surface. Choose per interface depth.
- Gating: the time window selects the interface. A "clean" scan gated at the wrong depth
  proves nothing — always record gate settings with the image.
- Through-scan (THRU) mode: any delam anywhere in the stack blocks transmission → good
  screen, no depth info. Use THRU to screen, pulse-echo to locate.

## Interface-by-interface signatures (molded wire-bond package)

| Interface | Healthy | Delam signature | Criticality |
|---|---|---|---|
| Mold ↔ die top (active face) | uniform gray | bright + phase-inverted patch, often starts at corners/edges | **Reject** — shear on ball bonds follows; J-STD-020-class criterion |
| Mold ↔ leadfingers / wire periphery | uniform | inverted patches over fingers | **Reject if it touches wire-bonded area** (stitch lift risk) |
| Die attach (die ↔ pad) | uniform, voids visible as spots | inverted region; distinguish void (round, stable) vs delam (spreading from edge) | Reject for thermal/electrical-path products; else trend % area |
| Mold ↔ pad backside | uniform | inverted patch | Record & trend; reject on growth through precon (moisture path) |
| Underfill (flip-chip) | uniform fillet + field | voids (round), corner delam (at die edge/corner) | Corner delam = reject (ULK crack precursor); voids per spec |
| Lid adhesive (FCBGA) | continuous line | gaps in bond line | Thermal-path dependent; trend |

## The five artifact traps (check before calling delam)

1. **Tilt/warpage shadowing** — package not flat or warped post-reflow: interface drops out
   of the gate at one side → fake "delam" crescent. Check Z-profile / re-fixture and rescan.
2. **Mold filler settling / compound porosity** — speckle that looks like micro-delam;
   uniform across all units incl. time-zero → material texture, not a defect.
3. **Exposed-pad standoff** — QFN pad soldered or taped to a carrier reflects strongly;
   scan bare or account for the backing.
4. **Saturated gain** — everything bright, phase unreadable. Re-scan with calibrated gain
   on a known-good reference unit first.
5. **Edge diffraction** at die edges/corners produces bright rims on healthy parts —
   compare against time-zero of the *same unit* before calling corner delam growth.

**Hard rule (Gate A):** "delamination grew" requires same-unit time-zero comparison.
"Delamination present" is the strongest claim a single scan supports — and only with phase
evidence and correct gating.

## Quantification recipes

- **Delam/void % area:** threshold the phase-inverted (or void) pixels within the interface
  region; report `% of pad area` (die attach) or `% of die area` (die top), plus the
  location map. Percentages without location hide hot-spot risk.
- **Die-attach voiding (X-ray):** total void % and largest single void % vs spec (typical
  ≤10–20 % total / ≤5–10 % single — device spec wins). Note voids under known hot spots.
- **Wire sweep (X-ray, top-down):** sweep % = max lateral deflection ÷ wire span × 100.
  Typical limit 5–10 %. Report worst wire + distribution, and check sweep *direction*
  correlates with mold flow (confirms mechanism).
- **Ball voiding (X-ray):** % of ball projected area; IPC-7095 class limits are the usual
  reference for BGA (TODO verify class/limit against the customer's workmanship spec).
- **HIP / non-wet (X-ray):** look for bump-paste separation line at an angle; low
  confidence in 2D — confirm electrically or by dye-and-pry. 3D/CT if available.

## Gate B — destructive confirmation (before lot-level decisions)

Acoustic/X-ray evidence alone must not scrap a lot or trigger a supplier claim:

1. Select ≥2 units representative of the image finding (worst + median).
2. Cross-section through the flagged region (or dye-and-pry for board-level opens/HIP).
3. Confirm the physical gap/void/crack matches the image location and size class.
4. Only then: lot disposition + 8D. If x-section contradicts the scan → suspect artifact,
   re-run Gate A checklist on the imaging.

## Disposition record format (Workflow 5 step 6)

```
Unit/serial · image IDs (scan settings: MHz, gate, gain) · interface · finding ·
quantification (% area, location) · criterion applied (spec/std) · pass/fail ·
time-zero comparison (Y/N, delta) · Gate B status (n/a | pending | confirmed | refuted) ·
next action
```
