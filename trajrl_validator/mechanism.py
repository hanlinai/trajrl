"""SN11 statement v1 — normative derivation and rails (spec/statement-v1.md).

Pure functions, integers only. The TypeScript settlement in trajrl-provider
(lib/mechanism/derive.ts) must produce bit-identical output; both are pinned
by spec/vectors/*.json.
"""
from __future__ import annotations

import copy
from typing import Any

U16 = 65535
DERIVED_ACCOUNT = ("gross_uusd", "net_uusd", "closing_uusd")
DERIVED_HOTKEY = ("base_uusd", "bonus_uusd", "gross_uusd", "alloc_uusd")


class StatementError(ValueError):
    """A statement that cannot be derived (malformed, unknown spec, ...)."""


def _int(x: Any, name: str) -> int:
    if not isinstance(x, int) or isinstance(x, bool) or x < 0:
        raise StatementError(f"{name} must be a non-negative integer")
    return x


def median_floor(values: list[int]) -> int:
    if not values:
        raise StatementError("no price sources")
    v = sorted(values)
    n = len(v)
    if n % 2:
        return v[n // 2]
    return (v[n // 2 - 1] + v[n // 2]) // 2


def strip(result: dict) -> dict:
    """Remove every derived field, leaving the settlement inputs."""
    r = copy.deepcopy(result)
    r.get("emission", {}).pop("value_uusd", None)
    r.pop("bonus", None)
    r.pop("weights", None)
    if isinstance(r.get("recycle"), dict):
        r["recycle"].pop("alloc_uusd", None)
    for acct in r.get("accounts", []):
        for k in DERIVED_ACCOUNT:
            acct.pop(k, None)
        for hk in acct.get("hotkeys", []):
            for k in DERIVED_HOTKEY:
                hk.pop(k, None)
    return r


def u16_weights(entries: list[tuple[str, int, int]], total: int) -> list[list]:
    """entries: (hotkey, uid, alloc). Largest-remainder to exactly 65535."""
    if total <= 0:
        raise StatementError("u16 total must be positive")
    rows = []
    for hk, uid, alloc in entries:
        if alloc <= 0:
            continue
        rows.append([hk, uid, alloc * U16 // total, alloc * U16 % total])
    short = U16 - sum(r[2] for r in rows)
    if short < 0 or short > len(rows):
        raise StatementError("allocations exceed total")
    for r in sorted(rows, key=lambda r: (-r[3], r[1]))[:short]:
        r[2] += 1
    rows.sort(key=lambda r: r[1])
    return [[hk, uid, w] for hk, uid, w, _ in rows]


def derive(inp: dict) -> dict:
    """Recompute every derived field from the settlement inputs."""
    r = copy.deepcopy(inp)
    rails = r["rails"]
    prices: dict[str, int] = {}
    for p in r["prices"]:
        if p["spec"] in prices:
            raise StatementError(f"duplicate spec {p['spec']}")
        prices[p["spec"]] = _int(p["price_uusd"], "price_uusd")

    em = r["emission"]
    value = _int(em["alpha_budget_rao"], "alpha_budget_rao") * _int(
        em["alpha_price_uusd"], "alpha_price_uusd") // 1_000_000_000
    em["value_uusd"] = value

    bonus_on = bool(rails.get("bonus_enabled"))
    base_total = 0
    elig_total = 0
    seen_hk: set[str] = set()
    seen_uid: set[int] = set()
    for acct in r["accounts"]:
        for hk in acct["hotkeys"]:
            if hk["hotkey"] in seen_hk:
                raise StatementError(f"duplicate hotkey {hk['hotkey']}")
            seen_hk.add(hk["hotkey"])
            if hk.get("uid") is not None:
                if hk["uid"] in seen_uid:
                    raise StatementError(f"duplicate uid {hk['uid']}")
                seen_uid.add(_int(hk["uid"], "uid"))
            base = elig = 0
            for s in hk.get("supply", []):
                if s["spec"] not in prices:
                    raise StatementError(f"spec {s['spec']} not in catalog prices")
                muh = _int(s["muh"], "muh")
                emuh = _int(s.get("eligible_muh", 0), "eligible_muh")
                if emuh > muh:
                    raise StatementError("eligible_muh exceeds muh")
                if not bonus_on and emuh:
                    raise StatementError("eligible_muh while bonus disabled")
                base += prices[s["spec"]] * muh // 1000
                elig += prices[s["spec"]] * emuh // 1000
            hk["base_uusd"] = base
            hk["_elig"] = elig
            base_total += base
            elig_total += elig

    if not bonus_on or elig_total == 0:
        b_eff = 0
    else:
        b_eff = min(rails["bonus_cap_ppm"],
                    rails["bonus_budget_ppm"] * base_total // elig_total)
    r["bonus"] = {"base_uusd": base_total, "eligible_uusd": elig_total, "b_eff_ppm": b_eff}

    cap = value * rails["concentration_bps"] // 10000
    allocs: list[tuple[dict, int]] = []
    for acct in r["accounts"]:
        g = 0
        for hk in acct["hotkeys"]:
            hk["bonus_uusd"] = hk.pop("_elig") * b_eff // 1_000_000
            hk["gross_uusd"] = hk["base_uusd"] + hk["bonus_uusd"] + _int(
                hk.get("orders_uusd", 0), "orders_uusd")
            g += hk["gross_uusd"]
        pen = _int(acct["penalties_uusd"], "penalties_uusd")
        opening = _int(acct["opening_uusd"], "opening_uusd")
        acct["gross_uusd"] = g
        acct["net_uusd"] = max(0, g - pen - opening)
        acct["closing_uusd"] = max(0, opening + pen - g)
        net = acct["net_uusd"]
        a = [(net * hk["gross_uusd"] // g) if (g > 0 and hk.get("uid") is not None) else 0
             for hk in acct["hotkeys"]]
        tot = sum(a)
        if tot > cap:
            a = [x * cap // tot for x in a]
        for hk, x in zip(acct["hotkeys"], a):
            hk["alloc_uusd"] = x
            allocs.append((hk, x))

    total = sum(x for _, x in allocs)
    if total > value:
        for hk, x in allocs:
            hk["alloc_uusd"] = x * value // total if value else 0
    paid = sum(hk["alloc_uusd"] for hk, _ in allocs)

    rec = r["recycle"]
    rec["alloc_uusd"] = value - paid
    exceptions = list(r.get("exceptions", []))
    if value == 0:
        for hk, _ in allocs:
            hk["alloc_uusd"] = 0
        rec["alloc_uusd"] = 0
        r["weights"] = [[rec["hotkey"], rec["uid"], U16]]
        if "zero-emission" not in exceptions:
            exceptions.append("zero-emission")
    else:
        entries = [(hk["hotkey"], hk["uid"], hk["alloc_uusd"]) for hk, _ in allocs]
        entries.append((rec["hotkey"], rec["uid"], rec["alloc_uusd"]))
        r["weights"] = u16_weights(entries, value)
    r["exceptions"] = exceptions
    return r


def check_rails(result: dict, *, pinned_rails: dict | None = None,
                team_keys: set[str] | None = None,
                prev_closing: dict[str, int] | None = None) -> list[str]:
    """Return the list of failed rails (empty = pass). Never raises."""
    fails: list[str] = []
    try:
        derived = derive(strip(result))
    except (StatementError, KeyError, TypeError) as e:
        return [f"integrity:derive:{e}"]

    for k in ("emission", "bonus", "accounts", "recycle", "weights"):
        if derived.get(k) != result.get(k):
            fails.append(f"integrity:{k}")
    if sum(w[2] for w in result.get("weights", [])) != U16:
        fails.append("integrity:weights-sum")

    rails = result["rails"]
    if pinned_rails is not None:
        for k, v in pinned_rails.items():
            if rails.get(k) != v:
                fails.append(f"constitution:{k}")

    used = {s["spec"] for a in result["accounts"] for h in a["hotkeys"] for s in h.get("supply", [])}
    for p in result["prices"]:
        if p["spec"] in used and p.get("status") != "live":
            fails.append(f"catalog:{p['spec']}")
        try:
            ref = median_floor([int(s["value_uusd"]) for s in p.get("sources", [])])
        except (StatementError, KeyError, TypeError, ValueError):
            fails.append(f"price_band:{p['spec']}:sources")
            continue
        if ref != p.get("ref_median_uusd"):
            fails.append(f"price_band:{p['spec']}:median")
        price = p["price_uusd"]
        if abs(price - ref) > ref * rails["band_bps"] // 10000:
            fails.append(f"price_band:{p['spec']}:band")
        prev = p.get("prev_price_uusd")
        if prev is not None and abs(price - prev) > prev * rails["max_move_bps"] // 10000:
            fails.append(f"price_band:{p['spec']}:move")

    value = result["emission"].get("value_uusd", 0)
    cap = value * rails["concentration_bps"] // 10000
    team = team_keys or set()
    paid = 0
    for a in result["accounts"]:
        s = sum(h.get("alloc_uusd", 0) for h in a["hotkeys"])
        paid += s
        if s > cap:
            fails.append(f"concentration:{a['coldkey']}")
        if s > a.get("net_uusd", 0):
            fails.append(f"payout_cap:{a['coldkey']}")
        if s > 0 and a["coldkey"] in team:
            fails.append(f"self_payment:{a['coldkey']}")
        for h in a["hotkeys"]:
            if h.get("alloc_uusd", 0) > 0 and h["hotkey"] in team:
                fails.append(f"self_payment:{h['hotkey']}")
            if h.get("alloc_uusd", 0) > 0 and not h.get("supply") and not h.get("orders_uusd"):
                fails.append(f"verified_only:{h['hotkey']}")
        if prev_closing is not None and a.get("opening_uusd") != prev_closing.get(a["coldkey"], 0):
            fails.append(f"continuity:{a['coldkey']}")
    if prev_closing is not None:
        present = {a["coldkey"] for a in result["accounts"]}
        for ck, bal in prev_closing.items():
            if bal > 0 and ck not in present:
                fails.append(f"continuity:dropped:{ck}")
    if paid > value:
        fails.append("payout_cap:total")
    return sorted(set(fails))
