import json
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any


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
                events.append(event)
    return events

if __name__ == "__main__":
    filePath = "./dataset_a/ses_20260630-121953-LAPTOP-R36BQBTE/chunk_20260630-1200-LAPTOP-R36BQBTE/events.jsonl"
    events = loadEvents(filePath)
    print(f"Loaded {len(events)} events from {filePath}")
    for event in events:
        print(event)
        break