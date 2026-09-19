# Work Log

## Day 1

- Created the project scaffold
- add session loading, event loading and intigirty check
- found negetive ms_since last second
- found negative ms_since_last_event is strongly associated with screenshot_smart, but it is not exclusively a screenshot phenomenon because a few mouse_scroll events also have negative values

## Day 2

- understand the data more thoroughly
- brainstorm on the ideas to implement segmentation of units of work
- simplified integrity check: dropped per-event issue tracking in favor of a single set of issue types, added validation for required fields, duplicate event_id, and duplicate sequence_number
- integrity check now also collects raw values for timestamp_ms backward jumps and negative ms_since_last_event so they can be pooled across sessions and summarized (min/q1/median/q3/max)

## Day 3

- added feature-extraction helpers to `utils.py` (BrowserTab, AppOrProcessName, ExtractedText, ActionTaken, EventSignature, AppContext) for use in segmentation

## Day 4

- deep dive on the segmentation approach: micro-unit aggregation from L2/L3 events (collapse keystroke/click runs into one action), an OS-thread-style model for deinterleaving concurrent work, and an isContinuation-style compatibility check (case-ID match > element-anchor match > graded app/time/text score)
- built `analysis/groundTruth.py` (using copilot) to ground hyperparameters in real data: execution duration distribution, resume gaps, noise_block types/durations, split task counts
- built `analysis/apps.py`(using copilot): inventories every distinct app across all sessions in both datasets (22 in A, 12 in B, 9 shared) -- useful for auditing which apps should count as noise

## Day 5

- mid-semester exam, no work done

## Day 6

- fixed `appDomainSimilarity`: was scoring 1.0 for any app seen in the last 5
  units, not just the immediately preceding one; and path/domain/app signals
  were overwriting each other (`max`) instead of aggregating (noisy-OR)
- fixed `SpansCanTouch`'s bounding-box overlap check, which degenerated to
  near-always-true once threads had a few units (their outer span outgrows
  `resumeWindowSeconds` fast) — replaced with a real two-pointer merge scan
- rewrote `AssignThreads` from single-pass greedy to agglomerative: every unit
  starts as its own thread, best-scoring admissible merge applied repeatedly
  via a heap; a merge interleaves two threads by time and validates every new
  cross-adjacency, so one bad link rejects the whole merge
- fixed `normalizedTs`/`timestampDt` naming mismatch between `ingest.py` and
  `segmentation.py` that made `buildMicroUnits` crash on real data
- built the missing Step 1 glue: `labeling.py` (fingerprint clustering),
  `metrics.py` (IoU matching + purity/V-measure/ARI against `gt_manifest.json`,
  no `sklearn`), `pipeline.py`, three driver scripts
- found and fixed a real bug: labels were assigned per-session, so the same
  process got different labels across sessions — labeling now runs once over
  the whole dataset
- tuned `minThreadUnits` and `similarityThreshold` against Dataset A: boundary
  F1 0.16 → 0.43, label purity 0.28 → 0.40 (measured correctly only after the
  per-session labeling bug was fixed) — ran the sweeps and cross-checked the
  metric numbers with VSCode Copilot alongside Claude
- verified `AssignThreads`/`ContinuationScore` behavior against real data (unit
  conservation, time ordering, brute-force cross-check on `SpansCanTouch`)
  using Copilot in VSCode for a second opinion on the test cases
- built Step 2 (`analysis.py`): DFG branching factor, priority ranking, and a
  handling-patterns metric — which surfaced that the top 3 labels each mix five
  real HR review sub-flows instead of isolating one apiece
- built Step 3 automation for the most frequent real sub-flow (payroll-item
  confirmation, 43% of segments) as an n8n workflow, since only browser UI
  interaction was ever observed in the logs, not API traffic — used Copilot in
  VSCode for part of the n8n node/JSON structure and the mock portal script
