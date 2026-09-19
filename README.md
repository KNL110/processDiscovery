# IBYTask

## Student Information

- **Full name:** Krunal Asari
- **University:** Indian Institute of Technology Goa
- **Department/Major:** Mathematics and Computing
- **Email:** krunalkumar.asari.24033@iitgoa.ac.in


## What this is

Recovers units of work from raw operation logs (Step 1), ranks recurring
processes as automation candidates (Step 2), and automates the top one (Step 3).

## Step 1 — Segmentation

`src/ibytask/segmentation.py`

1. `buildMicroUnits` — collapses runs of same-app/same-action events into
   `MicroUnit`s. Events matching `boundarySignalEventTypes` (app switch,
   navigation, dialogs, window changes) always become their own isolated unit.
2. `AssignThreads` — agglomerative merge: every unit starts as its own thread,
   then the best-scoring admissible merge is applied repeatedly. A merge
   interleaves two threads by time and validates every new cross-adjacency it
   creates via `ContinuationScore`; one bad link rejects the whole merge.

**Scoring** (`ContinuationScore`, range roughly `[-1, 1]`):

- Same case ID seen before in the thread, or a matching case-specific element
  anchor → score `1.0` (certain continuation)
- Otherwise: `0.7 * AppDomainSimilarity + 0.3 * TextOverlap`, blended with
  `TimeDecay(gap)` (`30%` weight), minus a `0.3` penalty if a boundary-signal
  event occurred in the gap
- `AppDomainSimilarity`: `1.0` same app as last unit, `0.4` app seen recently
  in thread, combined via noisy-OR with `0.9`/`0.6` for same-path/same-domain

Threads whose score clears `joinThreshold` merge; `resumeWindowSeconds` bounds
how large a time gap can still count as a resume.

**Output**: `outputs/segments.jsonl`, one `{session_id, start, end, label}` per
segment. Labels come from Step 2's clustering, not Step 1 itself.

### Hyperparameters

All tunable, all set as keyword args in `pipeline.RunStep1ForDataset` /
`RunStep1ForSession` (current values below were fit against Dataset A ground
truth, not guessed — see `outputs/datasetAMetricsPerSession.json`):

| Param | Current | Effect |
| --- | --- | --- |
| `resumeWindowSeconds` | 300 | max gap still eligible to resume a thread |
| `joinThreshold` | 0.55 | min `ContinuationScore` to admit a merge |
| `minThreadUnits` | 14 | drops short threads before labeling (noise filter) |
| `similarityThreshold` | 0.55 | min fingerprint similarity to share a label |

Re-run `scripts/evaluateOnDatasetA.py` with different values to see the effect
on boundary F1 / label purity before trusting a change — these four already
moved F1 0.16 → 0.43 and purity 0.28 → 0.40 once tuned, so results are
sensitive to them and likely still improvable.

## Step 2 — Analysis

`src/ibytask/labeling.py`, `src/ibytask/analysis.py`

- **Labeling**: segments get a `SegmentFingerprint` (apps/domains/paths/text
  tokens as counters). Pairs scoring above `similarityThreshold` on a weighted
  cosine/Jaccard blend get union-find'd into the same label (`process_0`,
  `process_1`, ...) — connected components, not Louvain (no `networkx`
  dependency here).
- **Ranking**: per label, builds a directly-follows graph (DFG) of actions.
  `priorityScore = normalizedTotalTime * (1 - 0.5 * normalizedBranchingFactor)`
  — time spent (opportunity) discounted by branching factor (complexity).
- **Handling patterns**: canonicalizes each execution's action sequence (only
  actions with a specific target, e.g. `click: pi-note`) and counts distinct
  skeletons per label — answers whether a label hides multiple real patterns.

**Output**: `outputs/datasetBCandidates.json` (ranked stats per label),
`outputs/step2Analysis.md` (priority order + reasoning, written by hand from
the script's real numbers).

**Known limitation**: label purity is low (~0.40 on Dataset A). The top three
Dataset B labels each mix five real HR review sub-flows rather than isolating
one apiece — see `outputs/step2Analysis.md`.

## Step 3 — Automation

`automation/`

Targets the most frequent real sub-flow found by inspecting raw events inside
the top-ranked label: payroll-item change confirmation (element ids `pi-note` /
`btn-pi-ok`, 43% of all Dataset B segments touch this flow). Routine change
types (dependent deduction, overtime allowance) are approved with the observed
note template; anything needing manager approval is flagged for a human.

Built as an **n8n workflow**, not a script — closer to what an HR ops team
could read and modify without an engineer.

- `automation/mockPortalApi.py` — stands in for the real portal (only
  operation logs are available, not API access): `GET /queue`,
  `POST /queue/<caseId>/approve|flag`
- `automation/n8n/topCandidateConfirmation.json` — the workflow:
  `Manual Trigger → Get Queue → Compute Decision (Set node) → Is Routine? (IF) → Approve / Flag`
- `automation/topCandidateQueue.json` — mock queue data, resets to
  all-`pending` after each demo run

### Running it

```bash
# terminal 1: mock portal
python3 automation/mockPortalApi.py

# terminal 2: n8n via Docker (host networking - simplest and most reliable on
# native Linux Docker, since host.docker.internal can be flaky there;
# on Docker Desktop (Mac/Windows), --network host is unsupported - use
# -p 5678:5678 --add-host=host.docker.internal:host-gateway instead, and swap
# 127.0.0.1:5133 for host.docker.internal:5133 in the workflow's HTTP nodes)
docker run -it --rm --name n8n --network host \
  -v n8n_data:/home/node/.n8n \
  n8nio/n8n
```

Open `http://localhost:5678` → create owner account (first run only) →
**Workflows → Import from File** → `automation/n8n/topCandidateConfirmation.json`
→ **Execute Workflow**.

## Running the pipeline

```bash
uv run python scripts/evaluateOnDatasetA.py      # Step 1 metrics vs ground truth
uv run python scripts/generateSegmentsForDatasetB.py  # Step 1 deliverable
uv run python scripts/analyzeDatasetB.py         # Step 2 ranked candidates
```

## Repo layout

```text
src/ibytask/       segmentation, labeling, analysis, pipeline, metrics, ingest
src/analysis/       standalone ground-truth / app-inventory scripts
scripts/            the three runnable entry points above
automation/         Step 3 (mock portal + n8n workflow)
outputs/            generated - segments.jsonl, candidate rankings, metrics
reports/            work_log.md
```
