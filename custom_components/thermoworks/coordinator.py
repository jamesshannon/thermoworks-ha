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

    @callback
    def _async_on_update(self, service_info: BluetoothServiceInfo) -> SensorUpdate:
        """Handle BLE advertisement updates.

        Processes advertisements for device identification and RSSI tracking.
        Temperature data is NOT available from advertisements.
        """
        return self._data.update(service_info)

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Return True when a GATT poll is needed for fresh data."""
        return (
            not self.hass.is_stopping
            and self._data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> SensorUpdate:
        """Poll the device via GATT connection for temperature data."""
        return await self._data.async_poll(last_service_info.device)
