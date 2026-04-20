"""Profile loader: loads, validates and expands range templates."""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from typing import Any

_LOGGER = logging.getLogger(__name__)

REQUIRED_PROFILE_KEYS = {"name", "device", "transport"}
VALID_PLATFORMS = {"number", "switch", "button", "select"}
VALID_TRANSPORTS = {"osc_udp"}


class ProfileError(Exception):
    """Raised when a profile is invalid."""


def list_builtin_profiles(profiles_dir: str) -> dict[str, str]:
    """Return {display_name: filepath} for all JSON files in profiles_dir."""
    result: dict[str, str] = {}
    if not os.path.isdir(profiles_dir):
        return result
    for fname in sorted(os.listdir(profiles_dir)):
        if fname.endswith(".json"):
            full_path = os.path.join(profiles_dir, fname)
            try:
                with open(full_path, encoding="utf-8") as f:
                    data = json.load(f)
                display = data.get("name", fname.removesuffix(".json"))
            except Exception:
                display = fname.removesuffix(".json")
            result[display] = full_path
    return result


def load_profile(path_or_content: str, *, is_content: bool = False) -> dict[str, Any]:
    """Load, validate and expand a profile. Returns expanded profile dict."""
    if is_content:
        raw = json.loads(path_or_content)
    else:
        with open(path_or_content, encoding="utf-8") as f:
            raw = json.load(f)

    _validate(raw)
    expanded = _expand_entities(raw)
    # Normalize all entities: osc_path -> osc_address
    expanded["entities"] = [normalize_entity(e) for e in expanded.get("entities", [])]
    return expanded


def _validate(profile: dict) -> None:
    missing = REQUIRED_PROFILE_KEYS - set(profile.keys())
    if missing:
        raise ProfileError(f"Profile missing required keys: {missing}")

    transport = profile.get("transport", {})
    t_type = transport.get("type")
    if t_type not in VALID_TRANSPORTS:
        raise ProfileError(f"Unsupported transport type: {t_type!r}. Valid: {VALID_TRANSPORTS}")

    entities = profile.get("entities", [])
    entity_templates = profile.get("entity_templates", [])

    # Comment-only entries (no platform) are allowed and silently ignored
    real_entities = [e for e in entities if e.get("platform")]
    real_templates = [e for e in entity_templates if e.get("platform")]

    if not real_entities and not real_templates:
        raise ProfileError("Profile must define at least one entity or entity_template with a platform.")

    for ent in real_entities:
        plat = ent.get("platform")
        if plat not in VALID_PLATFORMS:
            raise ProfileError(f"Entity {ent.get('name')!r} has unsupported platform: {plat!r}")


def _expand_entities(profile: dict) -> dict:
    """Expand entity_templates with range: into flat entity list."""
    profile = deepcopy(profile)

    # Skip comment-only entries (no platform key)
    expanded: list[dict] = [e for e in profile.get("entities", []) if e.get("platform")]

    for tmpl in profile.get("entity_templates", []):
        if not tmpl.get("platform"):
            continue  # comment entry

        range_cfg = tmpl.get("range")
        if not range_cfg:
            expanded.append(_substitute(tmpl, 1, var=None, pad=0))
            continue

        # Support both our schema (from/to) and generated code (start/end)
        start = range_cfg.get("from", range_cfg.get("start", 1))
        end = range_cfg.get("to", range_cfg.get("end", start))
        pad = range_cfg.get("pad", 0)
        var = range_cfg.get("var")  # named variable e.g. "ch", "n"

        for i in range(start, end + 1):
            entity = _substitute(tmpl, i, var=var, pad=pad)
            entity.pop("range", None)
            expanded.append(entity)

    profile["entities"] = expanded
    profile.pop("entity_templates", None)
    return profile


def _substitute(template: dict, n: int, var: str | None, pad: int) -> dict:
    """Recursively substitute {n}, {ch}, and named {var} placeholders."""
    n_str = str(n).zfill(pad) if pad else str(n)

    def _sub(value: Any) -> Any:
        if isinstance(value, str):
            value = value.replace("{n}", n_str).replace("{ch}", n_str)
            if var:
                value = value.replace(f"{{{var}}}", n_str)
            return value
        if isinstance(value, dict):
            return {k: _sub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_sub(item) for item in value]
        return value

    return _sub(deepcopy(template))


def normalize_entity(entity: dict) -> dict:
    """Alias osc_path -> osc_address and feedback_path -> feedback_address."""
    entity = dict(entity)
    if "osc_path" in entity and "osc_address" not in entity:
        entity["osc_address"] = entity.pop("osc_path")
    if "feedback_path" in entity and "feedback_address" not in entity:
        entity["feedback_address"] = entity.pop("feedback_path")
    return entity
