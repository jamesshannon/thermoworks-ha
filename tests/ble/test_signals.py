"""Tests for the ThermoWorks Signals driver and parsers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.thermoworks_bt.ble.signals import (
    UUID_DEVICE_INFO,
    UUID_PROBE_CONFIG,
    UUID_TEMPERATURES,
    UUID_WIFI,
    ProbeTemps,
    WifiInfo,
    is_signals,
    parse_device_info,
    parse_probe_config,
    parse_temperatures,
    parse_wifi,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "signals"


def load_capture(name: str = "capture-2024-01-v4.21.json") -> dict[str, bytes]:
    """Return {uuid: payload bytes} from a capture fixture."""
    doc = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    out: dict[str, bytes] = {}
    for uuid, entry in doc["characteristics"].items():
        if "hex" in entry:
            out[uuid.lower()] = bytes.fromhex(entry["hex"])
        else:
            out[uuid.lower()] = entry["ascii"].encode("ascii")
    return out


@pytest.fixture
def capture() -> dict[str, bytes]:
    return load_capture()


class TestIsSignals:
    def test_prefix_match(self) -> None:
        assert is_signals("TMW022") is True
        assert is_signals("TMW022-ABCD") is True

    def test_rejects_other_and_none(self) -> None:
        assert is_signals("BlueDOT") is False
        assert is_signals("TMW") is False
        assert is_signals(None) is False


class TestParseTemperatures:
    def test_fixture_probe_1_attached_in_fahrenheit(self, capture) -> None:
        probes = parse_temperatures(capture[UUID_TEMPERATURES], fahrenheit=True)
        assert len(probes) == 4
        p1 = probes[0]
        assert p1.connected is True
        assert p1.temperature_c == pytest.approx(21.9, abs=0.05)  # 71.4F
        assert p1.max_c == pytest.approx(22.1, abs=0.05)          # 71.7F
        assert p1.min_c == pytest.approx(21.2, abs=0.05)          # 70.2F

    def test_fixture_empty_probes_are_disconnected_with_none(self, capture) -> None:
        probes = parse_temperatures(capture[UUID_TEMPERATURES], fahrenheit=True)
        for p in probes[1:]:
            assert p == ProbeTemps(
                connected=False, temperature_c=None, max_c=None, min_c=None
            )

    def test_celsius_passthrough(self) -> None:
        payload = b"21.9,0,22.1,0,21.2,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        probes = parse_temperatures(payload, fahrenheit=False)
        assert probes[0].temperature_c == 21.9

    def test_negative_temperature_fahrenheit(self) -> None:
        payload = b"-4.0,0,10.0,0,-10.0,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        probes = parse_temperatures(payload, fahrenheit=True)
        assert probes[0].temperature_c == -20.0

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 28 fields"):
            parse_temperatures(b"71.4,0,71.7,0", fahrenheit=True)

    def test_non_numeric_raises(self) -> None:
        payload = b"abc,0,71.7,0,70.2,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        with pytest.raises(ValueError):
            parse_temperatures(payload, fahrenheit=True)

    def test_extra_trailing_fields_ignored(self) -> None:
        payload = (
            b"71.4,0,71.7,0,70.2,0,0"
            + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
            + b",255,0"
        )
        assert len(parse_temperatures(payload, fahrenheit=True)) == 4


class TestParseProbeConfig:
    def test_fixture_probe_1(self, capture) -> None:
        cfg = parse_probe_config(capture[UUID_PROBE_CONFIG[0]], fahrenheit=True)
        assert cfg.alarm_high_c == pytest.approx(71.1, abs=0.05)
        assert cfg.alarm_low_c == pytest.approx(0.0, abs=0.05)
        assert cfg.flag == 1
        assert cfg.label == "CH 1"

    def test_fixture_probe_4_with_trailing_fields(self, capture) -> None:
        cfg = parse_probe_config(capture[UUID_PROBE_CONFIG[3]], fahrenheit=True)
        assert cfg.flag == 1
        assert cfg.label == "CH 4"

    def test_celsius_passthrough_and_custom_label(self) -> None:
        cfg = parse_probe_config(b"95,60,0,Bris,0.0,", fahrenheit=False)
        assert cfg.alarm_high_c == 95.0
        assert cfg.alarm_low_c == 60.0
        assert cfg.flag == 0
        assert cfg.label == "Bris"

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 4 fields"):
            parse_probe_config(b"160,32", fahrenheit=True)


class TestParseDeviceInfo:
    def test_fixture(self, capture) -> None:
        info = parse_device_info(capture[UUID_DEVICE_INFO])
        assert info.battery_pct == 100
        assert info.mac == "24:62:ab:e0:c1:be"
        assert info.firmware == "v4.21"
        assert info.raw_fields[1] == "67"

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 5 fields"):
            parse_device_info(b"100,67")

    def test_battery_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_device_info(b"150,0,0,aa:bb:cc:dd:ee:ff,v4.21")


class TestCapture2026:
    """Real payloads from the owner's unit: trailing commas, 4-char labels."""

    @pytest.fixture
    def capture26(self) -> dict[str, bytes]:
        return load_capture("capture-2026-09-v4.21-noprobe.json")

    def test_trailing_comma_and_no_probes(self, capture26) -> None:
        probes = parse_temperatures(capture26[UUID_TEMPERATURES], fahrenheit=True)
        assert len(probes) == 4
        assert all(not p.connected and p.temperature_c is None for p in probes)

    def test_probe_config_flag_and_truncated_label(self, capture26) -> None:
        cfg = parse_probe_config(capture26[UUID_PROBE_CONFIG[0]], fahrenheit=True)
        assert cfg.flag == 0
        assert cfg.label == "Gril"
        assert cfg.alarm_high_c == pytest.approx(182.2, abs=0.05)  # 360F
        assert cfg.alarm_low_c == pytest.approx(107.2, abs=0.05)   # 225F
        assert (
            parse_probe_config(capture26[UUID_PROBE_CONFIG[1]], fahrenheit=True).flag
            == 1
        )

    def test_probe_4_extra_fields_ignored(self, capture26) -> None:
        cfg = parse_probe_config(capture26[UUID_PROBE_CONFIG[3]], fahrenheit=True)
        assert cfg.label == "CH 4"
        assert cfg.flag == 0

    def test_device_info_battery_is_field_0(self, capture26) -> None:
        info = parse_device_info(capture26[UUID_DEVICE_INFO])
        assert info.battery_pct == 66
        assert info.mac == "24:0a:c4:ec:2e:0e"
        assert info.firmware == "v4.21"

    def test_wifi(self, capture26) -> None:
        assert parse_wifi(capture26[UUID_WIFI]).ssid == "Mo2Net"


class TestParseWifi:
    def test_fixture(self, capture) -> None:
        wifi = parse_wifi(capture[UUID_WIFI])
        assert wifi == WifiInfo(
            ssid="MyWifi", connected=True, cloud_host="iotservice.thermoworks.com"
        )

    def test_disconnected(self) -> None:
        wifi = parse_wifi(b"MyWifi,0,iotservice.thermoworks.com,0")
        assert wifi.connected is False

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 2 fields"):
            parse_wifi(b"MyWifi")
