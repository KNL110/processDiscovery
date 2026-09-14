from dataclasses import dataclass, field
from typing import Any, Dict

from .utils import AppContext, EventSignature

nonWorkEventTypes = {
    "session_start", "session_end",
    "extension_connected", "extension_disconnected",
    "upload_started", "upload_completed", "upload_failed",
    "screenshot_smart",
}

@dataclass
class Thread:
    threadId = None
    events = None
    recentApps = None
    allApss = None
    lastDomain = None
    lastPath = None
    lastTs = None

    def __init__(self, threadId: int):
        self.threadId = threadId


def ExtractWork(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workEvents = [e for e in events if e.get("event_type") not in nonWorkEventTypes]

    openThreads: Dict[int,Thread] = {}
    nextThreadId = 2
    openThreads[1] = Thread(threadId=1)
    for event in workEvents:
        sig = EventSignature(event)
        ts = event["normalized_ts"]

        
    return workEvents
