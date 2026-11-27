"""When to submit. Pure decisions — no IO.

A new tempo is submitted at once. The same vector is resubmitted every
RESUBMIT_BLOCKS so last_update stays inside activity_cutoff. A tempo below the
last applied one is never submitted: that monotonic guard is what stops a
genuinely-signed old statement from being replayed.
"""
from __future__ import annotations

RESUBMIT_BLOCKS = 150     # > SN11 weights_rate_limit (100) with margin for inclusion lag
BLOCK_S = 12


def should_submit(*, tempo: int, last_applied: int | None, current_block: int | None,
                  last_submit_block: int | None, now: float, last_submit_ts: float | None,
                  interval_blocks: int = RESUBMIT_BLOCKS) -> bool:
    if last_applied is None or tempo > last_applied:
        return True
    if tempo < last_applied:
        return False
    if current_block is None or last_submit_block is None:
        if last_submit_ts is None:
            return True
        elapsed = now - last_submit_ts
        return elapsed < 0 or elapsed >= interval_blocks * BLOCK_S
    return current_block - last_submit_block >= interval_blocks
