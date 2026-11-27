"""Persisted validator state, written atomically. Each field validates on read."""
from __future__ import annotations

import json
import os


def read_state(path: str) -> dict:
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _int(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def last_applied(s: dict) -> int | None:
    return _int(s.get("last_applied"))


def last_submit_block(s: dict) -> int | None:
    return _int(s.get("last_submit_block"))


def last_submit_ts(s: dict) -> float | None:
    v = s.get("last_submit_ts")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def cached_weights(s: dict) -> list | None:
    from .rails import well_formed
    w = s.get("cached_weights")
    return w if well_formed(w) else None


def closings(s: dict) -> tuple[int | None, dict[str, int] | None]:
    """(tempo, {coldkey: closing_uusd}) of the last verified statement."""
    t = _int(s.get("closings_tempo"))
    c = s.get("closings")
    if t is None or not isinstance(c, dict):
        return None, None
    if not all(isinstance(k, str) and _int(v) is not None for k, v in c.items()):
        return None, None
    return t, c


def write_state(path: str, **fields) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cur = read_state(path)
    cur.update(fields)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cur, f)
    os.replace(tmp, path)
