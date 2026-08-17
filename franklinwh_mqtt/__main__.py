"""Entrypoint: python -m franklinwh_mqtt"""

from __future__ import annotations

import logging
import signal
import sys
import time

from .config import KNOWN_APPS, Config, ConfigError
from .health import Health, serve
from .mqtt import Publisher
from .poller import Poller

log = logging.getLogger("franklinwh_mqtt")


def main() -> int:
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Deliberately never log the gateway serial or MQTT password.
    log.info(
        "starting: gateway %s:%d -> mqtt %s:%d base=%s awtrix=%s apps=%s every %ds",
        config.fwh_host,
        config.fwh_port,
        config.mqtt_host,
        config.mqtt_port,
        config.base_topic,
        config.awtrix_prefix or "(disabled)",
        ",".join(config.awtrix_apps),
        config.poll_interval,
    )

    health = Health(liveness_window=max(config.poll_interval, 60) * 3)
    serve(health, config.listen_port)

    publisher = Publisher(
        config, on_connection_change=lambda up: setattr(health, "mqtt_connected", up)
    )
    publisher.start()

    # Retained apps persist on the broker, so explicitly unpublish any app
    # that has been removed from AWTRIX_APPS since a previous deployment.
    for app in KNOWN_APPS:
        if app not in config.awtrix_apps:
            publisher.remove_awtrix_app(app)

    poller = Poller(config.fwh_host, config.fwh_serial, config.fwh_port)

    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        health.beat()
        reading = poller.poll_once()
        if reading is not None:
            publisher.publish_reading(reading, stale=False)
            delay = config.poll_interval
        else:
            stale = poller.is_stale(config.stale_after)
            if poller.last_good is not None:
                # Keep the clock showing last-known-good values; a frozen
                # number beats a blank display. The stale flag tells other
                # consumers not to trust it.
                publisher.publish_reading(poller.last_good, stale=stale)
            elif stale:
                publisher.publish_status("stale")
            delay = poller.retry_delay

        deadline = time.monotonic() + delay
        while running and time.monotonic() < deadline:
            health.beat()
            time.sleep(1)

    log.info("shutting down")
    publisher.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
