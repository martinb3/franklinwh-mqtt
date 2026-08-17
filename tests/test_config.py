import pytest

from franklinwh_mqtt.config import Config, ConfigError

REQUIRED = {
    "FWH_HOST": "gateway.example",
    "FWH_SERIAL": "SERIAL123",
    "MQTT_HOST": "broker.example",
    "MQTT_USER": "user",
    "MQTT_PASSWORD": "pass",
}


def set_env(monkeypatch, extra=None):
    for key, value in {**REQUIRED, **(extra or {})}.items():
        monkeypatch.setenv(key, value)


def test_defaults(monkeypatch):
    set_env(monkeypatch)
    config = Config.from_env()
    assert config.mqtt_port == 1883
    assert config.base_topic == "home/franklinwh"
    assert config.awtrix_prefix == ""
    assert config.awtrix_apps == ("soc", "solar", "load", "grid")
    assert config.poll_interval == 30


def test_missing_required(monkeypatch):
    set_env(monkeypatch)
    monkeypatch.delenv("FWH_SERIAL")
    with pytest.raises(ConfigError, match="FWH_SERIAL"):
        Config.from_env()


def test_app_subset_and_icons(monkeypatch):
    set_env(
        monkeypatch,
        {"AWTRIX_APPS": "soc, solar", "AWTRIX_ICON_SOC": "120", "AWTRIX_PREFIX": "awtrix_abc/"},
    )
    config = Config.from_env()
    assert config.awtrix_apps == ("soc", "solar")
    assert config.awtrix_icons == {"soc": "120"}
    assert config.awtrix_prefix == "awtrix_abc"  # trailing slash stripped


def test_unknown_app_rejected(monkeypatch):
    set_env(monkeypatch, {"AWTRIX_APPS": "soc,frobnicate"})
    with pytest.raises(ConfigError, match="frobnicate"):
        Config.from_env()
