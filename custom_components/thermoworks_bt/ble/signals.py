"""ThermoWorks Signals BLE constants and parsers.

Signals (advertised local name ``TMW022``) exposes its state as ASCII,
comma-separated GATT characteristics that must be read from an active
connection; the advertisement carries no sensor data. Protocol reference:
``docs/protocol/signals-ble.md``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from sensor_state_data import (
    BinarySensorDeviceClass,
    SensorData,
    SensorDeviceClass,
    SensorLibrary,
    Units,
)

from .device import DeviceDriver

if TYPE_CHECKING:
    from bleak import BleakClient

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

DEVICE_NAME_PREFIX = "TMW022"

# GATT characteristic UUIDs (lowercase, as bleak normalises them).
UUID_TEMPERATURES = "5f5f9010-0e0d-4bd4-b5dc-e4ff47a45984"
UUID_DEVICE_INFO = "3ce0c366-691f-43e6-b625-3f0912ff6ea7"
UUID_WIFI = "b4f1d66a-ecab-4e03-8b43-b9df904ebcdf"
UUID_PROBE_CONFIG: tuple[str, str, str, str] = (
    "0a990c1f-b61a-441c-8f7d-f775b6ff9400",
    "f7c21d1c-5cb9-4b9b-ab7e-e1d8e7a51724",
    "cfacb2d0-2d81-4c82-a168-13314e38a338",
    "c99c943f-da4b-4ee3-92ec-c806006e9e7f",
)

PROBE_COUNT = 4
FIELDS_PER_PROBE = 7
# Temperature payload field layout per probe: temp, state, max, state, min, state, 0
_TEMP_INDEX, _STATE_INDEX, _MAX_INDEX, _MIN_INDEX = 0, 1, 2, 4
PROBE_ATTACHED_STATE = 0
NO_PROBE_STATE = 3
PROBE_FAULT_STATE = 2


@dataclass(frozen=True, slots=True)
class ProbeTemps:
    """Live temperatures for one probe channel. Values are None when no probe."""

    connected: bool
    temperature_c: float | None
    max_c: float | None
    min_c: float | None


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    """Alarm setpoints and label for one probe channel."""

    alarm_high_c: float | None
    alarm_low_c: float | None
    flag: int
    """Raw field 2. Observed 0/1; meaning unknown (it is NOT the channel number)."""
    label: str
    """Channel label as sent by the device (custom names are truncated to 4 chars)."""


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Device-level information."""

    battery_pct: int
    """Field 0. Provisional: 2024 notes guessed field 1, but field 1 reads 0 on a
    running unit while field 0 reads a plausible percentage."""
    mac: str
    firmware: str
    raw_fields: tuple[str, ...]
    """All fields as received; fields 1 and 2 are not yet understood."""


@dataclass(frozen=True, slots=True)
class WifiInfo:
    """WiFi status. Parsed for diagnostics; only ``connected`` becomes an entity."""

    ssid: str
    connected: bool
    cloud_host: str


def is_signals(name: str | None) -> bool:
    """Return True if the BLE local name identifies a Signals unit."""
    return name is not None and name.startswith(DEVICE_NAME_PREFIX)


def _fields(data: bytes, minimum: int, what: str) -> list[str]:
    """Decode an ASCII CSV payload and enforce a minimum field count."""
    text = bytes(data).decode("ascii", errors="replace").strip("\x00\r\n ")
    fields = text.split(",")
    if len(fields) < minimum:
        raise ValueError(
            f"Signals {what}: expected at least {minimum} fields, "
            f"got {len(fields)}: {text!r}"
        )
    return fields


def _to_celsius(value: float, fahrenheit: bool) -> float:
    return round((value - 32.0) * 5.0 / 9.0, 1) if fahrenheit else round(value, 1)


def _valid(
    fields: list[str], base: int, value_index: int, fahrenheit: bool
) -> float | None:
    """Return the value at value_index if its own state flag (value_index+1) is 0."""
    if int(fields[base + value_index + 1]) != PROBE_ATTACHED_STATE:
        return None
    return _to_celsius(float(fields[base + value_index]), fahrenheit)


def parse_temperatures(data: bytes, fahrenheit: bool) -> tuple[ProbeTemps, ...]:
    """Parse the temperature characteristic into four ProbeTemps."""
    fields = _fields(data, PROBE_COUNT * FIELDS_PER_PROBE, "temperatures")
    probes: list[ProbeTemps] = []
    for p in range(PROBE_COUNT):
        base = p * FIELDS_PER_PROBE
        connected = int(fields[base + _STATE_INDEX]) != NO_PROBE_STATE
        if not connected:
            probes.append(ProbeTemps(False, None, None, None))
            continue
        probes.append(
            ProbeTemps(
                connected=True,
                temperature_c=_valid(fields, base, _TEMP_INDEX, fahrenheit),
                max_c=_valid(fields, base, _MAX_INDEX, fahrenheit),
                min_c=_valid(fields, base, _MIN_INDEX, fahrenheit),
            )
        )
    return tuple(probes)


def parse_probe_config(data: bytes, fahrenheit: bool) -> ProbeConfig:
    """Parse one probe-config characteristic: high, low, flag, label, ..."""
    fields = _fields(data, 4, "probe config")
    return ProbeConfig(
        alarm_high_c=_to_celsius(float(fields[0]), fahrenheit),
        alarm_low_c=_to_celsius(float(fields[1]), fahrenheit),
        flag=int(fields[2]),
        label=fields[3].strip(),
    )


def parse_device_info(data: bytes) -> DeviceInfo:
    """Parse the device-info characteristic: battery, ?, ?, mac, firmware."""
    fields = _fields(data, 5, "device info")
    battery = int(fields[0])
    if not 0 <= battery <= 100:
        raise ValueError(f"Signals device info: battery out of range: {battery}")
    return DeviceInfo(
        battery_pct=battery,
        mac=fields[3].strip().lower(),
        firmware=fields[4].strip(),
        raw_fields=tuple(fields),
    )


def parse_wifi(data: bytes) -> WifiInfo:
    """Parse the wifi characteristic: ssid, flag, host, flag."""
    fields = _fields(data, 2, "wifi")
    return WifiInfo(
        ssid=fields[0],
        connected=fields[1].strip() == "1",
        cloud_host=fields[2].strip() if len(fields) > 2 else "",
    )


@dataclass(frozen=True, slots=True)
class SignalsReading:
    """One full poll of a Signals unit. Optional parts are None if their read failed."""

    probes: tuple[ProbeTemps, ...]
    configs: tuple[ProbeConfig | None, ...]
    info: DeviceInfo | None
    wifi: WifiInfo | None


def alarm_state(
    probe: ProbeTemps, cfg: ProbeConfig | None
) -> tuple[bool | None, bool | None]:
    """Return (high_alarm, low_alarm), computed in HA from setpoints.

    The device exposes setpoints but no alarm flag on the read side. A
    disconnected probe never alarms; a missing config makes the state unknown.
    """
    if cfg is None:
        return (None, None)
    if not probe.connected or probe.temperature_c is None:
        return (False, False)
    high = cfg.alarm_high_c is not None and probe.temperature_c >= cfg.alarm_high_c
    low = cfg.alarm_low_c is not None and probe.temperature_c <= cfg.alarm_low_c
    return (high, low)


class SignalsDevice(DeviceDriver):
    """Driver for the ThermoWorks Signals 4-channel thermometer (read-only)."""

    device_type = "Signals"
    min_poll_interval = 30.0

    def __init__(self, fahrenheit: bool = True, **options: object) -> None:
        """Create the driver.

        Args:
            fahrenheit: Device display unit. Signals sends temperatures in its
                display unit with no unit marker; v1 assumes °F. If the unit is
                set to °C every temperature will be off by the F→C transform
                (obvious in HA).
        """
        super().__init__(fahrenheit=fahrenheit, **options)
        self.fahrenheit = fahrenheit

    @classmethod
    def matches(cls, local_name: str | None) -> bool:
        """Return True if the advertised local name identifies a Signals unit."""
        return is_signals(local_name)

    def device_name(self, local_name: str | None, address: str) -> str:
        """Return the name shown in Home Assistant, using the MAC's last 4 hex chars."""
        suffix = address.replace(":", "").replace("-", "")[-4:].upper()
        return f"Signals {suffix}"

    async def async_read(
        self, client: BleakClient, *, timeout: float
    ) -> SignalsReading:
        """Read all characteristics inside one connection.

        Device info is read first so a unit flag (if one is ever located there)
        is known before temperatures are parsed. Temperature failures propagate;
        every other read degrades to None for that part of the reading.
        """
        info = await self._read_optional(
            client, UUID_DEVICE_INFO, parse_device_info, timeout, "device info"
        )
        fahrenheit = self.fahrenheit

        raw = await asyncio.wait_for(client.read_gatt_char(UUID_TEMPERATURES), timeout)
        _LOGGER.debug("temperatures: %s", bytes(raw))
        probes = parse_temperatures(bytes(raw), fahrenheit)

        wifi = await self._read_optional(client, UUID_WIFI, parse_wifi, timeout, "wifi")
        configs = tuple(
            [
                await self._read_optional(
                    client, uuid, lambda b: parse_probe_config(b, fahrenheit),
                    timeout, f"probe {n} config",
                )
                for n, uuid in enumerate(UUID_PROBE_CONFIG, start=1)
            ]
        )
        return SignalsReading(probes=probes, configs=configs, info=info, wifi=wifi)

    @staticmethod
    async def _read_optional(
        client: BleakClient,
        uuid: str,
        parse: Callable[[bytes], T],
        timeout: float,
        what: str,
    ) -> T | None:
        """Read + parse one characteristic; None on any failure except timeout."""
        try:
            raw = await asyncio.wait_for(client.read_gatt_char(uuid), timeout)
        except asyncio.TimeoutError:
            raise
        except Exception as err:  # noqa: BLE001 - degrade, do not fail the poll
            _LOGGER.debug("Signals %s read failed: %s", what, err)
            return None
        _LOGGER.debug("%s: %s", what, bytes(raw))
        try:
            return parse(bytes(raw))
        except ValueError as err:
            _LOGGER.debug("Signals %s parse failed: %s", what, err)
            return None

    def apply(self, reading: SignalsReading, data: SensorData) -> None:
        """Translate a Signals reading into sensor/binary-sensor keys on ``data``."""
        for n, probe in enumerate(reading.probes, start=1):
            cfg = reading.configs[n - 1] if n - 1 < len(reading.configs) else None
            high, low = alarm_state(probe, cfg)
            self._temp(
                data, f"probe_{n}_temperature", f"Probe {n} Temperature",
                probe.temperature_c,
            )
            self._temp(
                data, f"probe_{n}_max", f"Probe {n} Session Max", probe.max_c
            )
            self._temp(
                data, f"probe_{n}_min", f"Probe {n} Session Min", probe.min_c
            )
            self._temp(
                data, f"probe_{n}_alarm_high_setpoint",
                f"Probe {n} High Alarm Setpoint",
                cfg.alarm_high_c if cfg else None,
            )
            self._temp(
                data, f"probe_{n}_alarm_low_setpoint",
                f"Probe {n} Low Alarm Setpoint",
                cfg.alarm_low_c if cfg else None,
            )
            data.update_sensor(
                key=f"probe_{n}_channel_label",
                native_unit_of_measurement=None,
                native_value=cfg.label if cfg else None,
                name=f"Probe {n} Channel Label",
            )
            data.update_binary_sensor(
                key=f"probe_{n}_connected",
                native_value=probe.connected,
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                name=f"Probe {n}",
            )
            data.update_binary_sensor(
                key=f"probe_{n}_alarm_high",
                native_value=high,
                device_class=BinarySensorDeviceClass.PROBLEM,
                name=f"Probe {n} High Alarm",
            )
            data.update_binary_sensor(
                key=f"probe_{n}_alarm_low",
                native_value=low,
                device_class=BinarySensorDeviceClass.PROBLEM,
                name=f"Probe {n} Low Alarm",
            )

        info = reading.info
        data.update_predefined_sensor(
            SensorLibrary.BATTERY__PERCENTAGE,
            info.battery_pct if info else None,
            key="battery",
            name="Battery",
        )
        if info:
            data.set_device_sw_version(info.firmware)

        data.update_binary_sensor(
            key="wifi_connected",
            native_value=reading.wifi.connected if reading.wifi else None,
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            name="WiFi",
        )

    @staticmethod
    def _temp(data: SensorData, key: str, name: str, value: float | None) -> None:
        """Emit one temperature sensor in native Celsius."""
        data.update_sensor(
            key=key,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
            native_value=value,
            device_class=SensorDeviceClass.TEMPERATURE,
            name=name,
        )
