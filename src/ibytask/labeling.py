import math
from collections import Counter
from typing import Any, Dict, List

from .utils import SegmentFingerprint


def Cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    normA = math.sqrt(sum(v * v for v in a.values()))
    normB = math.sqrt(sum(v * v for v in b.values()))
    return dot / (normA * normB) if normA and normB else 0.0


def Jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def FingerprintSimilarity(fpA: Dict[str, Any], fpB: Dict[str, Any]) -> float:
    appSim = Cosine(fpA["apps"], fpB["apps"])
    domainSim = Cosine(fpA["domains"], fpB["domains"])
    pathSim = Cosine(fpA["paths"], fpB["paths"])
    textSim = Jaccard(set(fpA["textTokens"]), set(fpB["textTokens"]))
    return 0.35 * appSim + 0.25 * domainSim + 0.25 * pathSim + 0.15 * textSim


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry


def LabelSegments(segmentEventLists: List[List[Dict[str, Any]]], similarityThreshold: float = 0.45) -> List[str]:
    """ pairwise fingerprint similarity above threshold -> same connected component -> same label.
    connected components instead of Louvain (no networkx dep here): simpler, and adequate
    since we only need "recurring process gets the same label", not densest-subgraph detail. """
    fingerprints = [SegmentFingerprint(events) for events in segmentEventLists]
    uf = UnionFind(len(fingerprints))
    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            if FingerprintSimilarity(fingerprints[i], fingerprints[j]) >= similarityThreshold:
                uf.union(i, j)

    labelOf: Dict[int, str] = {}
    nextClusterIdx = 0
    for i in range(len(fingerprints)):
        root = uf.find(i)
        if root not in labelOf:
            labelOf[root] = f"process_{nextClusterIdx}"
            nextClusterIdx += 1
    return [labelOf[uf.find(i)] for i in range(len(fingerprints))]
