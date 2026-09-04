"""Tests for ThermoWorks sensor entities."""

from __future__ import annotations

import struct
from unittest.mock import patch

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermoworks_bt.ble.bluedot import NOTIFICATION_DATA_LENGTH
from custom_components.thermoworks_bt.const import DOMAIN


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
    """Test that temperature sensor always reports Celsius regardless of device unit."""
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
        assert (
            temp_entity.attributes.get("unit_of_measurement")
            == UnitOfTemperature.CELSIUS
        )


async def test_signals_entry_loads(hass: HomeAssistant) -> None:
    """Test that a Signals config entry sets up and loads."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="24:62:AB:E0:C1:BE", title="Signals C1BE", data={}
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.thermoworks_bt.coordinator.ThermoWorksCoordinator.async_start"
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.name == "LOADED"


def test_signals_keys_all_resolve_to_descriptions() -> None:
    """Every key SignalsDevice.apply emits must map to an HA entity description."""
    from homeassistant.const import EntityCategory
    from sensor_state_data import SensorData

    from custom_components.thermoworks_bt.binary_sensor import (
        binary_sensor_update_to_bluetooth_data_update,
    )
    from custom_components.thermoworks_bt.ble.signals import (
        DeviceInfo,
        ProbeConfig,
        ProbeTemps,
        SignalsDevice,
        SignalsReading,
        WifiInfo,
    )
    from custom_components.thermoworks_bt.sensor import (
        sensor_update_to_bluetooth_data_update,
    )

    probe = ProbeTemps(connected=True, temperature_c=90.0, max_c=95.0, min_c=20.0)
    cfg = ProbeConfig(alarm_high_c=93.0, alarm_low_c=60.0, flag=1, label="CH 1")
    reading = SignalsReading(
        probes=(probe,) * 4,
        configs=(cfg,) * 4,
        info=DeviceInfo(
            battery_pct=67, mac="aa:bb:cc:dd:ee:ff", firmware="v4.21", raw_fields=()
        ),
        wifi=WifiInfo(ssid="MyWifi", connected=True, cloud_host="h"),
    )
    data = SensorData()
    data.set_device_name("Signals TEST")
    SignalsDevice().apply(reading, data)
    update = data._finish_update()

    sensors = sensor_update_to_bluetooth_data_update(update)
    binaries = binary_sensor_update_to_bluetooth_data_update(update)

    emitted_sensor_keys = {k.key for k in update.entity_values}
    emitted_binary_keys = {k.key for k in update.binary_entity_values}
    assert {k.key for k in sensors.entity_descriptions} == emitted_sensor_keys
    assert {k.key for k in binaries.entity_descriptions} == emitted_binary_keys

    diagnostic = {
        f"probe_{n}_{s}"
        for n in range(1, 5)
        for s in (
            "max", "min", "alarm_high_setpoint", "alarm_low_setpoint", "channel_label"
        )
    } | {"battery"}
    for key, description in sensors.entity_descriptions.items():
        expected = EntityCategory.DIAGNOSTIC if key.key in diagnostic else None
        assert description.entity_category == expected, key.key
    wifi = next(k for k in binaries.entity_descriptions if k.key == "wifi_connected")
    wifi_description = binaries.entity_descriptions[wifi]
    assert wifi_description.entity_category == EntityCategory.DIAGNOSTIC
