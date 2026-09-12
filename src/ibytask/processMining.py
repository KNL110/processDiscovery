import json
from datetime import datetime
import pathlib
from collections import Counter
from typing import List, Dict, Any

def integrityCheck(events: List[Dict[str, Any]]) -> tuple[bool, set, Dict[str, List[str]]]:
    """Validate raw events and return issues grouped by event ID."""
    failedIntigrity = set()
    eventIssues = {}

    def addIssue(event: Dict[str, Any], issue: str) -> None:
        failedIntigrity.add(issue)
        eventIssues.setdefault(event["event_id"], []).append(issue)

    if not events:
        failedIntigrity.add("no events")
        return False, failedIntigrity, eventIssues

    session_ids = {event["session_id"] for event in events}

    for i in range(1,len(events)):
        prev = events[i-1]
        curr = events[i]
        prevSeq = prev["correlation"]["sequence_number"]
        currSeq = curr["correlation"]["sequence_number"]
        if currSeq <= prevSeq:
            addIssue(curr, "sequence went backwards")
        # if currSeq != prevSeq + 1:
        #     addIssue(curr, "sequence break")

        sourceDelta = curr["correlation"]["ms_since_last_event"]
        if sourceDelta is not None and sourceDelta < 0:
            addIssue(curr, "negative source ms_since_last_event")

        if curr["timestamp_ms"] < prev["timestamp_ms"]:
            addIssue(curr, "raw timestamp went backwards")

    if len(session_ids) != 1:
        failedIntigrity.add("multiple session")
    if failedIntigrity:
        return False, failedIntigrity, eventIssues
    return True, failedIntigrity, eventIssues

def loadEvents(filePath: str) -> List[Dict[str, Any]]:
    events = []
    with open(filePath, 'r') as f:
        for line in f:
            if line.strip():
                event = json.loads(line)
                event['timestamp_dt'] = datetime.fromisoformat(event["timestamp_iso"].replace("Z", "+00:00"))
                events.append(event)
    return events

def loadSession(dirPath: str) -> List:
    chunkPath = pathlib.Path(dirPath)
    chunks = [d for d in chunkPath.iterdir() if d.is_dir() and d.name.startswith("chunk_")]
    chunks.sort(key=lambda d: d.name)
    events = []
    for chunk in chunks:
        events.extend(loadEvents(f"{chunk}/events.jsonl"))
    events.sort(key=lambda d: d["correlation"]["sequence_number"])
    return [event for event in events if event["event_type"] != "screenshot_smart"]

def normalizeEvents(events: List[Dict[str, Any]],integrityIssues: Dict[str, List[str]]) -> tuple[List[Dict[str, Any]], Dict[str, Counter]]:
    """Create a process-mining-safe timeline without changing raw event fields.

    Raw-data issues are detected only by ``integrityCheck`` and passed in here.
    Add future source-validation rules to ``integrityCheck``. Add only
    normalization-specific rules, such as a new repair strategy, to this function.
    """
    normalizedEvents = []
    issueCounts = Counter()
    previousEvent = None
    previousNormalizedTimestamp = None
    for event in events:
        normalizedEvent = event.copy()
        issues = list(integrityIssues.get(event["event_id"], []))
        rawTimestamp = event["timestamp_ms"]

        normalizedTimestamp = rawTimestamp if previousNormalizedTimestamp is None else max(
            rawTimestamp, previousNormalizedTimestamp
        )
        if normalizedTimestamp != rawTimestamp:
            issues.append("timestamp clamped")

        normalizedEvent["normalized_timestamp_ms"] = normalizedTimestamp
        normalizedEvent["normalized_ms_since_last_event"] = (
            None if previousNormalizedTimestamp is None
            else normalizedTimestamp - previousNormalizedTimestamp
        )
        normalizedEvent["normalization_issues"] = issues

        issueCounts.update(issues)
        normalizedEvents.append(normalizedEvent)
        previousEvent = event
        previousNormalizedTimestamp = normalizedTimestamp

    return normalizedEvents, issueCounts

if __name__ == "__main__":
    datasetPath = "./dataset_a"
    sessions = [d for d in pathlib.Path(datasetPath).iterdir() if d.is_dir()]
    sessionPath = "./dataset_a/ses_20260630-121953-LAPTOP-R36BQBTE"
    cnt = 0
    fails = set()
    normalizationIssues = Counter()
    for session in sessions:
        sessionPath = session
        rawEvents = loadSession(str(sessionPath))
        isIntegrityValid, failedIntegrity, sessionIntegrityIssues = integrityCheck(rawEvents)
        events, sessionNormalizationIssues = normalizeEvents(rawEvents, sessionIntegrityIssues)
        normalizationIssues.update(sessionNormalizationIssues)

        if not isIntegrityValid:
            # print(f"Integrity check failed for session {sessionPath}: {failedIntegrity}")
            # print("="*50)
            fails.update(failedIntegrity)
            cnt += 1
    print(f"Total sessions with structural integrity issues: {cnt}")
    print(f"Total structural integrity issues: {fails}")
    print(f"Normalization issues: {dict(normalizationIssues)}")
