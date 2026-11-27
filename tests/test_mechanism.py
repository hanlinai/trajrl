import copy

import pytest

from trajrl_validator.mechanism import (U16, StatementError, check_rails, derive,
                                        median_floor, strip, u16_weights)
from conftest import load_vectors

VECS = load_vectors()


@pytest.mark.parametrize("vec", VECS, ids=[v["name"] for v in VECS])
def test_vectors_rederive(vec):
    assert derive(vec["input"]) == vec["expected"]
    assert derive(strip(vec["expected"])) == vec["expected"]


@pytest.mark.parametrize("vec", VECS, ids=[v["name"] for v in VECS])
def test_vectors_pass_rails(vec):
    assert check_rails(vec["expected"]) == []


@pytest.mark.parametrize("vec", VECS, ids=[v["name"] for v in VECS])
def test_weights_sum(vec):
    assert sum(w[2] for w in vec["expected"]["weights"]) == U16


def _acct(res, ck):
    return next(a for a in res["accounts"] if a["coldkey"] == ck)


def test_carry_forward_doc_example():
    out = {v["name"]: v["expected"] for v in VECS}["carry_forward"]
    a = _acct(out, "5CK_A")
    assert a["gross_uusd"] == 4_999_960   # ≈ $5
    assert a["net_uusd"] == 1_999_960     # gross 5 − opening 3 → ≈ 2
    assert a["closing_uusd"] == 0
    b = _acct(out, "5CK_B")
    assert b["net_uusd"] == 0 and b["closing_uusd"] == 2_000_000 - 280_000


def test_unmappable_doc_example():
    out = {v["name"]: v["expected"] for v in VECS}["unmappable"]
    a = _acct(out, "5CK_A")
    dead, live = a["hotkeys"]
    assert dead["alloc_uusd"] == 0
    # gross 100 unmappable + 1 live, net 101 → live gets ≈1, never 101
    assert live["alloc_uusd"] == a["net_uusd"] * live["gross_uusd"] // a["gross_uusd"]
    assert live["alloc_uusd"] < 1_000_000


def test_bonus_capped_at_20pct():
    out = {v["name"]: v["expected"] for v in VECS}["bonus"]
    assert out["bonus"]["b_eff_ppm"] == 200_000


def test_oversupply_never_exceeds_emission():
    out = {v["name"]: v["expected"] for v in VECS}["oversupply"]
    paid = sum(h["alloc_uusd"] for a in out["accounts"] for h in a["hotkeys"])
    assert paid <= out["emission"]["value_uusd"]
    cap = out["emission"]["value_uusd"] * 2000 // 10000
    assert all(sum(h["alloc_uusd"] for h in a["hotkeys"]) <= cap for a in out["accounts"])


def test_median_floor():
    assert median_floor([3, 1, 2]) == 2
    assert median_floor([1, 2, 3, 6]) == 2
    with pytest.raises(StatementError):
        median_floor([])


def test_u16_tie_break_by_uid():
    w = u16_weights([("a", 5, 1), ("b", 2, 1), ("c", 9, 1)], 3)
    assert w == [["b", 2, 21845], ["a", 5, 21845], ["c", 9, 21845]]
    w = u16_weights([("a", 5, 1), ("b", 2, 1)], 2)
    assert w == [["b", 2, 32768], ["a", 5, 32767]]


def _basic():
    return copy.deepcopy({v["name"]: v["expected"] for v in VECS}["basic"])


def test_tampered_weight_fails_integrity():
    r = _basic()
    r["weights"][1][2] += 1
    r["weights"][0][2] -= 1
    assert "integrity:weights" in check_rails(r)


def test_inflated_supply_detected():
    r = _basic()
    r["accounts"][0]["hotkeys"][0]["alloc_uusd"] += 10
    assert any(f.startswith("integrity") for f in check_rails(r))


def test_price_out_of_band():
    r = _basic()
    r["prices"][0]["price_uusd"] = 400_000
    r = derive(strip(r))
    assert "price_band:tdx.c3-4:band" in check_rails(r)
    assert "price_band:tdx.c3-4:move" in check_rails(r)


def test_median_mismatch():
    r = _basic()
    r["prices"][0]["ref_median_uusd"] = 1
    assert "price_band:tdx.c3-4:median" in check_rails(r)


def test_planned_spec_not_payable():
    r = _basic()
    r["prices"][0]["status"] = "planned"
    assert "catalog:tdx.c3-4" in check_rails(r)


def test_unknown_spec_fails_derive():
    r = _basic()
    r["accounts"][0]["hotkeys"][0]["supply"][0]["spec"] = "gpu.h100-niche"
    assert check_rails(r)[0].startswith("integrity:derive")


def test_constitution_pinned():
    r = _basic()
    r["rails"]["concentration_bps"] = 9000
    r = derive(strip(r))
    pinned = {"version": 1, "band_bps": 2500, "max_move_bps": 1000, "concentration_bps": 2000}
    assert "constitution:concentration_bps" in check_rails(r, pinned_rails=pinned)


def test_self_payment():
    r = _basic()
    assert "self_payment:5CK_B" in check_rails(r, team_keys={"5CK_B"})
    assert "self_payment:5HK_A1" in check_rails(r, team_keys={"5HK_A1"})


def test_continuity():
    r = _basic()
    assert check_rails(r, prev_closing={}) == []
    assert "continuity:5CK_C" in check_rails(r, prev_closing={"5CK_C": 5})
    assert "continuity:dropped:5CK_Z" in check_rails(r, prev_closing={"5CK_Z": 5})


def test_lowered_opening_balance_detected_by_continuity():
    r = _basic()
    acct = _acct(r, "5CK_C")
    acct["opening_uusd"] = 0
    r = derive(strip(r))
    assert check_rails(r, prev_closing={"5CK_C": 1_000_000})


def test_bonus_while_disabled_rejected():
    r = _basic()
    r["accounts"][0]["hotkeys"][0]["supply"][0]["eligible_muh"] = 10
    assert check_rails(r)[0].startswith("integrity:derive")
