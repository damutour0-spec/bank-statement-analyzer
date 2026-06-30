from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "rules.json"
DEFAULT_PROFILE = "enterprise_flow_review"

DEFAULT_RULES: dict[str, Any] = {
    "balance_continuity": {"enabled": True, "tolerance": "0.02"},
    "duplicates": {"enabled": True},
    "low_confidence": {"enabled": True, "threshold": 0.8},
    "sensitive_keywords": {
        "enabled": True,
        "keywords": ["借款", "还款", "贷款", "网贷", "博彩", "担保", "保证金", "代偿", "逾期", "法院", "执行"],
    },
    "large_round_amount": {"enabled": True, "min_amount": "10000", "round_base": "10000"},
    "same_day_in_out": {"enabled": True, "min_income": "50000", "expense_income_ratio": "0.8"},
    "counterparty_concentration": {"enabled": True, "max_ratio": "0.5"},
}

DEFAULT_CONFIG: dict[str, Any] = {
    "default_profile": DEFAULT_PROFILE,
    "profiles": {
        DEFAULT_PROFILE: DEFAULT_RULES,
    },
}


def load_rule_config(path: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    config_path = path or env_path() or DEFAULT_CONFIG_PATH
    config = read_config(config_path)
    profile_name = profile or os.getenv("RULE_PROFILE") or config.get("default_profile") or DEFAULT_PROFILE
    return resolve_profile(config, profile_name)


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_CONFIG)
    return data


def resolve_profile(config: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    selected = profiles.get(profile) if isinstance(profiles.get(profile), dict) else {}
    merged = deep_merge(copy.deepcopy(DEFAULT_RULES), selected)
    merged["_profile"] = profile
    return merged


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def env_path() -> Path | None:
    raw = os.getenv("RULE_CONFIG_PATH")
    return Path(raw) if raw else None
