"""run_agent: drive the turn-based loop with a candidate-supplied function."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from .client import Client
from .types import AgentFile, Observation, Scorecard, TurnResult


ChooseAction = Callable[[Observation], Union[Any, Awaitable[Any]]]


def run_agent(
    choose_action: ChooseAction,
    *,
    client: Optional[Client] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config: Any = None,
    agent_files: Optional[Iterable[AgentFile]] = None,
    on_turn: Optional[Callable[[Observation, TurnResult, bool], None]] = None,
) -> Scorecard:
    """Drive a full run loop and return the final scorecard.

    The choose_action callable may be sync or async (a coroutine). If async,
    we run it on an event loop.
    """
    if client is None:
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        client = Client(**kwargs)

    run = client.start_run(config=config, agent_files=agent_files)
    obs = run.observation
    while True:
        maybe = choose_action(obs)
        action = _resolve(maybe)
        r = client.action(run.run_id, action)
        if on_turn is not None:
            on_turn(r.observation, r.result, r.done)
        if r.done:
            assert r.scorecard is not None
            return r.scorecard
        obs = r.observation


def _resolve(value: Any) -> Any:
    """Sync-friendly resolution of a possibly-async ChooseAction result."""
    if inspect.iscoroutine(value):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an existing loop: schedule and wait via a task.
                return loop.run_until_complete(value)  # may raise; caller's choice
        except RuntimeError:
            pass
        return asyncio.run(value)
    return value
