"""Chain access. bittensor is lazy-imported so tests and dry-run need no chain extra."""
from __future__ import annotations

from dataclasses import dataclass

U16 = 65535


@dataclass
class ChainView:
    sub: object
    hotkeys: list[str]
    block: int | None


def resolve_uids(weights: list[list], hotkeys_on_chain: list[str],
                 owner_hotkey: str) -> tuple[list[int], list[int], int]:
    """Map [hotkey, u16] to on-chain uids, renormalised to exactly 65535.

    Weight held by hotkeys no longer registered moves to the owner (recycle)
    uid when it is registered — dropping it would silently scale everyone else
    *up*, paying out emission the statement chose to recycle. Returns
    (uids, weights, dropped_u16).
    """
    uid_of = {hk: uid for uid, hk in enumerate(hotkeys_on_chain)}
    agg: dict[int, int] = {}
    dropped = 0
    for hk, w in weights:
        if hk in uid_of:
            agg[uid_of[hk]] = agg.get(uid_of[hk], 0) + w
        else:
            dropped += w
    if dropped and owner_hotkey in uid_of:
        o = uid_of[owner_hotkey]
        agg[o] = agg.get(o, 0) + dropped
    present = sorted((u, w) for u, w in agg.items() if w > 0)
    if not present:
        return [], [], dropped
    total = sum(w for _, w in present)
    scaled = [[u, w * U16 // total, w * U16 % total] for u, w in present]
    gap = U16 - sum(s[1] for s in scaled)
    for s in sorted(scaled, key=lambda s: (-s[2], s[0]))[:gap]:
        s[1] += 1
    return [s[0] for s in scaled], [s[1] for s in scaled], dropped


def extrinsic_ok(res) -> tuple[bool, str]:
    """bittensor 10.x ExtrinsicResponse has no __bool__ — read .success."""
    success = getattr(res, "success", None)
    if success is not None:
        return bool(success), str(getattr(res, "message", "") or "")
    if isinstance(res, tuple):
        return bool(res[0]), str(res[1]) if len(res) > 1 else ""
    return bool(res), ""


class ChainClient:
    """One long-lived Subtensor connection; reconnect once per failing tick."""

    def __init__(self, network: str, netuid: int):
        self.network, self.netuid, self._sub = network, netuid, None

    def snapshot(self) -> ChainView:
        last: Exception | None = None
        for _ in range(2):
            try:
                if self._sub is None:
                    import bittensor as bt
                    self._sub = bt.Subtensor(network=self.network)
                meta = self._sub.metagraph(self.netuid)
                try:
                    b = self._sub.get_current_block()
                    block = b if isinstance(b, int) and not isinstance(b, bool) and b > 0 else None
                except Exception:
                    block = None
                return ChainView(self._sub, list(meta.hotkeys), block)
            except Exception as e:  # noqa: BLE001 — bittensor raises a zoo
                last = e
                self.close()
        raise last  # type: ignore[misc]

    def set_weights(self, view: ChainView, *, wallet: str, hotkey: str,
                    uids: list[int], weights: list[int]) -> bool:
        try:
            import bittensor as bt
            wal = bt.Wallet(name=wallet, hotkey=hotkey)
            res = view.sub.set_weights(wallet=wal, netuid=self.netuid, uids=uids,
                                       weights=weights, version_key=0, wait_for_inclusion=True)
            ok, why = extrinsic_ok(res)
            print(f"[chain] set_weights({len(uids)} uids) -> {ok}{f' ({why})' if why else ''}", flush=True)
            return ok
        except Exception as e:  # noqa: BLE001
            print(f"[chain] set_weights failed ({type(e).__name__}: {e})", flush=True)
            return False

    def close(self) -> None:
        if self._sub is not None:
            for c in (lambda: self._sub.substrate.close(), lambda: self._sub.close()):
                try:
                    c()
                except Exception:
                    pass
            self._sub = None
