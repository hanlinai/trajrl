import hashlib
import json
import pathlib

import pytest

VECTORS = pathlib.Path(__file__).resolve().parent.parent / "spec" / "vectors"


def load_vectors():
    return [json.loads(p.read_text()) for p in sorted(VECTORS.glob("*.json"))]


@pytest.fixture(scope="session")
def master():
    from bittensor_wallet import Keypair
    return Keypair.create_from_uri("//TrajrlMaster")


def make_envelope(kp, result: dict, netuid: int = 11) -> dict:
    from trajrl_validator.sync import tempo_message
    rj = json.dumps(result, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(rj.encode()).hexdigest()
    sig = kp.sign(tempo_message(netuid, result["tempo"], digest).encode()).hex()
    return {"v": 1, "netuid": netuid, "tempo": result["tempo"], "result_json": rj,
            "digest": digest, "signature": sig, "signer": kp.ss58_address}
