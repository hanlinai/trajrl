"""Signed liveness heartbeat to the provider. Best-effort; never raises."""
from __future__ import annotations

import hashlib
import json
import time

import httpx

HEARTBEAT_PATH = "/api/subnet/v1/validator/heartbeat"


def canonical_message(netuid: int, method: str, path: str, ts: int, body: bytes = b"") -> str:
    return f"trajrl-sn11:api:v1:{netuid}:{method.upper()}:{path}:{ts}:{hashlib.sha256(body).hexdigest()}"


def signed_headers(keypair, netuid: int, method: str, path: str, body: bytes = b"",
                   *, ts: int | None = None) -> dict[str, str]:
    ts = int(time.time()) if ts is None else ts
    msg = canonical_message(netuid, method, path, ts, body)
    return {"X-Validator-Hotkey": keypair.ss58_address, "X-Validator-Ts": str(ts),
            "X-Validator-Sig": keypair.sign(msg.encode()).hex(),
            "Content-Type": "application/json"}


def post_heartbeat(api: str, keypair, netuid: int, *, version: str, tempo: int | None,
                   digest: str | None, source: str | None, failures: list[str],
                   client: httpx.Client) -> bool:
    try:
        body = json.dumps({"v": 1, "version": version, "tempo": tempo, "digest": digest,
                           "source": source, "failures": failures[:50]},
                          separators=(",", ":")).encode()
        r = client.post(f"{api.rstrip('/')}{HEARTBEAT_PATH}", content=body,
                        headers=signed_headers(keypair, netuid, "POST", HEARTBEAT_PATH, body))
        return r.status_code < 300
    except Exception as e:  # noqa: BLE001
        print(f"[heartbeat] failed ({type(e).__name__}: {e})", flush=True)
        return False


def touch(path: str) -> None:
    try:
        with open(path, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass
