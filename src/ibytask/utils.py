import re
from typing import Any, Counter, Dict
from urllib.parse import urlparse

asciiTokenPattern = re.compile(r"[A-Za-z0-9_]{2,}")

def tokenizeText(text: str | None) -> set[str]:
    #for rough topical similarity
    if not text:
        return set()
    return {t.lower() for t in asciiTokenPattern.findall(text)}

def BrowserTab(event : dict[str,Any]):
    tab = event.get("context", {}).get("active_browser_tab")
    if not tab or not tab.get("url"):
        return None, None
    parsedUrl = urlparse(tab["url"])
    return parsedUrl.netloc, parsedUrl.path


def AppOrProcessName(event: dict[str, Any]) -> str | None:
    activeApp = event.get("context", {}).get("active_app")
    if activeApp:
        return activeApp.get("app_name") or activeApp.get("process_name")
    return None

def ExtractedText(event: dict[str, Any]) -> str | None:
    extracted = event.get("context", {}).get("extracted_text")
    return extracted.get("text") if extracted else None

def ActionTaken(event : dict[str,Any]) -> str | None:
    eventType = event.get("event_type")

    if eventType == "browser_click":
        element = event.get("payload", {}).get("element",{})
        elementId = element.get("attributes",{}).get("id","")
        return f"click: {elementId}" if elementId else "click"
    
    elif eventType == "browser_navigation":
        domain,path = BrowserTab(event)
        return f"nav: {domain}/{path}" if path else "nav"
    
    elif eventType == "app_switch":
        newApp = event.get("payload", {}).get("new_app")
        return f"switch: {newApp}" if newApp else "switch"
    
    return eventType



def EventSignature(event : Dict[str, Any]) -> Dict[str, Any]:
    domain,path = BrowserTab(event)
    return {
        "app": AppOrProcessName(event),
        "domain":domain,
        "path": path,
        "action": ActionTaken(event),
        "textTokens": tokenizeText(ExtractedText(event)),
    }

def AppContext(eventSig: Dict[str, Any]) -> str | None:
    if not eventSig["app"]:
        return None
    if eventSig["domain"]:
        return f"{eventSig["app"]}|{eventSig["domain"]}"
    return eventSig["app"]



def SegmentFingerprint(events: list[Dict[str, Any]]) -> Dict[str, Any]:
    apps : Counter = Counter()
    domains : Counter = Counter()
    paths : Counter = Counter()
    textTokens : Counter = Counter()
    actionSeq : list[str] = []
    for event in events:
        sig = EventSignature(event)
        appContext = AppContext(sig)
        if appContext:
            apps[appContext] += 1
        if sig["domain"]:
            domains[sig["domain"]] += 1
        if sig["path"]:
            paths[sig["path"]] += 1
        textTokens.update(sig["textTokens"])
        actionSeq.append(sig["action"])

    return {
        "apps": dict(apps),
        "domains": dict(domains),
        "paths": dict(paths),
        "textTokens": dict(textTokens),
        "actionSeq": actionSeq,
        "eventCount": len(events),
    }