# tornasol (Python SDK)

Official Python SDK for [tornasol](https://tornasol.kemenylabs.com/) - the turn-based assessment platform.

```bash
pip install tornasol
```

Python 3.10+. Zero runtime dependencies (uses stdlib `urllib`).

## Quick start

```python
import os
from tornasol import run_agent

def choose(observation):
    return {"direction": "right"}

scorecard = run_agent(choose, api_key=os.environ["TORNASOL_API_KEY"])
print(scorecard.score, scorecard.turns)
```

## CLI

```bash
# Run an agent file (must define choose_action)
TORNASOL_API_KEY=k_... tornasol-run-agent --agent ./agent.py

# Submit as final answer
TORNASOL_API_KEY=k_... tornasol-submit-agent --agent ./agent.py --notes "v3"
```

## Programmatic API

```python
from tornasol import Client, AgentFile

c = Client(
    base_url="https://tornasol-api.kemenylabs.com",
    api_key=os.environ["TORNASOL_API_KEY"],
)

# Optional: bind a canonical hash of your code to this run; a later
# submission with the same files will link back via matching_runs.
with open("agent.py", "rb") as f:
    src = f.read()

run = c.start_run(agent_files=[AgentFile(path="agent.py", content=src)])

obs = run.observation
while True:
    action = decide_action(obs)        # your logic
    r = c.action(run.run_id, action)
    if r.done:
        print(r.scorecard); break
    obs = r.observation
```

## Hash-based verification

The SDK computes a canonical `agent_hash` of your file set (`hash_agent_files`) and sends it on `start_run` and `submit`. The server stores it and, on submit, returns the runs whose hash matches:

```python
sub = c.submit(files=[AgentFile(path="agent.py", content=src)])
print(sub.matching_runs)   # ["run-abc", ...] - runs that used this exact code
```

The hash is order-independent and stable across runs: same files → same hash. The server never receives the source on `start_run`, only the hash; the bytes are uploaded once on `submit`.

## Tests

```bash
python -m unittest discover tests
```

## License

MIT
