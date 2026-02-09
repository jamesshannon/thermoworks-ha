"""Tests for ThermoWorks coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermoworks.const import DOMAIN

from . import BLUEDOT_SERVICE_INFO


async def test_coordinator_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator is created when entry is set up."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.thermoworks.coordinator.ThermoWorksCoordinator.async_start"
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state.name == "LOADED"
    assert mock_config_entry.runtime_data is not None


async def test_coordinator_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator is cleaned up on unload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.thermoworks.coordinator.ThermoWorksCoordinator.async_start"
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state.name == "NOT_LOADED"
