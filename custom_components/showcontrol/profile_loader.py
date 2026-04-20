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
VALID_OSC_ARG_TEMPLATES = {"float", "int", "scaled_255"}


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
            except Exception:  # noqa: BLE001
                display = fname.removesuffix(".json")
            result[display] = full_path
    return result


def load_profile(path_or_content: str, *, is_content: bool = False) -> dict[str, Any]:
    """Load and validate a profile. Returns expanded profile dict."""
    if is_content:
        raw = json.loads(path_or_content)
    else:
        with open(path_or_content, encoding="utf-8") as f:
            raw = json.load(f)

    _validate(raw)
    return _expand_entities(raw)


def _validate(profile: dict) -> None:
    """Validate profile structure and all entity/template definitions."""
    missing = REQUIRED_PROFILE_KEYS - set(profile.keys())
    if missing:
        raise ProfileError(f"Profile missing required keys: {missing}")

    transport = profile.get("transport", {})
    t_type = transport.get("type")
    if t_type not in VALID_TRANSPORTS:
        raise ProfileError(
            f"Unsupported transport type: {t_type!r}. Valid: {VALID_TRANSPORTS}"
        )

    entities = profile.get("entities", [])
    templates = profile.get("entity_templates", [])

    if not entities and not templates:
        raise ProfileError("Profile must define at least one entity or entity_template.")

    # Validate flat entities
    for ent in entities:
        _validate_entity_def(ent, context="entities")

    # FIX: also validate entity_templates before expansion
    for tmpl in templates:
        _validate_entity_def(tmpl, context="entity_templates")


def _validate_entity_def(ent: dict, context: str = "") -> None:
    """Validate a single entity or template definition."""
    name = ent.get("name", "<unnamed>")
    plat = ent.get("platform")
    if plat not in VALID_PLATFORMS:
        raise ProfileError(
            f"[{context}] Entity {name!r} has unsupported platform: {plat!r}. "
            f"Valid: {VALID_PLATFORMS}"
        )
    if not ent.get("osc_address"):
        raise ProfileError(f"[{context}] Entity {name!r} is missing 'osc_address'.")

    # FIX: validate osc_arg_template if present
    tmpl_val = ent.get("osc_arg_template")
    if tmpl_val is not None and tmpl_val not in VALID_OSC_ARG_TEMPLATES:
        raise ProfileError(
            f"[{context}] Entity {name!r} has unknown osc_arg_template: {tmpl_val!r}. "
            f"Valid: {VALID_OSC_ARG_TEMPLATES}"
        )


def _expand_entities(profile: dict) -> dict:
    """Expand entity_templates with range: into flat entity list."""
    profile = deepcopy(profile)
    expanded: list[dict] = list(profile.get("entities", []))

    for tmpl in profile.get("entity_templates", []):
        range_cfg = tmpl.get("range")
        if not range_cfg:
            expanded.append(_substitute(tmpl, 1))
            continue

        start = range_cfg.get("start", 1)
        end = range_cfg.get("end", start)
        pad = range_cfg.get("pad", 0)

        for n in range(start, end + 1):
            entity = _substitute(tmpl, n, ch=n, pad=pad)
            entity.pop("range", None)
            expanded.append(entity)

    profile["entities"] = expanded
    profile.pop("entity_templates", None)
    return profile


def _substitute(template: dict, n: int, ch: int | None = None, pad: int = 0) -> dict:
    """Recursively substitute {n}, {ch} placeholders."""
    if ch is None:
        ch = n

    n_str = str(n).zfill(pad) if pad else str(n)
    ch_str = str(ch).zfill(pad) if pad else str(ch)

    def _sub(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("{n}", n_str).replace("{ch}", ch_str)
        if isinstance(value, dict):
            return {k: _sub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_sub(i) for i in value]
        return value

    return _sub(deepcopy(template))
