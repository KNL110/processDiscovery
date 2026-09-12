import json
import statistics
from datetime import datetime
import pathlib
from typing import List, Dict, Any, Optional

requiredFields = ("event_id", "session_id", "timestamp_ms", "timestamp_iso", "correlation")

def fiveNumberSummary(values: List[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    sortedVals = sorted(values)
    if len(sortedVals) == 1:
        q1 = q3 = sortedVals[0]
    else:
        q1, _, q3 = statistics.quantiles(sortedVals, n=4)
    return {
        "count": len(sortedVals),
        "min": sortedVals[0],
        "q1": q1,
        "median": statistics.median(sortedVals),
        "q3": q3,
        "max": sortedVals[-1],
    }

def integrityCheck(events: List[Dict[str, Any]]) -> tuple[bool, set, Dict[str, List[float]]]:
    # Validate raw events and return issues, plus raw values for timestamp_ms backward
    # jumps and negative ms_since_last_event so callers can pool them across sessions.
    failedIntigrity = set()
    timestampBackwardDeltas = []
    negativeMsSinceLastEvent = []

    def addIssue(issue: str) -> None:
        failedIntigrity.add(issue)
    if not events:
        failedIntigrity.add("no events")
        return False, failedIntigrity, {"timestamp_ms_backward_delta": [], "negative_ms_since_last_event": []}

    seenEventIds = set()
    sessionIds = set()

    for i, event in enumerate(events):
        for field in requiredFields:
            if event.get(field) is None:
                addIssue(f"missing field: {field}")

        eventId = event.get("event_id")
        if eventId is not None:
            if eventId in seenEventIds:
                addIssue(f"duplicate event_id: {eventId}")
            seenEventIds.add(eventId)

        sessionId = event.get("session_id")
        if sessionId is not None:
            sessionIds.add(sessionId)


        correlation = event.get("correlation") or {}
        sourceDelta = correlation.get("ms_since_last_event")
        if sourceDelta is not None and sourceDelta < 0:
            addIssue(f"negative ms_since_last_event: {sourceDelta}")
            negativeMsSinceLastEvent.append(sourceDelta)

        if i == 0:
            continue
        prev = events[i - 1]

        currSeq = correlation.get("sequence_number")
        prevSeq = (prev.get("correlation") or {}).get("sequence_number")
        if currSeq is not None and prevSeq is not None:
            if currSeq < prevSeq:
                addIssue(f"sequence went backwards: {currSeq} < {prevSeq}")
            elif currSeq == prevSeq:
                addIssue(f"duplicate sequence_number: {currSeq}")

        timestampMs = event.get("timestamp_ms")
        prevTs, currTs = prev.get("timestamp_ms"), timestampMs
        if prevTs is not None and currTs is not None and currTs < prevTs:
            addIssue(f"timestamp_ms went backwards: {currTs} < {prevTs}")
            timestampBackwardDeltas.append(prevTs - currTs)

    if len(sessionIds) > 1:
        failedIntigrity.add("multiple session")

    rawValues = {
        "timestamp_ms_backward_delta": timestampBackwardDeltas,
        "negative_ms_since_last_event": negativeMsSinceLastEvent,
    }
    return (not failedIntigrity), failedIntigrity, rawValues

def loadEvents(filePath: pathlib.Path) -> List[Dict[str, Any]]:
    events = []
    with open(filePath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                event = json.loads(line)
                event['timestamp_dt'] = datetime.fromisoformat(event["timestamp_iso"].replace("Z", "+00:00"))
                events.append(event)
    return events

def loadSession(dirPath: pathlib.Path) -> List:
    chunkPath = pathlib.Path(dirPath)
    chunks = [d for d in chunkPath.iterdir() if d.is_dir() and d.name.startswith("chunk_")]
    events = []
    for chunk in chunks:
        events.extend(loadEvents(chunk / "events.jsonl"))
    events.sort(key=lambda d: d["correlation"]["sequence_number"])
    return normalizeTimestamps(events)

def listSessions(datasetDir: pathlib.Path) -> list[pathlib.Path]:
    return sorted(d for d in datasetDir.iterdir() if d.is_dir() and d.name.startswith("ses_"))

def normalizeTimestamps(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lastTs = None
    for event in events:
        ts = event["timestamp_dt"]
        if lastTs is not None and ts < lastTs:
            ts = lastTs
        event["normalized_ts"] = ts
        lastTs = ts
    return events


if __name__ == "__main__":
    datasetPath = "./dataset_a"
    sessions = listSessions(pathlib.Path(datasetPath))
    sessionPath = "./dataset_a/ses_20260630-121953-LAPTOP-R36BQBTE"
    cnt = 0
    allTimestampBackwardDeltas = []
    allNegativeMsSinceLastEvent = []
    for session in sessions:
        sessionPath = session
        Events = loadSession(sessionPath)
        isIntegrityValid, failedIntegrity, rawValues = integrityCheck(Events)
        allTimestampBackwardDeltas.extend(rawValues["timestamp_ms_backward_delta"])
        allNegativeMsSinceLastEvent.extend(rawValues["negative_ms_since_last_event"])
        if not isIntegrityValid:
            cnt += 1
    print(f"Total sessions with structural integrity issues: {cnt}")
    print(f"timestamp_ms_backward_delta: {fiveNumberSummary(allTimestampBackwardDeltas)}")
    print(f"negative_ms_since_last_event: {fiveNumberSummary(allNegativeMsSinceLastEvent)}")
