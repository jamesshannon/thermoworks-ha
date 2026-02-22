"""BlueDOT-specific BLE constants and parsing."""

from __future__ import annotations

import struct
from dataclasses import dataclass

# GATT characteristic UUID for BlueDOT temperature notifications.
CHARACTERISTIC_UUID = "783f2991-23e0-4bdc-ac16-78601bd84b39"

# Expected notification payload length.
NOTIFICATION_DATA_LENGTH = 20

# Probe status values.
PROBE_CONNECTED = 0x00
PROBE_DISCONNECTED = 0x03

# Unit values.
UNIT_CELSIUS = 0x00
UNIT_FAHRENHEIT = 0x01


@dataclass(frozen=True, slots=True)
class BlueDOTReading:
    """Parsed reading from a BlueDOT notification payload."""

    probe_connected: bool
    temperature_celsius: float
    alarm_temperature_celsius: float
    alarm_silenced: bool
    alarm_disabled: bool
    device_unit_fahrenheit: bool
    mac_address: bytes
    alarm_active: bool


def parse_notification_data(data: bytes) -> BlueDOTReading:
    """Parse a 20-byte BlueDOT notification payload.

    Byte layout:
        0:      Probe status (0=connected, 3=disconnected)
        1-4:    Temperature, little-endian int32, whole degrees in device units
        5-8:    Alarm temperature, little-endian int32, device units
        9:      Alarm silenced (0=no, 1=yes)
        10:     Alarm disabled (0=enabled, 1=disabled)
        11:     Units (0=Celsius, 1=Fahrenheit)
        12:     Unknown
        13-18:  MAC address
        19:     Alarm active (0=no, 1=yes)

    Args:
        data: Raw 20-byte notification payload.

    Returns:
        Parsed BlueDOTReading with temperature always in Celsius.

    Raises:
        ValueError: If data is not the expected length.
    """
    if len(data) != NOTIFICATION_DATA_LENGTH:
        raise ValueError(
            f"Expected {NOTIFICATION_DATA_LENGTH} bytes, got {len(data)}"
        )

    probe_status = data[0]
    raw_temp = struct.unpack_from("<i", data, 1)[0]
    raw_alarm_temp = struct.unpack_from("<i", data, 5)[0]
    alarm_silenced = data[9] != 0
    alarm_disabled = data[10] != 0
    unit = data[11]
    mac_address = data[13:19]
    alarm_active = data[19] != 0

    is_fahrenheit = unit == UNIT_FAHRENHEIT
    temperature = _to_celsius(raw_temp, is_fahrenheit)
    alarm_temperature = _to_celsius(raw_alarm_temp, is_fahrenheit)

    return BlueDOTReading(
        probe_connected=probe_status == PROBE_CONNECTED,
        temperature_celsius=temperature,
        alarm_temperature_celsius=alarm_temperature,
        alarm_silenced=alarm_silenced,
        alarm_disabled=alarm_disabled,
        device_unit_fahrenheit=is_fahrenheit,
        mac_address=mac_address,
        alarm_active=alarm_active,
    )


def _to_celsius(temp: int, is_fahrenheit: bool) -> float:
    """Convert a temperature value to Celsius.

    Args:
        temp: Temperature in the device's native unit.
        is_fahrenheit: True if the device is set to Fahrenheit.

    Returns:
        Temperature in Celsius.
    """
    if is_fahrenheit:
        return round((temp - 32) * 5 / 9, 1)
    return float(temp)


def is_bluedot(name: str | None) -> bool:
    """Check if a BLE device name matches a BlueDOT device.

    Args:
        name: BLE device local name.

    Returns:
        True if the name indicates a BlueDOT device.
    """
    if name is None:
        return False
    return name.startswith("BlueDOT")
