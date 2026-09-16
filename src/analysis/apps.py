import pathlib
import sys
from collections import Counter

from ibytask.ingest import listSessions, loadSession


def AppNames(event: dict) -> list[str]:
    names = []
    activeApp = event.get("context", {}).get("active_app")
    if activeApp:
        name = activeApp.get("app_name") or activeApp.get("process_name")
        if name:
            names.append(name)
    payload = event.get("payload", {}) or {}
    for key in ("new_app", "previous_app"):
        app = payload.get(key)
        if isinstance(app, dict):
            name = app.get("app_name") or app.get("process_name")
            if name:
                names.append(name)
    return names


def appCounts(datasetDir: pathlib.Path) -> tuple[Counter, dict[str, set[str]]]:
    #Returns event count per app, session names each app appears in
    counts: Counter = Counter()
    sessionsSeenIn: dict[str, set[str]] = {}
    for sessionDir in listSessions(datasetDir):
        for event in loadSession(sessionDir):
            for name in AppNames(event):
                counts[name] += 1
                sessionsSeenIn.setdefault(name, set()).add(sessionDir.name)
    return counts, sessionsSeenIn


def main():
    root = pathlib.Path(".")
    allApps: set[str] = set()
    perDataset: dict[str, tuple[Counter, dict[str, set[str]]]] = {}

    for label in ("dataset_a", "dataset_b"):
        counts, sessionsSeenIn = appCounts(root / label)
        perDataset[label] = (counts, sessionsSeenIn)
        allApps |= set(counts)
        print(f"=== {label}: {len(counts)} distinct apps, {sum(counts.values())} app-bearing events ===")
        for app, c in counts.most_common():
            nSessions = len(sessionsSeenIn[app])
            print(f"  {app:35s} {c:6d} events  ({nSessions} sessions)")
        print()

    print(f"=== union across both datasets: {len(allApps)} distinct apps ===")
    onlyA = set(perDataset["dataset_a"][0]) - set(perDataset["dataset_b"][0])
    onlyB = set(perDataset["dataset_b"][0]) - set(perDataset["dataset_a"][0])
    both = set(perDataset["dataset_a"][0]) & set(perDataset["dataset_b"][0])
    print(f"only in dataset_a ({len(onlyA)}):", sorted(onlyA))
    print(f"only in dataset_b ({len(onlyB)}):", sorted(onlyB))
    print(f"in both ({len(both)}):", sorted(both))


if __name__ == "__main__":
    main()
