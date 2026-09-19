# Step 3 — Automation for Step 2's Top Candidate

Automates confirmation of pending payroll-item changes at `127.0.0.1:5133`: a
reviewer types a confirmation note into `#pi-note` and clicks `#btn-pi-ok`.
Routine change types (dependent deduction, overtime allowance) are approved
automatically with the observed note template; anything requiring manager
approval is flagged for a human.

`mockPortalApi.py` stands in for the real portal (`GET /queue`,
`POST /queue/<caseId>/approve|flag`), since only operation logs are available.
The decision logic itself is an n8n workflow (`n8n/topCandidateConfirmation.json`)
rather than a script, since a workflow tool is what an HR ops team could
actually read and modify without an engineer.

## Running it

```bash
# terminal 1: the mock portal (binds 0.0.0.0 so the n8n container can reach it)
python3 automation/mockPortalApi.py

# terminal 2: n8n via Docker (host networking - most reliable on native Linux
# Docker, where host.docker.internal DNS resolution can hang/fail)
docker run -it --rm --name n8n --network host \
  -v n8n_data:/home/node/.n8n \
  n8nio/n8n
```

Then open `http://localhost:5678`, create an owner account (first run only),
**Workflows → Import from File**, pick `automation/n8n/topCandidateConfirmation.json`,
and click **Execute Workflow**.

`topCandidateQueue.json` resets to all-`pending` after each demo run.

## Workflow shape

`Manual Trigger` → `Get Queue` (`GET /queue`, one output item per pending case)
→ `Compute Decision` (Set node: `isRoutine`, `note`, `reason` from the case
fields) → `Is Routine?` (IF node) → `Approve` (`POST /queue/<id>/approve`) or
`Flag` (`POST /queue/<id>/flag`).

The workflow's HTTP nodes call `http://127.0.0.1:5133` (not `localhost`, to
avoid the container resolving it to the IPv6 loopback where nothing listens),
which only reaches the host's `mockPortalApi.py` under `--network host`
(Linux). On Docker Desktop (Mac/Windows), `--network host` isn't supported -
use `-p 5678:5678 --add-host=host.docker.internal:host-gateway` instead and
swap `127.0.0.1:5133` for `host.docker.internal:5133` in the three HTTP
Request nodes.
