# v1: what is implemented

Date: 2026-11-24. This note maps `incentive-mechanism.md` onto what v1 implements across two repositories:

- `trajrl-provider`: the provider site, settlement, and the validator API
- this repository: the spec and the validator

## Decisions

| Topic | v1 | Mechanism doc |
|---|---|---|
| Who computes the allocation | The settlement worker in `trajrl-provider`, deterministic (`baseline-v1`) | Eleven, with the baseline as fallback. Eleven's slot `allocation` exists and is `null` |
| Validators | Verify the signature, re-derive every number, check the rails, then submit | Same: they check Eleven's allocation against the rails |
| Prices | An admin catalog target, clamped to ±band around the median of market sources and to a max move per tempo | Eleven prices within the same rails |
| Market sources | Pluggable (`static`, `http-json`); each observation is stored with a response hash | Seven or more exchanges and cloud list prices, fetched inside TDX |
| Units | Reference-unit-hours (`tdx.c3-4` = 1, `tdx.c3-8` = 2), measured in seconds, split at tempo boundaries | Same |
| Accounting unit | Integer micro-USD at the source tempo's approved price (`usd-v1`). Debt is never re-priced | Open launch decision |
| Occupancy bonus | Implemented (`b_eff = min(cap, budget × Base / Eligible)`) but **off**, so eligible time is zero | Off until eligibility trials pass |
| Payout cap | Σ paid ≤ emission value, and ≤ Σ net. The remainder is weighted to the owner hotkey | Same; the chain recycling path is still a launch gate |
| Concentration | Per-coldkey cap on paid share (20% of emission value) | Same |
| Penalties | ×2 doubling per attributable incident in 24 h, capped at ×8. Overlaps are deducted once. Disputes hold the deduction | Same (proposed parameters) |
| Debt | Per coldkey; carried by `opening` → `closing`; checked by validators through the continuity rail | Same |
| Collateral | Per-hotkey registry replay (reserve, activate, exit, retire, chain_read). Only covered, active or exiting commitments earn | Same. The on-chain read path is still to be wired; operators record confirmed reads |
| Admission | Applications, a signed capacity budget (ceiling, ready floor, exit reserve), approval → provisioning → verified → ready | Same |
| Orders | Admin posts. Providers offer ready capacity. Assignment uses a fixed candidate set and a committed and revealed seed. Payment is pro rata at the posted price | Same |
| Tempo | Native subtensor epochs: `(block + netuid + 1) % (tempo + 1) == 0` | Same |
| Exceptions | No statement is signed for that tempo. Validators keep the last landed vector. Balances pass through unchanged | The chain action for each exception is still a launch gate |

## Trust boundaries in v1

- **Platform.** The sandbox platform is the only writer of service evidence. It pushes signed records to
  `/api/platform/v1/records` (sr25519, pinned `PLATFORM_HOTKEY`, ±300 s).
- **Master key.** It signs statements. Validators pin its ss58 locally. The provider site re-verifies every stored
  statement before serving it, and answers 503 if it does not verify.
- **Validators.** They re-derive everything except evidence: interval verification, incidents and source values.
  Those inputs are fixed by `inputs_digest` and published per tempo for audit.

## Still open (from §10 of the mechanism)

- Shadow mode for Eleven: run it beside the baseline and publish both.
- The on-chain collateral read and write path. Release enforcement of the exit reservation.
- Real market adapters, and the price fetch inside TDX.
- The chain recycling path versus normalised weights.
- Dispute adjudication deadlines and the compensation policy for corrections to settled tempos.
