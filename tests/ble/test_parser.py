"""Tests for ThermoWorksBluetoothDeviceData parser."""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thermoworks.ble.bluedot import NOTIFICATION_DATA_LENGTH
from custom_components.thermoworks.ble.parser import (
    ThermoWorksBluetoothDeviceData,
)


def _make_service_info(name: str = "BlueDOT", address: str = "AA:BB:CC:DD:EE:FF"):
    """Create a mock BluetoothServiceInfoBleak."""
    service_info = MagicMock()
    service_info.name = name
    service_info.address = address
    service_info.rssi = -60
    service_info.manufacturer_data = {}
    service_info.service_data = {}
    service_info.service_uuids = []
    service_info.source = "local"
    return service_info


def _build_notification_payload(
    *,
    probe_status: int = 0x00,
    temperature: int = 25,
    alarm_temp: int = 100,
    alarm_silenced: int = 0,
    alarm_disabled: int = 0,
    unit: int = 0x00,
    mac: bytes = b"\xAA\xBB\xCC\xDD\xEE\xFF",
    alarm_active: int = 0,
) -> bytearray:
    """Build a 20-byte notification payload."""
    data = bytearray(NOTIFICATION_DATA_LENGTH)
    data[0] = probe_status
    struct.pack_into("<i", data, 1, temperature)
    struct.pack_into("<i", data, 5, alarm_temp)
    data[9] = alarm_silenced
    data[10] = alarm_disabled
    data[11] = unit
    data[13:19] = mac
    data[19] = alarm_active
    return data


class TestSupported:
    """Tests for device support detection."""

    def test_supported_bluedot(self) -> None:
        """Test that BlueDOT device names are recognized."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        assert device.supported(info) is True

    def test_supported_bluedot_with_suffix(self) -> None:
        """Test BlueDOT name with suffix."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT 1234")
        assert device.supported(info) is True

    def test_not_supported_unknown_device(self) -> None:
        """Test that unknown device names are rejected."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="SomeOtherDevice")
        assert device.supported(info) is False

    def test_not_supported_none_name(self) -> None:
        """Test that None device name is rejected."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        info.name = None
        assert device.supported(info) is False


class TestStartUpdate:
    """Tests for _start_update device metadata."""

    def test_sets_device_metadata_for_bluedot(self) -> None:
        """Test that update() sets device type and manufacturer."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        result = device.update(info)

        # Verify device metadata was set.
        assert result.devices
        device_info = list(result.devices.values())[0]
        assert device_info.name == "BlueDOT"
        assert device_info.manufacturer == "ThermoWorks"

    def test_skips_non_bluedot(self) -> None:
        """Test that update() skips unknown devices."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="NotABlueDOT")
        result = device.update(info)

        # Should still return a SensorUpdate, just without device metadata.
        assert result is not None


class TestPollNeeded:
    """Tests for poll_needed timing logic."""

    def test_poll_needed_initially(self) -> None:
        """Test that poll is needed on first call."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info()
        assert device.poll_needed(info, None) is True

    @patch("custom_components.thermoworks.ble.parser.monotonic_time_coarse")
    def test_poll_not_needed_within_interval(self, mock_time: MagicMock) -> None:
        """Test that poll is not needed within the minimum interval."""
        device = ThermoWorksBluetoothDeviceData()
        device._last_full_update = 100.0
        mock_time.return_value = 110.0  # 10 seconds later

        info = _make_service_info()
        assert device.poll_needed(info, None) is False

    @patch("custom_components.thermoworks.ble.parser.monotonic_time_coarse")
    def test_poll_needed_after_interval(self, mock_time: MagicMock) -> None:
        """Test that poll is needed after the minimum interval."""
        device = ThermoWorksBluetoothDeviceData()
        device._last_full_update = 100.0
        mock_time.return_value = 131.0  # 31 seconds later

        info = _make_service_info()
        assert device.poll_needed(info, None) is True


class TestAsyncPoll:
    """Tests for async_poll with mocked BLE."""

    @pytest.mark.asyncio
    async def test_poll_returns_sensor_update(self) -> None:
        """Test that polling returns a SensorUpdate with temperature data."""
        device = ThermoWorksBluetoothDeviceData()
        # Pre-initialize device with an update call.
        info = _make_service_info(name="BlueDOT")
        device.update(info)

        payload = _build_notification_payload(temperature=25, unit=0x00)
        ble_device = MagicMock()
        ble_device.address = "AA:BB:CC:DD:EE:FF"

        mock_client = AsyncMock()

        async def _mock_start_notify(uuid, callback):
            # Simulate receiving a notification.
            callback(0, payload)

        mock_client.start_notify = _mock_start_notify
        mock_client.stop_notify = AsyncMock()
        mock_client.disconnect = AsyncMock()

        with patch(
            "custom_components.thermoworks.ble.parser.establish_connection",
            return_value=mock_client,
        ):
            result = await device.async_poll(ble_device)

        assert result is not None
        # Check that temperature sensor value is present.
        found_temp = False
        for key, value in result.entity_values.items():
            if "temperature" in key.key:
                assert value.native_value == 25.0
                found_temp = True
        assert found_temp, "Temperature sensor not found in update"

    @pytest.mark.asyncio
    async def test_poll_returns_binary_sensors(self) -> None:
        """Test that polling returns binary sensor data."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        device.update(info)

        payload = _build_notification_payload(
            probe_status=0x00, alarm_active=0x01, unit=0x00
        )
        ble_device = MagicMock()
        ble_device.address = "AA:BB:CC:DD:EE:FF"

        mock_client = AsyncMock()

        async def _mock_start_notify(uuid, callback):
            callback(0, payload)

        mock_client.start_notify = _mock_start_notify
        mock_client.stop_notify = AsyncMock()
        mock_client.disconnect = AsyncMock()

        with patch(
            "custom_components.thermoworks.ble.parser.establish_connection",
            return_value=mock_client,
        ):
            result = await device.async_poll(ble_device)

        # Check binary sensor values.
        binary_values = {
            key.key: value.native_value
            for key, value in result.binary_entity_values.items()
        }
        assert binary_values.get("probe_connected") is True
        assert binary_values.get("alarm_active") is True

    @pytest.mark.asyncio
    async def test_poll_disconnects_on_success(self) -> None:
        """Test that the client disconnects after successful poll."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        device.update(info)

        payload = _build_notification_payload(unit=0x00)
        ble_device = MagicMock()
        ble_device.address = "AA:BB:CC:DD:EE:FF"

        mock_client = AsyncMock()

        async def _mock_start_notify(uuid, callback):
            callback(0, payload)

        mock_client.start_notify = _mock_start_notify
        mock_client.stop_notify = AsyncMock()
        mock_client.disconnect = AsyncMock()

        with patch(
            "custom_components.thermoworks.ble.parser.establish_connection",
            return_value=mock_client,
        ):
            await device.async_poll(ble_device)

        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_disconnects_on_timeout(self) -> None:
        """Test that the client disconnects even on timeout."""
        device = ThermoWorksBluetoothDeviceData()
        info = _make_service_info(name="BlueDOT")
        device.update(info)

        ble_device = MagicMock()
        ble_device.address = "AA:BB:CC:DD:EE:FF"

        mock_client = AsyncMock()
        # Don't call the callback, so it times out.
        mock_client.start_notify = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        mock_client.disconnect = AsyncMock()

        with (
            patch(
                "custom_components.thermoworks.ble.parser.establish_connection",
                return_value=mock_client,
            ),
            patch(
                "custom_components.thermoworks.ble.parser.NOTIFICATION_TIMEOUT",
                0.1,
            ),
            pytest.raises(asyncio.TimeoutError),
        ):
            await device.async_poll(ble_device)

        mock_client.disconnect.assert_called_once()
