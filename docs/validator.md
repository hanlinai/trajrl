# Running an SN11 validator (v1, follower)

In v1 the allocation is computed centrally and signed. Your validator neither scores nor computes. It
refuses anything it cannot reproduce and submits what it can.

## Every tick (default 60 s)

1. `GET {TRAJRL_API}/api/subnet/v1/tempo/latest`. The response is capped at 4 MiB.
2. **Verify.**
   - Recompute `sha256(result_json)`. It must equal `digest`.
   - Verify the **raw** sr25519 signature over `trajrl-sn11:tempo:v1:{netuid}:{tempo}:{digest}` against `TRAJRL_MASTER_HOTKEY`.
   - The signer named in the payload is ignored.
3. **Refuse replays.** A tempo lower than the last one applied is never submitted.
4. **Re-derive.** `mechanism.derive(strip(result))` must reproduce the following exactly, using integer arithmetic:
   - the emission value
   - the bonus
   - every hotkey's base, bonus, gross and alloc
   - every coldkey's net and closing balance
   - the recycle amount
   - the u16 vector
5. **Check the rails** (`spec/statement-v1.md`):

   | Rail | Check |
   |---|---|
   | Constitution | Rails equal your pinned rails |
   | Catalog only | Every paid spec is in the catalog and live |
   | Price band | The median is recomputed from the listed sources; the price is inside the band and within the max move |
   | Verified only | Only verified supply is paid |
   | No self-payment | Your `TRAJRL_TEAM_KEYS` are never paid |
   | Concentration | Each coldkey is within the concentration cap |
   | Payout cap | Total payout respects the cap |
   | Ledger continuity | Each opening balance equals the previous tempo's closing balance (fetched and verified when not cached) |

6. **Decide:**
   1. A valid `allocation` (Eleven's, empty in v1) is submitted.
   2. Otherwise the valid baseline `weights` are submitted.
   3. Otherwise the last vector you landed is resubmitted.
   4. Otherwise 100% goes to the owner hotkey.
7. **Map hotkeys to uids on your own metagraph.** Weight held by hotkeys that are no longer registered moves to the owner uid, so the vector is never silently scaled up. The result is renormalised to exactly 65535.
8. **Submit.**
   - A new tempo is submitted at once. The same tempo is resubmitted every `TRAJRL_RESUBMIT_BLOCKS` (150) to stay inside `activity_cutoff`.
   - `ExtrinsicResponse.success` is read explicitly: bittensor 10.x responses are always truthy.
9. **Post a signed heartbeat** to `/api/subnet/v1/validator/heartbeat`, signed with your own hotkey. It carries the tempo, digest, source and rail failures, and the operator's dashboard shows them.

## Configuration

| Env | Default | |
|---|---|---|
| `TRAJRL_WALLET`, `TRAJRL_HOTKEY` | — | bittensor wallet names |
| `TRAJRL_MASTER_HOTKEY` | — | statement signer (pin from the subnet's announcement) |
| `TRAJRL_OWNER_HOTKEY` | — | recycle target |
| `TRAJRL_API` | `https://provider.trajrl.com` | |
| `TRAJRL_NETUID` / `TRAJRL_NETWORK` | `11` / `finney` | |
| `TRAJRL_TEAM_KEYS` | empty | comma-separated hotkeys/coldkeys that must never be paid |
| `TRAJRL_PINNED_RAILS` | v1 constitution | JSON to override, `off` to disable the constitution check |
| `TRAJRL_POLL_S` | 60 | |
| `TRAJRL_RESUBMIT_BLOCKS` | 150 | must stay above `weights_rate_limit` |
| `TRAJRL_STATE_FILE`, `TRAJRL_HEARTBEAT_FILE` | `/var/lib/trajrl/…` | |
| `TRAJRL_DRY_RUN` | off | verify and log only |

## What the validator cannot check

The validator recomputes everything derivable from the statement. It cannot independently verify the following:

- **Service records** (which intervals were verified). They are platform-signed evidence, and their hashes are in the statement's `inputs_digest`.
- **Incidents.**
- **Market source values.**

Penalties and debt only ever reduce payouts. Continuity catches debt being dropped or forgiven between tempos.
