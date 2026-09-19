""" Step 2: run Step 1 on Dataset B, then rank labels as automation candidates. """

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ibytask.analysis import AnalyzeSegments, SessionOperators
from ibytask.pipeline import RunStep1ForDataset

repoRoot = pathlib.Path(__file__).resolve().parents[1]
datasetBDir = repoRoot / "dataset_b"
outputPath = repoRoot / "outputs" / "datasetBCandidates.json"

PIPELINE_PARAMS = dict(resumeWindowSeconds=300.0, joinThreshold=0.55, similarityThreshold=0.55)


def main():
    allSegments = RunStep1ForDataset(datasetBDir, **PIPELINE_PARAMS)
    operators = SessionOperators(datasetBDir)
    candidates = AnalyzeSegments(allSegments, operators)

    outputPath.parent.mkdir(exist_ok=True)
    outputPath.write_text(
        json.dumps([vars(c) for c in candidates], indent=2, default=str), encoding="utf-8"
    )

    print(f"{len(candidates)} labels found across {len(allSegments)} segments\n")
    print(f"{'label':<14}{'count':>7}{'totalMin':>10}{'people':>8}{'branching':>11}"
          f"{'patterns':>10}{'domPattern%':>12}{'priority':>10}")
    for c in candidates:
        print(f"{c.label:<14}{c.executionCount:>7}{c.totalSeconds/60:>10.1f}{c.distinctOperators:>8}"
              f"{c.branchingFactor:>11.2f}{c.distinctPatterns:>10}"
              f"{c.dominantPatternShare*100:>11.0f}%{c.priorityScore:>10.3f}")


if __name__ == "__main__":
    main()
