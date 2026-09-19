""" deliverable: run Step 1 on Dataset B (no ground truth) and write segments.jsonl.
Labels are assigned once across the whole dataset so the same recurring process
gets the same label in every session (see pipeline.RunStep1ForDataset). """

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ibytask.pipeline import RunStep1ForDataset

repoRoot = pathlib.Path(__file__).resolve().parents[1]
datasetBDir = repoRoot / "dataset_b"
outputPath = repoRoot / "outputs" / "segments.jsonl"

# same parameters validated in evaluateOnDatasetA.py's default run
PIPELINE_PARAMS = dict(resumeWindowSeconds=300.0, joinThreshold=0.55, similarityThreshold=0.55)


def main():
    allSegments = RunStep1ForDataset(datasetBDir, **PIPELINE_PARAMS)

    outputPath.parent.mkdir(exist_ok=True)
    with open(outputPath, "w", encoding="utf-8") as f:
        for seg in allSegments:
            f.write(json.dumps({
                "session_id": seg.sessionId,
                "start": seg.start.isoformat().replace("+00:00", "Z"),
                "end": seg.end.isoformat().replace("+00:00", "Z"),
                "label": seg.label,
            }, ensure_ascii=False) + "\n")

    bySession = {}
    for seg in allSegments:
        bySession[seg.sessionId] = bySession.get(seg.sessionId, 0) + 1
    for sessionId, count in sorted(bySession.items()):
        print(f"{sessionId}: {count} segments")
    print(f"Wrote {len(allSegments)} segments to {outputPath}")


if __name__ == "__main__":
    main()
