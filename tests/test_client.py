"""Tests for tornasol.Client and run_agent against a tiny fake server.

Run with:   python -m unittest tests/test_client.py
"""

from __future__ import annotations

import json
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tornasol import AgentFile, Client, TornasolError, hash_agent_files, run_agent


_STATE: dict = {"turn": 0, "run_hash": ""}


class _FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # silence
        return

    def _send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(n) if n > 0 else b""
        return json.loads(raw or b"{}")

    def _auth_ok(self) -> bool:
        return self.headers.get("X-API-Key") == "test-key"

    def do_POST(self):  # noqa: N802
        if not self._auth_ok():
            return self._send_json(401, {"error": "unauthorized"})
        if self.path == "/api/v1/run":
            req = self._read_body()
            _STATE["turn"] = 0
            _STATE["run_hash"] = req.get("agent_hash", "") or ""
            return self._send_json(200, {
                "run_id": "run-abc",
                "engine": "fake-engine",
                "agent_hash": _STATE["run_hash"],
                "observation": {
                    "run_id": "run-abc", "engine": "fake-engine",
                    "turn": 0, "status": "in_progress", "payload": None,
                },
            })
        if self.path.startswith("/api/v1/run/") and self.path.endswith("/action"):
            _STATE["turn"] += 1
            t = _STATE["turn"]
            done = t >= 2
            body = {
                "observation": {
                    "run_id": "run-abc", "engine": "fake-engine",
                    "turn": t, "status": "won" if done else "in_progress",
                    "payload": None,
                },
                "result": {"effect": "moved"},
                "done": done,
            }
            if done:
                body["scorecard"] = {
                    "run_id": "run-abc", "engine": "fake-engine", "status": "won",
                    "score": 1.0, "turns": t, "elapsed_ms": 1,
                    "ended_at": "2026-05-19T00:00:00Z",
                }
            return self._send_json(200, body)
        if self.path == "/api/v1/submission":
            req = self._read_body()
            sub_hash = req.get("agent_hash", "")
            matching = ["run-abc"] if sub_hash and sub_hash == _STATE["run_hash"] else []
            return self._send_json(200, {
                "id": "sub-1", "agent_hash": sub_hash,
                "blob_ref": f"agent-artifacts/tenant/{sub_hash}.zip",
                "files": len(req.get("files", [])), "bytes_in": 10,
                "reused_hash": False, "matching_runs": matching,
            })
        self._send_json(404, {"error": "not found"})


def _start_server() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), _FakeHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    port = srv.server_address[1]
    return srv, f"http://127.0.0.1:{port}"


class TestSDK(unittest.TestCase):
    def setUp(self) -> None:
        self.srv, self.base = _start_server()

    def tearDown(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()

    def test_run_agent_drives_loop(self) -> None:
        calls = 0

        def choose(_obs):
            nonlocal calls
            calls += 1
            return {"direction": "right"}

        sc = run_agent(choose, api_key="test-key", base_url=self.base)
        self.assertEqual(sc.score, 1.0)
        self.assertEqual(sc.status, "won")
        self.assertEqual(calls, 2)

    def test_hash_is_order_independent(self) -> None:
        a, _ = hash_agent_files([
            AgentFile(path="a.py", content=b"one"),
            AgentFile(path="b.py", content=b"two"),
        ])
        b, _ = hash_agent_files([
            AgentFile(path="b.py", content=b"two"),
            AgentFile(path="a.py", content=b"one"),
        ])
        self.assertEqual(a, b)
        self.assertRegex(a, r"^[a-f0-9]{64}$")

    def test_submit_matches_when_hashes_align(self) -> None:
        c = Client(api_key="test-key", base_url=self.base)
        files = [AgentFile(path="agent.py", content=b"module")]
        run = c.start_run(agent_files=files)
        r = c.submit(files=files)
        self.assertEqual(r.agent_hash, run.agent_hash)
        self.assertEqual(r.matching_runs, ["run-abc"])

    def test_submit_no_match_when_hashes_differ(self) -> None:
        c = Client(api_key="test-key", base_url=self.base)
        c.start_run(agent_files=[AgentFile(path="agent.py", content=b"v1")])
        r = c.submit(files=[AgentFile(path="agent.py", content=b"v2")])
        self.assertEqual(r.matching_runs, [])

    def test_unauthorized_raises(self) -> None:
        c = Client(api_key="wrong-key", base_url=self.base)
        with self.assertRaises(TornasolError) as cm:
            c.start_run()
        self.assertEqual(cm.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
