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
| `AWTRIX_APPS` | `soc,solar,load,grid,battery` | Which apps to publish. `soc` is the battery level; `battery` is its charge/discharge rate |
| `AWTRIX_ICON_<APP>` | *(none)* | Optional icon per app, e.g. `AWTRIX_ICON_SOC=fwh_soc` |
| `AWTRIX_ICON_SOC_CHARGING` / `..._DISCHARGING` | *(none)* | Battery-level icon swapped by charge direction; falls back to `AWTRIX_ICON_SOC` |
| `AWTRIX_ICON_BATTERY_CHARGING` / `..._DISCHARGING` | *(none)* | Same, for the battery-rate app; falls back to `AWTRIX_ICON_BATTERY` |
| `AWTRIX_DEADBAND_W` | `100` | Displayed watts below this magnitude show as an unsigned `0.0kW`. Matches the 0.1kW display granularity, so sensor noise and the batteries' ~55W standby draw never get a misleading sign. Telemetry topics keep the raw value. `0` disables. |
| `AWTRIX_CHARGE_THRESHOLD_W` | `100` | Battery power must exceed this before the icon reports charging or discharging. Must clear the battery system's standby draw — each aPower unit pulls ~25-30W for its own electronics even when idle. |
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
| `<AWTRIX_PREFIX>/custom/fwh_{soc,solar,load,grid,battery}` | Awtrix custom-app JSON, e.g. `{"text":"87%","icon":"fwh_soc"}` |

Sign conventions in the data: `grid_w` positive = importing, negative =
exporting; `battery_w` positive = batteries discharging into the home.

## How values are displayed

The telemetry topics always carry raw gateway values. These rules apply only
to what is rendered on the clock, where a 32x8 matrix leaves about six
characters beside an icon:

- **Always kW**, one decimal. A consistent unit reads faster than one that
  changes scale, and it bounds the string length. Display granularity is
  therefore 0.1kW.
- **Sources are signed**: the grid and battery apps show `+` when supplying
  the house and `-` when absorbing it (importing/exporting, discharging/
  charging). Solar and load are unsigned, since their direction is fixed.
- **Zero is never signed.** The sign is decided on the rounded value, so a
  39W flow shows `0.0kW`, not `+0.0kW`.
- **Below `AWTRIX_DEADBAND_W` reads as zero.** The default 100W matches the
  0.1kW granularity, and is deliberately above the ~55W an idle two-unit
  battery system draws for its own electronics — otherwise standby draw
  displays as a charge.
- **The battery icon follows direction**, not the number: green charging,
  amber discharging, grey idle, using `AWTRIX_CHARGE_THRESHOLD_W`. Keep that
  threshold and the deadband equal, or the icon and the number will disagree
  near the boundary.

## Running

```sh
pip install -r requirements.txt
FWH_HOST=... FWH_SERIAL=... MQTT_HOST=... MQTT_USER=... MQTT_PASSWORD=... \
  python -m franklinwh_mqtt
```

Container images are published to `ghcr.io/martinb3/franklinwh-mqtt` by the
`Build image` workflow (x86-64 only; the Dockerfile itself is architecture
independent).

## Icons

`icons/` holds an 8x8 icon per app (battery, sun, house, transmission pylon)
plus the script that draws them. Icons live only on the clock's flash, so a
re-flash with "erase" wipes them; regenerate and re-upload with:

```sh
python icons/generate_icons.py --out icons/ --upload <clock-host>
```

Then point the bridge at them with `AWTRIX_ICON_SOC=fwh_soc`,
`AWTRIX_ICON_SOLAR=fwh_solar`, and so on (Awtrix references an icon by
filename without its extension).

## Development

```sh
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```
