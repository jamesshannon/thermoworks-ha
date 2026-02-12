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

    def _start_update(self, data: BluetoothServiceInfoBleak) -> None:
        """Handle BLE advertisement data.

        Called by BluetoothData.update() on each advertisement. This sets up
        device metadata but does NOT parse temperature — that requires an
        active GATT connection via async_poll().

        Note: RSSI is automatically updated by the base class after this method.
        """
        _LOGGER.debug(
            "_start_update called for device: name='%s', address=%s, RSSI=%d",
            data.name, data.address, data.rssi
        )
        is_supported = is_bluedot(data.name)
        _LOGGER.debug("  is_bluedot('%s') = %s", data.name, is_supported)

        if is_supported:
            _LOGGER.debug("  Setting device metadata for BlueDOT")
            self.set_device_type("BlueDOT")
            self.set_device_name(data.name)
            self.set_device_manufacturer("ThermoWorks")
        else:
            _LOGGER.debug("  Not a BlueDOT device, skipping")

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
        now = monotonic_time_coarse()
        if last_poll is None:
            _LOGGER.debug(
                "Poll needed for %s: no previous poll", self.get_device_name()
            )
            return True

        time_since_poll = now - last_poll
        needed = time_since_poll > MIN_POLL_INTERVAL
        _LOGGER.debug(
            "Poll needed check for %s: %.1fs since last poll (min: %.1fs) -> %s",
            self.get_device_name(),
            time_since_poll,
            MIN_POLL_INTERVAL,
            needed,
        )
        return needed

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
        from bleak.exc import BleakError

        _LOGGER.debug("Connecting to %s", ble_device.address)
        reading_event = asyncio.Event()
        reading: BlueDOTReading | None = None

        def _on_notification(_sender: int, data: bytearray) -> None:
            nonlocal reading
            _LOGGER.debug("Received notification: %s", data.hex())
            try:
                reading = parse_notification_data(bytes(data))
                _LOGGER.debug("Parsed reading: %s", reading)
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
            _LOGGER.debug("Connected, starting notification subscription")
            try:
                await client.start_notify(CHARACTERISTIC_UUID, _on_notification)
            except BleakError as err:
                if "Notify acquired" in str(err):
                    _LOGGER.debug(
                        "Notification already subscribed, waiting briefly and retrying"
                    )
                    # Wait a moment for BlueZ to clean up previous subscription
                    await asyncio.sleep(0.5)
                    # Try to stop any existing subscription first
                    try:
                        await client.stop_notify(CHARACTERISTIC_UUID)
                    except Exception:
                        pass  # Ignore errors, subscription might not exist
                    # Retry the subscription
                    await client.start_notify(CHARACTERISTIC_UUID, _on_notification)
                else:
                    raise

            try:
                await asyncio.wait_for(
                    reading_event.wait(), timeout=NOTIFICATION_TIMEOUT
                )
                _LOGGER.debug("Notification received successfully")
            finally:
                try:
                    await client.stop_notify(CHARACTERISTIC_UUID)
                except Exception as err:
                    _LOGGER.debug("Error stopping notifications: %s", err)
        finally:
            try:
                await client.disconnect()
                _LOGGER.debug("Disconnected from %s", ble_device.address)
            except Exception as err:
                _LOGGER.debug("Error during disconnect: %s", err)

        assert reading is not None
        return reading
