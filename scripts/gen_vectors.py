"""Regenerate spec/vectors/*.json from the Python reference derivation.

    python scripts/gen_vectors.py

The provider's TypeScript implementation is tested against these files.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from trajrl_validator.mechanism import derive  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "spec" / "vectors"
RAILS = {"version": 1, "band_bps": 2500, "max_move_bps": 1000, "concentration_bps": 2000,
         "bonus_cap_ppm": 200000, "bonus_budget_ppm": 100000, "bonus_enabled": False}


def price(spec, p, prev=None, sources=(270000, 280000, 290000), status="live", cls="sandbox"):
    srcs = [{"name": f"src{i}", "value_uusd": v, "hash": f"{i:064x}"} for i, v in enumerate(sources)]
    vs = sorted(sources)
    n = len(vs)
    med = vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) // 2
    return {"class": cls, "spec": spec, "status": status, "price_uusd": p,
            "prev_price_uusd": prev, "ref_median_uusd": med, "sources": srcs}


def hk(hotkey, uid, supply=(), orders=0):
    return {"hotkey": hotkey, "uid": uid,
            "supply": [{"spec": s, "muh": m, "eligible_muh": e} for s, m, e in supply],
            "orders_uusd": orders}


def acct(ck, hotkeys, pen=0, opening=0):
    return {"coldkey": ck, "opening_uusd": opening, "penalties_uusd": pen, "hotkeys": hotkeys}


def base(tempo, accounts, *, alpha=147_600_000_000, alpha_usd=1_490_000, rails=None, prices=None):
    return {
        "v": 1, "netuid": 11, "tempo": tempo,
        "window": {"start_block": tempo * 361, "end_block": (tempo + 1) * 361,
                   "start_ts": 1_763_000_000 + tempo * 4332, "end_ts": 1_763_000_000 + (tempo + 1) * 4332},
        "rule_version": "baseline-v1", "catalog_version": 1,
        "rails": dict(rails or RAILS),
        "inputs_digest": "0" * 64,
        "prices": prices or [price("tdx.c3-4", 280000, 280000), price("tdx.c3-8", 560000, 560000, (540000, 560000, 580000))],
        "emission": {"alpha_budget_rao": alpha, "alpha_price_uusd": alpha_usd},
        "accounts": accounts,
        "recycle": {"hotkey": "5OWNER", "uid": 0},
        "allocation": None,
        "exceptions": [],
    }


H = 1000  # one reference-unit-hour in muh
CASES = {
    # 3 providers, supply worth far less than emission → most of it recycles.
    "basic": base(100, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 3 * 1200, 0)]), hk("5HK_A2", 7, [("tdx.c3-8", 2 * 1200, 0)])]),
        acct("5CK_B", [hk("5HK_B1", 5, [("tdx.c3-4", 10 * 1200, 0)])]),
        acct("5CK_C", [hk("5HK_C1", 9, [("tdx.c3-4", 1200, 0)])], pen=100_000),
    ]),
    # Supply worth more than emission → everyone scaled down, nothing recycled
    # except rounding; concentration still binds on the big one.
    "oversupply": base(101, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 400 * H, 0)])]),
        acct("5CK_B", [hk("5HK_B1", 5, [("tdx.c3-4", 300 * H, 0)])]),
        acct("5CK_C", [hk("5HK_C1", 9, [("tdx.c3-8", 150 * H, 0)])]),
        acct("5CK_D", [hk("5HK_D1", 11, [("tdx.c3-4", 250 * H, 0)])]),
        acct("5CK_E", [hk("5HK_E1", 12, [("tdx.c3-4", 260 * H, 0)])]),
        acct("5CK_F", [hk("5HK_F1", 13, [("tdx.c3-4", 240 * H, 0)])]),
    ], alpha=147_600_000_000, alpha_usd=1_000_000),
    # Doc example: gross 5, no new penalties, opening 3 → net 2, closing 0 (×1 USD).
    "carry_forward": base(102, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 17857, 0)])], opening=3_000_000),
        acct("5CK_B", [hk("5HK_B1", 5, [("tdx.c3-4", 1000, 0)])], pen=2_000_000),
    ]),
    # Doc example: gross 100 on an unmappable key and 1 on a live key → allocate 1.
    "unmappable": base(103, [
        acct("5CK_A", [hk("5HK_DEAD", None, [("tdx.c3-4", 357143, 0)]),
                       hk("5HK_LIVE", 4, [("tdx.c3-4", 3571, 0)])]),
    ]),
    # Occupancy bonus on: b_eff = min(20%, 10% * Base / Eligible).
    "bonus": base(104, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 10 * H, 8 * H)])]),
        acct("5CK_B", [hk("5HK_B1", 5, [("tdx.c3-4", 10 * H, 1 * H)])]),
        acct("5CK_C", [hk("5HK_C1", 9, [("tdx.c3-8", 10 * H, 0)])]),
    ], rails={**RAILS, "bonus_enabled": True}),
    # One dominant provider under a 20% concentration cap.
    "concentration": base(105, [
        acct("5CK_BIG", [hk("5HK_BIG1", 3, [("tdx.c3-4", 600 * H, 0)]), hk("5HK_BIG2", 4, [("tdx.c3-8", 300 * H, 0)])]),
        acct("5CK_SMALL", [hk("5HK_S1", 5, [("tdx.c3-4", 10 * H, 0)])]),
    ]),
    # Order settlement adds posted-price value on top of standing supply.
    "orders": base(106, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 5 * H, 0)], orders=12_500_000)]),
        acct("5CK_B", [hk("5HK_B1", 5, [], orders=4_000_000)]),
    ]),
    # No emission this tempo → 100% recycle, exception recorded.
    "zero_emission": base(107, [
        acct("5CK_A", [hk("5HK_A1", 3, [("tdx.c3-4", 5 * H, 0)])]),
    ], alpha=0),
    # No providers at all.
    "empty": base(108, []),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, inp in CASES.items():
        out = derive(inp)
        (OUT / f"{name}.json").write_text(json.dumps(
            {"name": name, "input": inp, "expected": out}, indent=1, sort_keys=True) + "\n")
        print(name, out["weights"], out["recycle"])


if __name__ == "__main__":
    main()
