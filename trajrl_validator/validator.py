"""Main loop: fetch → verify → re-derive + rails → decide → submit.

    trajrl-validator            # run forever
    trajrl-validator --once     # one tick (useful with TRAJRL_DRY_RUN=1)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

from . import __version__
from .config import Config, from_env
from .rails import closings, decide
from .schedule import should_submit
from .state import (cached_weights, closings as state_closings, last_applied,
                    last_submit_block, last_submit_ts, read_state, write_state)
from .sync import fetch_latest, fetch_tempo, verify_envelope


def prev_closings(cfg: Config, client: httpx.Client, tempo: int, st: dict) -> dict[str, int] | None:
    """Closings of tempo-1 for the continuity rail; None when unavailable."""
    t, c = state_closings(st)
    if t == tempo - 1:
        return c
    if tempo == 0:
        return None
    try:
        env = fetch_tempo(cfg.api, tempo - 1, client)
    except Exception:  # noqa: BLE001
        return None
    ok, _, res, _ = verify_envelope(env, master_hotkey=cfg.master_hotkey, netuid=cfg.netuid)
    return closings(res) if ok and res else None


def tick(cfg: Config, client: httpx.Client, chain, *, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    st = read_state(cfg.state_file)
    result, digest, reason = None, None, "fetch"
    try:
        env = fetch_latest(cfg.api, client)
        ok, reason, result, digest = verify_envelope(
            env, master_hotkey=cfg.master_hotkey, netuid=cfg.netuid)
        if not ok:
            result, digest = None, None
    except Exception as e:  # noqa: BLE001
        reason = f"fetch:{type(e).__name__}"
    if result is None:
        print(f"[sync] no usable statement: {reason}", flush=True)

    tempo = result["tempo"] if result else last_applied(st)
    la = last_applied(st)
    if result is not None and la is not None and result["tempo"] < la:
        print(f"[sync] refusing replay of tempo {result['tempo']} < {la}", flush=True)
        result, tempo = None, la

    prev = prev_closings(cfg, client, result["tempo"], st) if result else None
    d = decide(result, pinned_rails=cfg.pinned_rails, team_keys=cfg.team_keys,
               prev_closing=prev, cached=cached_weights(st), owner_hotkey=cfg.owner_hotkey)
    out = {"tempo": tempo, "verify": reason, "source": d.source, "failures": d.failures,
           "weights": d.weights, "submitted": False}
    if d.failures:
        print(f"[rails] tempo {tempo}: {d.source} after failures {d.failures[:8]}", flush=True)
    if result is not None:
        write_state(cfg.state_file, closings_tempo=result["tempo"], closings=closings(result))

    if tempo is None:
        tempo = -1
    if cfg.dry_run:
        print(f"[dry-run] tempo {tempo} source={d.source} weights={d.weights}", flush=True)
        return out

    view = chain.snapshot()
    if not should_submit(tempo=tempo, last_applied=la, current_block=view.block,
                         last_submit_block=last_submit_block(st), now=now,
                         last_submit_ts=last_submit_ts(st)):
        return out
    from .chain import resolve_uids
    uids, ws, dropped = resolve_uids(d.weights, view.hotkeys, cfg.owner_hotkey)
    if dropped:
        print(f"[chain] {dropped}/65535 weight on unregistered hotkeys moved to owner", flush=True)
    if not uids:
        print("[chain] nothing resolvable on chain; not submitting", flush=True)
        return out
    if chain.set_weights(view, wallet=cfg.wallet, hotkey=cfg.hotkey, uids=uids, weights=ws):
        write_state(cfg.state_file, last_applied=max(tempo, la or -1),
                    last_submit_block=view.block, last_submit_ts=now,
                    cached_weights=d.weights if d.source in ("allocation", "baseline") else cached_weights(st),
                    cached_digest=digest)
        out["submitted"] = True
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="trajrl-validator")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = from_env()
    if args.dry_run:
        cfg.dry_run = True
    print(f"[trajrl-validator {__version__}] netuid={cfg.netuid} api={cfg.api} "
          f"master={cfg.master_hotkey} dry_run={cfg.dry_run}", flush=True)
    from .chain import ChainClient
    from .heartbeat import post_heartbeat, touch
    chain = ChainClient(cfg.network, cfg.netuid)
    kp = None
    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                out = tick(cfg, client, chain)
                touch(cfg.heartbeat_file)
                if not cfg.dry_run:
                    if kp is None:
                        import bittensor as bt
                        kp = bt.Wallet(name=cfg.wallet, hotkey=cfg.hotkey).hotkey
                    st = read_state(cfg.state_file)
                    post_heartbeat(cfg.api, kp, cfg.netuid, version=__version__,
                                   tempo=out["tempo"], digest=st.get("cached_digest"),
                                   source=out["source"], failures=out["failures"], client=client)
            except Exception as e:  # noqa: BLE001
                print(f"[loop] tick failed ({type(e).__name__}: {e})", flush=True)
            if args.once:
                return
            time.sleep(cfg.poll_s)


def healthcheck() -> None:
    path = os.environ.get("TRAJRL_HEARTBEAT_FILE", "/var/lib/trajrl/heartbeat")
    max_age = int(os.environ.get("TRAJRL_HEALTH_MAX_AGE_S", "900"))
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        sys.exit(1)
    sys.exit(0 if age < max_age else 1)


if __name__ == "__main__":
    main()
