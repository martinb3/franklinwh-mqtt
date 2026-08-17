"""Tiny stdlib health server for Kubernetes probes.

/healthz — the poll loop has run recently (process not wedged).
/readyz  — the MQTT connection is currently up.
"""

from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class Health:
    def __init__(self, liveness_window: float):
        self._liveness_window = liveness_window
        self._last_loop = time.monotonic()
        self.mqtt_connected = False

    def beat(self) -> None:
        self._last_loop = time.monotonic()

    @property
    def alive(self) -> bool:
        return (time.monotonic() - self._last_loop) < self._liveness_window


def serve(health: Health, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            if self.path == "/healthz":
                ok = health.alive
            elif self.path == "/readyz":
                ok = health.mqtt_connected
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n" if ok else b"unhealthy\n")

        def log_message(self, fmt, *args):  # probes are noisy; keep quiet
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="health", daemon=True)
    thread.start()
    log.info("health server listening on :%d", port)
    return server
