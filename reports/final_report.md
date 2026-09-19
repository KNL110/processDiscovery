# Final Report

## Step 1 — Segmentation (summary)

Full method in `README.md`. Validated on Dataset A (63 sessions, tuned params:
`resumeWindowSeconds=300`, `joinThreshold=0.55`, `similarityThreshold=0.55`):

| Metric | Value |
|---|---|
| Boundary precision / recall | 0.585 / 0.341 |
| Boundary F1 (IoU ≥ 0.5) | 0.431 |
| Mean IoU of matched segments | 0.600 |
| Label purity | 0.399 |
| Label V-measure | 0.578 |
| Label Adjusted Rand Index | 0.309 |

Honest read: about a third of ground-truth executions are recovered as
boundaries (recall 0.34), and matched boundaries are only moderately tight
(IoU 0.60). Label purity (0.40) says clustering conflates distinct real
processes more often than it should — this directly shaped the Step 2 finding
below, so it isn't just a Step 1 caveat.

## Step 2 — Analysis and prioritization

Full detail: `outputs/step2Analysis.md`, `outputs/datasetBCandidates.json`.
Method: `src/ibytask/analysis.py`. 195 Dataset B segments, 14 labels; three
labels (`process_0/1/2`) cover 184 of 195 (94%), the rest are one-off outliers
excluded from consideration.

| Rank | Label | Executions | Total time | Branching factor | Priority score |
|---|---|---|---|---|---|
| 1 | process_0 | 60 | 17.6 min | 2.44 | 0.506 |
| 2 | process_1 | 73 | 27.2 min | 3.80 | 0.500 |
| 3 | process_2 | 51 | 13.1 min | 3.08 | 0.311 |

`priorityScore = normalizedTotalTime * (1 - 0.5 * normalizedBranchingFactor)`:
opportunity (time spent) discounted by complexity (DFG branching factor —
process-mining-standard: fewer distinct next-steps means a more repeatable,
lower-risk-to-automate flow). `process_0` and `process_1` are a near-tie;
`process_0` wins on lower branching factor even though `process_1` has more
raw volume.

**Are there different handling patterns within the same label?** Yes.
Reducing each execution to a canonical action skeleton (only actions with a
specific target, e.g. `click: pi-note`) shows no single skeleton dominates any
top-3 label (18–22% dominant-pattern share). Checking which specific form
field each execution touches explains why — all three labels mix several real
HR sub-flows that share app/domain/text features but are functionally
distinct:

| Label | pi-note (payroll) | rt-note (resident tax) | si-note (social ins.) | ob-note (onboarding) | la-note (leave) |
|---|---|---|---|---|---|
| process_0 | 28% | 43% | 3% | 13% | 12% |
| process_1 | 56% | 0% | 14% | 11% | 18% |
| process_2 | 49% | 0% | 25% | 0% | 25% |

This is a real limitation of the clustering (it groups by app/domain/timing/
text overlap, none of which separate these sub-flows), not a Dataset-B fluke —
it matches the low global purity already measured on Dataset A above.

## Step 3 — What was built, why that process and scope, why that form

**Process and scope.** The automation targets the `pi-note` / `btn-pi-ok`
payroll-item change confirmation flow — a single, template-driven decision
found by inspecting raw events inside the top-ranked label, not the label as a
whole. `pi-note` is the largest single flow inside `process_1` (56% of its 73
executions) and the second-largest inside `process_0` (28%); across all
segments it is the most frequent individually-identifiable flow (83 of 195
executions touch it). Scope was deliberately kept to one flow: the handling-
pattern finding above shows the top labels are each a mix of several distinct
processes, so automating a whole label as one unit would apply one decision
rule to work that doesn't share one rule.

**Decision rule.** Change types with an observed fixed note template and
`requiresManagerApproval: false` (`Dependent Deduction Change`, `Overtime
Allowance Adjustment`) are auto-approved with that template; everything else
is flagged for a human. The rule is read directly off field values present in
the logs, not inferred or assumed.

**Why an n8n workflow, and why the alternatives were rejected.** `projREADME.md`
leaves the implementation form open; options considered:

- **Python deterministic script** — rejected as the primary form because the
  audience for this tool (HR ops reviewing a queue) isn't engineers; a script
  requires a developer to read or adjust the note template or the routine/
  non-routine list. A visual workflow does not.
- **RPA / desktop UI automation** (driving the real browser via clicks) —
  rejected as the highest-maintenance option: it breaks on any CSS/layout
  change, and the logs give no evidence either way about how stable the real
  portal's DOM is.
- **LLM/agent-driven decision** — rejected because the rule is already fully
  explicit (`changeType` + `requiresManagerApproval` are literal field values,
  not something requiring judgment or text interpretation). Adding an LLM in
  the loop would add cost and non-determinism with no offsetting benefit here.
- **n8n workflow** (chosen) — a visual, business-readable workflow
  (`Manual Trigger → Get Queue → Compute Decision → Is Routine? → Approve/Flag`,
  `automation/n8n/topCandidateConfirmation.json`) that an HR ops lead can read,
  pause, and edit the routine-type list or note template on without an
  engineer. It talks to `automation/mockPortalApi.py` (`GET /queue`,
  `POST /queue/<caseId>/approve|flag`) standing in for the real portal, since
  only browser UI events were ever observed in the logs — no API traffic.

## What manual work remains after deployment, and expected impact

- Every **flagged** case (any `changeType` other than the two routine ones,
  or any case with `requiresManagerApproval: true`) still needs a human — by
  design, since the logs show no example of what a legitimately *rejected*
  routine case looks like.
- Only the `pi-note` flow is automated. The `rt-note` / `si-note` / `ob-note` /
  `la-note` flows inside the same labels — the majority of `process_0`'s and
  `process_2`'s volume — remain fully manual.
- Someone still owns the underlying policy (which change types count as
  routine, what the note must say) — the automation encodes today's rule, it
  doesn't maintain it.

**Realistic impact (approximate, not directly measured):** `pi-note`
executions account for 83 of 195 Dataset B segments. Using each label's
average execution time as a stand-in for `pi-note`'s own time (`process_0`
17.6s, `process_1` 22.3s avg — no finer per-sub-flow timing exists in the
data), that's roughly 26 minutes of handling time across 15 sessions, or
~1.7 min/session — a modest, not dramatic, reduction, concentrated in
turnaround consistency (same note, same rule, every time) more than headcount.
This estimate assumes the mock queue's 2-of-5 routine/flagged split is
representative, which is unverified against the real system.

## Anticipated implementation and rollout risks

| Risk | Evidence | Mitigation |
|---|---|---|
| The real portal may expose no API at all — everything observed is browser DOM interaction. | Dataset B has zero API/network-style event types (`screenshot_smart`, `keystroke`, `mouse_click`, `browser_click`, `browser_navigation`, ... — no `api_call`/`xhr`/`fetch`); all 608 `browser_form_input` events have `value: null`. | Run a short technical spike against the real system before committing to the API approach; the n8n HTTP nodes would be swapped for browser-automation nodes if no API exists, at higher maintenance cost. |
| The routine-vs-flag rule is inferred from field values, never validated against a real rejected case. | No counter-example of a routine-labeled case actually being rejected exists in Dataset B. | Ship in shadow mode first: log the workflow's verdict next to the human's real action for a trial period before enabling real auto-approval. |
| Auto-approving the wrong case is a compliance/payroll risk, not just an inconvenience. | The flow changes payroll deduction/allowance data tied to real employee IDs. | Default to flag-for-human on anything outside the two explicitly-observed routine types; log every auto-approval with its exact note for audit. |
| The Step 2 clustering may have merged distinct real processes under one label. | Directly measured: label purity 0.40 on Dataset A, and the handling-pattern table above shows every top label mixing 2–5 real sub-flows. | Before extending automation to any other label, manually confirm its sub-flow boundaries rather than trusting the cluster as one process. |
| `pi-note` may not be the single best target — `rt-note` is a larger share of `process_0` (43% vs. `pi-note`'s 28%) than initially assumed when scoping. | Directly measured in the handling-pattern breakdown above. | Treat `rt-note` (resident-tax confirmation) as the next candidate to scope and evaluate before broadening past a single flow. |
| Operator variation: 4 different operators perform this flow; not verified they follow an identical procedure. | `distinctOperators = 4` for every top label — presence, not proof of identical procedure. | Validate the rule against a sample of each operator's cases before full rollout. |

## Day allocation

- **Day 1**: project scaffold, session/event loading, integrity checking;
  found `ms_since_last_event` anomalies tied to `screenshot_smart`.
- **Day 2**: deeper data review; simplified and extended the integrity check;
  began brainstorming the segmentation approach.
- **Day 3**: feature-extraction helpers (`utils.py`) for segmentation.
- **Day 4**: segmentation design (micro-unit aggregation, thread model,
  continuation scoring); grounded hyperparameters and app inventory in real
  data.
- **Day 5**: no work (mid-semester exam).
- **Day 6**: the bulk of the build — fixed two real scoring bugs
  (`AppDomainSimilarity` recency/aggregation, `SpansCanTouch`'s tautological
  bounding-box check), rewrote `AssignThreads` as an agglomerative merge,
  fixed a field-naming crash, built the missing Step 1 glue (`labeling.py`,
  `metrics.py`, `pipeline.py`), found and fixed a per-session labeling bug,
  tuned hyperparameters against Dataset A (boundary F1 0.16 → 0.43, purity
  0.28 → 0.40), built Step 2's DFG ranking and handling-pattern analysis, and
  built the Step 3 n8n automation.
- **Day 7**: report writing, README documentation, repo cleanup, live
  Docker/n8n verification with the actual runtime environment.

Day 6 concentrating most of the build was not the plan going in — Day 4's
design work surfaced two scoring bugs only once run against real data, and
chasing those down (rather than shipping a design that looked right on paper)
is what moved boundary F1 and label purity from unusable to defensible
numbers, and is what the priority ranking and Step 3 target in this report are
actually based on.
