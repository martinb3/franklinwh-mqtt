import json

import pytest

from franklinwh_mqtt.awtrix import format_power, payload_for
from franklinwh_mqtt.poller import Reading


def reading(**overrides):
    base = dict(
        ts=1000.0,
        soc=49.5263,
        battery_soc_each=[51.9, 52.2],
        solar_w=59.0,
        load_w=6015.0,
        grid_w=18.0,
        battery_w=5935.0,
        generator_w=0.0,
        kwh={},
    )
    base.update(overrides)
    return Reading(**base)


def test_format_power_watts():
    assert format_power(450) == "450W"
    assert format_power(0) == "0W"


def test_format_power_kilowatts():
    assert format_power(5240) == "5.2kW"
    assert format_power(-1500) == "-1.5kW"


def test_format_power_signed_import_export():
    assert format_power(18, signed=True) == "+18W"
    assert format_power(-2300, signed=True) == "-2.3kW"


def test_soc_payload_rounds():
    body = json.loads(payload_for("soc", reading()))
    assert body == {"text": "50%"}


def test_icon_included_when_given():
    body = json.loads(payload_for("solar", reading(), icon="551"))
    assert body == {"text": "59W", "icon": "551"}


def test_unknown_app_raises():
    with pytest.raises(ValueError):
        payload_for("nope", reading())
