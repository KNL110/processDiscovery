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
#-----------------------------------------------------------------------------------------------

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

#-----------------------------------------------------------------------------------------------

@dataclass
class Thread:
    threadId: int
    units: list[MicroUnit] = field(default_factory=list)
    seenCaseIds: set[str] = field(default_factory=set)
    recentApps: list[str] = field(default_factory=list)
    textTokens: set[str] = field(default_factory=set)

    def lastUnit(self) -> MicroUnit:
        return self.units[-1]

    def attach(self, unit: MicroUnit) -> None:
        self.units.append(unit)
        if unit.app:
            self.recentApps.append(unit.app)
            self.recentApps = self.recentApps[-5:]
        self.seenCaseIds |= unit.caseIds
        self.textTokens |= unit.textTokens

def AppDomainSimilarity(unit: MicroUnit, thread: Thread) -> float:
    # range: [0.0, 1.0]. appScore in {0.0, 0.4, 1.0}, locationScore in {0.0, 0.6, 0.9};
    last = thread.lastUnit()

    if unit.app and unit.app == last.app:
        appScore = 1.0
    elif unit.app and unit.app in thread.recentApps:
        appScore = 0.4
    else:
        appScore = 0.0

    if unit.domain and unit.domain == last.domain:
        locationScore = 0.9 if unit.path and unit.path == last.path else 0.6
    else:
        locationScore = 0.0

    return 1 - (1 - appScore) * (1 - locationScore)


def TextOverlap(unit: MicroUnit, thread: Thread) -> float:
    if not unit.textTokens or not thread.textTokens:
        return 0.0
    union = unit.textTokens | thread.textTokens
    return len(unit.textTokens & thread.textTokens) / len(union) if union else 0.0
