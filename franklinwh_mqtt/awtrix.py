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

# Battery power below this magnitude is not treated as a charge or discharge.
# It has to clear the battery system's own standby draw: each aPower unit
# pulls roughly 25-30W for its electronics, so a two-unit system idles near
# -55W while the cells sit untouched — the gateway's cumulative charge counter
# does not move and SOC does not budge. A threshold below that draw would
# report "charging" all night.
DEFAULT_CHARGE_THRESHOLD_W = 100.0


def apply_deadband(watts: float, deadband: float) -> float:
    """Collapse sensor noise around zero to exactly zero.

    The gateway idles at a watt or two in either direction — solar reading
    -1W after dark, grid reading +3W with nothing happening. Below the
    deadband there is no signal worth showing, and a flickering sign is
    worse than a steady 0. Anything larger passes through untouched, so a
    genuine anomaly (negative solar in daylight) stays visible.
    """
    return 0.0 if abs(watts) <= deadband else watts


def format_power(watts: float) -> str:
    """618 -> "0.6kW", 5240 -> "5.2kW", -2300 -> "-2.3kW".

    Always kW, never bare watts: one consistent unit is quicker to read at a
    glance than a number whose scale you have to check first, and it keeps
    the string short enough to avoid scrolling on a 32x8 matrix.

    Import is the ordinary state for this system, so it reads as a bare
    number like every other app. Only a negative sign is worth the pixels:
    it means power is flowing the unusual way, out to the grid.
    """
    kw = round(watts / 1000, 1)
    # Anything under 50W rounds to zero; render that as plain "0.0kW" rather
    # than letting a small negative print as "-0.0kW".
    if kw == 0:
        kw = 0.0
    return f"{kw:.1f}kW"


def icon_for(
    app: str,
    reading: Reading,
    icons: dict,
    charge_threshold: float = DEFAULT_CHARGE_THRESHOLD_W,
) -> Optional[str]:
    """Pick an app's icon, varying the battery icon by charge direction.

    battery_w is positive while the batteries discharge into the house and
    negative while they charge, but small negative values are just the
    system's standby draw (see DEFAULT_CHARGE_THRESHOLD_W), so the reading
    has to clear a threshold before it counts as either direction. Falls back
    to the plain icon whenever a direction-specific one was not configured.
    """
    if app == "soc":
        flow = reading.battery_w
        if flow <= -charge_threshold and icons.get("soc_charging"):
            return icons["soc_charging"]
        if flow >= charge_threshold and icons.get("soc_discharging"):
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
        body = {"text": format_power(apply_deadband(reading.grid_w, deadband))}
    else:
        raise ValueError(f"unknown awtrix app {app!r}")
    if icon:
        body["icon"] = icon
    return json.dumps(body)
