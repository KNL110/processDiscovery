from dataclasses import dataclass, field
from typing import Any, Dict

from .utils import *

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
class MicroUnit:
    events: list[dict[str, Any]]
    startTs: Any
    endTs: Any
    app: str | None
    domain: str | None
    path: str | None
    elementAnchor: str | None
    caseIds: set[str]
    textTokens: set[str]
    isBoundarySignal: bool
    
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

def sameRun(
        prevAction: str,
        prevApp: str | None, 
        prevAnchor: str | None, 
        currAction: str, 
        currApp: str | None, 
        currAnchor: str | None
    ) -> bool:
    if prevAnchor or currAnchor:
        return prevAnchor == currAnchor
    return prevAction == currAction and prevApp == currApp

def buildMicroUnits(events: list[dict[str, Any]]) -> list[MicroUnit]:
    units: list[MicroUnit] = []
    current: list[dict[str, Any]] = []

    def addUnitNClear():
        if not current:
            return
        sig = EventSignature(current[0])
        anchor = ElementAnchor(current[0])
        caseIds: set[str] = set(caseIdPattern.findall(anchor)) if anchor else set()
        textTokens: set[str] = set()
        for e in current:
            textTokens |= EventSignature(e)["textTokens"]

        units.append(MicroUnit(
            events=list(current),
            startTs=current[0]["normalizedTs"], 
            endTs=current[-1]["normalizedTs"],
            app=AppContext(sig),
            domain=sig["domain"], 
            path=sig["path"],
            elementAnchor=anchor, 
            caseIds=caseIds, 
            textTokens=textTokens,
            isBoundarySignal=current[0]["event_type"] in boundarySignalEventTypes,
        ))
        current.clear()

    prevAction = prevApp = prevAnchor = None
    for event in events:
        if not IsWorkEvent(event):
            continue
        sig = EventSignature(event)
        anchor = ElementAnchor(event)
        isBoundary = event["event_type"] in boundarySignalEventTypes

        if isBoundary:
            addUnitNClear()
            current.append(event)
            addUnitNClear()
        elif current and sameRun(prevAction, prevApp, prevAnchor, sig["action"], AppContext(sig), anchor): # type: ignore
            current.append(event)
        else:
            addUnitNClear()
            current.append(event)
        prevAction, prevApp, prevAnchor = sig["action"], AppContext(sig), anchor
    addUnitNClear()
    return units

def ExtractWork(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workEvents = [e for e in events if e.get("event_type") not in nonWorkEventTypes]

    openThreads: Dict[int,Thread] = {}
    nextThreadId = 2
    openThreads[1] = Thread(threadId=1)
    for event in workEvents:
        sig = EventSignature(event)
        ts = event["normalized_ts"]

        
    return workEvents
