import json

import pytest

from franklinwh_mqtt.awtrix import format_power, icon_for, payload_for
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


@pytest.mark.parametrize("watts", [-2.0, -1.0, -0.4, 0.0, 1.0, 2.0])
def test_deadband_collapses_noise_in_both_directions(watts):
    assert json.loads(payload_for("solar", reading(solar_w=watts)))["text"] == "0W"
    assert json.loads(payload_for("load", reading(load_w=watts)))["text"] == "0W"
    assert json.loads(payload_for("grid", reading(grid_w=watts)))["text"] == "0W"


@pytest.mark.parametrize("watts,expected", [(3.0, "3W"), (-3.0, "-3W")])
def test_just_outside_deadband_passes_through(watts, expected):
    assert json.loads(payload_for("solar", reading(solar_w=watts)))["text"] == expected


def test_real_values_untouched():
    assert json.loads(payload_for("solar", reading(solar_w=4300.0)))["text"] == "4.3kW"
    # Export to the grid is genuinely negative and must survive the deadband.
    assert json.loads(payload_for("grid", reading(grid_w=-2300.0)))["text"] == "-2.3kW"


def test_deadband_is_configurable():
    assert json.loads(payload_for("solar", reading(solar_w=8.0), deadband=10))["text"] == "0W"
    assert json.loads(payload_for("solar", reading(solar_w=8.0), deadband=0))["text"] == "8W"


def test_soc_percentage_is_not_deadbanded():
    # SOC is a percentage, not a power reading; 1% must not become 0%.
    assert json.loads(payload_for("soc", reading(soc=1.0)))["text"] == "1%"


def test_icon_included_when_given():
    body = json.loads(payload_for("solar", reading(), icon="551"))
    assert body == {"text": "59W", "icon": "551"}


ICONS = {
    "soc": "plain",
    "soc_charging": "green",
    "soc_discharging": "amber",
    "solar": "sun",
}


def test_icon_shows_charging_when_battery_power_negative():
    assert icon_for("soc", reading(battery_w=-1500.0), ICONS) == "green"


def test_icon_shows_discharging_when_battery_power_positive():
    assert icon_for("soc", reading(battery_w=2200.0), ICONS) == "amber"


@pytest.mark.parametrize("watts", [0.0, -1.0, -27.0, -53.0, -54.0, -99.0, 60.0])
def test_standby_draw_is_not_charging(watts):
    """Two idle aPower units pull ~55W for their own electronics.

    Observed on real hardware: p_fhp sat at -53W for minutes while SOC and
    the gateway's cumulative charge counter never moved. That must read as
    idle, not as a charge cycle.
    """
    assert icon_for("soc", reading(battery_w=watts), ICONS) == "plain"


def test_threshold_boundary_is_inclusive():
    assert icon_for("soc", reading(battery_w=-100.0), ICONS) == "green"
    assert icon_for("soc", reading(battery_w=100.0), ICONS) == "amber"


def test_charge_threshold_is_configurable():
    assert icon_for("soc", reading(battery_w=-60.0), ICONS, charge_threshold=50) == "green"


def test_icon_falls_back_when_state_icons_absent():
    assert icon_for("soc", reading(battery_w=-1500.0), {"soc": "plain"}) == "plain"


def test_icon_for_other_apps_unaffected_by_battery():
    assert icon_for("solar", reading(battery_w=-1500.0), ICONS) == "sun"


def test_unknown_app_raises():
    with pytest.raises(ValueError):
        payload_for("nope", reading())
