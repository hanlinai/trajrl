"""Verify a saved statement envelope offline.

    curl -s https://provider.trajrl.com/api/subnet/v1/tempo/1234 > tempo.json
    TRAJRL_MASTER_HOTKEY=5… python -m trajrl_validator.verify tempo.json [--prev prev.json]

Checks the signature against the master key you pin, re-derives every number from the line
items, checks every rail, and prints the weight vector a validator would submit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .config import DEFAULT_RAILS
from .mechanism import check_rails
from .rails import closings
from .sync import verify_envelope


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m trajrl_validator.verify")
    ap.add_argument("envelope")
    ap.add_argument("--prev", help="envelope of tempo-1, for the ledger-continuity rail")
    ap.add_argument("--master", default=os.environ.get("TRAJRL_MASTER_HOTKEY", ""))
    ap.add_argument("--netuid", type=int, default=int(os.environ.get("TRAJRL_NETUID", "11")))
    ap.add_argument("--team", default=os.environ.get("TRAJRL_TEAM_KEYS", ""))
    a = ap.parse_args(argv)
    if not a.master:
        print("set TRAJRL_MASTER_HOTKEY or --master", file=sys.stderr)
        return 2
    env = json.load(open(a.envelope))
    ok, why, res, digest = verify_envelope(env, master_hotkey=a.master, netuid=a.netuid)
    print(f"signature: {why}")
    if not ok:
        return 1
    prev = None
    if a.prev:
        pok, pwhy, pres, _ = verify_envelope(json.load(open(a.prev)), master_hotkey=a.master, netuid=a.netuid)
        if not pok or pres["tempo"] != res["tempo"] - 1:
            print(f"prev: unusable ({pwhy})")
        else:
            prev = closings(pres)
    team = {k.strip() for k in a.team.split(",") if k.strip()}
    fails = check_rails(res, pinned_rails=DEFAULT_RAILS, team_keys=team, prev_closing=prev)
    print(f"tempo {res['tempo']} digest {digest}")
    print("rails: " + ("all pass" if not fails else "FAIL " + ", ".join(fails)))
    for hk, uid, w in res["weights"]:
        print(f"  uid {uid:>4}  {w:>6}  {hk}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
