"""Coordinator for ThermoWorks Bluetooth devices."""

from __future__ import annotations

from datetime import timedelta
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
from homeassistant.helpers.event import async_track_time_interval

from .ble.parser import ThermoWorksBluetoothDeviceData

_LOGGER = logging.getLogger(__name__)

# Fallback polling interval when advertisements aren't triggering polls
FALLBACK_POLL_INTERVAL = timedelta(seconds=60)


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
        self._entry = entry
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

    def start_fallback_poll(self) -> None:
        """Start fallback timer-based polling.

        This ensures polling happens even if advertisements aren't coming through,
        which can occur due to HA's advertisement deduplication or device behavior.
        """
        _LOGGER.info(
            "Starting fallback polling timer (interval: %s)", FALLBACK_POLL_INTERVAL
        )
        self._entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_timer_poll, FALLBACK_POLL_INTERVAL
            )
        )

    async def _async_timer_poll(self, _now) -> None:
        """Fallback timer-triggered poll.

        This is called periodically by the timer to ensure we get updates even if
        advertisements aren't triggering polls.
        """
        from bleak.exc import BleakError

        _LOGGER.debug("Fallback timer triggered, checking if poll is needed")

        # Get the device to poll
        device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

        if device is None:
            _LOGGER.debug("Device not available for timer poll (out of range or off)")
            # Mark entities as unavailable but keep them registered
            self._mark_unavailable()
            return

        # Manually trigger a poll
        try:
            _LOGGER.info("Executing timer-based poll for %s", self.address)
            update = await self._data.async_poll(device)
            # Push the update to registered processors (marks as available)
            self.async_set_updated_data(update)
            _LOGGER.debug("Timer poll completed successfully")
        except (TimeoutError, asyncio.TimeoutError):
            _LOGGER.debug("Timer poll timed out (device may be out of range or off)")
            self._mark_unavailable()
        except BleakError as err:
            if "Failed to connect" in str(err) or "not found" in str(err):
                _LOGGER.debug(
                    "Timer poll failed: device unreachable (may be off or out of range)"
                )
            else:
                _LOGGER.warning("Timer poll failed with Bluetooth error: %s", err)
            self._mark_unavailable()
        except Exception as err:
            _LOGGER.warning("Timer poll failed: %s", err, exc_info=True)
            self._mark_unavailable()

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

    def _mark_unavailable(self) -> None:
        """Mark the device as unavailable.

        This keeps entities registered but marks them as unavailable,
        preventing the 'no longer being provided' message.
        """
        _LOGGER.debug("Marking device as unavailable")
        for processor in self._processors:
            processor.async_handle_unavailable()
