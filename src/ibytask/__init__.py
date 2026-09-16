import pathlib

import ibytask.ingest as pm

def main() -> None:
    datasetPath = "./dataset_a"
    sessions = pm.listSessions(pathlib.Path(datasetPath))
    sessionPath = "./dataset_a/ses_20260630-121953-LAPTOP-R36BQBTE"
    cnt = 0
    allTimestampBackwardDeltas = []
    allNegativeMsSinceLastEvent = []
    for session in sessions:
        sessionPath = session
        Events = pm.loadSession(sessionPath)
        isIntegrityValid, failedIntegrity, rawValues = pm.integrityCheck(Events)
        allTimestampBackwardDeltas.extend(rawValues["timestamp_ms_backward_delta"])
        allNegativeMsSinceLastEvent.extend(rawValues["negative_ms_since_last_event"])
        if not isIntegrityValid:
            cnt += 1
    print(f"Total sessions with structural integrity issues: {cnt}")
    print(f"timestamp_ms_backward_delta: {pm.fiveNumberSummary(allTimestampBackwardDeltas)}")
    print(f"negative_ms_since_last_event: {pm.fiveNumberSummary(allNegativeMsSinceLastEvent)}")
