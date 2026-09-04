"""ThermoWorks BLE device data: connection lifecycle and driver dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from bluetooth_data_tools import monotonic_time_coarse
from bluetooth_sensor_state_data import BluetoothData
from sensor_state_data import SensorUpdate

from .device import DeviceDriver, driver_for

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bluetooth_sensor_state_data import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

# Default minimum seconds between polls; drivers override via min_poll_interval.
MIN_POLL_INTERVAL = 30.0

# Timeout in seconds for each GATT operation during a poll.
NOTIFICATION_TIMEOUT = 10.0


class ThermoWorksBluetoothDeviceData(BluetoothData):
    """Identify a ThermoWorks device from advertisements and poll it via GATT."""

    def __init__(self, **driver_options: Any) -> None:
        super().__init__()
        self._driver_options = driver_options
        self._driver: DeviceDriver | None = None

    @property
    def driver(self) -> DeviceDriver | None:
        """The driver selected from the last advertisement, if any."""
        return self._driver

    def _start_update(self, data: BluetoothServiceInfoBleak) -> None:
        """Select a driver and set device metadata from an advertisement.

        Temperature is never available from advertisements; see async_poll().
        RSSI is updated by the base class after this method.
        """
        _LOGGER.debug(
            "_start_update: name='%s', address=%s, RSSI=%d",
            data.name, data.address, data.rssi,
        )
        driver = driver_for(data.name, **self._driver_options)
        if driver is None:
            _LOGGER.debug("  '%s' is not a supported ThermoWorks device", data.name)
            return
        self._driver = driver
        self.set_device_type(driver.device_type)
        self.set_device_name(driver.device_name(data.name, data.address))
        self.set_device_manufacturer("ThermoWorks")

    def poll_needed(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Return True if enough time has passed since the last poll."""
        if last_poll is None:
            _LOGGER.debug(
                "Poll needed for %s: no previous poll", self.get_device_name()
            )
            return True
        interval = self._driver.min_poll_interval if self._driver else MIN_POLL_INTERVAL
        elapsed = monotonic_time_coarse() - last_poll
        needed = elapsed > interval
        _LOGGER.debug(
            "Poll needed check for %s: %.1fs since last poll (min: %.1fs) -> %s",
            self.get_device_name(), elapsed, interval, needed,
        )
        return needed

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """Connect, read one sample through the driver, disconnect."""
        driver = self._driver
        if driver is None:
            raise RuntimeError(
                "No driver selected; update() must see an advertisement first"
            )
        _LOGGER.debug("Polling %s (%s)", self.get_device_name(), ble_device.address)
        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        try:
            reading = await driver.async_read(client, timeout=NOTIFICATION_TIMEOUT)
        finally:
            try:
                await client.disconnect()
                _LOGGER.debug("Disconnected from %s", ble_device.address)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error during disconnect: %s", err)
        driver.apply(reading, self)
        return self._finish_update()
