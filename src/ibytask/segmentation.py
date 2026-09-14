from dataclasses import dataclass, field
from typing import Any, Dict

from .utils import AppContext, EventSignature

nonWorkEventTypes = {
    "session_start", "session_end",
    "extension_connected", "extension_disconnected",
    "upload_started", "upload_completed", "upload_failed",
    "screenshot_smart",
}

boundarySignalEventTypes = {
    "window_title_change", "window_state_change",
    "browser_alert", "browser_tab_event","browser_navigation",
    "dialog_opened", "dialog_closed","app_switch"
}

noiseApps = {"WindowsTerminal", "procmine-desktop-agent", "Windows Explorer", "OpenWith", "prl_cc"}

def IsWorkEvent(event: dict[str, Any]) -> bool:
    if event["event_type"] in nonWorkEventTypes:
        return False
    if event["event_type"] == "keystroke" and event.get("payload", {}).get("key_action") == "release":
        return False
    return True

@dataclass
class Thread:
    threadId = None
    events = None
    recentApps = None
    allApps = None
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
