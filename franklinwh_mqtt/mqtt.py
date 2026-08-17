"""MQTT publishing: raw telemetry topics plus optional Awtrix apps.

All state topics are retained so any consumer (the Awtrix clock after a
reboot, a future Home Assistant) immediately sees the latest values. The
broker's Last Will flips the status topic to "offline" if this process
disappears without unpublishing.
"""

from __future__ import annotations

import logging

import paho.mqtt.client as paho

from .awtrix import APP_TOPIC, icon_for, payload_for
from .config import Config
from .poller import Reading

log = logging.getLogger(__name__)

SCALAR_FIELDS = ("soc", "solar_w", "load_w", "grid_w", "battery_w", "generator_w")


class Publisher:
    def __init__(self, config: Config, on_connection_change=None):
        self._config = config
        self._on_connection_change = on_connection_change
        self.connected = False

        self._client = paho.Client(
            callback_api_version=paho.CallbackAPIVersion.VERSION2,
            client_id="franklinwh-mqtt",
        )
        self._client.username_pw_set(config.mqtt_user, config.mqtt_password)
        self._client.will_set(self.status_topic, "offline", retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect

    @property
    def status_topic(self) -> str:
        return f"{self._config.base_topic}/status"

    def start(self) -> None:
        # connect_async + loop_start: paho owns reconnection in its network
        # thread, so a broker restart never blocks the poll loop.
        self._client.connect_async(self._config.mqtt_host, self._config.mqtt_port)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.publish(self.status_topic, "offline", retain=True)
        self._client.loop_stop()
        self._client.disconnect()

    def _handle_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            log.error("MQTT connect refused: %s", reason_code)
            return
        log.info("MQTT connected")
        self.connected = True
        if self._on_connection_change:
            self._on_connection_change(True)

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected: %s", reason_code)
        self.connected = False
        if self._on_connection_change:
            self._on_connection_change(False)

    def publish_reading(self, reading: Reading, stale: bool) -> None:
        base = self._config.base_topic
        state = reading.as_dict(stale)
        self._publish(f"{base}/state", _json(state))
        for name in SCALAR_FIELDS:
            self._publish(f"{base}/{name}", str(state[name]))
        self._publish(self.status_topic, "stale" if stale else "online")

        if self._config.awtrix_prefix:
            for app in self._config.awtrix_apps:
                topic = APP_TOPIC.format(prefix=self._config.awtrix_prefix, app=app)
                deadband = self._config.awtrix_deadband_w
                icon = icon_for(
                    app,
                    reading,
                    self._config.awtrix_icons,
                    charge_threshold=self._config.awtrix_charge_threshold_w,
                )
                self._publish(
                    topic, payload_for(app, reading, icon, deadband=deadband)
                )

    def publish_status(self, status: str) -> None:
        self._publish(self.status_topic, status)

    def remove_awtrix_app(self, app: str) -> None:
        if self._config.awtrix_prefix:
            topic = APP_TOPIC.format(prefix=self._config.awtrix_prefix, app=app)
            self._publish(topic, "")

    def _publish(self, topic: str, payload: str) -> None:
        result = self._client.publish(topic, payload, retain=True)
        if result.rc != paho.MQTT_ERR_SUCCESS:
            log.debug("publish to %s queued/failed rc=%s", topic, result.rc)


def _json(obj) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"))
