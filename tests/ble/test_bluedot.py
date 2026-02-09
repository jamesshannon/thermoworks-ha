"""Tests for BlueDOT-specific BLE parsing."""

from __future__ import annotations

import struct

import pytest

from custom_components.thermoworks.ble.bluedot import (
    NOTIFICATION_DATA_LENGTH,
    BlueDOTReading,
    is_bluedot,
    parse_notification_data,
)


def _build_payload(
    *,
    probe_status: int = 0x00,
    temperature: int = 72,
    alarm_temp: int = 150,
    alarm_silenced: int = 0,
    alarm_disabled: int = 0,
    unit: int = 0x01,  # Fahrenheit by default to test conversion
    unknown: int = 0,
    mac: bytes = b"\xAA\xBB\xCC\xDD\xEE\xFF",
    alarm_active: int = 0,
) -> bytes:
    """Build a 20-byte BlueDOT notification payload."""
    data = bytearray(NOTIFICATION_DATA_LENGTH)
    data[0] = probe_status
    struct.pack_into("<i", data, 1, temperature)
    struct.pack_into("<i", data, 5, alarm_temp)
    data[9] = alarm_silenced
    data[10] = alarm_disabled
    data[11] = unit
    data[12] = unknown
    data[13:19] = mac
    data[19] = alarm_active
    return bytes(data)


class TestParseNotificationData:
    """Tests for parse_notification_data."""

    def test_basic_fahrenheit_reading(self) -> None:
        """Test parsing a typical Fahrenheit reading and conversion to C."""
        payload = _build_payload(temperature=72, unit=0x01)
        reading = parse_notification_data(payload)

        assert reading.probe_connected is True
        assert reading.temperature_celsius == pytest.approx(22.2, abs=0.1)
        assert reading.device_unit_fahrenheit is True

    def test_celsius_reading(self) -> None:
        """Test parsing a Celsius reading (no conversion needed)."""
        payload = _build_payload(temperature=25, unit=0x00)
        reading = parse_notification_data(payload)

        assert reading.temperature_celsius == 25.0
        assert reading.device_unit_fahrenheit is False

    def test_freezing_fahrenheit(self) -> None:
        """Test freezing point in Fahrenheit converts to 0 C."""
        payload = _build_payload(temperature=32, unit=0x01)
        reading = parse_notification_data(payload)

        assert reading.temperature_celsius == pytest.approx(0.0, abs=0.1)

    def test_negative_celsius(self) -> None:
        """Test negative Celsius temperature."""
        payload = _build_payload(temperature=-10, unit=0x00)
        reading = parse_notification_data(payload)

        assert reading.temperature_celsius == -10.0

    def test_negative_fahrenheit(self) -> None:
        """Test negative Fahrenheit temperature converts correctly."""
        payload = _build_payload(temperature=-4, unit=0x01)
        reading = parse_notification_data(payload)

        assert reading.temperature_celsius == pytest.approx(-20.0, abs=0.1)

    def test_zero_celsius(self) -> None:
        """Test zero Celsius."""
        payload = _build_payload(temperature=0, unit=0x00)
        reading = parse_notification_data(payload)

        assert reading.temperature_celsius == 0.0

    def test_probe_disconnected(self) -> None:
        """Test probe disconnected status."""
        payload = _build_payload(probe_status=0x03)
        reading = parse_notification_data(payload)

        assert reading.probe_connected is False

    def test_probe_connected(self) -> None:
        """Test probe connected status."""
        payload = _build_payload(probe_status=0x00)
        reading = parse_notification_data(payload)

        assert reading.probe_connected is True

    def test_alarm_active(self) -> None:
        """Test alarm active state."""
        payload = _build_payload(alarm_active=0x01)
        reading = parse_notification_data(payload)

        assert reading.alarm_active is True

    def test_alarm_inactive(self) -> None:
        """Test alarm inactive state."""
        payload = _build_payload(alarm_active=0x00)
        reading = parse_notification_data(payload)

        assert reading.alarm_active is False

    def test_alarm_silenced(self) -> None:
        """Test alarm silenced flag."""
        payload = _build_payload(alarm_silenced=0x01)
        reading = parse_notification_data(payload)

        assert reading.alarm_silenced is True

    def test_alarm_disabled(self) -> None:
        """Test alarm disabled flag."""
        payload = _build_payload(alarm_disabled=0x01)
        reading = parse_notification_data(payload)

        assert reading.alarm_disabled is True

    def test_alarm_temperature_conversion(self) -> None:
        """Test alarm temperature is also converted from F to C."""
        payload = _build_payload(alarm_temp=212, unit=0x01)
        reading = parse_notification_data(payload)

        assert reading.alarm_temperature_celsius == pytest.approx(100.0, abs=0.1)

    def test_mac_address(self) -> None:
        """Test MAC address is extracted correctly."""
        mac = b"\x11\x22\x33\x44\x55\x66"
        payload = _build_payload(mac=mac)
        reading = parse_notification_data(payload)

        assert reading.mac_address == mac

    def test_wrong_length_raises(self) -> None:
        """Test that wrong payload length raises ValueError."""
        with pytest.raises(ValueError, match="Expected 20 bytes"):
            parse_notification_data(b"\x00" * 10)

    def test_empty_payload_raises(self) -> None:
        """Test that empty payload raises ValueError."""
        with pytest.raises(ValueError):
            parse_notification_data(b"")

    def test_too_long_raises(self) -> None:
        """Test that too-long payload raises ValueError."""
        with pytest.raises(ValueError):
            parse_notification_data(b"\x00" * 21)

    def test_frozen_dataclass(self) -> None:
        """Test that BlueDOTReading is immutable."""
        payload = _build_payload()
        reading = parse_notification_data(payload)

        with pytest.raises(AttributeError):
            reading.temperature_celsius = 99.9  # type: ignore[misc]


class TestIsBluedot:
    """Tests for is_bluedot."""

    def test_exact_name(self) -> None:
        assert is_bluedot("BlueDOT") is True

    def test_name_with_suffix(self) -> None:
        assert is_bluedot("BlueDOT 1234") is True

    def test_name_with_number(self) -> None:
        assert is_bluedot("BlueDOT1") is True

    def test_wrong_name(self) -> None:
        assert is_bluedot("ThermoPro") is False

    def test_empty_name(self) -> None:
        assert is_bluedot("") is False

    def test_none_name(self) -> None:
        assert is_bluedot(None) is False

    def test_partial_match(self) -> None:
        assert is_bluedot("Blue") is False

    def test_case_sensitive(self) -> None:
        assert is_bluedot("bluedot") is False
        assert is_bluedot("BLUEDOT") is False
