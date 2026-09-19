# Step 2 — Dataset B Process Analysis

Source: `scripts/analyzeDatasetB.py` output, `outputs/datasetBCandidates.json`.
195 segments across 15 sessions, 14 labels.

## Processes performed, frequency, time, people involved

| Rank | Label | Executions | Total time | Distinct people | Sessions |
|---|---|---|---|---|---|
| 1 | process_0 | 60 | 17.6 min | 4 | 13/15 |
| 2 | process_1 | 73 | 27.2 min | 4 | 14/15 |
| 3 | process_2 | 51 | 13.1 min | 4 | 12/15 |
| 4-14 | process_3 .. process_13 | 1 each | <1.2 min each | 1 each | 1 each |

Three labels account for 184 of 195 segments (94%); the remaining 11 labels are
one-off outliers with a single execution each — not recurring processes, so not
automation candidates regardless of ranking.

## Are there different handling patterns within the same process?

Yes, and not in the way the clustering intends. Reducing each execution's action
sequence to a canonical skeleton (keeping only actions with a specific target —
which field/button/page was touched — and collapsing incidental repeats like
scroll/click counts) gives, per label:

| Label | Distinct skeletons | Dominant skeleton share |
|---|---|---|
| process_0 | 19 of 60 executions | 22% |
| process_1 | 22 of 73 executions | 18% |
| process_2 | 15 of 51 executions | 20% |

No single pattern dominates any of the top three labels. Checking which specific
form field each execution touched (`pi-note`, `rt-note`, `si-note`, `ob-note`,
`la-note` — payroll items, resident tax, social insurance, onboarding, and leave
applications respectively) explains why:

| Label | pi-note | rt-note | si-note | ob-note | la-note |
|---|---|---|---|---|---|
| process_0 | 17 (28%) | 26 (43%) | 2 (3%) | 8 (13%) | 7 (12%) |
| process_1 | 41 (56%) | 0 | 10 (14%) | 8 (11%) | 13 (18%) |
| process_2 | 25 (49%) | 0 | 13 (25%) | 0 | 13 (25%) |

All three top-ranked labels mix multiple distinct real HR review flows rather
than isolating one each. `AssignThreads`/`LabelSegments` group by app, domain,
timing, and text-token overlap (`labeling.py`), and all five of these flows run
in the same app, likely the same domain, and share HR-note vocabulary — the
features the clustering has don't distinguish them. This matches the low global
label purity already measured on Dataset A (≈0.40, see
`outputs/datasetAMetricsPerSession.json`) — it isn't a Dataset-B-specific fluke.

## Priority order and reasoning

`priorityScore = normalizedTotalTime * (1 - 0.5 * normalizedBranchingFactor)` —
opportunity (time spent, a proxy for time saved by automating) discounted by
complexity (branching factor, a proxy for how many decision paths an automation
would need to handle correctly).

1. **process_0** (0.506) — highest total time among labels with real recurring
   volume, and the lowest branching factor of the top three (2.44), so it scores
   highest on the opportunity/complexity tradeoff. But per the breakdown above,
   the actual best automation target inside it is resident-tax confirmation
   (`rt-note`, 43% of executions), not payroll items as assumed when Step 3 was
   built — pi-note is the second-largest share, not the largest.
2. **process_1** (0.500) — most total time of any label (27.2 min) and the most
   executions (73), but the highest branching factor of the top three (3.80)
   pulls its score down to a near-tie with process_0. Its five-way pi/si/ob/la
   mix is spread more unevenly (pi-note alone is 56%).
3. **process_2** (0.311) — clearly third: less total time, and its two-way
   pi-note/si-note/la-note split doesn't reach the volume of the first two.
4. **process_3 through process_13** — each a single execution seen once, in one
   session. Not recurring processes by any reasonable definition; excluded from
   automation consideration regardless of their (near-zero) priority scores.

## Consequence for Step 3

The automation built in `automation/` targets the `pi-note`/`btn-pi-ok` payroll
flow specifically (not "process_0" as a whole) — a directly observable,
template-driven decision found by inspecting raw events, not something the
labels above resolved on their own. Given the corrected breakdown, resident-tax
confirmation (`rt-note`, 43% of process_0) is the more frequent flow and could
be the better next target, or the clustering should be tightened before
trusting any label as one process automatically.
