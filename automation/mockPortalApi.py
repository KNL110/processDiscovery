""" mock stand-in for the real portal at 127.0.0.1:5133 (see automation/README.md).

Endpoints:
  GET  /queue                    -> list of pending cases
  POST /queue/<caseId>/approve  {"note": "..."} -> mark approved
  POST /queue/<caseId>/flag     {"reason": "..."} -> mark flagged for a human
"""

import json
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer

dataFile = pathlib.Path(__file__).parent / "topCandidateQueue.json"


def loadQueue() -> list:
    return json.loads(dataFile.read_text(encoding="utf-8"))


def saveQueue(queue: list) -> None:
    dataFile.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _sendJson(self, status: int, body) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/queue":
            self._sendJson(200, [c for c in loadQueue() if c["status"] == "pending"])
        else:
            self._sendJson(404, {"error": "not found"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "queue":
            self._sendJson(404, {"error": "not found"})
            return
        caseId, action = parts[1], parts[2]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        queue = loadQueue()
        case = next((c for c in queue if c["caseId"] == caseId), None)
        if case is None:
            self._sendJson(404, {"error": f"unknown caseId {caseId}"})
            return
        if action == "approve":
            case["status"] = "approved"
            case["note"] = body.get("note", "")
        elif action == "flag":
            case["status"] = "flagged"
            case["reason"] = body.get("reason", "")
        else:
            self._sendJson(400, {"error": f"unknown action {action}"})
            return
        saveQueue(queue)
        self._sendJson(200, case)

    def log_message(self, fmt, *args): # type: ignore
        print(f"[mockPortalApi] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    port = 5133
    print(f"Mock portal (topCandidateQueue.json) on http://0.0.0.0:{port}  (Ctrl+C to stop)")
    # binds all interfaces, not just localhost, so the n8n Docker container can reach
    # it via localhost (--network host, Linux) or host.docker.internal (Docker Desktop)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
