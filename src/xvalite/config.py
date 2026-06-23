"""Local user-settings persistence (JSON).

Stores UI preferences (range mode, volume, which panels are shown, last
input/output device) so they survive across launches. Saved to
``%APPDATA%/XVALite/config.json`` on Windows, else ``~/.config/XVALite``.

Loading is defensive: a missing/corrupt file falls back to DEFAULTS, and
unknown keys are ignored, so the app never fails to start over settings.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict

APP_DIR_NAME = "XVALite"
CONFIG_FILENAME = "config.json"

DEFAULTS: Dict[str, Any] = {
    "range_mode": "normal",          # "normal" (≤880 Hz) | "extended" (≤2100 Hz)
    "volume_pct": 10,                # file-playback volume
    "panels": {                      # which plot panes are visible
        "pitch": True,
        "formants": True,
        "oscilloscope": False,
        "spectrum": False,
        "narrowband": True,
        "wideband": False,
    },
    "peak_hold": True,               # spectrum view peak-hold trace
    "language": None,                # "ja" | "en"; None → resolve from system locale
    "input_device": None,            # combo label of the chosen device, or None
    "output_device": None,
}


def config_dir() -> str:
    # Tests/tools can redirect storage so they never touch the user's config.
    override = os.environ.get("XVALITE_CONFIG_DIR")
    if override:
        return override
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_DIR_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_FILENAME)


def load_config() -> Dict[str, Any]:
    """Return saved settings merged over DEFAULTS (never raises)."""
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(config_path(), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(saved, dict):
        return cfg
    for key, default in DEFAULTS.items():
        if key not in saved:
            continue
        if isinstance(default, dict) and isinstance(saved[key], dict):
            merged = dict(default)
            merged.update({k: v for k, v in saved[key].items() if k in default})
            cfg[key] = merged
        else:
            cfg[key] = saved[key]
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Write settings to disk (best-effort; ignores I/O errors)."""
    try:
        os.makedirs(config_dir(), exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
