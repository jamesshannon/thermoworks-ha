"""BlueDOT-specific BLE constants and parsing."""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sensor_state_data import BinarySensorDeviceClass, SensorData, SensorLibrary

from .device import DeviceDriver

if TYPE_CHECKING:
    from bleak import BleakClient

_LOGGER = logging.getLogger(__name__)

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


class BlueDOTDevice(DeviceDriver):
    """Driver for the ThermoWorks BlueDOT single-probe thermometer.

    BlueDOT does not expose a readable temperature characteristic; it pushes a
    20-byte notification shortly after a client subscribes. ``async_read``
    subscribes, waits for exactly one notification, and unsubscribes.
    """

    device_type = "BlueDOT"
    min_poll_interval = 30.0

    @classmethod
    def matches(cls, local_name: str | None) -> bool:
        """Return True if the advertised local name is a BlueDOT device."""
        return is_bluedot(local_name)

    async def async_read(
        self, client: BleakClient, *, timeout: float
    ) -> BlueDOTReading:
        """Subscribe, wait for one notification, unsubscribe, and return it."""
        from bleak.exc import BleakError

        reading_event = asyncio.Event()
        reading: BlueDOTReading | None = None

        def _on_notification(_sender: int, data: bytearray) -> None:
            nonlocal reading
            _LOGGER.debug("Received notification: %s", data.hex())
            try:
                reading = parse_notification_data(bytes(data))
            except ValueError:
                _LOGGER.warning(
                    "Failed to parse BlueDOT notification: %s", data.hex()
                )
                return
            reading_event.set()

        try:
            await client.start_notify(CHARACTERISTIC_UUID, _on_notification)
        except BleakError as err:
            if "Notify acquired" not in str(err):
                raise
            _LOGGER.debug("Notification already subscribed; retrying after cleanup")
            await asyncio.sleep(0.5)
            try:
                await client.stop_notify(CHARACTERISTIC_UUID)
            except Exception as err:  # noqa: BLE001 - best effort cleanup
                _LOGGER.debug("Error stopping stale notification: %s", err)
            await client.start_notify(CHARACTERISTIC_UUID, _on_notification)

        try:
            await asyncio.wait_for(reading_event.wait(), timeout=timeout)
        finally:
            try:
                await client.stop_notify(CHARACTERISTIC_UUID)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error stopping notifications: %s", err)

        assert reading is not None
        return reading

    def apply(self, reading: BlueDOTReading, data: SensorData) -> None:
        """Translate a BlueDOT reading into temperature/binary sensor keys."""
        data.update_predefined_sensor(
            SensorLibrary.TEMPERATURE__CELSIUS, reading.temperature_celsius
        )
        data.update_binary_sensor(
            key="probe_connected",
            native_value=reading.probe_connected,
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            name="Probe",
        )
        data.update_binary_sensor(
            key="alarm_active",
            native_value=reading.alarm_active,
            device_class=BinarySensorDeviceClass.PROBLEM,
            name="Alarm",
        )
