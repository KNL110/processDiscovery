from typing import Any, Counter, Dict
from urllib.parse import urlparse

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
        "action": ActionTaken(event)
    }

def AppContext(eventSig: Dict[str, Any]) -> str | None:
    if not eventSig["app"]:
        return None
    if eventSig["domain"]:
        return f"{eventSig["app"]}|{eventSig["domain"]}"
    return eventSig["app"]


