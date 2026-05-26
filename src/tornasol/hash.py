"""Canonical sha256 hash of an agent file set.

Order-independent and stable: the same set of (path, content) always
yields the same hex digest. Scheme:

    1. Normalize each path (forward slashes, posix-style clean, no abs,
       no '..').
    2. Reject duplicate paths.
    3. Sort by normalized path.
    4. Per file:  per_i = sha256(path || 0x00 || content)
    5. Final:     hash  = sha256(per_1 || per_2 || ...)
"""

from __future__ import annotations

import hashlib
import posixpath
from typing import Iterable

from .types import AgentFile


def hash_agent_files(files: Iterable[AgentFile]) -> tuple[str, list[AgentFile]]:
    """Return (hex_sha256, normalized_sorted_files).

    Raises ValueError if the set is empty, has duplicate paths, or any
    path is absolute / escapes the root.
    """
    norm: list[AgentFile] = []
    seen: set[str] = set()
    for f in files:
        path = _normalize_path(f.path)
        if path in seen:
            raise ValueError(f"tornasol: duplicate path {path!r}")
        seen.add(path)
        content = f.content
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(
                f"AgentFile.content must be bytes or str (got {type(content).__name__})"
            )
        norm.append(AgentFile(path=path, content=bytes(content)))
    if not norm:
        raise ValueError("tornasol: at least one file is required")

    norm.sort(key=lambda f: f.path)

    h = hashlib.sha256()
    for f in norm:
        per = hashlib.sha256()
        per.update(f.path.encode("utf-8"))
        per.update(b"\x00")
        per.update(f.content)  # type: ignore[arg-type]
        h.update(per.digest())
    return h.hexdigest(), norm


def _normalize_path(p: str) -> str:
    if not isinstance(p, str) or p == "":
        raise ValueError("tornasol: empty agent file path")
    cleaned = posixpath.normpath(p.replace("\\", "/"))
    if cleaned.startswith("/"):
        raise ValueError(f"tornasol: absolute agent file path {p!r}")
    if cleaned == "." or cleaned == ".." or cleaned.startswith("../"):
        raise ValueError(f"tornasol: agent file path escapes root {p!r}")
    return cleaned
