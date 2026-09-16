import json
import pathlib
import sys
from datetime import datetime
from typing import Any, Dict, List

from ibytask.ingest import fiveNumberSummary, listSessions, readJsonlFile


def loadGtManifest(sessionDir: pathlib.Path) -> Dict[str, Any]:
    return json.loads((sessionDir / "gt_manifest.json").read_text(encoding="utf-8"))


def loadGtEvents(sessionDir: pathlib.Path) -> List[Dict[str, Any]]:
    return readJsonlFile(sessionDir / "gt.jsonl")


def parseTs(s: str) -> datetime:
    return datetime.fromisoformat(s)


def executionDurations(sessionDirs: List[pathlib.Path]) -> List[float]:
    durations = []
    for sessionDir in sessionDirs:
        for process in loadGtManifest(sessionDir)["processes"]:
            for ex in process["executions"]:
                if ex.get("start_ts") and ex.get("end_ts"):
                    durations.append((parseTs(ex["end_ts"]) - parseTs(ex["start_ts"])).total_seconds())
    return durations


def resumeGapsFromEvents(sessionDirs: List[pathlib.Path]) -> List[float]:
    """Direct process_suspended -> process_resumed gap, matched by split_id, from
    the raw gt.jsonl event stream. The most direct real measurement of 'how long
    can someone step away and still resume the same execution'."""
    gaps = []
    for sessionDir in sessionDirs:
        suspendedAt: Dict[str, datetime] = {}
        for e in loadGtEvents(sessionDir):
            if e.get("event") == "process_suspended" and e.get("split_id"):
                suspendedAt[e["split_id"]] = parseTs(e["ts_utc"])
            elif e.get("event") == "process_resumed" and e.get("split_id") in suspendedAt:
                gaps.append((parseTs(e["ts_utc"]) - suspendedAt.pop(e["split_id"])).total_seconds())
    return gaps


def sameCaseResumeGapsFromManifest(sessionDirs: List[pathlib.Path]) -> List[float]:
    """Cross-check against resumeGapsFromEvents using gt_manifest's
    continues_from_prev-linked executions instead of raw gt.jsonl events."""
    gaps = []
    for sessionDir in sessionDirs:
        for process in loadGtManifest(sessionDir)["processes"]:
            execs = sorted(
                (ex for ex in process["executions"] if ex.get("start_ts") and ex.get("end_ts")),
                key=lambda e: e.get("seq", 0),
            )
            for prev, curr in zip(execs, execs[1:]):
                if curr.get("continues_from_prev"):
                    gaps.append((parseTs(curr["start_ts"]) - parseTs(prev["end_ts"])).total_seconds())
    return gaps


def resumeGapsFromExpectedBoundaries(sessionDirs: List[pathlib.Path]) -> List[float]:
    """A third, independent cross-check: expected_boundaries is a curated,
    ordered boundary timeline the manifest ships specifically for evaluation --
    pairing consecutive process_suspended -> process_resumed entries for the
    same process code sidesteps gt.jsonl's documented quirks (duplicate
    process_started lines, unpaired switched_out) entirely."""
    gaps = []
    for sessionDir in sessionDirs:
        boundaries = loadGtManifest(sessionDir)["expected_boundaries"]
        suspendedAt: Dict[str, datetime] = {}
        for b in boundaries:
            if b["type"] == "process_suspended":
                suspendedAt[b["code"]] = parseTs(b["ts"])
            elif b["type"] == "process_resumed" and b["code"] in suspendedAt:
                gaps.append((parseTs(b["ts"]) - suspendedAt.pop(b["code"])).total_seconds())
    return gaps


def switchedOutGaps(sessionDirs: List[pathlib.Path]) -> List[float]:
    """process_switched_out -> the next process_started/resumed -- the 'normal'
    gap when moving on to different work, not a resume of the same case."""
    gaps = []
    for sessionDir in sessionDirs:
        lastSwitchOutTs = None
        for e in loadGtEvents(sessionDir):
            if e.get("event") == "process_switched_out":
                lastSwitchOutTs = parseTs(e["ts_utc"])
            elif e.get("event") in ("process_started", "process_resumed") and lastSwitchOutTs:
                gaps.append((parseTs(e["ts_utc"]) - lastSwitchOutTs).total_seconds())
                lastSwitchOutTs = None
    return gaps


def differentCaseGaps(sessionDirs: List[pathlib.Path]) -> List[float]:
    """Gap between the end of one execution and the start of the next one (in
    wall-clock order) when they're different cases and the next isn't a resume
    -- the baseline 'moved on to something unrelated' gap."""
    gaps = []
    for sessionDir in sessionDirs:
        allExecs = []
        for process in loadGtManifest(sessionDir)["processes"]:
            for ex in process["executions"]:
                if ex.get("start_ts") and ex.get("end_ts"):
                    allExecs.append((parseTs(ex["start_ts"]), parseTs(ex["end_ts"]), ex.get("case_id"), ex.get("continues_from_prev")))
        allExecs.sort()
        for (_, prevEnd, prevCase, _), (currStart, _, currCase, currContinues) in zip(allExecs, allExecs[1:]):
            if currCase != prevCase and not currContinues:
                gaps.append((currStart - prevEnd).total_seconds())
    return gaps


def noiseBlockDurations(sessionDirs: List[pathlib.Path]) -> List[float]:
    """noise_blocks has no explicit duration -- only an injection timestamp and
    type -- so this reports the gap to the NEXT boundary of any kind as a proxy
    for how long the noise interlude runs before real work resumes."""
    durations = []
    for sessionDir in sessionDirs:
        manifest = loadGtManifest(sessionDir)
        boundaryTsSorted = sorted(parseTs(b["ts"]) for b in manifest["expected_boundaries"])
        for block in manifest.get("noise_blocks", []):
            ts = parseTs(block["ts"])
            nextTs = next((t for t in boundaryTsSorted if t > ts), None)
            if nextTs:
                durations.append((nextTs - ts).total_seconds())
    return durations


def noiseBlockTypeCounts(sessionDirs: List[pathlib.Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for sessionDir in sessionDirs:
        for block in loadGtManifest(sessionDir).get("noise_blocks", []):
            counts[block["type"]] = counts.get(block["type"], 0) + 1
    return counts


def splitTaskCounts(sessionDirs: List[pathlib.Path]) -> List[float]:
    """From split_processes: how many tasks happen in the phase-1 half of a
    split execution before it gets interrupted -- a precise, task-id-level
    cross-check on 'how much work happens before a genuine interruption'."""
    counts = []
    for sessionDir in sessionDirs:
        for split in loadGtManifest(sessionDir).get("split_processes", {}).values():
            counts.append(float(len(split.get("phase1_task_ids", []))))
    return counts


def main():
    datasetDir = pathlib.Path(__file__).resolve().parents[1] / "dataset_a"
    sessionDirs = listSessions(datasetDir)
    print(f"analyzing {len(sessionDirs)} sessions")

    print("execution durations (s):", fiveNumberSummary(executionDurations(sessionDirs)))
    print("resume gaps, gt.jsonl suspend->resume (s):", fiveNumberSummary(resumeGapsFromEvents(sessionDirs)))
    print("resume gaps, gt_manifest continues_from_prev (s):", fiveNumberSummary(sameCaseResumeGapsFromManifest(sessionDirs)))
    print("resume gaps, expected_boundaries (s):", fiveNumberSummary(resumeGapsFromExpectedBoundaries(sessionDirs)))
    print("switched-out -> next process gaps (s):", fiveNumberSummary(switchedOutGaps(sessionDirs)))
    print("different-case, non-resume gaps (s):", fiveNumberSummary(differentCaseGaps(sessionDirs)))
    print("noise block -> next boundary gaps (s):", fiveNumberSummary(noiseBlockDurations(sessionDirs)))
    print("noise block types:", noiseBlockTypeCounts(sessionDirs))
    print("split phase-1 task counts:", fiveNumberSummary(splitTaskCounts(sessionDirs)))


if __name__ == "__main__":
    main()
