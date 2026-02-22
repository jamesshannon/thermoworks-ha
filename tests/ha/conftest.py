"""Shared fixtures for ThermoWorks HA component tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermoworks_bt.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this directory."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
def auto_mock_bluetooth(mock_bluetooth):
    """Mock bluetooth for all tests."""
    return mock_bluetooth


@pytest.fixture(autouse=True)
def mock_bluetooth_setup():
    """Mock bluetooth and bluetooth_adapters setup to bypass hardware dependencies."""
    with (
        patch("homeassistant.components.bluetooth.async_setup", return_value=True),
        patch("homeassistant.components.bluetooth.async_setup_entry", return_value=True),
        patch("homeassistant.components.bluetooth_adapters.async_setup", return_value=True),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for a BlueDOT device."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="9DC3DAD5-9E2C-0BEC-B420-14DCC706FB06",
        title="BlueDOT",
        data={},
    )
