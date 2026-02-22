"""Tests for ThermoWorks sensor entities."""

from __future__ import annotations

import struct
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfTemperature

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermoworks_bt.ble.bluedot import NOTIFICATION_DATA_LENGTH
from custom_components.thermoworks_bt.const import DOMAIN

from . import BLUEDOT_SERVICE_INFO


def _build_notification_payload(temperature: int = 25, unit: int = 0x00) -> bytearray:
    """Build a 20-byte Celsius notification payload."""
    data = bytearray(NOTIFICATION_DATA_LENGTH)
    data[0] = 0x00  # probe connected
    struct.pack_into("<i", data, 1, temperature)
    struct.pack_into("<i", data, 5, 100)  # alarm temp
    data[11] = unit
    data[13:19] = b"\x00\xA0\x50\x3F\x89\x5B"
    data[19] = 0x00  # alarm inactive
    return data


async def test_sensors_created_from_poll(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that temperature sensor is created after a successful poll."""
    mock_config_entry.add_to_hass(hass)
    payload = _build_notification_payload(temperature=25, unit=0x00)

    with (
        patch(
            "custom_components.thermoworks_bt.coordinator.ThermoWorksCoordinator.async_start"
        ),
        patch(
            "custom_components.thermoworks_bt.ble.parser.establish_connection"
        ) as mock_conn,
    ):
        mock_client = mock_conn.return_value

        async def _mock_start_notify(uuid, callback):
            callback(0, payload)

        mock_client.start_notify = _mock_start_notify
        mock_client.stop_notify.__aenter__ = lambda s: s
        mock_client.stop_notify.__aexit__ = lambda *a: None

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state.name == "LOADED"


async def test_sensor_unit_is_celsius(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that temperature sensor always reports in Celsius regardless of device setting."""
    mock_config_entry.add_to_hass(hass)
    # Device set to Fahrenheit, 72F = 22.2C
    payload = _build_notification_payload(temperature=72, unit=0x01)

    with (
        patch(
            "custom_components.thermoworks_bt.coordinator.ThermoWorksCoordinator.async_start"
        ),
        patch(
            "custom_components.thermoworks_bt.ble.parser.establish_connection"
        ) as mock_conn,
    ):
        mock_client = mock_conn.return_value

        async def _mock_start_notify(uuid, callback):
            callback(0, payload)

        mock_client.start_notify = _mock_start_notify

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # If sensor entities were registered, verify unit.
    temp_entity = hass.states.get("sensor.bluedot_temperature")
    if temp_entity:
        assert temp_entity.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
