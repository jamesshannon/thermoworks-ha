"""Tests for ThermoWorks config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.thermoworks_bt.const import DOMAIN

from . import BLUEDOT_SERVICE_INFO, NOT_THERMOWORKS_SERVICE_INFO


async def test_bluetooth_discovery_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a BlueDOT device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLUEDOT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "custom_components.thermoworks_bt.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "BlueDOT"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "9DC3DAD5-9E2C-0BEC-B420-14DCC706FB06"


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test that unsupported devices abort the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_THERMOWORKS_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user setup when no supported devices are in range."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_with_found_device(hass: HomeAssistant) -> None:
    """Test user setup when a BlueDOT is discovered."""
    with patch(
        "custom_components.thermoworks_bt.config_flow.async_discovered_service_info",
        return_value=[BLUEDOT_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a second discovery for the same device aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLUEDOT_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.thermoworks_bt.async_setup_entry", return_value=True
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    # Try to discover the same device again.
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLUEDOT_SERVICE_INFO,
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
