from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "rules.json"


DEFAULT_RULE_CONFIG: dict[str, Any] = {
    "balance_continuity": {"enabled": True, "tolerance": "0.02"},
    "duplicates": {"enabled": True},
    "low_confidence": {"enabled": True, "threshold": 0.8},
    "sensitive_keywords": {
        "enabled": True,
        "keywords": ["借款", "还款", "贷款", "网贷", "担保", "保证金"],
    },
    "large_round_amount": {"enabled": True, "min_amount": "10000", "round_base": "10000"},
    "same_day_in_out": {"enabled": True, "min_income": "50000", "expense_income_ratio": "0.8"},
    "counterparty_concentration": {"enabled": True, "max_ratio": "0.5"},
}


def load_rule_config(profile: str | None = None) -> dict[str, Any]:
    path = Path(os.getenv("RULE_CONFIG_PATH", str(CONFIG_PATH)))
    raw = load_raw_config(path)
    selected_profile = profile or os.getenv("RULE_PROFILE") or raw.get("default_profile") or "enterprise_flow_review"
    return resolve_profile(raw, selected_profile)


def load_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"profiles": {"enterprise_flow_review": DEFAULT_RULE_CONFIG}}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_profile(raw: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = raw.get("profiles", {})
    config = deepcopy(DEFAULT_RULE_CONFIG)
    deep_update(config, profiles.get(profile, {}))
    config["_profile"] = profile
    return config


def deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base
