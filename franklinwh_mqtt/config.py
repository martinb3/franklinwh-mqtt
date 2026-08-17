"""Configuration from environment variables.

Everything is env-driven so no deployment detail (hosts, serials,
credentials) ever needs to live in this repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .awtrix import DEFAULT_DEADBAND_W

KNOWN_APPS = ("soc", "solar", "load", "grid")


class ConfigError(Exception):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"required environment variable {name} is not set")
    return value


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


@dataclass
class Config:
    fwh_host: str
    fwh_serial: str
    fwh_port: int = 9000
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_password: str = ""
    base_topic: str = "home/franklinwh"
    awtrix_prefix: str = ""
    awtrix_apps: tuple[str, ...] = KNOWN_APPS
    awtrix_icons: dict[str, str] = field(default_factory=dict)
    awtrix_deadband_w: float = DEFAULT_DEADBAND_W
    poll_interval: int = 30
    stale_after: int = 180
    listen_port: int = 8000
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        apps_raw = os.environ.get("AWTRIX_APPS", ",".join(KNOWN_APPS))
        apps = tuple(a.strip() for a in apps_raw.split(",") if a.strip())
        unknown = [a for a in apps if a not in KNOWN_APPS]
        if unknown:
            raise ConfigError(
                f"AWTRIX_APPS contains unknown app(s) {unknown}; known: {list(KNOWN_APPS)}"
            )
        # Any AWTRIX_ICON_* variable becomes an icon keyed by its suffix, so
        # state-specific names (AWTRIX_ICON_SOC_CHARGING) work alongside the
        # per-app ones without this needing to know every state up front.
        prefix = "AWTRIX_ICON_"
        icons = {
            key[len(prefix) :].lower(): value.strip()
            for key, value in os.environ.items()
            if key.startswith(prefix) and value.strip()
        }
        return cls(
            fwh_host=_require("FWH_HOST"),
            fwh_serial=_require("FWH_SERIAL"),
            fwh_port=_int("FWH_PORT", 9000),
            mqtt_host=_require("MQTT_HOST"),
            mqtt_port=_int("MQTT_PORT", 1883),
            mqtt_user=_require("MQTT_USER"),
            mqtt_password=_require("MQTT_PASSWORD"),
            base_topic=os.environ.get("MQTT_BASE_TOPIC", "home/franklinwh").strip().rstrip("/"),
            awtrix_prefix=os.environ.get("AWTRIX_PREFIX", "").strip().rstrip("/"),
            awtrix_apps=apps,
            awtrix_icons=icons,
            awtrix_deadband_w=_float("AWTRIX_DEADBAND_W", DEFAULT_DEADBAND_W),
            poll_interval=_int("POLL_INTERVAL_SECONDS", 30),
            stale_after=_int("STALE_AFTER_SECONDS", 180),
            listen_port=_int("LISTEN_PORT", 8000),
            log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
