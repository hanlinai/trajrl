import copy
import json

from conftest import load_vectors, make_envelope
from trajrl_validator.chain import extrinsic_ok, resolve_uids
from trajrl_validator.rails import decide
from trajrl_validator.schedule import should_submit
from trajrl_validator.sync import verify_envelope

BASIC = {v["name"]: v["expected"] for v in load_vectors()}["basic"]


def test_verify_ok(master):
    env = make_envelope(master, BASIC)
    ok, why, res, dig = verify_envelope(env, master_hotkey=master.ss58_address, netuid=11)
    assert ok and why == "ok" and res == BASIC and dig == env["digest"]


def test_wrong_master_rejected(master):
    from bittensor_wallet import Keypair
    other = Keypair.create_from_uri("//Mallory")
    env = make_envelope(other, BASIC)
    assert verify_envelope(env, master_hotkey=master.ss58_address, netuid=11)[1] == "signature"


def test_byte_tamper_rejected(master):
    env = make_envelope(master, BASIC)
    env["result_json"] = env["result_json"].replace("5HK_A1", "5HK_X1")
    assert verify_envelope(env, master_hotkey=master.ss58_address, netuid=11)[1] == "digest"


def test_tempo_mismatch_rejected(master):
    env = make_envelope(master, BASIC)
    env["tempo"] += 1
    assert verify_envelope(env, master_hotkey=master.ss58_address, netuid=11)[1] == "signature"


def test_netuid_rejected(master):
    env = make_envelope(master, BASIC)
    assert verify_envelope(env, master_hotkey=master.ss58_address, netuid=12)[1] == "netuid"


def _decide(result, cached=None, **kw):
    return decide(result, pinned_rails=None, team_keys=set(), prev_closing=None,
                  cached=cached, owner_hotkey="5OWNER", **kw)


def test_policy_baseline():
    d = _decide(BASIC)
    assert d.source == "baseline" and sum(w for _, w in d.weights) == 65535


def test_policy_falls_back_to_cache_then_recycle():
    bad = copy.deepcopy(BASIC)
    bad["weights"][0][2] -= 5
    bad["weights"][1][2] += 5
    d = _decide(bad, cached=[["5HK_B1", 65535]])
    assert d.source == "cached" and d.failures
    d = _decide(bad)
    assert d.source == "recycle" and d.weights == [["5OWNER", 65535]]


def test_policy_refuses_recycle_to_another_hotkey():
    from trajrl_validator.mechanism import derive, strip
    r = copy.deepcopy(BASIC)
    r["recycle"]["hotkey"] = "5ATTACKER"
    r = derive(strip(r))  # every number re-derives: only the recycle target is wrong
    assert r["recycle"]["hotkey"] == "5ATTACKER"
    d = _decide(r)
    assert d.source == "recycle" and d.weights == [["5OWNER", 65535]] and "owner:recycle" in d.failures


def test_policy_allocation_used_when_valid():
    r = copy.deepcopy(BASIC)
    r["allocation"] = copy.deepcopy(BASIC)
    assert _decide(r).source == "allocation"
    r["allocation"]["weights"][0][2] -= 1
    d = _decide(r)
    assert d.source == "baseline" and any(f.startswith("allocation:") for f in d.failures)


def test_schedule():
    assert should_submit(tempo=5, last_applied=None, current_block=None, last_submit_block=None, now=0, last_submit_ts=None)
    assert should_submit(tempo=6, last_applied=5, current_block=10, last_submit_block=9, now=0, last_submit_ts=0)
    assert not should_submit(tempo=4, last_applied=5, current_block=10_000, last_submit_block=1, now=0, last_submit_ts=0)
    assert not should_submit(tempo=5, last_applied=5, current_block=100, last_submit_block=1, now=0, last_submit_ts=0)
    assert should_submit(tempo=5, last_applied=5, current_block=151, last_submit_block=1, now=0, last_submit_ts=0)


def test_resolve_uids_moves_unregistered_to_owner():
    chain = ["5OWNER", "x", "5HK_A", "5HK_B"]
    uids, ws, dropped = resolve_uids([["5HK_A", 30000], ["5HK_GONE", 5535], ["5OWNER", 30000]], chain, "5OWNER")
    assert dropped == 5535
    assert uids == [0, 2] and ws == [35535, 30000] and sum(ws) == 65535


def test_resolve_uids_owner_unregistered_renormalises():
    uids, ws, _ = resolve_uids([["a", 1], ["b", 1], ["gone", 1]], ["a", "b"], "OWN")
    assert uids == [0, 1] and sum(ws) == 65535


def test_extrinsic_ok():
    class R:
        success = False
        message = "No validator permit"
    assert extrinsic_ok(R()) == (False, "No validator permit")
    assert extrinsic_ok((True, "")) == (True, "")


def test_tick_dry_run(master, tmp_path, monkeypatch):
    import httpx
    from trajrl_validator import validator
    from trajrl_validator.config import Config

    env = make_envelope(master, BASIC)

    def handler(req: httpx.Request):
        if req.url.path.endswith("/tempo/latest"):
            return httpx.Response(200, content=json.dumps(env).encode())
        return httpx.Response(404)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = Config(wallet="w", hotkey="h", api="http://p", master_hotkey=master.ss58_address,
                 owner_hotkey="5OWNER", state_file=str(tmp_path / "s.json"), dry_run=True,
                 pinned_rails={"version": 1, "band_bps": 2500, "max_move_bps": 1000, "concentration_bps": 2000})
    out = validator.tick(cfg, client, chain=None)
    assert out["source"] == "baseline" and out["verify"] == "ok"
    assert out["weights"] == [[w[0], w[2]] for w in BASIC["weights"]]


def test_tick_submits_and_refuses_replay(master, tmp_path):
    import httpx
    from trajrl_validator import validator
    from trajrl_validator.chain import ChainView
    from trajrl_validator.config import Config

    newer = copy.deepcopy(BASIC)
    newer["tempo"] = BASIC["tempo"] + 1
    served = {"env": make_envelope(master, newer)}

    def handler(req):
        return httpx.Response(200, content=json.dumps(served["env"]).encode())

    class FakeChain:
        calls = []
        def snapshot(self):
            return ChainView(None, ["5OWNER", "x", "x2", "5HK_A1", "x4", "5HK_B1", "x6", "5HK_A2", "x8", "5HK_C1"], 1000)
        def set_weights(self, view, **kw):
            self.calls.append(kw)
            return True

    ch = FakeChain()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = Config(wallet="w", hotkey="h", api="http://p", master_hotkey=master.ss58_address,
                 owner_hotkey="5OWNER", state_file=str(tmp_path / "s.json"), pinned_rails=None)
    out = validator.tick(cfg, client, ch, now=1000.0)
    assert out["submitted"] and ch.calls[0]["uids"] == [0, 3, 5, 7, 9]
    # replay an older, genuinely signed statement → never submitted as new
    served["env"] = make_envelope(master, BASIC)
    out = validator.tick(cfg, client, ch, now=1001.0)
    assert not out["submitted"] and len(ch.calls) == 1
