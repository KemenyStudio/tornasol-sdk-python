"""HTTP client for the tornasol API.

Uses urllib from the standard library - zero dependencies. For users that
prefer requests/httpx, the Client is small enough to subclass or replace.

See https://github.com/KemenyStudio/tornasol-sdk-python for usage and issues.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .hash import hash_agent_files
from .types import (
    ActionResponse,
    AgentFile,
    Observation,
    Scorecard,
    StartRunResponse,
    SubmitResponse,
    TurnResult,
    parse_observation,
    parse_scorecard,
)


DEFAULT_BASE_URL = "https://tornasol-api.kemenylabs.com"


class TornasolError(Exception):
    """Raised for non-2xx HTTP responses. status_code carries the HTTP code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"tornasol: HTTP {status_code}: {message}")
        self.status_code = status_code
        self.server_message = message


@dataclass
class Client:
    """Thin client for the tornasol HTTP API.

    Example:
        c = Client(api_key=os.environ["TORNASOL_API_KEY"])
        run = c.start_run()
        r = c.action(run.run_id, {"direction": "right"})
    """

    base_url: str = DEFAULT_BASE_URL
    api_key: Optional[str] = None
    timeout: float = 30.0
    user_agent: str = "sdk-python"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("TORNASOL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "tornasol.Client: api_key required "
                "(pass api_key=... or set TORNASOL_API_KEY)"
            )
        if self.base_url == DEFAULT_BASE_URL:
            env = os.environ.get("TORNASOL_BASE_URL")
            if env:
                self.base_url = env

    # ----- public API -----

    def start_run(
        self,
        *,
        config: Any = None,
        agent_files: Optional[Iterable[AgentFile]] = None,
    ) -> StartRunResponse:
        body: dict[str, Any] = {}
        if config is not None:
            body["config"] = config
        if agent_files:
            agent_hash, _ = hash_agent_files(agent_files)
            body["agent_hash"] = agent_hash
        data = self._request("POST", "/api/v1/run", body)
        return StartRunResponse(
            run_id=data["run_id"],
            engine=data["engine"],
            agent_hash=data.get("agent_hash"),
            observation=parse_observation(data["observation"]),
        )

    def action(self, run_id: str, action_payload: Any) -> ActionResponse:
        data = self._request("POST", f"/api/v1/run/{run_id}/action", {"action": action_payload})
        result = TurnResult(
            effect=data.get("result", {}).get("effect"),
            error=data.get("result", {}).get("error"),
        )
        sc = parse_scorecard(data["scorecard"]) if data.get("scorecard") else None
        return ActionResponse(
            observation=parse_observation(data["observation"]),
            result=result,
            done=bool(data.get("done")),
            scorecard=sc,
        )

    def scorecard(self, run_id: str) -> Scorecard:
        data = self._request("GET", f"/api/v1/run/{run_id}/scorecard", None)
        return parse_scorecard(data)

    def submit(
        self,
        *,
        files: Iterable[AgentFile],
        run_id: Optional[str] = None,
        notes: str = "",
    ) -> SubmitResponse:
        agent_hash, normalized = hash_agent_files(files)
        body: dict[str, Any] = {
            "agent_hash": agent_hash,
            "files": _encode_agent_files(normalized),
        }
        if run_id:
            body["run_id"] = run_id
        if notes:
            body["notes"] = notes
        data = self._request("POST", "/api/v1/submission", body)
        return SubmitResponse(
            id=data["id"],
            agent_hash=data["agent_hash"],
            blob_ref=data["blob_ref"],
            files=int(data.get("files", 0)),
            bytes_in=int(data.get("bytes_in", 0)),
            reused_hash=bool(data.get("reused_hash")),
            matching_runs=list(data.get("matching_runs", [])),
            notes=data.get("notes", ""),
        )

    # ----- internals -----

    def _request(self, method: str, path: str, body: Any) -> dict:
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key or "",
            "X-Client": self.user_agent,
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read() or b""
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}")
                msg = parsed.get("error") or raw.decode("utf-8", errors="replace")
            except json.JSONDecodeError:
                msg = raw.decode("utf-8", errors="replace") or e.reason
            raise TornasolError(e.code, msg) from None
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def _encode_agent_files(files: Iterable[AgentFile]) -> list[dict[str, str]]:
    out = []
    for f in files:
        content = f.content
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(f"AgentFile.content must be bytes or str (got {type(content).__name__})")
        out.append({
            "path": f.path,
            "content_b64": base64.b64encode(content).decode("ascii"),
        })
    return out
