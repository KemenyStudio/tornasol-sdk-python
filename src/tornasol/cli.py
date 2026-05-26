"""CLI entry points for tornasol-run-agent and tornasol-submit-agent."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from .client import Client
from .runner import run_agent
from .types import AgentFile


def _load_agent_callable(path: str):
    p = Path(path).resolve()
    if not p.exists():
        sys.exit(f"agent file not found: {p}")
    spec = importlib.util.spec_from_file_location("agent_module", p)
    if spec is None or spec.loader is None:
        sys.exit(f"failed to load module: {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "choose_action", None) or getattr(mod, "chooseAction", None)
    if not callable(fn):
        sys.exit(f"{p}: must define choose_action(observation)")
    return fn, p


def run_agent_main() -> None:
    ap = argparse.ArgumentParser(prog="tornasol-run-agent",
                                  description="Run an agent against the tornasol server.")
    ap.add_argument("--agent", required=True, help="Python file defining choose_action")
    ap.add_argument("--config", help="JSON string for engine config", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--output", help="save scorecard JSON to this path", default=None)
    args = ap.parse_args()

    fn, agent_path = _load_agent_callable(args.agent)
    config = json.loads(args.config) if args.config else None
    files = [AgentFile(path=agent_path.name, content=agent_path.read_bytes())]

    client = Client(base_url=args.base_url) if args.base_url else Client()

    def on_turn(obs, result, done):
        tag = "✓ done" if done else f"  turn {obs.turn}"
        eff = f" ({result.effect})" if result.effect else ""
        print(f"{tag}{eff}  status={obs.status}")

    print(f"\n=== tornasol - running {agent_path.name} ===\n")
    sc = run_agent(fn, client=client, config=config, agent_files=files, on_turn=on_turn)
    print(f"\n=== scorecard ===")
    print(f"  status:  {sc.status}")
    print(f"  score:   {sc.score}")
    print(f"  turns:   {sc.turns}")
    print(f"  elapsed: {sc.elapsed_ms} ms\n")
    if args.output:
        Path(args.output).write_text(json.dumps(_dataclass_to_dict(sc), indent=2))
        print(f"Saved to {args.output}")


def submit_agent_main() -> None:
    ap = argparse.ArgumentParser(prog="tornasol-submit-agent",
                                  description="Submit an agent as the final answer.")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--root", default=None, help="directory to include (default: dir of --agent)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--run-id", default=os.environ.get("TORNASOL_RUN_ID", ""))
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    agent_abs = Path(args.agent).resolve()
    if not agent_abs.exists():
        sys.exit(f"not found: {agent_abs}")
    root = Path(args.root).resolve() if args.root else agent_abs.parent

    exclude_dirs = {"__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode", "dist", "build", ".venv", "venv"}
    exclude_ext = {".zip", ".tgz", ".tar", ".gz", ".bz2", ".rar", ".7z", ".log", ".pyc"}
    MAX_FILE = 1024 * 1024
    MAX_TOTAL = 5 * 1024 * 1024

    files: list[AgentFile] = []
    total = 0
    included_agent = False
    print(f"\n=== tornasol - submit agent ===")
    print(f"agent: {agent_abs}")
    print(f"root:  {root}\n")
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in exclude_dirs for part in p.parts):
            continue
        if p.suffix.lower() in exclude_ext:
            print(f"  · skip {p.relative_to(root)} (excluded ext)")
            continue
        size = p.stat().st_size
        if size > MAX_FILE:
            print(f"  · skip {p.relative_to(root)} ({size} > {MAX_FILE})")
            continue
        if total + size > MAX_TOTAL:
            print(f"  · skip {p.relative_to(root)} (total cap)")
            continue
        total += size
        files.append(AgentFile(path=str(p.relative_to(root)).replace(os.sep, "/"), content=p.read_bytes()))
        if p == agent_abs:
            included_agent = True
        print(f"  + {p.relative_to(root)} ({size} B)")
    if not included_agent:
        files.append(AgentFile(path=agent_abs.name, content=agent_abs.read_bytes()))
        print(f"  + {agent_abs.name} (forced - outside --root)")

    print(f"\ntotal: {len(files)} file(s), {sum(len(f.content) if isinstance(f.content, (bytes, bytearray)) else len(f.content.encode()) for f in files)} bytes")
    if args.dry_run:
        print("(dry-run: not sending)")
        return

    client = Client(base_url=args.base_url) if args.base_url else Client()
    resp = client.submit(files=files, run_id=args.run_id or None, notes=args.notes)
    print(f"\n✓ submitted")
    print(f"  id:            {resp.id}")
    print(f"  agent_hash:    {resp.agent_hash}")
    print(f"  reused_hash:   {resp.reused_hash}")
    matches = ", ".join(resp.matching_runs) if resp.matching_runs else "(none)"
    print(f"  matching_runs: {matches}\n")


def _dataclass_to_dict(o):
    from dataclasses import is_dataclass, asdict
    if is_dataclass(o):
        return asdict(o)
    return o
