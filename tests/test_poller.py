import time
from unittest import mock

from franklinwh_mqtt.poller import Poller, _normalize

DATA = {
    "soc": 49.5263,
    "fhpSoc": [51.9, 52.2],
    "p_sun": 59,
    "p_load": 6015,
    "p_uti": 18,
    "p_fhp": 5935,
    "p_gen": 0,
    "kwh_sun": 54.62,
    "kwh_load": 59.02,
    "kwh_uti_in": 14.47,
    "kwh_uti_out": 0.41,
    "kwh_fhp_chg": 21.43,
    "kwh_fhp_di": 11.77,
    "kwh_gen": 0,
}


def test_normalize_maps_fields():
    reading = _normalize(DATA, now=1234.0)
    assert reading.soc == 49.5263
    assert reading.solar_w == 59.0
    assert reading.load_w == 6015.0
    assert reading.grid_w == 18.0
    assert reading.battery_w == 5935.0
    assert reading.kwh["grid_out"] == 0.41
    state = reading.as_dict(stale=False)
    assert state["soc"] == 49.5
    assert state["stale"] is False


def _poller_with_response(response):
    poller = Poller("host", "serial")
    client = mock.MagicMock()
    client.__enter__.return_value.query_device_detail.return_value = response
    with mock.patch("franklinwh_mqtt.poller.LocalClient", return_value=client):
        return poller, poller.poll_once()


def test_poll_success_resets_backoff():
    poller, reading = _poller_with_response({"dataArea": DATA})
    assert reading is not None
    assert poller.last_good is reading
    assert poller.consecutive_failures == 0
    assert poller.retry_delay == Poller.BACKOFF_INITIAL


def test_poll_missing_fields_is_failure():
    poller, reading = _poller_with_response({"dataArea": {"soc": 1}})
    assert reading is None
    assert poller.consecutive_failures == 1
    assert poller.retry_delay == 10  # doubled once


def test_poll_exception_is_failure_and_backs_off():
    poller = Poller("host", "serial")
    with mock.patch("franklinwh_mqtt.poller.LocalClient", side_effect=OSError("boom")):
        assert poller.poll_once() is None
        assert poller.poll_once() is None
    assert poller.consecutive_failures == 2
    assert poller.retry_delay == 20


def test_staleness():
    poller = Poller("host", "serial")
    assert poller.is_stale(180)  # no data yet
    poller, reading = _poller_with_response({"dataArea": DATA})
    assert not poller.is_stale(180)
    poller.last_good.ts = time.time() - 300
    assert poller.is_stale(180)
