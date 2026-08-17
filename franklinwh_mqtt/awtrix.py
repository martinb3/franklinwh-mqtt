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


def format_power(watts: float, signed: bool = False) -> str:
    """450 -> "450W", 5240 -> "5.2kW"; signed adds +/- for grid flow."""
    sign = ""
    if signed and watts > 0:
        sign = "+"
    if abs(watts) >= 1000:
        return f"{sign}{watts / 1000:.1f}kW"
    return f"{sign}{watts:.0f}W"


def payload_for(app: str, reading: Reading, icon: Optional[str] = None) -> str:
    if app == "soc":
        body: dict = {"text": f"{reading.soc:.0f}%"}
    elif app == "solar":
        body = {"text": format_power(reading.solar_w)}
    elif app == "load":
        body = {"text": format_power(reading.load_w)}
    elif app == "grid":
        body = {"text": format_power(reading.grid_w, signed=True)}
    else:
        raise ValueError(f"unknown awtrix app {app!r}")
    if icon:
        body["icon"] = icon
    return json.dumps(body)
