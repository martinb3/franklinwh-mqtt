# franklinwh-mqtt

Polls a [FranklinWH](https://www.franklinwh.com/) aGate energy gateway over
its **local TCP endpoint** (no cloud, no internet dependency) and publishes
the readings to MQTT — both as plain retained telemetry topics and,
optionally, as ready-to-render [Awtrix 3](https://blueforcer.github.io/awtrix3/)
custom apps for a pixel clock such as the Ulanzi TC001.

Uses [`franklinwh-local`](https://pypi.org/project/franklinwh-local/), a
community client for the aGate's local protocol. That protocol is reverse
engineered and the library is an alpha release, so this bridge treats every
poll as fallible: fresh connection per poll, hard timeouts, exponential
backoff, and last-known-good values marked `stale` rather than dropped.

Not affiliated with or endorsed by FranklinWH.

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `FWH_HOST` | *(required)* | aGate IP or hostname on your LAN |
| `FWH_SERIAL` | *(required)* | Gateway serial number (FranklinWH app → Settings → Device Info → SN) |
| `FWH_PORT` | `9000` | aGate local TCP port |
| `MQTT_HOST` | *(required)* | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USER` / `MQTT_PASSWORD` | *(required)* | Broker credentials |
| `MQTT_BASE_TOPIC` | `home/franklinwh` | Prefix for telemetry topics |
| `AWTRIX_PREFIX` | *(empty = disabled)* | The clock's MQTT prefix, e.g. `awtrix_a1b2c3` |
| `AWTRIX_APPS` | `soc,solar,load,grid` | Which apps to publish |
| `AWTRIX_ICON_<APP>` | *(none)* | Optional icon ID per app, e.g. `AWTRIX_ICON_SOC=120` |
| `POLL_INTERVAL_SECONDS` | `30` | Seconds between polls |
| `STALE_AFTER_SECONDS` | `180` | Age after which data is flagged stale |
| `LISTEN_PORT` | `8000` | Health endpoint port (`/healthz`, `/readyz`) |
| `LOG_LEVEL` | `INFO` | Python log level |

## Topics published (all retained)

| Topic | Payload |
|---|---|
| `home/franklinwh/state` | Full JSON: `soc`, `battery_soc_each`, `solar_w`, `load_w`, `grid_w`, `battery_w`, `generator_w`, daily `kwh` counters, `ts`, `stale` |
| `home/franklinwh/soc` … `/generator_w` | Individual scalar values |
| `home/franklinwh/status` | `online` / `stale`; MQTT Last Will sets `offline` |
| `<AWTRIX_PREFIX>/custom/fwh_soc` etc. | Awtrix custom-app JSON, e.g. `{"text":"87%"}` |

Sign conventions: `grid_w` positive = importing, negative = exporting;
`battery_w` positive = batteries discharging into the home.

## Running

```sh
pip install -r requirements.txt
FWH_HOST=... FWH_SERIAL=... MQTT_HOST=... MQTT_USER=... MQTT_PASSWORD=... \
  python -m franklinwh_mqtt
```

Container images are published to `ghcr.io/martinb3/franklinwh-mqtt` by the
`Build image` workflow (x86-64 only; the Dockerfile itself is architecture
independent).

## Development

```sh
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```
