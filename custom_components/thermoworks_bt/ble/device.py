"""Device driver abstraction for ThermoWorks BLE thermometers.

A driver knows how to recognise a device from its advertised local name, how to
read one sample from an already-connected ``BleakClient``, and how to translate
that sample into sensor keys on a ``SensorData`` object. ``parser.py`` owns the
connection lifecycle and never inspects device-specific bytes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from bleak import BleakClient
    from sensor_state_data import SensorData


class DeviceDriver(ABC):
    """Base class for a ThermoWorks BLE device driver."""

    device_type: ClassVar[str]
    """Human-readable model name, e.g. ``"BlueDOT"``."""

    min_poll_interval: ClassVar[float]
    """Minimum seconds between GATT polls for this device type."""

    def __init__(self, **options: Any) -> None:
        """Accept driver options; drivers ignore options they do not use."""
        self._options = options

    @classmethod
    @abstractmethod
    def matches(cls, local_name: str | None) -> bool:
        """Return True if the advertised local name belongs to this device type."""

    def device_name(self, local_name: str | None, address: str) -> str:
        """Return the name shown in Home Assistant for this device."""
        return local_name or self.device_type

    @abstractmethod
    async def async_read(self, client: BleakClient, *, timeout: float) -> Any:
        """Read one sample from a connected client.

        Args:
            client: Connected ``BleakClient``; the caller disconnects it.
            timeout: Seconds to wait for each GATT operation.

        Returns:
            A driver-specific reading object accepted by :meth:`apply`.
        """

    @abstractmethod
    def apply(self, reading: Any, data: SensorData) -> None:
        """Translate a reading into sensor/binary-sensor keys on ``data``."""


def all_drivers() -> tuple[type[DeviceDriver], ...]:
    """Return every known driver class, in match-priority order.

    Driver modules import ``DeviceDriver`` from this module, so they are
    imported lazily here rather than at module load to avoid a circular import.
    """
    from .bluedot import BlueDOTDevice
    from .signals import SignalsDevice

    return (BlueDOTDevice, SignalsDevice)


def driver_for(local_name: str | None, **options: Any) -> DeviceDriver | None:
    """Return a new driver instance for the advertised name, or None."""
    for driver_cls in all_drivers():
        if driver_cls.matches(local_name):
            return driver_cls(**options)
    return None
