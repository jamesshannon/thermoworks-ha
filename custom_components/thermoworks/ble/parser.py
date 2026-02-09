"""ThermoWorks BLE device data parser."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from bluetooth_data_tools import monotonic_time_coarse
from bluetooth_sensor_state_data import BluetoothData
from sensor_state_data import BinarySensorDeviceClass, SensorLibrary, SensorUpdate

from .bluedot import (
    CHARACTERISTIC_UUID,
    BlueDOTReading,
    is_bluedot,
    parse_notification_data,
)

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bluetooth_sensor_state_data import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

# Minimum seconds between polls to avoid hammering the device.
MIN_POLL_INTERVAL = 30.0

# Timeout in seconds for waiting for a notification after subscribing.
NOTIFICATION_TIMEOUT = 10.0


class ThermoWorksBluetoothDeviceData(BluetoothData):
    """Parse and poll ThermoWorks BLE devices."""

    def __init__(self) -> None:
        super().__init__()
        self._last_full_update: float = 0.0

    def _start_update(self, data: BluetoothServiceInfoBleak) -> None:
        """Handle BLE advertisement data.

        Called by BluetoothData.update() on each advertisement. This sets up
        device metadata but does NOT parse temperature — that requires an
        active GATT connection via async_poll().
        """
        if is_bluedot(data.name):
            self.set_device_type("BlueDOT")
            self.set_device_name(data.name)
            self.set_device_manufacturer("ThermoWorks")

    def poll_needed(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Return True if enough time has passed since the last poll.

        Args:
            service_info: Latest BLE service info (unused but required by API).
            last_poll: Timestamp of last successful poll, or None.

        Returns:
            True if a new poll should be initiated.
        """
        return (
            not self._last_full_update
            or (monotonic_time_coarse() - self._last_full_update) > MIN_POLL_INTERVAL
        )

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """Connect to the device and read temperature data.

        Connects via GATT, subscribes to notifications, waits for one reading,
        parses it, and disconnects.

        Args:
            ble_device: The BLE device to connect to.

        Returns:
            SensorUpdate with the latest readings.
        """
        _LOGGER.debug("Polling ThermoWorks device %s", self.get_device_name())
        reading = await self._async_connect_and_read(ble_device)
        self._apply_reading(reading)
        self._last_full_update = monotonic_time_coarse()
        return self._finish_update()

    def _apply_reading(self, reading: BlueDOTReading) -> None:
        """Apply a parsed reading to the sensor update.

        Args:
            reading: Parsed BlueDOT notification data.
        """
        self.update_predefined_sensor(
            SensorLibrary.TEMPERATURE__CELSIUS,
            reading.temperature_celsius,
        )
        self.update_binary_sensor(
            key="probe_connected",
            native_value=reading.probe_connected,
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            name="Probe",
        )
        self.update_binary_sensor(
            key="alarm_active",
            native_value=reading.alarm_active,
            device_class=BinarySensorDeviceClass.PROBLEM,
            name="Alarm",
        )

    async def _async_connect_and_read(
        self, ble_device: BLEDevice
    ) -> BlueDOTReading:
        """Connect to a BlueDOT and read one notification.

        Args:
            ble_device: The BLE device to connect to.

        Returns:
            Parsed BlueDOTReading from the notification.

        Raises:
            asyncio.TimeoutError: If no notification is received in time.
            BleakError: On connection failure.
        """
        reading_event = asyncio.Event()
        reading: BlueDOTReading | None = None

        def _on_notification(_sender: int, data: bytearray) -> None:
            nonlocal reading
            try:
                reading = parse_notification_data(bytes(data))
            except ValueError:
                _LOGGER.warning(
                    "Failed to parse notification data from %s: %s",
                    ble_device.address,
                    data.hex(),
                )
                return
            reading_event.set()

        client = await establish_connection(
            BleakClient, ble_device, ble_device.address
        )
        try:
            await client.start_notify(CHARACTERISTIC_UUID, _on_notification)
            try:
                await asyncio.wait_for(
                    reading_event.wait(), timeout=NOTIFICATION_TIMEOUT
                )
            finally:
                await client.stop_notify(CHARACTERISTIC_UUID)
        finally:
            await client.disconnect()

        assert reading is not None
        return reading
