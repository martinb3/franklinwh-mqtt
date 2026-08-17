"""Poll the FranklinWH aGate local TCP endpoint.

The local protocol is reverse engineered (franklinwh-local is an alpha
release), so every poll assumes the worst: a fresh connection per cycle,
a hard timeout, and any exception treated as a failed poll rather than a
crash. A new LocalClient per poll also means a wedged TCP session from a
previous cycle can never poison the next one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from franklinwh_local import LocalClient

log = logging.getLogger(__name__)

# dataArea keys that must exist for a poll to count as a success.
_REQUIRED_KEYS = ("soc", "p_sun", "p_load", "p_uti")


@dataclass
class Reading:
    """One successful, normalized poll of the gateway."""

    ts: float
    soc: float
    battery_soc_each: list[float]
    solar_w: float
    load_w: float
    grid_w: float
    battery_w: float
    generator_w: float
    kwh: dict[str, float] = field(default_factory=dict)

    def as_dict(self, stale: bool) -> dict:
        return {
            "ts": int(self.ts),
            "stale": stale,
            "soc": round(self.soc, 1),
            "battery_soc_each": [round(s, 1) for s in self.battery_soc_each],
            "solar_w": self.solar_w,
            "load_w": self.load_w,
            "grid_w": self.grid_w,
            "battery_w": self.battery_w,
            "generator_w": self.generator_w,
            "kwh": {k: round(v, 3) for k, v in self.kwh.items()},
        }


def _normalize(data: dict, now: float) -> Reading:
    return Reading(
        ts=now,
        soc=float(data["soc"]),
        battery_soc_each=[float(s) for s in data.get("fhpSoc", [])],
        solar_w=float(data["p_sun"]),
        load_w=float(data["p_load"]),
        # Positive = importing from grid; negative = exporting.
        grid_w=float(data["p_uti"]),
        # Positive = batteries discharging into the home.
        battery_w=float(data.get("p_fhp", 0.0)),
        generator_w=float(data.get("p_gen", 0.0)),
        kwh={
            "solar": float(data.get("kwh_sun", 0.0)),
            "load": float(data.get("kwh_load", 0.0)),
            "grid_in": float(data.get("kwh_uti_in", 0.0)),
            "grid_out": float(data.get("kwh_uti_out", 0.0)),
            "battery_charge": float(data.get("kwh_fhp_chg", 0.0)),
            "battery_discharge": float(data.get("kwh_fhp_di", 0.0)),
            "generator": float(data.get("kwh_gen", 0.0)),
        },
    )


class Poller:
    """Polls the gateway, remembering the last good reading."""

    BACKOFF_INITIAL = 5
    BACKOFF_MAX = 60

    def __init__(self, host: str, serial: str, port: int = 9000, timeout: float = 10.0):
        self._host = host
        self._serial = serial
        self._port = port
        self._timeout = timeout
        self._backoff = self.BACKOFF_INITIAL
        self.last_good: Optional[Reading] = None
        self.consecutive_failures = 0

    def poll_once(self) -> Optional[Reading]:
        """Return a fresh Reading, or None on failure (backoff advances)."""
        try:
            with LocalClient(
                equip_no=self._serial,
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            ) as client:
                response = client.query_device_detail()
        except Exception as exc:  # alpha protocol: anything can happen
            self._record_failure(f"{type(exc).__name__}: {exc}")
            return None

        data = response.get("dataArea") if isinstance(response, dict) else None
        if not isinstance(data, dict) or any(k not in data for k in _REQUIRED_KEYS):
            self._record_failure("response missing expected dataArea fields")
            return None

        try:
            reading = _normalize(data, time.time())
        except (TypeError, ValueError, KeyError) as exc:
            self._record_failure(f"could not normalize response: {exc}")
            return None

        if self.consecutive_failures:
            log.info("gateway poll recovered after %d failures", self.consecutive_failures)
        self.consecutive_failures = 0
        self._backoff = self.BACKOFF_INITIAL
        self.last_good = reading
        return reading

    def _record_failure(self, reason: str) -> None:
        self.consecutive_failures += 1
        log.warning(
            "gateway poll failed (%d consecutive): %s", self.consecutive_failures, reason
        )
        self._backoff = min(self._backoff * 2, self.BACKOFF_MAX)

    @property
    def retry_delay(self) -> int:
        """Seconds to wait after a failed poll."""
        return self._backoff

    def is_stale(self, stale_after: int) -> bool:
        if self.last_good is None:
            return True
        return (time.time() - self.last_good.ts) > stale_after
