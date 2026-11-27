"""Decide what to submit: the submission policy of spec §Submission policy.

    1. allocation (Eleven) present and passes  → submit it
    2. baseline weights pass                   → submit them
    3. otherwise                               → last landed vector
    4. otherwise                               → 100% to the owner uid

Pure: no IO. Inputs are an already-verified result and local config.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .mechanism import U16, check_rails


@dataclass
class Decision:
    source: str                      # "allocation" | "baseline" | "cached" | "recycle"
    weights: list[list]              # [[hotkey, u16], ...]
    failures: list[str] = field(default_factory=list)


def _pairs(weights: list[list]) -> list[list]:
    return [[w[0], int(w[-1])] for w in weights]


def well_formed(w: object) -> bool:
    return (isinstance(w, list) and len(w) > 0 and all(
        isinstance(p, list) and len(p) in (2, 3) and isinstance(p[0], str)
        and isinstance(p[-1], int) and not isinstance(p[-1], bool) and 0 <= p[-1] <= U16
        for p in w))


def decide(result: dict | None, *, pinned_rails: dict | None, team_keys: set[str],
           prev_closing: dict[str, int] | None, cached: list | None,
           owner_hotkey: str) -> Decision:
    failures: list[str] = []
    if result is not None:
        alloc = result.get("allocation")
        if alloc is not None:
            # An agent allocation must itself be a full statement body that
            # re-derives and passes every rail (same checks, its own numbers).
            f = check_rails(alloc, pinned_rails=pinned_rails, team_keys=team_keys,
                            prev_closing=prev_closing, owner_hotkey=owner_hotkey) if isinstance(alloc, dict) else ["allocation:malformed"]
            if not f:
                return Decision("allocation", _pairs(alloc["weights"]))
            failures += [f"allocation:{x}" for x in f]
        f = check_rails(result, pinned_rails=pinned_rails, team_keys=team_keys,
                        prev_closing=prev_closing, owner_hotkey=owner_hotkey)
        if not f:
            return Decision("baseline", _pairs(result["weights"]), failures)
        failures += f
    if cached is not None and well_formed(cached):
        return Decision("cached", _pairs(cached), failures)
    return Decision("recycle", [[owner_hotkey, U16]], failures)


def closings(result: dict) -> dict[str, int]:
    return {a["coldkey"]: int(a.get("closing_uusd", 0)) for a in result.get("accounts", [])}
