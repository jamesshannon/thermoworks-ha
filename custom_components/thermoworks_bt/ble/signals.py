"""ThermoWorks Signals BLE constants and parsers.

Signals (advertised local name ``TMW022``) exposes its state as ASCII,
comma-separated GATT characteristics that must be read from an active
connection; the advertisement carries no sensor data. Protocol reference:
``docs/protocol/signals-ble.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    channel: int
    label: str


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Device-level information."""

    battery_pct: int
    mac: str
    firmware: str
    raw_fields: tuple[str, ...]
    """All fields as received; field 0 (observed ``100``) is not yet understood."""


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


def parse_temperatures(data: bytes, fahrenheit: bool) -> tuple[ProbeTemps, ...]:
    """Parse the temperature characteristic into four ProbeTemps."""
    fields = _fields(data, PROBE_COUNT * FIELDS_PER_PROBE, "temperatures")
    probes: list[ProbeTemps] = []
    for p in range(PROBE_COUNT):
        base = p * FIELDS_PER_PROBE
        state = int(fields[base + _STATE_INDEX])
        if state != PROBE_ATTACHED_STATE:
            probes.append(ProbeTemps(False, None, None, None))
            continue
        probes.append(
            ProbeTemps(
                connected=True,
                temperature_c=_to_celsius(
                    float(fields[base + _TEMP_INDEX]), fahrenheit
                ),
                max_c=_to_celsius(float(fields[base + _MAX_INDEX]), fahrenheit),
                min_c=_to_celsius(float(fields[base + _MIN_INDEX]), fahrenheit),
            )
        )
    return tuple(probes)


def parse_probe_config(data: bytes, fahrenheit: bool) -> ProbeConfig:
    """Parse one probe-config characteristic: high, low, channel, label, ..."""
    fields = _fields(data, 4, "probe config")
    return ProbeConfig(
        alarm_high_c=_to_celsius(float(fields[0]), fahrenheit),
        alarm_low_c=_to_celsius(float(fields[1]), fahrenheit),
        channel=int(fields[2]),
        label=fields[3].strip(),
    )


def parse_device_info(data: bytes) -> DeviceInfo:
    """Parse the device-info characteristic: ?, battery, ?, mac, firmware."""
    fields = _fields(data, 5, "device info")
    battery = int(fields[1])
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
