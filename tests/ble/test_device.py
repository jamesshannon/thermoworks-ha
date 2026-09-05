"""Tests for the DeviceDriver abstraction and BlueDOT driver."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sensor_state_data import SensorData

from custom_components.thermoworks_bt.ble.bluedot import (
    CHARACTERISTIC_UUID,
    BlueDOTDevice,
)
from custom_components.thermoworks_bt.ble.device import DeviceDriver, driver_for


def _bluedot_payload(temperature: int = 25, alarm_active: int = 0) -> bytearray:
    import struct

    data = bytearray(20)
    data[0] = 0x00
    struct.pack_into("<i", data, 1, temperature)
    struct.pack_into("<i", data, 5, 100)
    data[11] = 0x00
    data[13:19] = b"\xaa\xbb\xcc\xdd\xee\xff"
    data[19] = alarm_active
    return data


class TestDriverFor:
    def test_bluedot_name_returns_bluedot_driver(self) -> None:
        driver = driver_for("BlueDOT 1234")
        assert isinstance(driver, BlueDOTDevice)
        assert isinstance(driver, DeviceDriver)

    def test_unknown_name_returns_none(self) -> None:
        assert driver_for("SomeOtherDevice") is None

    def test_none_name_returns_none(self) -> None:
        assert driver_for(None) is None

    def test_options_are_accepted_and_ignored_by_bluedot(self) -> None:
        driver = driver_for("BlueDOT", fahrenheit=False)
        assert isinstance(driver, BlueDOTDevice)


class TestBlueDOTDevice:
    def test_class_attributes(self) -> None:
        assert BlueDOTDevice.device_type == "BlueDOT"
        assert BlueDOTDevice.min_poll_interval == 30.0

    def test_device_name_uses_local_name(self) -> None:
        assert BlueDOTDevice().device_name("BlueDOT", "AA:BB:CC:DD:EE:FF") == "BlueDOT"

    def test_device_name_falls_back_to_type(self) -> None:
        assert BlueDOTDevice().device_name(None, "AA:BB:CC:DD:EE:FF") == "BlueDOT"

    @pytest.mark.asyncio
    async def test_async_read_returns_parsed_notification(self) -> None:
        client = AsyncMock()

        async def _start_notify(uuid, callback):
            assert uuid == CHARACTERISTIC_UUID
            callback(0, _bluedot_payload(temperature=25))

        client.start_notify = _start_notify
        client.stop_notify = AsyncMock()

        reading = await BlueDOTDevice().async_read(client, timeout=1.0)
        assert reading.temperature_celsius == 25.0
        client.stop_notify.assert_awaited_once_with(CHARACTERISTIC_UUID)

    @pytest.mark.asyncio
    async def test_async_read_times_out_without_notification(self) -> None:
        client = AsyncMock()
        client.start_notify = AsyncMock()
        client.stop_notify = AsyncMock()
        with pytest.raises(asyncio.TimeoutError):
            await BlueDOTDevice().async_read(client, timeout=0.05)
        client.stop_notify.assert_awaited_once()

    def test_apply_emits_temperature_and_binary_keys(self) -> None:
        from custom_components.thermoworks_bt.ble.bluedot import (
            parse_notification_data,
        )

        payload = bytes(_bluedot_payload(temperature=30, alarm_active=1))
        reading = parse_notification_data(payload)
        data = SensorData()
        BlueDOTDevice().apply(reading, data)
        update = data._finish_update()
        temps = {k.key: v.native_value for k, v in update.entity_values.items()}
        binaries = {
            k.key: v.native_value for k, v in update.binary_entity_values.items()
        }
        assert temps["temperature"] == 30.0
        assert binaries["probe_connected"] is True
        assert binaries["alarm_active"] is True


class TestDriverRegistry:
    def test_signals_name_returns_signals_driver(self) -> None:
        from custom_components.thermoworks_bt.ble.signals import SignalsDevice

        assert isinstance(driver_for("TMW022"), SignalsDevice)

    def test_signals_driver_receives_fahrenheit_option(self) -> None:
        driver = driver_for("TMW022", fahrenheit=False)
        assert driver.fahrenheit is False

    def test_exports(self) -> None:
        from custom_components.thermoworks_bt import ble

        for name in ("DeviceDriver", "driver_for", "all_drivers", "BlueDOTDevice",
                     "SignalsDevice", "SignalsReading", "is_signals",
                     "ThermoWorksBluetoothDeviceData"):
            assert name in ble.__all__, name

    def test_all_drivers_order(self) -> None:
        from custom_components.thermoworks_bt.ble.bluedot import BlueDOTDevice
        from custom_components.thermoworks_bt.ble.device import all_drivers
        from custom_components.thermoworks_bt.ble.signals import SignalsDevice

        assert all_drivers() == (BlueDOTDevice, SignalsDevice)
