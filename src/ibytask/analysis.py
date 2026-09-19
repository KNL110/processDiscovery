from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List

from .pipeline import Segment
from .utils import ActionTaken, AppOrProcessName


@dataclass
class LabelStats:
    label: str
    executionCount: int
    totalSeconds: float
    avgSeconds: float
    medianSeconds: float
    distinctSessions: int
    distinctOperators: int
    distinctMachines: int
    dominantApps: List[str]
    branchingFactor: float
    dominantPathCoverage: float
    distinctPatterns: int
    dominantPatternShare: float
    priorityScore: float


def BuildDfg(actionSequences: List[List[str]]) -> Dict[str, Dict[str, int]]:
    """ directly-follows graph as adjacency dict: dfg[a][b] = observed a->b transition count. """
    dfg: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for seq in actionSequences:
        for a, b in zip(seq, seq[1:]):
            dfg[a][b] += 1
    return dfg


def BranchingFactorOf(dfg: Dict[str, Dict[str, int]]) -> float:
    outDegrees = [len(edges) for edges in dfg.values() if edges]
    return sum(outDegrees) / len(outDegrees) if outDegrees else 0.0


def DominantPathCoverageOf(dfg: Dict[str, Dict[str, int]]) -> float:
    """ of all observed transitions, what share follow each node's single most common next
    step? 1.0 = perfectly linear/deterministic process, low = many branches. """
    totalWeight = sum(sum(edges.values()) for edges in dfg.values())
    if totalWeight == 0:
        return 0.0
    dominantWeight = sum(max(edges.values()) for edges in dfg.values() if edges)
    return dominantWeight / totalWeight


def CanonicalSkeleton(actionSeq: List[str]) -> tuple:
    """ keep only actions annotated with a specific target (e.g. "click: pi-note",
    "nav: x/y") - which page/field/button was touched - and collapse consecutive
    duplicates. Drops generic noise (mouse_click, mouse_scroll, keystroke, ...) that
    varies in count per execution without reflecting a structurally different path. """
    meaningful = [a for a in actionSeq if a and (":" in a or a == "browser_form_input")]
    skeleton: List[str] = []
    for action in meaningful:
        if not skeleton or skeleton[-1] != action:
            skeleton.append(action)
    return tuple(skeleton)


def HandlingPatterns(actionSequences: List[List[str]]) -> Dict[tuple, int]:
    """ execution count per canonical action-skeleton - directly answers "are there
    different handling patterns within the same process". """
    counts: Counter = Counter()
    for seq in actionSequences:
        counts[CanonicalSkeleton(seq)] += 1
    return dict(counts)


def MinMaxNormalize(values: Dict[str, float]) -> Dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 1.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def AnalyzeSegments(segments: List[Segment], sessionOperators: Dict[str, Dict[str, str]]) -> List[LabelStats]:
    """ sessionOperators maps sessionId -> {"operator": usernameHash, "machine": machineId}
    (best-effort proxies pulled from event source, since there is no HR identity field). """
    byLabel: Dict[str, List[Segment]] = defaultdict(list)
    for seg in segments:
        byLabel[seg.label].append(seg)

    prelim: Dict[str, Dict[str, Any]] = {}
    rawTotals, rawComplexity = {}, {}
    for label, segs in byLabel.items():
        durations = [(s.end - s.start).total_seconds() for s in segs]
        actionSeqs = [[ActionTaken(e) or "" for e in s.events] for s in segs]
        appCounter: Counter = Counter()
        for s in segs:
            for e in s.events:
                app = AppOrProcessName(e)
                if app:
                    appCounter[app] += 1

        dfg = BuildDfg(actionSeqs)
        branching = BranchingFactorOf(dfg)
        coverage = DominantPathCoverageOf(dfg)
        patterns = HandlingPatterns(actionSeqs)
        dominantPatternCount = max(patterns.values()) if patterns else 0

        operators = {sessionOperators.get(s.sessionId, {}).get("operator") for s in segs}
        machines = {sessionOperators.get(s.sessionId, {}).get("machine") for s in segs}
        sessions = {s.sessionId for s in segs}

        prelim[label] = dict(
            label=label,
            executionCount=len(segs),
            totalSeconds=sum(durations),
            avgSeconds=sum(durations) / len(durations),
            medianSeconds=sorted(durations)[len(durations) // 2],
            distinctSessions=len(sessions),
            distinctOperators=len(operators - {None}),
            distinctMachines=len(machines - {None}),
            dominantApps=[app for app, _ in appCounter.most_common(3)],
            branchingFactor=branching,
            dominantPathCoverage=coverage,
            distinctPatterns=len(patterns),
            dominantPatternShare=dominantPatternCount / len(segs) if segs else 0.0,
        )
        rawTotals[label] = prelim[label]["totalSeconds"]
        rawComplexity[label] = branching

    normOpportunity = MinMaxNormalize(rawTotals)
    normComplexity = MinMaxNormalize(rawComplexity)

    results = []
    for label, stats in prelim.items():
        opportunity = normOpportunity.get(label, 0.0)
        complexityPenalty = normComplexity.get(label, 0.0)
        priority = opportunity * (1.0 - 0.5 * complexityPenalty)
        results.append(LabelStats(priorityScore=priority, **stats))

    results.sort(key=lambda s: s.priorityScore, reverse=True)
    return results


def SessionOperators(datasetDir) -> Dict[str, Dict[str, str]]:
    """ pull operator/machine proxies from the first event of each session's source field. """
    from .ingest import listSessions, loadSession

    result: Dict[str, Dict[str, str]] = {}
    for sessionDir in listSessions(datasetDir):
        events = loadSession(sessionDir)
        if not events:
            continue
        source = events[0].get("source", {})
        result[sessionDir.name] = {
            "operator": source.get("username_hash"),
            "machine": source.get("machine_id"),
        }
    return result
