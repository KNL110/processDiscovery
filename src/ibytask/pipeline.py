import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List

from .ingest import loadSession, listSessions
from .labeling import LabelSegments
from .segmentation import AssignThreads, buildMicroUnits


@dataclass
class Segment:
    sessionId: str
    start: Any
    end: Any
    label: str
    events: List[Dict[str, Any]]


def SegmentSession(
    sessionId: str,
    events: List[Dict[str, Any]],
    resumeWindowSeconds: float = 300.0,
    joinThreshold: float = 0.55,
    minThreadUnits: int = 14,  # picked from a 10-session sweep on dataset_a, best F1 vs gt_manifest
) -> List[Segment]:
    """ raw events -> MicroUnits -> merged Threads (our own segmentation, not the
    reference solution's deinterleave/burst approach). Segments come back unlabeled
    (label=""): labeling needs to see segments across every session at once so the
    same recurring process gets the same label everywhere, not just within one session. """
    units = buildMicroUnits(events)
    threads = AssignThreads(units, resumeWindowSeconds=resumeWindowSeconds, joinThreshold=joinThreshold)
    threads = [t for t in threads if len(t) >= minThreadUnits]

    segments = [
        Segment(
            sessionId=sessionId,
            start=thread[0].startTs,
            end=thread[-1].endTs,
            label="",
            events=[e for unit in thread for e in unit.events],
        )
        for thread in threads
    ]
    segments.sort(key=lambda s: s.start)
    return segments


def LabelSegmentsInPlace(segments: List[Segment], similarityThreshold: float = 0.45) -> None:
    labels = LabelSegments([s.events for s in segments], similarityThreshold=similarityThreshold)
    for segment, label in zip(segments, labels):
        segment.label = label


def RunStep1ForSession(sessionId: str, events: List[Dict[str, Any]], **kwargs) -> List[Segment]:
    """ convenience for a single session in isolation (e.g. quick inspection) - labels
    are only meaningful relative to this session's own segments, not the whole dataset.
    Prefer RunStep1ForDataset for anything that will be compared across sessions. """
    similarityThreshold = kwargs.pop("similarityThreshold", 0.55)
    segments = SegmentSession(sessionId, events, **kwargs)
    LabelSegmentsInPlace(segments, similarityThreshold=similarityThreshold)
    return segments


def RunStep1ForDataset(datasetDir: pathlib.Path, similarityThreshold: float = 0.55, **kwargs) -> List[Segment]:
    allSegments: List[Segment] = []
    for sessionDir in listSessions(datasetDir):
        events = loadSession(sessionDir)
        allSegments.extend(SegmentSession(sessionDir.name, events, **kwargs))

    LabelSegmentsInPlace(allSegments, similarityThreshold=similarityThreshold)
    allSegments.sort(key=lambda s: (s.sessionId, s.start))
    return allSegments
