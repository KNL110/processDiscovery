import json
from datetime import datetime
import pathlib
import pandas as pd
from typing import List, Dict, Any

def integrityCheck(events: List[Dict[str, Any]]) -> bool:
    failedIntigrity = set()
    if not events:
        failedIntigrity.add("no events")

    for i, event in enumerate(events):
        seq = event["correlation"]["sequence_number"]

        if seq != i:
            # print(f"sequence break at index {i}: expected {i}, got {seq}")
            failedIntigrity.add("sequence break")

    session_ids = {event["session_id"] for event in events}

    if len(session_ids) != 1:
        # print(f"multiple session IDs found: {session_ids}")
        failedIntigrity.add("multiple session")

    for i in range(1, len(events)):
        if events[i]["timestamp_ms"] < events[i - 1]["timestamp_ms"]:
            # print(f"timestamp went backwards at sequence {events[i]['correlation']['sequence_number']}")
            failedIntigrity.add("timestamp went backwards")

    if failedIntigrity:
        print(f"Integrity check failed: {failedIntigrity}")
        return False
    return True

def loadEvents(filePath: str) -> List[Dict[str, Any]]:
    """
    Load events from a JSON file.
    Args:
        filePath (str): The path to the JSON file containing events.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the events.
    """
    events = []
    with open(filePath, 'r') as f:
        for line in f:
            if line.strip():
                event = json.loads(line)
                event['timestamp_dt'] = datetime.fromisoformat(event["timestamp_iso"].replace("Z", "+00:00"))
                events.append(event)
    return events

def loadSession(dirPath: str) -> List:
    # get directory names where events.jsonl files are located pattern is chucnk_YYYYMMDD-HHMM-<MachineName>
    chunkPath = pathlib.Path(dirPath)
    chunks = [d for d in chunkPath.iterdir() if d.is_dir()]
    chunks.sort(key=lambda d: d.name)
    events = []
    for chunk in chunks:
        events.extend(loadEvents(f"{chunk}/events.jsonl"))
    return events

if __name__ == "__main__":
    datasetPath = "./dataset_a"
    sessions = [d for d in pathlib.Path(datasetPath).iterdir() if d.is_dir()]
    sessionPath = "./dataset_a/ses_20260630-121953-LAPTOP-R36BQBTE"
    for session in sessions:
        sessionPath = session
        events = loadSession(str(sessionPath))
        if not integrityCheck(events):
            print("="*50)
