"""Official Python SDK for tornasol - the turn-based assessment platform.

Quick start:

    from tornasol import Client, run_agent

    def choose(obs):
        return {"direction": "right"}

    scorecard = run_agent(choose, api_key="k_...")

See https://github.com/KemenyStudio/tornasol-sdk-python for usage and issues.
"""

from .client import Client, TornasolError
from .hash import hash_agent_files
from .runner import run_agent
from .types import (
    AgentFile,
    Observation,
    RenderSpec,
    TurnResult,
    Scorecard,
    StartRunResponse,
    ActionResponse,
    SubmitResponse,
    RunStatus,
)

__all__ = [
    "Client",
    "TornasolError",
    "run_agent",
    "hash_agent_files",
    "AgentFile",
    "Observation",
    "RenderSpec",
    "TurnResult",
    "Scorecard",
    "StartRunResponse",
    "ActionResponse",
    "SubmitResponse",
    "RunStatus",
]

__version__ = "0.1.0"
