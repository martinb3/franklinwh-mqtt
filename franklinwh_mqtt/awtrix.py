"""Format readings as Awtrix 3 custom-app payloads.

Awtrix 3 renders anything published (retained) to
``<prefix>/custom/<appname>`` as a page in its app rotation. Publishing
an empty payload to the same topic removes the app.
"""

from __future__ import annotations

import json
from typing import Optional

from .poller import Reading

# App name on the clock is namespaced so future non-FranklinWH apps
# (weather, planes, ...) can coexist in the rotation.
APP_TOPIC = "{prefix}/custom/fwh_{app}"

# Watts at or below this magnitude display as zero. See apply_deadband.
DEFAULT_DEADBAND_W = 2.0


def apply_deadband(watts: float, deadband: float) -> float:
    """Collapse sensor noise around zero to exactly zero.

    The gateway idles at a watt or two in either direction — solar reading
    -1W after dark, grid reading +3W with nothing happening. Below the
    deadband there is no signal worth showing, and a flickering sign is
    worse than a steady 0. Anything larger passes through untouched, so a
    genuine anomaly (negative solar in daylight) stays visible.
    """
    return 0.0 if abs(watts) <= deadband else watts


def format_power(watts: float, signed: bool = False) -> str:
    """450 -> "450W", 5240 -> "5.2kW"; signed adds +/- for grid flow."""
    sign = ""
    if signed and watts > 0:
        sign = "+"
    if abs(watts) >= 1000:
        return f"{sign}{watts / 1000:.1f}kW"
    return f"{sign}{watts:.0f}W"


def icon_for(
    app: str,
    reading: Reading,
    icons: dict,
    deadband: float = DEFAULT_DEADBAND_W,
) -> Optional[str]:
    """Pick an app's icon, varying the battery icon by charge direction.

    battery_w is positive while the batteries discharge into the house and
    negative while they charge. Falls back to the plain icon whenever a
    direction-specific one was not configured.
    """
    if app == "soc":
        flow = apply_deadband(reading.battery_w, deadband)
        if flow < 0 and icons.get("soc_charging"):
            return icons["soc_charging"]
        if flow > 0 and icons.get("soc_discharging"):
            return icons["soc_discharging"]
    return icons.get(app)


def payload_for(
    app: str,
    reading: Reading,
    icon: Optional[str] = None,
    deadband: float = DEFAULT_DEADBAND_W,
) -> str:
    """Render one app's payload. Deadband applies to display only — the raw
    values still go out on the telemetry topics untouched."""
    if app == "soc":
        body: dict = {"text": f"{reading.soc:.0f}%"}
    elif app == "solar":
        body = {"text": format_power(apply_deadband(reading.solar_w, deadband))}
    elif app == "load":
        body = {"text": format_power(apply_deadband(reading.load_w, deadband))}
    elif app == "grid":
        body = {
            "text": format_power(apply_deadband(reading.grid_w, deadband), signed=True)
        }
    else:
        raise ValueError(f"unknown awtrix app {app!r}")
    if icon:
        body["icon"] = icon
    return json.dumps(body)
