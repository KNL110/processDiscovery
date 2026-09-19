import heapq
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


# probabilistic measure of text overlap between a unit and a thread, range: [0.0, 1.0]
def TextOverlap(unit: MicroUnit, thread: Thread) -> float:
    if not unit.textTokens or not thread.textTokens:
        return 0.0
    union = unit.textTokens | thread.textTokens
    return len(unit.textTokens & thread.textTokens) / len(union) if union else 0.0

def BoundarySignalBetween(fromTs, toTs, boundaryTsSorted: list) -> bool:
    for ts in boundaryTsSorted:
        if ts <= fromTs:
            continue
        if ts >= toTs:
            break
        return True
    return False

def TimeDecay(gapSeconds: float, resumeWindowSeconds: float) -> float:
    """ a naive probabilistic decay function for the time gap between two units, range: [0.0, 1.0] 
     more time gap between two units, less likely they are in the same thread"""
    if gapSeconds <= 0:
        return 1.0
    return max(1.0 - gapSeconds / resumeWindowSeconds, 0.0)

def OverlapAwareGap(unit: MicroUnit, thread: Thread) -> float:
    return max(0.0, (unit.startTs - thread.lastUnit().endTs).total_seconds())

def ContinuationScore(
    unit: MicroUnit, thread: Thread, resumeWindowSeconds: float,
    boundaryTsSorted: list,
    appDomainWeight: float = 0.7, textWeight: float = 0.3, timeDecayWeight: float = 0.3,
    boundaryPenalty: float = 0.3
) -> float:
    """ probabilistic measure of whether unit continues thread, range: [0, 1.0].
    the hyperparameter resumeWindowSeconds is determined from the analysis of the given data,
    and boundaryTsSorted is a sorted list of timestamps of boundary signals in the session.
    Callers compare this against a joinThreshold themselves - kept separate so multiple
    open threads can be scored and ranked rather than stopping at the first passing one.
    """
    last = thread.lastUnit()
    rawGapSeconds = (unit.startTs - last.endTs).total_seconds()

    if rawGapSeconds > resumeWindowSeconds:
        return -1.0
    if unit.caseIds & thread.seenCaseIds:
        return 1.0
    if unit.elementAnchor and unit.elementAnchor == last.elementAnchor and IsCaseSpecificAnchor(unit.elementAnchor):
        return 1.0

    gapSeconds = OverlapAwareGap(unit, thread)
    baseScore = appDomainWeight * AppDomainSimilarity(unit, thread) + textWeight * TextOverlap(unit, thread)

    #entropy based descision fxn, to believe  timedecay can be more promissing or not
    score = TimeDecay(gapSeconds, resumeWindowSeconds)*timeDecayWeight + baseScore * (1-timeDecayWeight)
    if BoundarySignalBetween(last.endTs, unit.startTs, boundaryTsSorted):
        score = max(score-boundaryPenalty,0)
    return score

def SpansCanTouch(a: Thread, b: Thread, resumeWindowSeconds: float) -> bool:
    """
    cheap-ish prune: true iff at least one cross-thread pair would land adjacent to
    each other after interleaving a.units and b.units by startTs, with gap
    <= resumeWindowSeconds. A thread's own units are each individually time sorted
    already (attach() appends, TryMerge's interleave sorts), so this is a real
    two-pointer merge scan rather than a bounding-box check: a thread's outer span
    (first unit start to last unit end) can be many multiples of resumeWindowSeconds
    wide once it has several units, so "do the outer spans overlap" stops reflecting
    "is anything actually close in time" and degenerates into an almost-always-true
    check. Same worst case O(n+m) as TryMerge's interleave, but skips ContinuationScore
    entirely and exits the moment one qualifying cross-adjacency is found.
    """
    i = j = 0
    na, nb = len(a.units), len(b.units)
    prevFrom: str | None = None
    prevUnit: MicroUnit | None = None

    while i < na and j < nb:
        if a.units[i].startTs <= b.units[j].startTs:
            curFrom, curUnit = 'a', a.units[i]
            i += 1
        else:
            curFrom, curUnit = 'b', b.units[j]
            j += 1
        if prevFrom is not None and prevUnit is not None and prevFrom != curFrom:
            gap = max(0.0, (curUnit.startTs - prevUnit.endTs).total_seconds())
            if gap <= resumeWindowSeconds:
                return True
        prevFrom, prevUnit = curFrom, curUnit

    remaining, remainingFrom = (a.units[i:], 'a') if i < na else (b.units[j:], 'b')
    if remaining and prevUnit is not None and prevFrom != remainingFrom:
        gap = max(0.0, (remaining[0].startTs - prevUnit.endTs).total_seconds())
        return gap <= resumeWindowSeconds
    return False

def TryMerge(
    a: Thread, b: Thread, resumeWindowSeconds: float, joinThreshold: float, boundaryTsSorted: list
) -> tuple[list[MicroUnit], float] | None:
    """ 
    interleave a and b by time and validate the merge.
    """
    owner = {id(u): 0 for u in a.units}
    owner.update({id(u): 1 for u in b.units})
    merged = sorted(a.units + b.units, key=lambda u: u.startTs)

    prefix = Thread(threadId=-1)
    prefix.attach(merged[0])
    weakest = 1.0

    for i in range(1, len(merged)):
        prev, nxt = merged[i - 1], merged[i]
        if owner[id(prev)] != owner[id(nxt)]:
            score = ContinuationScore(nxt, prefix, resumeWindowSeconds, boundaryTsSorted)
            if score < joinThreshold:
                return None
            weakest = min(weakest, score)
        prefix.attach(nxt)

    return merged, weakest

def AssignThreads(units: list[MicroUnit], resumeWindowSeconds: float, joinThreshold: float) -> list[list[MicroUnit]]:
    """ agglomerative: every unit starts as its own thread, then the best scoring admissible
    merge is applied repeatedly until none is left.
    """
    boundaryTsSorted = sorted(u.startTs for u in units if u.isBoundarySignal)
    work = [u for u in units if not u.isBoundarySignal]  # boundary units are signal only, never members
    if not work:
        return []

    live: dict[int, Thread] = {}
    for i, unit in enumerate(work):
        thread = Thread(threadId=i)
        thread.attach(unit)
        live[i] = thread
    nextId = len(work)

    heap: list[tuple[float, int, int]] = []

    def pushPair(x: Thread, y: Thread) -> None:
        if not SpansCanTouch(x, y, resumeWindowSeconds):
            return
        result = TryMerge(x, y, resumeWindowSeconds, joinThreshold, boundaryTsSorted)
        if result:
            heapq.heappush(heap, (-result[1], x.threadId, y.threadId))

    threads = list(live.values())
    for i, x in enumerate(threads):
        for y in threads[i + 1:]:
            if not SpansCanTouch(x, y, resumeWindowSeconds):
                break  # work is time sorted, so everything further out is further away
            pushPair(x, y)

    while heap:
        _, idX, idY = heapq.heappop(heap)
        # lazy invalidation: any merge consuming x or y removed it from live, and while both
        # are live neither has changed, so a surviving entry's score is still current
        if idX not in live or idY not in live:
            continue
        x, y = live.pop(idX), live.pop(idY)
        result = TryMerge(x, y, resumeWindowSeconds, joinThreshold, boundaryTsSorted)
        if result is None:
            live[idX], live[idY] = x, y
            continue

        mergedUnits, _ = result
        merged = Thread(threadId=nextId)
        nextId += 1
        for unit in mergedUnits:
            merged.attach(unit)
        for other in live.values():
            pushPair(merged, other)
        live[merged.threadId] = merged

    finished = sorted(live.values(), key=lambda t: t.units[0].startTs)
    return [t.units for t in finished]
