# TrajRL · SN11

SN11 is confidential infrastructure for recursive self-improvement on Bittensor (see `docs/about.md`).
This repository holds the subnet's design, the allocation statement spec, and the **validator**.

| Path | What |
|---|---|
| `docs/about.md`, `docs/incentive-mechanism.md` | Strategy and target mechanism (2026-11-09) |
| `docs/v1-implementation.md` | What v1 actually implements, and how it maps to the mechanism |
| `docs/validator.md` | Running a validator |
| `spec/statement-v1.md` | The signed allocation statement: format, normative derivation, rails |
| `spec/vectors/` | Golden vectors shared with the TypeScript settlement (`trajrl-provider`) |
| `trajrl_validator/` | The validator |
| `scripts/gen_vectors.py` | Regenerates the vectors from the reference derivation |

## v1 in one paragraph

Settlement is **deterministic and verifiable**. The provider site (`trajrl-provider`) prices each catalog spec, computes every
coldkey's contribution, penalties and carried debt, caps payout at the value of verified supply,
recycles the rest to the owner hotkey, and signs one statement per native tempo with the master key.
Validators **verify** it independently. They check the master signature, **re-derive every number** from the statement's
own line items with integer math, check the rails against values they pin locally, and submit the
weights. If anything fails, they keep the last vector they landed (or recycle 100% to the owner).
Eleven's agent allocation has a slot in the statement (`allocation`), empty in v1.

## Validator quick start

```bash
uv venv && uv pip install -e '.[chain,dev]'
pytest                                   # 60 tests, includes the shared golden vectors

export TRAJRL_WALLET=my-wallet TRAJRL_HOTKEY=my-hotkey
export TRAJRL_MASTER_HOTKEY=5…                          # pinned, published with the launch
export TRAJRL_OWNER_HOTKEY=5ECzcM7sixWNEeD6RbpeEHW1YcYMFejwHuvDBgQxVSjGyrMS   # SN11's owner on chain
export TRAJRL_API=https://provider.trajrl.com
trajrl-validator --once --dry-run        # verify + re-derive + log the vector, no chain write
trajrl-validator                         # run
```

Or with Docker: `docker compose -f docker/docker-compose.validator.yml up -d`. Details in `docs/validator.md`.

## Check any statement yourself

```bash
curl -s https://provider.trajrl.com/api/subnet/v1/tempo/1234 > t.json
curl -s https://provider.trajrl.com/api/subnet/v1/tempo/1233 > prev.json
TRAJRL_MASTER_HOTKEY=5… python -m trajrl_validator.verify t.json --prev prev.json
```
