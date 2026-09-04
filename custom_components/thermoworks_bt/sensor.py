"""Support for ThermoWorks BLE sensors."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info
from sensor_state_data import (
    DeviceClass,
    DeviceKey,
    SensorDescription,
    SensorUpdate,
    Units,
)

from . import ThermoWorksConfigEntry

SENSOR_DESCRIPTIONS = {
    (DeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{DeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    (
        DeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=(
            f"{DeviceClass.SIGNAL_STRENGTH}"
            f"_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}"
        ),
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}

_DIAGNOSTIC_TEMPERATURE = SensorEntityDescription(
    key="diagnostic_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
)
_CHANNEL_LABEL = SensorEntityDescription(
    key="channel_label",
    entity_category=EntityCategory.DIAGNOSTIC,
)

# Per-key overrides take precedence over the (device_class, unit) defaults.
# Signals emits these keys (see ble/signals.py::SignalsDevice.apply).
SENSOR_DESCRIPTION_OVERRIDES: dict[str, SensorEntityDescription] = {}
for _n in range(1, 5):
    for _suffix in ("max", "min", "alarm_high_setpoint", "alarm_low_setpoint"):
        SENSOR_DESCRIPTION_OVERRIDES[f"probe_{_n}_{_suffix}"] = _DIAGNOSTIC_TEMPERATURE
    SENSOR_DESCRIPTION_OVERRIDES[f"probe_{_n}_channel_label"] = _CHANNEL_LABEL


def _description_for(
    device_key: DeviceKey, description: SensorDescription
) -> SensorEntityDescription | None:
    """Pick the HA entity description for a sensor-state-data description."""
    if (override := SENSOR_DESCRIPTION_OVERRIDES.get(device_key.key)) is not None:
        return override
    return SENSOR_DESCRIPTIONS.get(
        (description.device_class, description.native_unit_of_measurement)
    )


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): ha_description
            for device_key, description in sensor_update.entity_descriptions.items()
            if (ha_description := _description_for(device_key, description)) is not None
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoWorksConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ThermoWorks BLE sensors."""
    processor = PassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            ThermoWorksBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_register_processor(processor)
    )


class ThermoWorksBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[str | float | int | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a ThermoWorks BLE sensor."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
