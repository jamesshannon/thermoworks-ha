"""Tests for the ThermoWorks HA integration."""

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import MONOTONIC_TIME, BluetoothServiceInfoBleak


def _make_bluetooth_service_info(
    name: str,
    address: str,
    rssi: int = -60,
    manufacturer_data: dict | None = None,
    service_uuids: list | None = None,
    connectable: bool = True,
) -> BluetoothServiceInfoBleak:
    """Build a BluetoothServiceInfoBleak for testing."""
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=rssi,
        manufacturer_data=manufacturer_data or {},
        service_data={},
        service_uuids=service_uuids or [],
        source="local",
        device=BLEDevice(name=name, address=address, details={}),
        time=MONOTONIC_TIME(),
        advertisement=None,
        connectable=connectable,
        tx_power=-127,
    )


BLUEDOT_SERVICE_INFO = _make_bluetooth_service_info(
    name="BlueDOT",
    address="9DC3DAD5-9E2C-0BEC-B420-14DCC706FB06",
    rssi=-60,
)

NOT_THERMOWORKS_SERVICE_INFO = _make_bluetooth_service_info(
    name="NotAThermoWorks",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-70,
)
