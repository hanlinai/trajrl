# SN11 allocation statement — v1

Status: v1, centrally settled. The provider site (`trajrl-provider`) computes and
signs one statement per native tempo. Validators (`trajrl_validator`) verify the
signature, **re-derive every number they can from the statement's own line
items**, check the rails, and submit the resulting weights. Nothing in the
statement is trusted because it is stated; it is trusted because it recomputes.

All money is integer **micro-USD** (`uusd`, 1 USD = 1,000,000). All unit-hours
are integer **milli-unit-hours** (`muh`, 1 reference-unit-hour = 1,000). All
ratios are integer **basis points** (`bps`, 10,000 = 100%) or **ppm**
(1,000,000 = 100%). Every division is a floor division of non-negative integers.
This keeps TypeScript (BigInt) and Python (int) bit-identical.

## Envelope (served by `GET /api/subnet/v1/tempo/latest`)

```json
{ "v": 1, "netuid": 11, "tempo": 1234,
  "result_json": "<exact bytes that were hashed>",
  "digest": "<sha256 hex of result_json utf-8>",
  "signature": "<128 hex chars, raw sr25519 signature>",
  "signer": "<ss58 of master hotkey, display only>" }
```

Signed message (utf-8 bytes, raw sr25519, **no** `<Bytes>` wrapping):

```
trajrl-sn11:tempo:v1:{netuid}:{tempo}:{digest}
```

The validator pins the master hotkey in local config; `signer` is never used to
verify. The validator verifies against the digest it recomputed itself.

## Result (`result_json` parsed)

```jsonc
{
  "v": 1,
  "netuid": 11,
  "tempo": 1234,                         // native tempo index; must equal envelope
  "window": { "start_block": 0, "end_block": 360, "start_ts": 0, "end_ts": 4320 },
  "rule_version": "baseline-v1",
  "catalog_version": 1,
  "rails": {                             // constitution; validator pins and compares
    "version": 1,
    "band_bps": 2500,                    // price within ±band of reference median
    "max_move_bps": 1000,                // price moves at most this vs previous tempo
    "concentration_bps": 2000,           // max share of emission value per coldkey
    "bonus_cap_ppm": 200000,             // 20% per-interval bonus cap
    "bonus_budget_ppm": 100000,          // 10% network bonus budget
    "bonus_enabled": false
  },
  "inputs_digest": "<sha256 hex of the frozen settlement inputs>",
  "prices": [
    { "class": "sandbox", "spec": "tdx.c3-4", "status": "live",
      "price_uusd": 280000,              // per reference-unit-hour
      "prev_price_uusd": 280000,         // null on first tempo
      "ref_median_uusd": 280000,
      "sources": [ { "name": "aws", "value_uusd": 270000, "hash": "<sha256>" } ] }
  ],
  "emission": {
    "alpha_budget_rao": 147600000000,    // alpha for miners this tempo (1 alpha = 1e9 rao)
    "alpha_price_uusd": 1490000,         // USD per alpha
    "value_uusd": 219924000              // = alpha_budget_rao * alpha_price_uusd // 1e9
  },
  "bonus": { "base_uusd": 0, "eligible_uusd": 0, "b_eff_ppm": 0 },
  "accounts": [
    { "coldkey": "5C…",
      "opening_uusd": 0,                 // carried penalty balance
      "penalties_uusd": 0,               // deductions finalized this tempo
      "gross_uusd": 0, "net_uusd": 0, "closing_uusd": 0,
      "hotkeys": [
        { "hotkey": "5F…", "uid": 12,    // uid null = unmappable (not registered)
          "supply": [ { "spec": "tdx.c3-4", "muh": 4000, "eligible_muh": 0 } ],
          "orders_uusd": 0,
          "base_uusd": 0, "bonus_uusd": 0, "gross_uusd": 0,
          "alloc_uusd": 0 } ] }
  ],
  "recycle": { "hotkey": "5Owner…", "uid": 0, "alloc_uusd": 0 },
  "weights": [ ["5F…", 12, 31234], ["5Owner…", 0, 34301] ],  // [hotkey, uid, u16]
  "allocation": null,                    // Eleven's allocation slot (v1: always null)
  "exceptions": []                       // e.g. ["zero-emission"], ["rail-fallback:price_band"]
}
```

## Derivation (normative)

Let `P[spec]` be `price_uusd` from `prices`. For each hotkey `h`:

```
base_h        = Σ_s  P[s] * muh_s          // 1000
eligible_h    = Σ_s  P[s] * eligible_muh_s // 1000
```

Network bonus (only if `rails.bonus_enabled`, else `b_eff_ppm = 0` and all `eligible_muh` must be 0):

```
Base     = Σ_h base_h      (standing capacity only)
Eligible = Σ_h eligible_h
b_eff_ppm = 0                                         if Eligible == 0
          = min(bonus_cap_ppm, bonus_budget_ppm * Base // Eligible)   otherwise
bonus_h  = eligible_h * b_eff_ppm // 1_000_000
gross_h  = base_h + bonus_h + orders_uusd_h
```

Per coldkey `c` (all hotkeys of `c` aggregated **before** clipping):

```
G = Σ gross_h ;  net = max(0, G − penalties − opening) ;  closing = max(0, opening + penalties − G)
```

Spread `net` over the coldkey's hotkeys in proportion to gross, **including unmappable
hotkeys in the denominator**; unmappable shares stay unallocated (they recycle):

```
a_h = net * gross_h // G   if uid != null and G > 0   else 0
```

Concentration (cap per coldkey, in uusd of emission value):

```
cap = value_uusd * concentration_bps // 10000
A_c = Σ a_h ;  if A_c > cap:  a_h = a_h * cap // A_c
```

Payout cap (never pay more than the emission value; never more than net):

```
T = Σ all a_h ;  if T > value_uusd:  a_h = a_h * value_uusd // T
alloc_uusd_h = a_h
recycle.alloc_uusd = value_uusd − Σ alloc_uusd_h
```

Weights (u16, total exactly 65535). Entries are every hotkey with `alloc > 0` plus the
recycle hotkey if its alloc > 0. If `value_uusd == 0` the vector is `[[recycle, uid, 65535]]`
and exceptions contain `"zero-emission"`.

```
q_i = alloc_i * 65535 // value_uusd ;  r_i = alloc_i * 65535 % value_uusd
give (65535 − Σ q_i) extra units, one each, by r_i descending, ties by uid ascending
```

`weights` is ordered by uid ascending.

## Rails a validator checks

| Rail | Check |
|---|---|
| Integrity | signature, digest, `v`, netuid, tempo == envelope tempo, every derived field equals the stated field, weights sum to 65535 |
| Monotone | tempo ≥ last applied tempo (anti-replay) |
| Constitution | `rails` equals the validator's pinned rails |
| Catalog only | every `supply.spec` is in `prices` with `status == "live"`; no duplicate specs |
| Price band | `ref_median_uusd` == median of `sources[].value_uusd` (even count: floor of mean of the two middles); `|price − ref| ≤ ref * band_bps // 10000`; if `prev_price_uusd` not null, `|price − prev| ≤ prev * max_move_bps // 10000` |
| Verified supply only | a hotkey with zero `muh` and zero `orders_uusd` has `alloc_uusd == 0` (implied by derivation) |
| No self-payment | no hotkey or coldkey in the validator's pinned team list receives alloc > 0 (recycle hotkey excepted) |
| Concentration | Σ alloc per coldkey ≤ cap |
| Payout cap | Σ alloc ≤ value_uusd and per coldkey Σ alloc ≤ net |
| Ledger continuity | if the validator holds the statement for `tempo − 1`, each coldkey's `opening_uusd` equals that statement's `closing_uusd` (0 if absent) |

## Follow policy

1. `allocation` present and passes → submit it (v1: never present).
2. Baseline (`weights`) passes → submit it.
3. Otherwise resubmit the last vector this validator landed.
4. Otherwise recycle 100% to the pinned owner uid.

Golden vectors: `spec/vectors/*.json` — each file is `{ "name", "input": <result without derived fields>, "expected": <full result> }`.
Both implementations must reproduce `expected` byte-for-byte after canonical JSON.
