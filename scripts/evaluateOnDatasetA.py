""" run the Step 1 pipeline over every Dataset A session and report aggregate metrics
against gt_manifest.json. Labels are assigned once across the whole dataset (see
pipeline.RunStep1ForDataset) so label-consistency metrics reflect real cross-session
consistency, not per-session-local numbering."""

import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ibytask.metrics import BoundaryMetrics, LabelConsistency, LoadGtExecutions, MatchSegments
from ibytask.pipeline import RunStep1ForDataset

repoRoot = pathlib.Path(__file__).resolve().parents[1]
datasetADir = repoRoot / "dataset_a"
outputsDir = repoRoot / "outputs"


def Evaluate(**pipelineKwargs):
    allSegments = RunStep1ForDataset(datasetADir, **pipelineKwargs)
    segmentsBySession = defaultdict(list)
    for seg in allSegments:
        segmentsBySession[seg.sessionId].append(seg)

    totalTp = totalPred = totalGt = 0
    iouSum = 0.0
    perSession = []
    globalMatchedSegments, globalMatchedGt, globalMatches = [], [], []

    for sessionDir in sorted(datasetADir.iterdir()):
        if not sessionDir.is_dir() or not sessionDir.name.startswith("ses_"):
            continue
        gtExecutions = LoadGtExecutions(sessionDir)
        segments = segmentsBySession.get(sessionDir.name, [])

        matches = MatchSegments(segments, gtExecutions)
        bm = BoundaryMetrics(matches, numPred=len(segments), numGt=len(gtExecutions))
        lc = LabelConsistency(matches, segments, gtExecutions)

        totalTp += bm["tp"]
        totalPred += bm["numPred"]
        totalGt += bm["numGt"]
        iouSum += sum(m[2] for m in matches)
        perSession.append({"session": sessionDir.name, **bm, **lc})

        # re-index matches into the pooled lists so a single global label-consistency
        # score can be computed below - this is the metric that actually reflects
        # "same label used for the same process across sessions", not per-session purity
        for gi, pi, iou in matches:
            globalMatches.append((len(globalMatchedGt), len(globalMatchedSegments), iou))
            globalMatchedGt.append(gtExecutions[gi])
            globalMatchedSegments.append(segments[pi])

    precision = totalTp / totalPred if totalPred else 0.0
    recall = totalTp / totalGt if totalGt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    meanIou = iouSum / totalTp if totalTp else 0.0
    globalLc = LabelConsistency(globalMatches, globalMatchedSegments, globalMatchedGt)

    summary = {
        "params": pipelineKwargs,
        "boundary": {"precision": precision, "recall": recall, "f1": f1, "meanIou": meanIou,
                     "totalPred": totalPred, "totalGt": totalGt, "totalTp": totalTp},
        "labelConsistency": {
            "purity": globalLc["purity"],
            "vMeasure": globalLc["vMeasure"],
            "adjustedRandIndex": globalLc["adjustedRandIndex"],
            "matchedPairs": globalLc["matchedPairs"],
        },
    }
    return summary, perSession


if __name__ == "__main__":
    summary, perSession = Evaluate(resumeWindowSeconds=300.0, joinThreshold=0.55, similarityThreshold=0.55)
    print(json.dumps(summary, indent=2))
    outputsDir.mkdir(exist_ok=True)
    (outputsDir / "datasetAMetricsPerSession.json").write_text(json.dumps(perSession, indent=2), encoding="utf-8")
