"""Config flow for ThermoWorks Bluetooth integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .ble.parser import ThermoWorksBluetoothDeviceData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ThermoWorksConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThermoWorks Bluetooth devices."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: ThermoWorksBluetoothDeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = ThermoWorksBluetoothDeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth discovery."""
        assert self._discovered_device is not None
        assert self._discovery_info is not None
        device = self._discovered_device
        discovery_info = self._discovery_info
        title = device.get_device_name() or discovery_info.name
        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup from discovered devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids(include_ignore=False)
        _LOGGER.info("Config flow: Searching for ThermoWorks devices...")
        _LOGGER.debug("Current configured addresses: %s", current_addresses)

        discovered_count = 0
        for discovery_info in async_discovered_service_info(self.hass, False):
            discovered_count += 1
            address = discovery_info.address
            name = discovery_info.name
            _LOGGER.debug(
                "Checking discovered device: %s (%s)", name, address
            )

            if address in current_addresses or address in self._discovered_devices:
                _LOGGER.debug("  Skipping: already configured or in list")
                continue

            device = ThermoWorksBluetoothDeviceData()
            is_supported = device.supported(discovery_info)
            _LOGGER.debug("  Is supported: %s", is_supported)

            if is_supported:
                device_name = device.get_device_name() or discovery_info.name
                self._discovered_devices[address] = device_name
                _LOGGER.info("Found ThermoWorks device: %s (%s)", device_name, address)

        _LOGGER.info(
            "Discovery complete: checked %d devices, found %d ThermoWorks devices",
            discovered_count,
            len(self._discovered_devices),
        )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )
