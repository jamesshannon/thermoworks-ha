"""Support for ThermoWorks BLE binary sensors."""

from __future__ import annotations

from sensor_state_data import BinarySensorDeviceClass, DeviceKey, SensorUpdate

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass as HABinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from . import ThermoWorksConfigEntry

BINARY_SENSOR_DESCRIPTIONS = {
    BinarySensorDeviceClass.CONNECTIVITY: BinarySensorEntityDescription(
        key=str(BinarySensorDeviceClass.CONNECTIVITY),
        device_class=HABinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorDeviceClass.PROBLEM: BinarySensorEntityDescription(
        key=str(BinarySensorDeviceClass.PROBLEM),
        device_class=HABinarySensorDeviceClass.PROBLEM,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def binary_sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update for binary sensors."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(
                device_key
            ): BINARY_SENSOR_DESCRIPTIONS[description.device_class]
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if description.device_class in BINARY_SENSOR_DESCRIPTIONS
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(
                device_key
            ): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoWorksConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ThermoWorks BLE binary sensors."""
    processor = PassiveBluetoothDataProcessor(
        binary_sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            ThermoWorksBluetoothBinarySensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_register_processor(processor)
    )


class ThermoWorksBluetoothBinarySensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[bool | None, SensorUpdate]
    ],
    BinarySensorEntity,
):
    """Representation of a ThermoWorks BLE binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
