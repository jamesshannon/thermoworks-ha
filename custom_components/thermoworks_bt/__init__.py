"""The ThermoWorks Bluetooth integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ThermoWorksCoordinator

_LOGGER = logging.getLogger(__name__)

type ThermoWorksConfigEntry = ConfigEntry[ThermoWorksCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ThermoWorksConfigEntry
) -> bool:
    """Set up ThermoWorks BLE device from a config entry."""
    assert entry.unique_id is not None
    _LOGGER.info("Setting up ThermoWorks integration for %s", entry.unique_id)
    coordinator = ThermoWorksCoordinator(hass, entry)
    entry.runtime_data = coordinator
    _LOGGER.debug("Forwarding setup to platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start after all platforms have had a chance to subscribe.
    _LOGGER.info("Starting coordinator...")
    entry.async_on_unload(coordinator.async_start())
    # Start fallback timer-based polling to ensure updates even without advertisements
    coordinator.start_fallback_poll()
    _LOGGER.info("ThermoWorks integration setup complete")
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ThermoWorksConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
