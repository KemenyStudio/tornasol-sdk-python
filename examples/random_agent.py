# Random-action agent: returns one of four directions per turn.
#
#   TORNASOL_API_KEY=k_... tornasol-run-agent --agent ./random_agent.py

import random

DIRECTIONS = ["up", "down", "left", "right"]


def choose_action(observation):
    return {"direction": random.choice(DIRECTIONS)}
