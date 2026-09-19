import json
import math
import pathlib
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .pipeline import Segment


def LoadGtExecutions(sessionDir: pathlib.Path) -> List[Dict[str, Any]]:
    manifest = json.loads((sessionDir / "gt_manifest.json").read_text(encoding="utf-8"))
    executions = []
    for process in manifest["processes"]:
        for execution in process["executions"]:
            # a handful of executions carry a null end_ts (likely truncated by session
            # end before completion) - can't score against an undefined interval
            if not execution.get("start_ts") or not execution.get("end_ts"):
                continue
            executions.append({
                "code": process["code"],
                "start": datetime.fromisoformat(execution["start_ts"]),
                "end": datetime.fromisoformat(execution["end_ts"]),
                "caseId": execution["case_id"],
            })
    executions.sort(key=lambda e: e["start"])
    return executions


def IntervalIou(aStart, aEnd, bStart, bEnd) -> float:
    interStart, interEnd = max(aStart, bStart), min(aEnd, bEnd)
    intersection = max((interEnd - interStart).total_seconds(), 0.0)
    if intersection == 0.0:
        return 0.0
    union = (max(aEnd, bEnd) - min(aStart, bStart)).total_seconds()
    return intersection / union if union > 0 else 0.0


def MatchSegments(
    predSegments: List[Segment], gtExecutions: List[Dict[str, Any]], iouThreshold: float = 0.5
) -> List[Tuple[int, int, float]]:
    """ greedy one-to-one matching: highest-IoU pairs win first.
    returns (gtIndex, predIndex, iou) for matches that cleared the threshold. """
    candidates = []
    for gi, gt in enumerate(gtExecutions):
        for pi, pred in enumerate(predSegments):
            iou = IntervalIou(gt["start"], gt["end"], pred.start, pred.end)
            if iou > 0:
                candidates.append((iou, gi, pi))
    candidates.sort(reverse=True)

    usedGt, usedPred, matches = set(), set(), []
    for iou, gi, pi in candidates:
        if gi in usedGt or pi in usedPred or iou < iouThreshold:
            continue
        usedGt.add(gi)
        usedPred.add(pi)
        matches.append((gi, pi, iou))
    return matches


def BoundaryMetrics(matches: List[Tuple[int, int, float]], numPred: int, numGt: int) -> Dict[str, float]:
    tp = len(matches)
    precision = tp / numPred if numPred else 0.0
    recall = tp / numGt if numGt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    meanIou = sum(m[2] for m in matches) / tp if tp else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "meanIou": meanIou, "tp": tp, "numPred": numPred, "numGt": numGt}


def Entropy(labels: List[Any]) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    counts = Counter(labels)
    return -sum((c / n) * math.log(c / n) for c in counts.values())


def ConditionalEntropy(labels: List[Any], givenLabels: List[Any]) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    byGiven: Dict[Any, List[Any]] = defaultdict(list)
    for label, given in zip(labels, givenLabels):
        byGiven[given].append(label)
    return sum((len(group) / n) * Entropy(group) for group in byGiven.values())


def VMeasure(trueLabels: List[Any], predLabels: List[Any]) -> float:
    hTrue, hPred = Entropy(trueLabels), Entropy(predLabels)
    homogeneity = 1.0 if hTrue == 0 else 1 - ConditionalEntropy(trueLabels, predLabels) / hTrue
    completeness = 1.0 if hPred == 0 else 1 - ConditionalEntropy(predLabels, trueLabels) / hPred
    return 0.0 if (homogeneity + completeness) == 0 else 2 * homogeneity * completeness / (homogeneity + completeness)


def Comb2(n: int) -> int:
    return n * (n - 1) // 2


def AdjustedRandIndex(trueLabels: List[Any], predLabels: List[Any]) -> float:
    n = len(trueLabels)
    if n == 0:
        return 1.0
    contingency: Dict[Tuple[Any, Any], int] = Counter(zip(trueLabels, predLabels))
    rowSums: Dict[Any, int] = Counter(trueLabels)
    colSums: Dict[Any, int] = Counter(predLabels)

    sumComb = sum(Comb2(c) for c in contingency.values())
    sumCombRows = sum(Comb2(c) for c in rowSums.values())
    sumCombCols = sum(Comb2(c) for c in colSums.values())
    totalComb = Comb2(n)

    expected = (sumCombRows * sumCombCols) / totalComb if totalComb else 0.0
    maxIndex = (sumCombRows + sumCombCols) / 2
    denom = maxIndex - expected
    return 1.0 if denom == 0 else (sumComb - expected) / denom


def LabelConsistency(
    matches: List[Tuple[int, int, float]], predSegments: List[Segment], gtExecutions: List[Dict[str, Any]]
) -> Dict[str, float]:
    if len(matches) < 2:
        return {"purity": 0.0, "vMeasure": 0.0, "adjustedRandIndex": 0.0, "matchedPairs": len(matches)}
    predLabels = [predSegments[pi].label for _, pi, _ in matches]
    gtLabels = [gtExecutions[gi]["code"] for gi, _, _ in matches]

    clusters: Dict[str, List[str]] = defaultdict(list)
    for predLabel, gtLabel in zip(predLabels, gtLabels):
        clusters[predLabel].append(gtLabel)
    purity = sum(Counter(members).most_common(1)[0][1] for members in clusters.values()) / len(matches)

    return {
        "purity": purity,
        "vMeasure": VMeasure(gtLabels, predLabels),
        "adjustedRandIndex": AdjustedRandIndex(gtLabels, predLabels),
        "matchedPairs": len(matches),
    }
