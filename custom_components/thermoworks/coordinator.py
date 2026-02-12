"""Coordinator for ThermoWorks Bluetooth devices."""

from __future__ import annotations

import logging

from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .ble.parser import ThermoWorksBluetoothDeviceData

_LOGGER = logging.getLogger(__name__)


class ThermoWorksCoordinator(
    ActiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Coordinator for ThermoWorks Bluetooth devices.

    Uses ActiveBluetoothProcessorCoordinator to handle the connect-per-poll
    pattern: advertisements trigger device identification, and periodic polls
    connect via GATT to read temperature notifications.
    """

    _data: ThermoWorksBluetoothDeviceData

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        address = entry.unique_id
        assert address is not None
        _LOGGER.info(
            "Initializing ThermoWorks coordinator for device %s", address
        )
        self._data = ThermoWorksBluetoothDeviceData()
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=BluetoothScanningMode.ACTIVE,
            update_method=self._async_on_update,
            needs_poll_method=self._async_needs_poll,
            poll_method=self._async_poll_data,
            connectable=True,
        )
        _LOGGER.info("ThermoWorks coordinator initialized successfully")

    @callback
    def _async_on_update(self, service_info: BluetoothServiceInfo) -> SensorUpdate:
        """Handle BLE advertisement updates.

        Processes advertisements for device identification and RSSI tracking.
        Temperature data is NOT available from advertisements.
        """
        _LOGGER.info(
            "COORDINATOR CALLBACK: Advertisement received from %s (%s), RSSI: %d",
            service_info.name,
            service_info.address,
            service_info.rssi,
        )
        return self._data.update(service_info)

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Return True when a GATT poll is needed for fresh data."""
        if self.hass.is_stopping:
            _LOGGER.debug("Poll skipped: Home Assistant is stopping")
            return False

        if not self._data.poll_needed(service_info, last_poll):
            return False

        device = async_ble_device_from_address(
            self.hass, service_info.device.address, connectable=True
        )
        if not device:
            _LOGGER.debug("Poll skipped: device not available for connection")
            return False

        _LOGGER.debug("Poll will be initiated for %s", service_info.name)
        return True

    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> SensorUpdate:
        """Poll the device via GATT connection for temperature data."""
        return await self._data.async_poll(last_service_info.device)
