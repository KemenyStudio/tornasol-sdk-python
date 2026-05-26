"""Typed structures mirroring the tornasol protocol.

We use dataclasses (not Pydantic) to stay dependency-free. The server
returns JSON dicts; the convenience helpers in client.py wrap them into
these dataclasses for autocomplete-friendly access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union


RunStatus = Literal[
    "in_progress",
    "won",
    "lost",
    "errored",
    "gave_up",
    "expired",
]


@dataclass
class RenderSpec:
    primitive: Literal["grid", "text", "form", "choices", "image", "composite"]
    data: Any


@dataclass
class TurnResult:
    effect: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Observation:
    run_id: str
    engine: str
    turn: int
    status: RunStatus
    payload: Any
    render: Optional[RenderSpec] = None
    last_action: Any = None
    last_result: Optional[TurnResult] = None


@dataclass
class Scorecard:
    run_id: str
    engine: str
    status: RunStatus
    score: float
    turns: int
    elapsed_ms: int
    ended_at: str
    details: Any = None


@dataclass
class StartRunResponse:
    run_id: str
    engine: str
    observation: Observation
    agent_hash: Optional[str] = None


@dataclass
class ActionResponse:
    observation: Observation
    result: TurnResult
    done: bool
    scorecard: Optional[Scorecard] = None


@dataclass
class SubmitResponse:
    id: str
    agent_hash: str
    blob_ref: str
    files: int
    bytes_in: int
    reused_hash: bool
    matching_runs: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AgentFile:
    """One logical file of the agent. Content can be bytes or str (utf-8)."""
    path: str
    content: Union[bytes, str]


# --- helpers to map dicts → dataclasses ----------------------------------

def parse_observation(d: dict) -> Observation:
    render = None
    if d.get("render"):
        render = RenderSpec(primitive=d["render"]["primitive"], data=d["render"]["data"])
    last_result = None
    if d.get("last_result"):
        last_result = TurnResult(
            effect=d["last_result"].get("effect"),
            error=d["last_result"].get("error"),
        )
    return Observation(
        run_id=d["run_id"],
        engine=d["engine"],
        turn=d["turn"],
        status=d["status"],
        payload=d.get("payload"),
        render=render,
        last_action=d.get("last_action"),
        last_result=last_result,
    )


def parse_scorecard(d: dict) -> Scorecard:
    return Scorecard(
        run_id=d["run_id"],
        engine=d["engine"],
        status=d["status"],
        score=float(d.get("score", 0)),
        turns=int(d.get("turns", 0)),
        elapsed_ms=int(d.get("elapsed_ms", 0)),
        ended_at=d.get("ended_at", ""),
        details=d.get("details"),
    )
