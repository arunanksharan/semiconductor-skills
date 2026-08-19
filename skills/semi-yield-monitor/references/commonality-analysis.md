# Commonality analysis

Read this when you have a set of low-yielding lots and want to know which step, tool, or
chamber they share — and, more importantly, when the answer you get is not trustworthy.

Commonality analysis is the highest-yield and most-abused technique in the yield engineer's
kit. It finds associations quickly and it manufactures false ones just as quickly.

## The method

1. **Assemble a lot-level yield table.** One yield per lot, computed consistently: same test
   insertion, same exclusions, same retest policy.
2. **Assemble a process history table.** For each lot, which tool (and chamber, and often
   which slot/port) ran it at each step, and when. This is the WIP history from the MES.
3. **For every step, group the lots by tool** (and by chamber where the tool has them).
4. **Compare each group's mean yield to the grand mean** and rank the deltas.
5. **Discount groups with few lots.** A group of one lot cannot separate the tool from the
   lot. `commonality.py` weights by `sqrt(n_lots)` and labels single-lot groups
   `HYPOTHESIS ONLY`.
6. **Check the confounders below before acting on the ranking.**

```
python commonality.py --history history.csv --die-results die_results.csv --min-delta 2.0
```

`history.csv` schema is `lot_id,step,tool,chamber,date` (chamber may be blank). Yields come
either from a canonical `die_results.csv` or from a `lot_id,yield` CSV.

## The statistics of ranking suspects

The ranking is a screening device, not a test. Treat every number in it as a starting point.

**Multiple comparisons are the central problem.** A fab with 300 steps and an average of 4
tools per step gives you well over a thousand tool groups. At any conventional significance
level, dozens will look "significant" by chance alone on random data. A ranked list always
has a top entry — the list being non-empty is not evidence.

Practical consequences:
- **Effect size beats p-value.** A 7-point yield delta over 6 lots is worth investigating;
  a 0.8-point delta with a small p-value over 40 lots probably is not, and is more likely a
  slow drift you have already lived with.
- **Set a threshold before you look.** `--min-delta` exists so you commit to a magnitude
  first. Moving it downward after seeing the results is how people talk themselves into a
  tool change.
- **Require replication.** Two lots on a suspect tool is the bare minimum to distinguish the
  tool from a lot. Three or more, spread over time, is a real signal.
- **Ask for the negative case.** The strongest evidence is not "the bad lots all ran tool A"
  but "the bad lots ran tool A *and* the good lots did not, and lots that later ran tool A
  also went bad." A tool that ran every lot in the set — good and bad — explains nothing,
  even if its group mean happens to be low.
- **Sample size cuts both ways.** With 4 lots (as in this skill's sample data), the analysis
  can only generate a hypothesis. `commonality.py` says so explicitly rather than pretending.

**A useful sanity number:** the standard error on a group mean is roughly the lot-to-lot
yield sigma divided by sqrt(n_lots). If lot-to-lot sigma is 1.5 points and the group has 3
lots, the standard error is ~0.9 points, so a 2-point delta is barely more than 2 sigma —
interesting, not conclusive. Compute this before you present a ranking.

## Confounding, which is where this technique goes wrong

### Time
This is the big one. Tools are not assigned randomly: they go down for PM, they get
qualified in batches, they get loaded preferentially when they are fast. So **tool usage is
correlated with calendar time**, and anything else that changed at the same time — a
material lot, a recipe revision, a test program, an ambient excursion, a new operator shift
pattern — is confounded with the tool.

Defenses:
- Plot yield against time first, before any commonality analysis. If yield stepped on a
  date, look for what changed on that date; the tool ranking will point at whichever tool
  happened to be running then.
- Check whether the suspect tool's lots are contiguous in time. If they are, you have a time
  effect wearing a tool costume.
- Stratify: within a single narrow time window, does the tool difference persist? If the
  window has too few lots to answer, say that instead of ignoring it.

### Tool-to-tool correlation
Lots often travel together through several steps, so the same subset of lots hits ETCH-02,
then CMP-03, then LITHO-01. All three will rank as suspects. The pattern is a property of
the routing, not of the tools.

Defense: look at the *lot sets*, not just the deltas. `commonality.py` prints the lot list
per group for exactly this. If two steps' suspect groups have the same lot list, the data
cannot separate them, and no amount of statistics will. You need lots that split the
routing — either from history, or by running a deliberate split lot.

### Queue time and dwell
The interval between steps affects yield in many modules (queue-time-sensitive layers,
resist ageing, native-oxide regrowth). A tool that is slow or heavily loaded produces long
queue times downstream. The tool then looks bad while the actual mechanism is the wait.

Defense: include timestamps in the history and check whether the suspect group also has
anomalous queue times.

### Chamber and slot aliasing
"Tool" is often too coarse. A multi-chamber tool where one chamber is drifting shows a
diluted effect at tool level and a sharp one at chamber level. The same applies to slot,
port, load lock, head, and site.

Defense: always run the analysis at the finest granularity your history supports, and expect
the effect to *sharpen* as you refine. If it does not sharpen, the chamber is not the story.
`commonality.py` groups by (tool, chamber) whenever a chamber column is present.

### Rework and split lots
A reworked lot has been through a step twice, sometimes on different tools. Simple history
joins either double-count it or silently drop one pass.

Defense: check for duplicate (lot, step) rows before analysing; decide explicitly which pass
you mean.

### Survivorship
If low-yielding lots get scrapped and never reach final test, the tool that produced them
looks fine in the final-test data. Analyse at the earliest insertion where you still have
every lot.

### The metric itself changed
A "yield drop" common to a set of lots can be a test-program revision, a bin-map change, or a
limit tightening. Nothing in the fab moved. Always confirm the test program revision and
limit set before running commonality on a yield shift — see `spc-for-yield.md`.

## Reading the output honestly

`commonality.py` prints, per step, every tool/chamber group with its lot count, mean yield,
and delta from the grand mean, followed by a suspect ranking scored by
`|delta| * sqrt(n_lots)`.

- **Single-lot groups are tagged `HYPOTHESIS ONLY`.** With one lot, "tool X is bad" and "lot
  Y is bad" are the same statement.
- **A group covering all lots has delta 0 by construction.** Not exoneration — a tool that
  ran everything cannot be tested this way at all.
- **The absence of a suspect is informative.** If no group clears the threshold, the loss is
  probably not tool-assigned: look at spatial signatures, at a process-wide condition, or at
  the incoming material.

## What to do with a suspect

Ranking a suspect is the beginning of the work, not the end.

1. **Look for a matching physical signature.** A suspect etch chamber should produce a wafer
   map consistent with an etch mechanism. If the spatial signature says "reticle" and the
   commonality says "etch chamber", one of them is wrong; usually the commonality.
2. **Pull the tool's own data** — FDC traces, chamber parameters, PM history, part changes,
   qual results — around the dates in question. Correlate the yield delta with an actual
   parameter excursion, not just with the tool's name.
3. **Check the time order.** Did the tool's parameter move *before* the yield moved?
4. **Design the confirming experiment.** A split lot across the suspect tool and a reference
   tool, run in the same time window, settles in one lot what a hundred retrospective
   analyses cannot.
5. **Only then consider a hold or a tool-down.** Holding a tool is expensive and holding the
   wrong one is worse: it moves all the work onto the remaining tools, which changes their
   loading and queue times, which perturbs the very data you would use to check yourself.

## Reporting language

Because this technique produces associations, the write-up has to be careful:
- "Lots on ETCH-02/CH-B averaged 7.6 points below the grand mean" — a fact.
- "ETCH-02/CH-B caused the yield loss" — a claim requiring the physical signature, the tool
  data, the time order, and ideally the split lot.
- Always state the lot count and whether the groups are confounded with time. A commonality
  result without its lot count is not a result.
