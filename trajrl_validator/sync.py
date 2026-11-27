"""Fetch and verify the master-signed allocation statement (spec/statement-v1.md).

Trust model: this validator trusts nothing it is told — it checks that the master hotkey pinned in *local* config signed these
exact bytes, then (in rails.py / mechanism.py) re-derives every number from the
statement's own line items before submitting anything.

The master signs sha256(result_json). The vector we submit is always taken from
the verified result_json bytes, never from any other envelope field.
"""
from __future__ import annotations

import hashlib
import json

import httpx

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
LATEST_PATH = "/api/subnet/v1/tempo/latest"


def tempo_message(netuid: int, tempo: int, digest_hex: str) -> str:
    return f"trajrl-sn11:tempo:v1:{netuid}:{tempo}:{digest_hex}"


def verify_sr25519(sig_hex: str, message: bytes, ss58: str) -> bool:
    """Raw sr25519 verify. Deliberately not Keypair.verify, which silently
    retries with a <Bytes>-wrapped message and so widens what a signature binds."""
    try:
        import sr25519
        from bittensor_wallet import Keypair
        pub = Keypair(ss58_address=ss58).public_key
        raw = bytes.fromhex(sig_hex.removeprefix("0x"))
        return len(raw) == 64 and bool(sr25519.verify(raw, message, pub))
    except (ValueError, TypeError, AttributeError):
        return False


def verify_envelope(env: object, *, master_hotkey: str, netuid: int
                    ) -> tuple[bool, str, dict | None, str | None]:
    """Return (ok, reason, result, digest). `result` is the parsed, verified
    result_json; `digest` is the locally recomputed sha256."""
    if not isinstance(env, dict) or env.get("v") != 1:
        return False, "version", None, None
    if env.get("netuid") != netuid:
        return False, "netuid", None, None
    rj = env.get("result_json")
    if not isinstance(rj, str):
        return False, "malformed", None, None
    digest = hashlib.sha256(rj.encode("utf-8")).hexdigest()
    if digest != env.get("digest"):
        return False, "digest", None, None
    tempo = env.get("tempo")
    if not isinstance(tempo, int) or isinstance(tempo, bool) or tempo < 0:
        return False, "malformed", None, None
    sig = env.get("signature")
    if not isinstance(sig, str) or not verify_sr25519(
            sig, tempo_message(netuid, tempo, digest).encode(), master_hotkey):
        return False, "signature", None, None
    try:
        result = json.loads(rj)
    except ValueError:
        return False, "malformed", None, None
    if (not isinstance(result, dict) or result.get("v") != 1
            or result.get("tempo") != tempo or result.get("netuid") != netuid):
        return False, "malformed", None, None
    return True, "ok", result, digest


def _get_json(client: httpx.Client, url: str) -> dict:
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        cl = resp.headers.get("content-length")
        if cl is not None and int(cl) > MAX_RESPONSE_BYTES:
            raise httpx.HTTPError(f"response too large ({cl} bytes)")
        body = bytearray()
        for chunk in resp.iter_bytes():
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise httpx.HTTPError("response exceeded size cap")
    return json.loads(bytes(body))


def fetch_latest(api_base: str, client: httpx.Client) -> dict:
    return _get_json(client, f"{api_base.rstrip('/')}{LATEST_PATH}")


def fetch_tempo(api_base: str, tempo: int, client: httpx.Client) -> dict:
    return _get_json(client, f"{api_base.rstrip('/')}/api/subnet/v1/tempo/{tempo}")
