"""Configuration from environment. The master hotkey, owner hotkey and the
constitution (rails) are pinned here — never taken from the statement."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_RAILS = {"version": 1, "band_bps": 2500, "max_move_bps": 1000,
                 "concentration_bps": 2000, "bonus_cap_ppm": 200000,
                 "bonus_budget_ppm": 100000}


@dataclass
class Config:
    wallet: str
    hotkey: str
    api: str = "https://provider.trajrl.com"
    master_hotkey: str = ""
    owner_hotkey: str = ""
    netuid: int = 11
    network: str = "finney"
    poll_s: int = 60
    resubmit_blocks: int = 150
    state_file: str = "/var/lib/trajrl/validator-state.json"
    heartbeat_file: str = "/var/lib/trajrl/heartbeat"
    team_keys: set[str] = field(default_factory=set)
    pinned_rails: dict | None = field(default_factory=lambda: dict(DEFAULT_RAILS))
    dry_run: bool = False


def from_env(env: dict[str, str] | None = None) -> Config:
    e = os.environ if env is None else env

    def need(k: str) -> str:
        v = e.get(k, "").strip()
        if not v:
            raise SystemExit(f"missing required env {k}")
        return v

    rails_env = e.get("TRAJRL_PINNED_RAILS", "").strip()
    if rails_env.lower() == "off":
        rails = None
    elif rails_env:
        rails = json.loads(rails_env)
    else:
        rails = dict(DEFAULT_RAILS)
    return Config(
        wallet=need("TRAJRL_WALLET"),
        hotkey=need("TRAJRL_HOTKEY"),
        api=e.get("TRAJRL_API", "https://provider.trajrl.com"),
        master_hotkey=need("TRAJRL_MASTER_HOTKEY"),
        owner_hotkey=need("TRAJRL_OWNER_HOTKEY"),
        netuid=int(e.get("TRAJRL_NETUID", "11")),
        network=e.get("TRAJRL_NETWORK", "finney"),
        poll_s=int(e.get("TRAJRL_POLL_S", "60")),
        resubmit_blocks=int(e.get("TRAJRL_RESUBMIT_BLOCKS", "150")),
        state_file=e.get("TRAJRL_STATE_FILE", "/var/lib/trajrl/validator-state.json"),
        heartbeat_file=e.get("TRAJRL_HEARTBEAT_FILE", "/var/lib/trajrl/heartbeat"),
        team_keys={k.strip() for k in e.get("TRAJRL_TEAM_KEYS", "").split(",") if k.strip()},
        pinned_rails=rails,
        dry_run=e.get("TRAJRL_DRY_RUN", "") in ("1", "true", "yes"),
    )
