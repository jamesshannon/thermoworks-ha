# ThermoWorks Signals BLE Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only ThermoWorks Signals (4-probe, local name `TMW022*`) support to the `thermoworks_bt` Home Assistant custom integration over local BLE, without touching the ThermoWorks cloud.

**Architecture:** Introduce a small `DeviceDriver` abstraction in `custom_components/thermoworks_bt/ble/device.py`; move the existing BlueDOT notify-read logic behind it unchanged; add a `SignalsDevice` driver that performs 7 GATT reads per poll and parses ASCII CSV payloads into typed readings. `parser.py` keeps only connection lifecycle and driver selection. The HA layer (`sensor.py`, `binary_sensor.py`) gains per-key description overrides for diagnostic entities. A read-only dump script produces real-device fixtures (Phase 1) that the parser tests consume.

**Tech Stack:** Python 3.13, Home Assistant `ActiveBluetoothProcessorCoordinator` / `PassiveBluetoothDataProcessor`, `bleak`, `bleak-retry-connector`, `sensor-state-data`, `bluetooth-sensor-state-data`, pytest + `pytest-homeassistant-custom-component`, ruff.

**Spec:** `docs/superpowers/specs/2026-09-04-signals-ble-design.md` — read it first. The plan argues from it.

## Global Constraints

- **Read-only.** No task may call `write_gatt_char` on a Signals device, in code, tests, or scripts.
- All temperature entities are native **°C**; conversion happens at parse time.
- Emit `None` for any entity key whose value is unknown this poll. Never omit a key that was previously emitted; never fabricate `False`/`0`.
- Entity keys are fixed strings (`probe_{n}_temperature` …); channel labels never influence keys or entity IDs.
- **All existing upstream tests in `tests/ble/test_bluedot.py`, `tests/ble/test_parser.py`, and `tests/ha/` must pass unchanged.** Do not edit them except to *add* tests. This is the regression guard for the refactor.
- `parser.py` must keep module-level names `MIN_POLL_INTERVAL`, `NOTIFICATION_TIMEOUT`, and `establish_connection` importable — upstream tests patch them by that path.
- Style: ruff `E,F,I,W`, line length 88, `from __future__ import annotations`, docstrings on public functions, `_LOGGER.debug` not `print` (scripts excepted).
- Version bump to `0.10.0` in `manifest.json` (Task 9 only).
- Commits: conventional prefix (`feat:`, `refactor:`, `test:`, `docs:`), trailer `Co-Authored-By: Claude <noreply@anthropic.com>`. Work on branch `feature/signals`. Never push without being asked.
- Run commands from the repo root `C:\Users\sjmot\Projects\ThermoWork`. Python is the lean venv `.venv\Scripts\python` (bleak, sensor-state-data, pytest, ruff — **no Home Assistant**; HA does not install on Windows).
- **Testing model (decided by the owner — do not install `homeassistant` or `pytest-homeassistant-custom-component` locally):**
  - `tests/ble/` runs locally: `.venv\Scripts\python -m pytest tests/ble -q`. `tests/ble/conftest.py` makes the `ble` sub-package importable without HA.
  - `tests/ha/` is written to upstream's pattern but runs only in GitHub CI (`.github/workflows/validate.yaml`) after `git push origin feature/signals`. CI runs HA tests with `|| true`, so **read the "Run HA integration tests" step log** — a red test there does not fail the workflow.
  - The HA layer is verified on the owner's live Home Assistant via the **Home Assistant MCP tools** (`ha_write_file`, `ha_restart`, `ha_get_logs`, `ha_list_entities`, `ha_get_entity_state`). `ha_write_file` and `ha_restart` prompt for approval — that is expected.
- Pushing to `origin` (the owner's fork `sjmotew/thermoworks-ha`, branch `feature/signals`) is part of the workflow for CI. Never push to `upstream`.

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `custom_components/thermoworks_bt/ble/device.py` (new) | `DeviceDriver` ABC, `DRIVERS`, `driver_for()` | 1, 5 |
| `custom_components/thermoworks_bt/ble/bluedot.py` (modify) | existing parse fns unchanged + new `BlueDOTDevice(DeviceDriver)` | 1 |
| `custom_components/thermoworks_bt/ble/parser.py` (modify) | connection lifecycle only; delegates to driver | 2 |
| `custom_components/thermoworks_bt/ble/signals.py` (new) | Signals UUIDs, dataclasses, `parse_*`, `alarm_state`, `SignalsDevice` | 3, 4, 5 |
| `custom_components/thermoworks_bt/ble/__init__.py` (modify) | exports | 5 |
| `custom_components/thermoworks_bt/sensor.py` (modify) | battery default + per-key overrides + text sensor support | 6 |
| `custom_components/thermoworks_bt/binary_sensor.py` (modify) | per-key overrides | 6 |
| `custom_components/thermoworks_bt/manifest.json` (modify) | `TMW022*` matcher, version | 6, 9 |
| `tests/fixtures/signals/capture-2024-01-v4.21.json`, `capture-2026-09-v4.21-noprobe.json` (new) | transcribed captures | 3 |
| `tests/ble/test_device.py` (new) | `driver_for`, `BlueDOTDevice` | 1 |
| `tests/ble/test_signals.py` (new) | parse fns, alarm_state, apply, async_read | 3, 4, 5 |
| `tests/ha/__init__.py` (modify, add only) | `SIGNALS_SERVICE_INFO` | 6 |
| `tests/ha/test_config_flow.py` (modify, add only) | Signals discovery title | 6 |
| `tests/ha/test_sensor.py` (modify, add only) | Signals entities created | 6 |
| `scripts/dump_signals.py` (new) | Phase 1 read-only characteristic dump | 7 |
| `docs/protocol/signals-ble.md`, `docs/protocol/phase1-verification.md` (new) | protocol reference, hardware checklist | 7 |
| `README.md`, `info.md`, `CHANGELOG.md` (modify) | user docs | 9 |

Tasks 1–7 need no hardware. Task 8 needs the Signals unit and a Bluetooth adapter. Task 9 closes out.

---

### Task 0: Environment

**Files:** none (venv only)

- [ ] **Step 1: Lean venv** (skip if `.venv` exists)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install pytest pytest-asyncio bleak bleak-retry-connector bluetooth-data-tools bluetooth-sensor-state-data sensor-state-data ruff
```

- [ ] **Step 2: Confirm the import shim exists** — `tests/ble/conftest.py` (already committed) registers synthetic `custom_components` / `custom_components.thermoworks_bt` packages when `homeassistant` is not importable, so `tests/ble` can import the `ble` sub-package. Do not delete it.

- [ ] **Step 3: Record the baseline**

Run: `.venv\Scripts\python -m pytest tests/ble -q` → expected `41 passed`.
`.venv` is git-ignored (`.gitignore` line 28).

---

### Task 1: `DeviceDriver` abstraction + `BlueDOTDevice`

**Files:**
- Create: `custom_components/thermoworks_bt/ble/device.py`
- Modify: `custom_components/thermoworks_bt/ble/bluedot.py` (append; do not alter existing functions)
- Test: `tests/ble/test_device.py`

**Interfaces:**
- Produces:
  - `class DeviceDriver(ABC)` with `device_type: ClassVar[str]`, `min_poll_interval: ClassVar[float]`, `__init__(self, **options)`, `classmethod matches(cls, local_name: str | None) -> bool`, `device_name(self, local_name: str | None, address: str) -> str`, `async async_read(self, client: BleakClient, *, timeout: float) -> Any`, `apply(self, reading: Any, data: SensorData) -> None`
  - `all_drivers() -> tuple[type[DeviceDriver], ...]` (lazy-imports the driver modules on each call to avoid circular imports) and `driver_for(local_name: str | None, **options) -> DeviceDriver | None`
  - `class BlueDOTDevice(DeviceDriver)` in `bluedot.py`, `device_type = "BlueDOT"`, `min_poll_interval = 30.0`

- [ ] **Step 1: Write the failing tests**

`tests/ble/test_device.py`:

```python
"""Tests for the DeviceDriver abstraction and BlueDOT driver."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

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
        from custom_components.thermoworks_bt.ble.bluedot import parse_notification_data

        reading = parse_notification_data(bytes(_bluedot_payload(temperature=30, alarm_active=1)))
        data = SensorData()
        BlueDOTDevice().apply(reading, data)
        update = data._finish_update()
        temps = {k.key: v.native_value for k, v in update.entity_values.items()}
        binaries = {k.key: v.native_value for k, v in update.binary_entity_values.items()}
        assert temps["temperature"] == 30.0
        assert binaries["probe_connected"] is True
        assert binaries["alarm_active"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/ble/test_device.py -q`
Expected: ImportError — `custom_components.thermoworks_bt.ble.device` does not exist.

- [ ] **Step 3: Create `ble/device.py`**

```python
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

    return (BlueDOTDevice,)


def driver_for(local_name: str | None, **options: Any) -> DeviceDriver | None:
    """Return a new driver instance for the advertised name, or None."""
    for driver_cls in all_drivers():
        if driver_cls.matches(local_name):
            return driver_cls(**options)
    return None
```

- [ ] **Step 4: Append `BlueDOTDevice` to `ble/bluedot.py`**

Add these imports at the top of `bluedot.py` (keep the existing ones):

```python
import asyncio
import logging
from typing import TYPE_CHECKING

from sensor_state_data import BinarySensorDeviceClass, SensorData, SensorLibrary

from .device import DeviceDriver

if TYPE_CHECKING:
    from bleak import BleakClient

_LOGGER = logging.getLogger(__name__)
```

Append at the end of the file (after `is_bluedot`):

```python
class BlueDOTDevice(DeviceDriver):
    """Driver for the ThermoWorks BlueDOT single-probe thermometer.

    BlueDOT does not expose a readable temperature characteristic; it pushes a
    20-byte notification shortly after a client subscribes. ``async_read``
    subscribes, waits for exactly one notification, and unsubscribes.
    """

    device_type = "BlueDOT"
    min_poll_interval = 30.0

    @classmethod
    def matches(cls, local_name: str | None) -> bool:
        return is_bluedot(local_name)

    async def async_read(self, client: BleakClient, *, timeout: float) -> BlueDOTReading:
        from bleak.exc import BleakError

        reading_event = asyncio.Event()
        reading: BlueDOTReading | None = None

        def _on_notification(_sender: int, data: bytearray) -> None:
            nonlocal reading
            _LOGGER.debug("Received notification: %s", data.hex())
            try:
                reading = parse_notification_data(bytes(data))
            except ValueError:
                _LOGGER.warning("Failed to parse BlueDOT notification: %s", data.hex())
                return
            reading_event.set()

        try:
            await client.start_notify(CHARACTERISTIC_UUID, _on_notification)
        except BleakError as err:
            if "Notify acquired" not in str(err):
                raise
            _LOGGER.debug("Notification already subscribed; retrying after cleanup")
            await asyncio.sleep(0.5)
            try:
                await client.stop_notify(CHARACTERISTIC_UUID)
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass
            await client.start_notify(CHARACTERISTIC_UUID, _on_notification)

        try:
            await asyncio.wait_for(reading_event.wait(), timeout=timeout)
        finally:
            try:
                await client.stop_notify(CHARACTERISTIC_UUID)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error stopping notifications: %s", err)

        assert reading is not None
        return reading

    def apply(self, reading: BlueDOTReading, data: SensorData) -> None:
        data.update_predefined_sensor(
            SensorLibrary.TEMPERATURE__CELSIUS, reading.temperature_celsius
        )
        data.update_binary_sensor(
            key="probe_connected",
            native_value=reading.probe_connected,
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            name="Probe",
        )
        data.update_binary_sensor(
            key="alarm_active",
            native_value=reading.alarm_active,
            device_class=BinarySensorDeviceClass.PROBLEM,
            name="Alarm",
        )
```

Note on imports: `bluedot.py` imports `DeviceDriver` from `device.py` at module top; `device.py` imports the driver classes only inside `all_drivers()`. Keep it that way — a module-level import in `device.py` of any driver module creates a circular import the moment `ble/__init__.py` imports `bluedot` first.

- [ ] **Step 5: Run tests**

Run: `.venv\Scripts\python -m pytest tests/ble -q`
Expected: new tests pass; all existing `test_bluedot.py`/`test_parser.py` still pass (parser is untouched so far).

- [ ] **Step 6: Lint and commit**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
git add custom_components/thermoworks_bt/ble/device.py custom_components/thermoworks_bt/ble/bluedot.py tests/ble/test_device.py
git commit -m "refactor(ble): introduce DeviceDriver abstraction with BlueDOT driver" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: `parser.py` delegates to the driver

**Files:**
- Modify: `custom_components/thermoworks_bt/ble/parser.py` (whole file rewritten below)
- Test: `tests/ble/test_parser.py` (add only; existing tests must pass unchanged)

**Interfaces:**
- Consumes: `driver_for`, `DeviceDriver` (Task 1)
- Produces: `ThermoWorksBluetoothDeviceData(**driver_options)` with unchanged public methods `update()`, `supported()`, `poll_needed()`, `async_poll()`, `get_device_name()`; module constants `MIN_POLL_INTERVAL = 30.0`, `NOTIFICATION_TIMEOUT = 10.0`; property `driver -> DeviceDriver | None`

- [ ] **Step 1: Add failing tests to `tests/ble/test_parser.py`** (append at end of file)

```python
class TestDriverSelection:
    """Tests that the parser selects a driver from the advertised name."""

    def test_driver_is_none_before_update(self) -> None:
        device = ThermoWorksBluetoothDeviceData()
        assert device.driver is None

    def test_driver_selected_on_update(self) -> None:
        from custom_components.thermoworks_bt.ble.bluedot import BlueDOTDevice

        device = ThermoWorksBluetoothDeviceData()
        device.update(_make_service_info(name="BlueDOT"))
        assert isinstance(device.driver, BlueDOTDevice)

    def test_poll_interval_comes_from_driver(self) -> None:
        device = ThermoWorksBluetoothDeviceData()
        device.update(_make_service_info(name="BlueDOT"))
        with patch(
            "custom_components.thermoworks_bt.ble.parser.monotonic_time_coarse",
            return_value=100.0 + device.driver.min_poll_interval + 1,
        ):
            assert device.poll_needed(_make_service_info(), 100.0) is True

    @pytest.mark.asyncio
    async def test_poll_without_driver_raises(self) -> None:
        device = ThermoWorksBluetoothDeviceData()
        ble_device = MagicMock()
        ble_device.address = "AA:BB:CC:DD:EE:FF"
        with pytest.raises(RuntimeError):
            await device.async_poll(ble_device)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/ble/test_parser.py::TestDriverSelection -q`
Expected: FAIL — `driver` attribute does not exist.

- [ ] **Step 3: Rewrite `parser.py`**

```python
"""ThermoWorks BLE device data: connection lifecycle and driver dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from bluetooth_data_tools import monotonic_time_coarse
from bluetooth_sensor_state_data import BluetoothData
from sensor_state_data import SensorUpdate

from .device import DeviceDriver, driver_for

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bluetooth_sensor_state_data import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

# Default minimum seconds between polls; drivers override via min_poll_interval.
MIN_POLL_INTERVAL = 30.0

# Timeout in seconds for each GATT operation during a poll.
NOTIFICATION_TIMEOUT = 10.0


class ThermoWorksBluetoothDeviceData(BluetoothData):
    """Identify a ThermoWorks device from advertisements and poll it via GATT."""

    def __init__(self, **driver_options: Any) -> None:
        super().__init__()
        self._driver_options = driver_options
        self._driver: DeviceDriver | None = None

    @property
    def driver(self) -> DeviceDriver | None:
        """The driver selected from the last advertisement, if any."""
        return self._driver

    def _start_update(self, data: BluetoothServiceInfoBleak) -> None:
        """Select a driver and set device metadata from an advertisement.

        Temperature is never available from advertisements; see async_poll().
        RSSI is updated by the base class after this method.
        """
        _LOGGER.debug(
            "_start_update: name='%s', address=%s, RSSI=%d",
            data.name, data.address, data.rssi,
        )
        driver = driver_for(data.name, **self._driver_options)
        if driver is None:
            _LOGGER.debug("  '%s' is not a supported ThermoWorks device", data.name)
            return
        self._driver = driver
        self.set_device_type(driver.device_type)
        self.set_device_name(driver.device_name(data.name, data.address))
        self.set_device_manufacturer("ThermoWorks")

    def poll_needed(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        """Return True if enough time has passed since the last poll."""
        if last_poll is None:
            _LOGGER.debug("Poll needed for %s: no previous poll", self.get_device_name())
            return True
        interval = self._driver.min_poll_interval if self._driver else MIN_POLL_INTERVAL
        elapsed = monotonic_time_coarse() - last_poll
        needed = elapsed > interval
        _LOGGER.debug(
            "Poll needed check for %s: %.1fs since last poll (min: %.1fs) -> %s",
            self.get_device_name(), elapsed, interval, needed,
        )
        return needed

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """Connect, read one sample through the driver, disconnect."""
        driver = self._driver
        if driver is None:
            raise RuntimeError(
                "No driver selected; update() must see an advertisement first"
            )
        _LOGGER.debug("Polling %s (%s)", self.get_device_name(), ble_device.address)
        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        try:
            reading = await driver.async_read(client, timeout=NOTIFICATION_TIMEOUT)
        finally:
            try:
                await client.disconnect()
                _LOGGER.debug("Disconnected from %s", ble_device.address)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error during disconnect: %s", err)
        driver.apply(reading, self)
        return self._finish_update()
```

- [ ] **Step 4: Run the full BLE suite**

Run: `.venv\Scripts\python -m pytest tests/ble -q`
Expected: all pass, including every pre-existing test in `test_parser.py` (they patch `parser.establish_connection`, `parser.monotonic_time_coarse`, `parser.NOTIFICATION_TIMEOUT` — all still module-level names).

- [ ] **Step 5: Lint and commit**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
git add custom_components/thermoworks_bt/ble/parser.py tests/ble/test_parser.py
git commit -m "refactor(ble): parser delegates reads to DeviceDriver" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Signals pure parsers + 2024 fixture

**Files:**
- Create: `custom_components/thermoworks_bt/ble/signals.py`
- Create: `tests/fixtures/signals/capture-2024-01-v4.21.json`
- Create: `tests/ble/test_signals.py`

**Interfaces:**
- Produces (all in `signals.py`):
  - constants `DEVICE_NAME_PREFIX = "TMW022"`, `NO_PROBE_STATE = 3`, `PROBE_COUNT = 4`, `FIELDS_PER_PROBE = 7`, `UUID_TEMPERATURES`, `UUID_DEVICE_INFO`, `UUID_WIFI`, `UUID_PROBE_CONFIG: tuple[str, str, str, str]` (all lowercase)
  - dataclasses `ProbeTemps(connected: bool, temperature_c: float | None, max_c: float | None, min_c: float | None)`, `ProbeConfig(alarm_high_c: float | None, alarm_low_c: float | None, flag: int, label: str)` (`flag` = raw field 2, semantics unknown — NOT a channel number), `DeviceInfo(battery_pct: int, mac: str, firmware: str, raw_fields: tuple[str, ...])` (battery from field 0, provisional), `WifiInfo(ssid: str, connected: bool, cloud_host: str)`
  - a second fixture `tests/fixtures/signals/capture-2026-09-v4.21-noprobe.json` transcribed from the owner's unit (`docs/captures/recon-2026-09-04-v4.21-noprobe.txt`)
  - `is_signals(name: str | None) -> bool`
  - `parse_temperatures(data: bytes, fahrenheit: bool) -> tuple[ProbeTemps, ...]`
  - `parse_probe_config(data: bytes, fahrenheit: bool) -> ProbeConfig`
  - `parse_device_info(data: bytes) -> DeviceInfo`
  - `parse_wifi(data: bytes) -> WifiInfo`

- [ ] **Step 1: Create the fixture file**

`tests/fixtures/signals/capture-2024-01-v4.21.json` — transcribed from `wnoisephx/thermoworks-ble/Docs/Signals.txt`. Probe 2 and 3 config lines were not in the capture; they are synthesized from probe 1's shape. Field 2 of the probe-config payload is `1` in every captured line — it is a flag, not a channel number.

```json
{
  "source": "https://github.com/wnoisephx/thermoworks-ble/blob/main/Docs/Signals.txt",
  "captured": "2024-01",
  "firmware": "v4.21",
  "scenario": "probe 1 attached, probes 2-4 empty, device in Fahrenheit",
  "local_name": "TMW022",
  "address": "24:62:AB:E0:C1:BE",
  "characteristics": {
    "5f5f9010-0e0d-4bd4-b5dc-e4ff47a45984": {
      "ascii": "71.4,0,71.7,0,70.2,0,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0"
    },
    "0a990c1f-b61a-441c-8f7d-f775b6ff9400": { "ascii": "160,32,1,CH 1,0.0" },
    "f7c21d1c-5cb9-4b9b-ab7e-e1d8e7a51724": { "ascii": "160,32,1,CH 2,0.0" },
    "cfacb2d0-2d81-4c82-a168-13314e38a338": { "ascii": "160,32,1,CH 3,0.0" },
    "c99c943f-da4b-4ee3-92ec-c806006e9e7f": { "ascii": "160,32,1,CH 4,0,0,255,0" },
    "3ce0c366-691f-43e6-b625-3f0912ff6ea7": { "ascii": "100,67,0,24:62:ab:e0:c1:be,v4.21" },
    "b4f1d66a-ecab-4e03-8b43-b9df904ebcdf": { "ascii": "MyWifi,1,iotservice.thermoworks.com,1" }
  }
}
```

`tests/fixtures/signals/capture-2026-09-v4.21-noprobe.json` — transcribed verbatim from `docs/captures/recon-2026-09-04-v4.21-noprobe.txt` (owner's unit, no probes attached). Note the trailing commas and 4-character labels; these are what the device really sends.

```json
{
  "source": "docs/captures/recon-2026-09-04-v4.21-noprobe.txt",
  "captured": "2026-09-04",
  "firmware": "v4.21",
  "scenario": "no probes attached, phone app closed, device presumed Fahrenheit",
  "local_name": "TMW022",
  "address": "24:0A:C4:EC:2E:0E",
  "characteristics": {
    "5f5f9010-0e0d-4bd4-b5dc-e4ff47a45984": {
      "ascii": "-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,"
    },
    "0a990c1f-b61a-441c-8f7d-f775b6ff9400": { "ascii": "360,225,0,Gril,0.0," },
    "f7c21d1c-5cb9-4b9b-ab7e-e1d8e7a51724": { "ascii": "120,32,1,Roas,0.0," },
    "cfacb2d0-2d81-4c82-a168-13314e38a338": { "ascii": "120,32,1,Roas,0.0," },
    "c99c943f-da4b-4ee3-92ec-c806006e9e7f": { "ascii": "160,32,0,CH 4,0.0,225,0" },
    "3ce0c366-691f-43e6-b625-3f0912ff6ea7": { "ascii": "66,0,0,24:0a:c4:ec:2e:0e,v4.21," },
    "b4f1d66a-ecab-4e03-8b43-b9df904ebcdf": { "ascii": "Mo2Net,1,iotservice.thermoworks.com,1" }
  }
}
```

- [ ] **Step 2: Write the failing tests**

`tests/ble/test_signals.py`:

```python
"""Tests for the ThermoWorks Signals driver and parsers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.thermoworks_bt.ble import signals
from custom_components.thermoworks_bt.ble.signals import (
    UUID_DEVICE_INFO,
    UUID_PROBE_CONFIG,
    UUID_TEMPERATURES,
    UUID_WIFI,
    DeviceInfo,
    ProbeConfig,
    ProbeTemps,
    WifiInfo,
    is_signals,
    parse_device_info,
    parse_probe_config,
    parse_temperatures,
    parse_wifi,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "signals"


def load_capture(name: str = "capture-2024-01-v4.21.json") -> dict[str, bytes]:
    """Return {uuid: payload bytes} from a capture fixture."""
    doc = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    out: dict[str, bytes] = {}
    for uuid, entry in doc["characteristics"].items():
        if "hex" in entry:
            out[uuid.lower()] = bytes.fromhex(entry["hex"])
        else:
            out[uuid.lower()] = entry["ascii"].encode("ascii")
    return out


@pytest.fixture
def capture() -> dict[str, bytes]:
    return load_capture()


class TestIsSignals:
    def test_prefix_match(self) -> None:
        assert is_signals("TMW022") is True
        assert is_signals("TMW022-ABCD") is True

    def test_rejects_other_and_none(self) -> None:
        assert is_signals("BlueDOT") is False
        assert is_signals("TMW") is False
        assert is_signals(None) is False


class TestParseTemperatures:
    def test_fixture_probe_1_attached_in_fahrenheit(self, capture) -> None:
        probes = parse_temperatures(capture[UUID_TEMPERATURES], fahrenheit=True)
        assert len(probes) == 4
        p1 = probes[0]
        assert p1.connected is True
        assert p1.temperature_c == pytest.approx(21.9, abs=0.05)  # 71.4F
        assert p1.max_c == pytest.approx(22.1, abs=0.05)          # 71.7F
        assert p1.min_c == pytest.approx(21.2, abs=0.05)          # 70.2F

    def test_fixture_empty_probes_are_disconnected_with_none(self, capture) -> None:
        probes = parse_temperatures(capture[UUID_TEMPERATURES], fahrenheit=True)
        for p in probes[1:]:
            assert p == ProbeTemps(connected=False, temperature_c=None, max_c=None, min_c=None)

    def test_celsius_passthrough(self) -> None:
        payload = b"21.9,0,22.1,0,21.2,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        probes = parse_temperatures(payload, fahrenheit=False)
        assert probes[0].temperature_c == 21.9

    def test_negative_temperature_fahrenheit(self) -> None:
        payload = b"-4.0,0,10.0,0,-10.0,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        probes = parse_temperatures(payload, fahrenheit=True)
        assert probes[0].temperature_c == -20.0

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 28 fields"):
            parse_temperatures(b"71.4,0,71.7,0", fahrenheit=True)

    def test_non_numeric_raises(self) -> None:
        payload = b"abc,0,71.7,0,70.2,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3
        with pytest.raises(ValueError):
            parse_temperatures(payload, fahrenheit=True)

    def test_extra_trailing_fields_ignored(self) -> None:
        payload = b"71.4,0,71.7,0,70.2,0,0" + b",-63.0,3,-63.0,3,-63.0,3,0" * 3 + b",255,0"
        assert len(parse_temperatures(payload, fahrenheit=True)) == 4


class TestParseProbeConfig:
    def test_fixture_probe_1(self, capture) -> None:
        cfg = parse_probe_config(capture[UUID_PROBE_CONFIG[0]], fahrenheit=True)
        assert cfg.alarm_high_c == pytest.approx(71.1, abs=0.05)
        assert cfg.alarm_low_c == pytest.approx(0.0, abs=0.05)
        assert cfg.flag == 1
        assert cfg.label == "CH 1"

    def test_fixture_probe_4_with_trailing_fields(self, capture) -> None:
        cfg = parse_probe_config(capture[UUID_PROBE_CONFIG[3]], fahrenheit=True)
        assert cfg.flag == 1
        assert cfg.label == "CH 4"

    def test_celsius_passthrough_and_custom_label(self) -> None:
        cfg = parse_probe_config(b"95,60,0,Bris,0.0,", fahrenheit=False)
        assert cfg.alarm_high_c == 95.0
        assert cfg.alarm_low_c == 60.0
        assert cfg.flag == 0
        assert cfg.label == "Bris"

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 4 fields"):
            parse_probe_config(b"160,32", fahrenheit=True)


class TestParseDeviceInfo:
    def test_fixture(self, capture) -> None:
        info = parse_device_info(capture[UUID_DEVICE_INFO])
        assert info.battery_pct == 100
        assert info.mac == "24:62:ab:e0:c1:be"
        assert info.firmware == "v4.21"
        assert info.raw_fields[1] == "67"

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 5 fields"):
            parse_device_info(b"100,67")

    def test_battery_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_device_info(b"150,0,0,aa:bb:cc:dd:ee:ff,v4.21")


class TestCapture2026:
    """Real payloads from the owner's unit: trailing commas, 4-char labels."""

    @pytest.fixture
    def capture26(self) -> dict[str, bytes]:
        return load_capture("capture-2026-09-v4.21-noprobe.json")

    def test_trailing_comma_and_no_probes(self, capture26) -> None:
        probes = parse_temperatures(capture26[UUID_TEMPERATURES], fahrenheit=True)
        assert len(probes) == 4
        assert all(not p.connected and p.temperature_c is None for p in probes)

    def test_probe_config_flag_and_truncated_label(self, capture26) -> None:
        cfg = parse_probe_config(capture26[UUID_PROBE_CONFIG[0]], fahrenheit=True)
        assert cfg.flag == 0
        assert cfg.label == "Gril"
        assert cfg.alarm_high_c == pytest.approx(182.2, abs=0.05)  # 360F
        assert cfg.alarm_low_c == pytest.approx(107.2, abs=0.05)   # 225F
        assert parse_probe_config(capture26[UUID_PROBE_CONFIG[1]], fahrenheit=True).flag == 1

    def test_probe_4_extra_fields_ignored(self, capture26) -> None:
        cfg = parse_probe_config(capture26[UUID_PROBE_CONFIG[3]], fahrenheit=True)
        assert cfg.label == "CH 4"
        assert cfg.flag == 0

    def test_device_info_battery_is_field_0(self, capture26) -> None:
        info = parse_device_info(capture26[UUID_DEVICE_INFO])
        assert info.battery_pct == 66
        assert info.mac == "24:0a:c4:ec:2e:0e"
        assert info.firmware == "v4.21"

    def test_wifi(self, capture26) -> None:
        assert parse_wifi(capture26[UUID_WIFI]).ssid == "Mo2Net"


class TestParseWifi:
    def test_fixture(self, capture) -> None:
        wifi = parse_wifi(capture[UUID_WIFI])
        assert wifi == WifiInfo(
            ssid="MyWifi", connected=True, cloud_host="iotservice.thermoworks.com"
        )

    def test_disconnected(self) -> None:
        wifi = parse_wifi(b"MyWifi,0,iotservice.thermoworks.com,0")
        assert wifi.connected is False

    def test_too_few_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="expected at least 2 fields"):
            parse_wifi(b"MyWifi")
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py -q`
Expected: ImportError — `signals` module does not exist.

- [ ] **Step 4: Create `ble/signals.py` (parsers only; the driver class is Task 5)**

```python
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
            f"Signals {what}: expected at least {minimum} fields, got {len(fields)}: {text!r}"
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
                temperature_c=_to_celsius(float(fields[base + _TEMP_INDEX]), fahrenheit),
                max_c=_to_celsius(float(fields[base + _MAX_INDEX]), fahrenheit),
                min_c=_to_celsius(float(fields[base + _MIN_INDEX]), fahrenheit),
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
```

- [ ] **Step 5: Run tests**

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py -q`
Expected: all pass. If `test_negative_temperature_fahrenheit` fails on rounding, check `_to_celsius`: (−4 − 32) × 5/9 = −20.0 exactly.

- [ ] **Step 6: Lint and commit**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
git add custom_components/thermoworks_bt/ble/signals.py tests/ble/test_signals.py tests/fixtures/signals/
git commit -m "feat(signals): add Signals CSV parsers with capture fixtures" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: `alarm_state` and `SignalsDevice.apply`

**Files:**
- Modify: `custom_components/thermoworks_bt/ble/signals.py` (append)
- Test: `tests/ble/test_signals.py` (append)

**Interfaces:**
- Consumes: Task 3 dataclasses; `DeviceDriver` (Task 1)
- Produces:
  - `SignalsReading(probes: tuple[ProbeTemps, ...], configs: tuple[ProbeConfig | None, ...], info: DeviceInfo | None, wifi: WifiInfo | None)`
  - `alarm_state(probe: ProbeTemps, cfg: ProbeConfig | None) -> tuple[bool | None, bool | None]`
  - `class SignalsDevice(DeviceDriver)` with `device_type = "Signals"`, `min_poll_interval = 30.0`, `matches`, `device_name`, `apply` (and `async_read` in Task 5)
  - Entity keys emitted by `apply` (n = 1..4): sensors `probe_{n}_temperature`, `probe_{n}_max`, `probe_{n}_min`, `probe_{n}_alarm_high_setpoint`, `probe_{n}_alarm_low_setpoint`, `probe_{n}_channel_label`, `battery`; binary sensors `probe_{n}_connected`, `probe_{n}_alarm_high`, `probe_{n}_alarm_low`, `wifi_connected`

- [ ] **Step 1: Append failing tests to `tests/ble/test_signals.py`**

```python
from sensor_state_data import SensorData

from custom_components.thermoworks_bt.ble.signals import (
    SignalsDevice,
    SignalsReading,
    alarm_state,
)

ATTACHED = ProbeTemps(connected=True, temperature_c=90.0, max_c=95.0, min_c=20.0)
EMPTY = ProbeTemps(connected=False, temperature_c=None, max_c=None, min_c=None)
CFG = ProbeConfig(alarm_high_c=93.0, alarm_low_c=60.0, flag=1, label="CH 1")


class TestAlarmState:
    @pytest.mark.parametrize(
        ("temp", "expected"),
        [(92.9, (False, False)), (93.0, (True, False)), (60.0, (False, True)), (59.0, (False, True))],
    )
    def test_thresholds_inclusive(self, temp, expected) -> None:
        probe = ProbeTemps(connected=True, temperature_c=temp, max_c=temp, min_c=temp)
        assert alarm_state(probe, CFG) == expected

    def test_disconnected_probe_is_not_alarming(self) -> None:
        assert alarm_state(EMPTY, CFG) == (False, False)

    def test_missing_config_is_unknown(self) -> None:
        assert alarm_state(ATTACHED, None) == (None, None)


def _reading(**overrides) -> SignalsReading:
    base = dict(
        probes=(ATTACHED, EMPTY, EMPTY, EMPTY),
        configs=(CFG, CFG, CFG, CFG),
        info=DeviceInfo(battery_pct=67, mac="24:62:ab:e0:c1:be", firmware="v4.21", raw_fields=()),
        wifi=WifiInfo(ssid="x", connected=True, cloud_host="h"),
    )
    base.update(overrides)
    return SignalsReading(**base)


def _apply(reading: SignalsReading):
    data = SensorData()
    SignalsDevice().apply(reading, data)
    update = data._finish_update()
    sensors = {k.key: v.native_value for k, v in update.entity_values.items()}
    binaries = {k.key: v.native_value for k, v in update.binary_entity_values.items()}
    return sensors, binaries, update


class TestSignalsDeviceApply:
    def test_class_attributes_and_matching(self) -> None:
        assert SignalsDevice.device_type == "Signals"
        assert SignalsDevice.min_poll_interval == 30.0
        assert SignalsDevice.matches("TMW022") is True
        assert SignalsDevice.matches("BlueDOT") is False

    def test_device_name_uses_mac_suffix(self) -> None:
        assert SignalsDevice().device_name("TMW022", "24:62:AB:E0:C1:BE") == "Signals C1BE"

    def test_attached_probe_emits_values(self) -> None:
        sensors, binaries, _ = _apply(_reading())
        assert sensors["probe_1_temperature"] == 90.0
        assert sensors["probe_1_max"] == 95.0
        assert sensors["probe_1_min"] == 20.0
        assert sensors["probe_1_alarm_high_setpoint"] == 93.0
        assert sensors["probe_1_alarm_low_setpoint"] == 60.0
        assert sensors["probe_1_channel_label"] == "CH 1"
        assert binaries["probe_1_connected"] is True
        assert binaries["probe_1_alarm_high"] is False
        assert binaries["probe_1_alarm_low"] is False

    def test_empty_probe_emits_none_not_missing(self) -> None:
        sensors, binaries, _ = _apply(_reading())
        assert "probe_2_temperature" in sensors and sensors["probe_2_temperature"] is None
        assert sensors["probe_2_max"] is None
        assert binaries["probe_2_connected"] is False
        assert binaries["probe_2_alarm_high"] is False

    def test_missing_config_emits_none(self) -> None:
        sensors, binaries, _ = _apply(_reading(configs=(None, CFG, CFG, CFG)))
        assert sensors["probe_1_alarm_high_setpoint"] is None
        assert sensors["probe_1_channel_label"] is None
        assert binaries["probe_1_alarm_high"] is None

    def test_missing_info_and_wifi_emit_none(self) -> None:
        sensors, binaries, _ = _apply(_reading(info=None, wifi=None))
        assert sensors["battery"] is None
        assert binaries["wifi_connected"] is None

    def test_battery_and_wifi_and_firmware(self) -> None:
        sensors, binaries, update = _apply(_reading())
        assert sensors["battery"] == 67
        assert binaries["wifi_connected"] is True
        device = next(iter(update.devices.values()))
        assert device.sw_version == "v4.21"

    def test_all_keys_always_present(self) -> None:
        sensors, binaries, _ = _apply(_reading(configs=(None,) * 4, info=None, wifi=None))
        for n in range(1, 5):
            for key in ("temperature", "max", "min", "alarm_high_setpoint",
                        "alarm_low_setpoint", "channel_label"):
                assert f"probe_{n}_{key}" in sensors
            for key in ("connected", "alarm_high", "alarm_low"):
                assert f"probe_{n}_{key}" in binaries
        assert "battery" in sensors and "wifi_connected" in binaries
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py -q`
Expected: ImportError on `SignalsDevice`.

- [ ] **Step 3: Append to `ble/signals.py`**

Add imports at the top of the file:

```python
import logging
from typing import TYPE_CHECKING

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
```

Append after `parse_wifi`:

```python
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
            fahrenheit: Assumed device display unit until a unit flag is located
                (see docs/protocol/signals-ble.md, "Open questions").
        """
        super().__init__(fahrenheit=fahrenheit, **options)
        self.fahrenheit = fahrenheit

    @classmethod
    def matches(cls, local_name: str | None) -> bool:
        return is_signals(local_name)

    def device_name(self, local_name: str | None, address: str) -> str:
        suffix = address.replace(":", "").replace("-", "")[-4:].upper()
        return f"Signals {suffix}"

    def apply(self, reading: SignalsReading, data: SensorData) -> None:
        for n, probe in enumerate(reading.probes, start=1):
            cfg = reading.configs[n - 1] if n - 1 < len(reading.configs) else None
            high, low = alarm_state(probe, cfg)
            self._temp(data, f"probe_{n}_temperature", f"Probe {n} Temperature", probe.temperature_c)
            self._temp(data, f"probe_{n}_max", f"Probe {n} Session Max", probe.max_c)
            self._temp(data, f"probe_{n}_min", f"Probe {n} Session Min", probe.min_c)
            self._temp(
                data, f"probe_{n}_alarm_high_setpoint", f"Probe {n} High Alarm Setpoint",
                cfg.alarm_high_c if cfg else None,
            )
            self._temp(
                data, f"probe_{n}_alarm_low_setpoint", f"Probe {n} Low Alarm Setpoint",
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
        data.update_sensor(
            key=key,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
            native_value=value,
            device_class=SensorDeviceClass.TEMPERATURE,
            name=name,
        )
```

`async_read` is still abstract at this point, so `SignalsDevice()` cannot be instantiated. For this task only, add a temporary stub inside the class so tests run — it is replaced in Task 5:

```python
    async def async_read(self, client: BleakClient, *, timeout: float) -> SignalsReading:
        raise NotImplementedError("implemented in Task 5")
```

- [ ] **Step 4: Run tests**

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py -q`
Expected: all pass. If `update_predefined_sensor` rejects `None`, replace that call with `data.update_sensor(key="battery", native_unit_of_measurement=Units.PERCENTAGE, native_value=..., device_class=SensorDeviceClass.BATTERY, name="Battery")` — same effect.

- [ ] **Step 5: Lint and commit**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
git add custom_components/thermoworks_bt/ble/signals.py tests/ble/test_signals.py
git commit -m "feat(signals): SignalsDevice.apply with derived alarm state" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: `SignalsDevice.async_read`, driver registration, exports

**Files:**
- Modify: `custom_components/thermoworks_bt/ble/signals.py` (replace the stub)
- Modify: `custom_components/thermoworks_bt/ble/device.py` (register driver)
- Modify: `custom_components/thermoworks_bt/ble/__init__.py`
- Test: `tests/ble/test_signals.py` (append), `tests/ble/test_device.py` (append)

**Interfaces:**
- Consumes: `parse_*`, `SignalsReading` (Tasks 3–4)
- Produces: `SignalsDevice.async_read(client, *, timeout) -> SignalsReading`; `all_drivers() == (BlueDOTDevice, SignalsDevice)`; `ble/__init__` exports `SignalsDevice`, `SignalsReading`, `is_signals`, `driver_for`, `all_drivers`, `DeviceDriver`, `BlueDOTDevice`

- [ ] **Step 1: Append failing tests to `tests/ble/test_signals.py`**

```python
import asyncio


class FakeClient:
    """Minimal BleakClient stand-in keyed by lowercase UUID."""

    def __init__(self, responses: dict[str, bytes | Exception], delay: float = 0.0):
        self.responses = responses
        self.delay = delay
        self.reads: list[str] = []

    async def read_gatt_char(self, uuid):
        uuid = str(uuid).lower()
        self.reads.append(uuid)
        if self.delay:
            await asyncio.sleep(self.delay)
        value = self.responses[uuid]
        if isinstance(value, Exception):
            raise value
        return bytearray(value)


class TestSignalsAsyncRead:
    @pytest.mark.asyncio
    async def test_full_read_from_fixture(self, capture) -> None:
        client = FakeClient(capture)
        reading = await SignalsDevice().async_read(client, timeout=1.0)
        assert reading.probes[0].connected is True
        assert reading.configs[3].flag == 1
        assert reading.info.firmware == "v4.21"
        assert reading.wifi.connected is True

    @pytest.mark.asyncio
    async def test_reads_device_info_before_temperatures(self, capture) -> None:
        client = FakeClient(capture)
        await SignalsDevice().async_read(client, timeout=1.0)
        assert client.reads.index(UUID_DEVICE_INFO) < client.reads.index(UUID_TEMPERATURES)

    @pytest.mark.asyncio
    async def test_temperature_read_failure_raises(self, capture) -> None:
        capture[UUID_TEMPERATURES] = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await SignalsDevice().async_read(FakeClient(capture), timeout=1.0)

    @pytest.mark.asyncio
    async def test_temperature_parse_failure_raises(self, capture) -> None:
        capture[UUID_TEMPERATURES] = b"garbage"
        with pytest.raises(ValueError):
            await SignalsDevice().async_read(FakeClient(capture), timeout=1.0)

    @pytest.mark.asyncio
    async def test_optional_read_failures_degrade_to_none(self, capture) -> None:
        capture[UUID_DEVICE_INFO] = RuntimeError("boom")
        capture[UUID_WIFI] = b"bad"
        capture[UUID_PROBE_CONFIG[1]] = RuntimeError("boom")
        reading = await SignalsDevice().async_read(FakeClient(capture), timeout=1.0)
        assert reading.info is None
        assert reading.wifi is None
        assert reading.configs[0] is not None
        assert reading.configs[1] is None

    @pytest.mark.asyncio
    async def test_read_timeout_raises(self, capture) -> None:
        with pytest.raises(asyncio.TimeoutError):
            await SignalsDevice().async_read(FakeClient(capture, delay=0.2), timeout=0.05)
```

Append to `tests/ble/test_device.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py::TestSignalsAsyncRead tests/ble/test_device.py::TestDriverRegistry -q`
Expected: FAIL — `NotImplementedError`, `driver_for("TMW022")` is None, exports missing.

- [ ] **Step 3: Replace the stub in `signals.py` with the real `async_read`**

```python
    async def async_read(self, client: BleakClient, *, timeout: float) -> SignalsReading:
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
            await self._read_optional(
                client, uuid, lambda b: parse_probe_config(b, fahrenheit), timeout,
                f"probe {n} config",
            )
            for n, uuid in enumerate(UUID_PROBE_CONFIG, start=1)
        )
        return SignalsReading(probes=probes, configs=configs, info=info, wifi=wifi)

    @staticmethod
    async def _read_optional(client, uuid, parse, timeout, what):
        """Read + parse one characteristic; return None on any failure except timeout."""
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
```

Add `import asyncio` to the top of `signals.py`.

- [ ] **Step 4: Register the driver in `device.py`**

Replace the body of `all_drivers()`:

```python
def all_drivers() -> tuple[type[DeviceDriver], ...]:
    """Return every known driver class, in match-priority order.

    Driver modules import ``DeviceDriver`` from this module, so they are
    imported lazily here rather than at module load to avoid a circular import.
    """
    from .bluedot import BlueDOTDevice
    from .signals import SignalsDevice

    return (BlueDOTDevice, SignalsDevice)
```

- [ ] **Step 5: Update `ble/__init__.py`**

```python
"""ThermoWorks BLE parsing library."""

from .bluedot import BlueDOTDevice, BlueDOTReading, is_bluedot, parse_notification_data
from .device import DeviceDriver, all_drivers, driver_for
from .parser import ThermoWorksBluetoothDeviceData
from .signals import SignalsDevice, SignalsReading, is_signals

__all__ = [
    "BlueDOTDevice",
    "BlueDOTReading",
    "DeviceDriver",
    "SignalsDevice",
    "SignalsReading",
    "ThermoWorksBluetoothDeviceData",
    "all_drivers",
    "driver_for",
    "is_bluedot",
    "is_signals",
    "parse_notification_data",
]
```

- [ ] **Step 6: Run the full BLE suite**

Run: `.venv\Scripts\python -m pytest tests/ble -q`
Expected: all pass.

- [ ] **Step 7: Lint, commit, push (first CI run — confirms the refactor against upstream's HA tests)**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
git add custom_components/thermoworks_bt/ble tests/ble
git commit -m "feat(signals): async_read over GATT and driver registration" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
git push -u origin feature/signals
```

Then check `https://github.com/sjmotew/thermoworks-ha/actions`: hassfest + HACS validation green, and in the "Run HA integration tests" log all upstream `tests/ha` tests `PASSED` (that step never fails the run — read it).

---

### Task 6: Home Assistant layer

**Files:**
- Modify: `custom_components/thermoworks_bt/sensor.py`
- Modify: `custom_components/thermoworks_bt/binary_sensor.py`
- Modify: `custom_components/thermoworks_bt/manifest.json`
- Modify (add only): `tests/ha/__init__.py`, `tests/ha/test_config_flow.py`, `tests/ha/test_sensor.py`

**Interfaces:**
- Consumes: entity keys from Task 4
- Produces: `SENSOR_DESCRIPTION_OVERRIDES`, `BINARY_SENSOR_DESCRIPTION_OVERRIDES`; `TMW022*` discovery

- [ ] **Step 1: Add Signals service info to `tests/ha/__init__.py`** (append)

```python
SIGNALS_SERVICE_INFO = _make_bluetooth_service_info(
    name="TMW022",
    address="24:62:AB:E0:C1:BE",
    rssi=-66,
    manufacturer_data={25124: b"\xab\xe0\xc1\xbe"},
)
```

- [ ] **Step 2: Append failing tests**

`tests/ha/test_config_flow.py`:

```python
async def test_bluetooth_discovery_signals(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a Signals device."""
    from . import SIGNALS_SERVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SIGNALS_SERVICE_INFO,
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
    assert result2["title"] == "Signals C1BE"
    assert result2["result"].unique_id == "24:62:AB:E0:C1:BE"
```

`tests/ha/test_sensor.py` (mirrors upstream's `test_sensors_created_from_poll`; entity-level assertions are done on the live instance in Step 9 instead, because this test cannot be run locally):

```python
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
```

`sensor.py` imports Home Assistant, so the description-lookup logic cannot be unit-tested locally; it is exercised by the live-instance check in Step 9.

- [ ] **Step 3: Verify the BLE suite still passes** (the HA tests are verified by CI in Step 8)

Run: `.venv\Scripts\python -m pytest tests/ble -q`
Expected: all pass.

- [ ] **Step 4: Modify `sensor.py`**

Replace the `SENSOR_DESCRIPTIONS` block and the lookup with:

```python
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)

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


def _description_for(device_key: DeviceKey, description) -> SensorEntityDescription | None:
    """Pick the HA entity description for a sensor-state-data description."""
    if (override := SENSOR_DESCRIPTION_OVERRIDES.get(device_key.key)) is not None:
        return override
    return SENSOR_DESCRIPTIONS.get(
        (description.device_class, description.native_unit_of_measurement)
    )
```

Then in `sensor_update_to_bluetooth_data_update`, replace the `entity_descriptions=` comprehension with:

```python
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): ha_description
            for device_key, description in sensor_update.entity_descriptions.items()
            if (ha_description := _description_for(device_key, description)) is not None
        },
```

Widen the entity generic and value type:

```python
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
```

- [ ] **Step 5: Modify `binary_sensor.py`**

After `BINARY_SENSOR_DESCRIPTIONS`, add:

```python
from homeassistant.const import EntityCategory

BINARY_SENSOR_DESCRIPTION_OVERRIDES: dict[str, BinarySensorEntityDescription] = {
    "wifi_connected": BinarySensorEntityDescription(
        key="wifi_connected",
        device_class=HABinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def _description_for(device_key: DeviceKey, description) -> BinarySensorEntityDescription | None:
    if (override := BINARY_SENSOR_DESCRIPTION_OVERRIDES.get(device_key.key)) is not None:
        return override
    return BINARY_SENSOR_DESCRIPTIONS.get(description.device_class)
```

And replace the `entity_descriptions=` comprehension in `binary_sensor_update_to_bluetooth_data_update` with:

```python
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): ha_description
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if (ha_description := _description_for(device_key, description)) is not None
        },
```

- [ ] **Step 6: Modify `manifest.json`**

```json
  "bluetooth": [
    {
      "local_name": "BlueDOT*",
      "connectable": true
    },
    {
      "local_name": "TMW022*",
      "connectable": true
    }
  ],
```

- [ ] **Step 7: Lint, run BLE suite, commit, push**

```powershell
.venv\Scripts\python -m ruff check custom_components tests
.venv\Scripts\python -m pytest tests/ble -q
git add custom_components/thermoworks_bt/sensor.py custom_components/thermoworks_bt/binary_sensor.py custom_components/thermoworks_bt/manifest.json tests/ha
git commit -m "feat(signals): HA entities, diagnostic overrides, TMW022 discovery" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
git push -u origin feature/signals
```

- [ ] **Step 8: Check CI**

Open `https://github.com/sjmotew/thermoworks-ha/actions` (or `gh run list --branch feature/signals` then `gh run view <id> --log`). Confirm: HACS validation and hassfest pass; in the "Run HA integration tests" step log, `test_bluetooth_discovery_signals` and `test_signals_entry_loads` show `PASSED`. Fix and re-push until they do.

- [ ] **Step 9: Deploy to the live Home Assistant and confirm it loads (no Signals hardware needed)**

Using the Home Assistant MCP tools, write each of these files to `custom_components/thermoworks_bt/<same relative path>` with `ha_write_file` (description: "thermoworks_bt: Signals support, feature/signals @ <short sha>"):

```
__init__.py  binary_sensor.py  config_flow.py  const.py  coordinator.py  manifest.json  sensor.py  strings.json
ble/__init__.py  ble/bluedot.py  ble/device.py  ble/parser.py  ble/signals.py
```

(The `brand/*.png` files are HACS/brand assets only and are not needed at runtime. If `ha_write_file` cannot create the `ble/` directory, fall back to installing via HACS → Custom repositories → `https://github.com/sjmotew/thermoworks-ha` → Redownload → pick branch `feature/signals`.)

Then `ha_restart`, wait ~60 s, and `ha_get_logs(level="ERROR")` — there must be no entries mentioning `thermoworks_bt`. `ha_get_logs(level="WARNING")` should not show `thermoworks_bt` import/setup warnings either. In the HA UI, Settings → Devices & Services → Add Integration → "ThermoWorks Bluetooth" must be listed (this proves the manifest loaded).

---

### Task 7: Phase 1 dump script and protocol docs

**Files:**
- Create: `scripts/dump_signals.py`
- Create: `docs/protocol/signals-ble.md`
- Create: `docs/protocol/phase1-verification.md`
- Create: `docs/captures/.gitkeep`

**Interfaces:**
- Produces: JSON captures in `docs/captures/` with the same schema as `tests/fixtures/signals/capture-2024-01-v4.21.json` plus `hex` per characteristic and a `notifications` list.

- [ ] **Step 1: Write `scripts/dump_signals.py`**

```python
#!/usr/bin/env python3
"""Read-only dump of every GATT characteristic on a ThermoWorks Signals.

Usage:
    python scripts/dump_signals.py --scan
    python scripts/dump_signals.py <ADDRESS> --scenario baseline [--listen 60]

Writes docs/captures/signals-<firmware>-<UTC timestamp>-<scenario>.json.
This script NEVER writes to the device.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("bleak is required: pip install bleak")
    sys.exit(1)

PREFIX = "TMW022"
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "captures"
UUID_DEVICE_INFO = "3ce0c366-691f-43e6-b625-3f0912ff6ea7"


def _ascii(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace")


async def scan(timeout: float) -> list[tuple[str, str]]:
    print(f"Scanning {timeout:.0f}s for {PREFIX}* ...")
    found = []
    for dev, adv in (await BleakScanner.discover(timeout=timeout, return_adv=True)).values():
        if dev.name and dev.name.startswith(PREFIX):
            found.append((dev.address, dev.name))
            print(f"  {dev.name}  {dev.address}  RSSI {adv.rssi}  mfr={adv.manufacturer_data}")
    if not found:
        print("  none found (is the unit on, Bluetooth enabled, and the phone app closed?)")
    return found


async def dump(address: str, scenario: str, listen: float) -> Path:
    result: dict = {
        "captured": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario,
        "address": address,
        "services": [],
        "characteristics": {},
        "notifications": [],
    }
    print(f"Connecting to {address} ...")
    async with BleakClient(address) as client:
        print("Connected. Enumerating services ...")
        for service in client.services:
            svc = {"uuid": service.uuid, "description": service.description, "chars": []}
            for ch in service.characteristics:
                svc["chars"].append({"uuid": ch.uuid, "properties": list(ch.properties)})
                entry: dict = {"properties": list(ch.properties), "service": service.uuid}
                if "read" in ch.properties:
                    try:
                        raw = bytes(await client.read_gatt_char(ch))
                        entry["hex"] = raw.hex()
                        entry["ascii"] = _ascii(raw)
                        print(f"  READ   {ch.uuid}: {entry['ascii']!r}")
                    except Exception as err:  # noqa: BLE001
                        entry["error"] = repr(err)
                        print(f"  READ   {ch.uuid}: ERROR {err!r}")
                else:
                    print(f"  SKIP   {ch.uuid}: {ch.properties}")
                result["characteristics"][ch.uuid.lower()] = entry
            result["services"].append(svc)

        info = result["characteristics"].get(UUID_DEVICE_INFO, {}).get("ascii", "")
        firmware = info.split(",")[4].strip() if info.count(",") >= 4 else "unknown"
        result["firmware"] = firmware

        notify_chars = [
            ch for s in client.services for ch in s.characteristics
            if "notify" in ch.properties or "indicate" in ch.properties
        ]
        if notify_chars and listen > 0:
            print(f"Subscribing to {len(notify_chars)} notify-capable characteristics for {listen:.0f}s ...")

            def _handler_for(uuid: str):
                def _h(_sender, data: bytearray) -> None:
                    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                    raw = bytes(data)
                    result["notifications"].append(
                        {"time": ts, "uuid": uuid, "hex": raw.hex(), "ascii": _ascii(raw)}
                    )
                    print(f"  NOTIFY {uuid}: {_ascii(raw)!r}")
                return _h

            subscribed = []
            for ch in notify_chars:
                try:
                    await client.start_notify(ch, _handler_for(ch.uuid.lower()))
                    subscribed.append(ch)
                except Exception as err:  # noqa: BLE001
                    print(f"  notify subscribe failed {ch.uuid}: {err!r}")
            try:
                await asyncio.sleep(listen)
            finally:
                for ch in subscribed:
                    try:
                        await client.stop_notify(ch)
                    except Exception:  # noqa: BLE001
                        pass

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"signals-{firmware}-{stamp}-{scenario}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("address", nargs="?", help="BLE address (or omit with --scan)")
    p.add_argument("--scan", action="store_true", help="scan for Signals units and exit")
    p.add_argument("--scenario", default="baseline", help="label for this capture")
    p.add_argument("--listen", type=float, default=60.0, help="seconds to listen for notifications")
    p.add_argument("--timeout", type=float, default=10.0, help="scan timeout")
    args = p.parse_args()

    if args.scan:
        asyncio.run(scan(args.timeout))
        return
    address = args.address
    if not address:
        found = asyncio.run(scan(args.timeout))
        if len(found) != 1:
            p.error("pass the address explicitly")
        address = found[0][0]
    asyncio.run(dump(address, args.scenario, args.listen))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test without hardware**

Run: `.venv\Scripts\python scripts/dump_signals.py --help`
Expected: usage text, exit 0. Run: `.venv\Scripts\python -m ruff check scripts` — clean.

- [ ] **Step 3: Write `docs/protocol/signals-ble.md`**

Copy spec §3 verbatim as the body, under a heading "# ThermoWorks Signals BLE protocol", and add these two sections at the end:

```markdown
## Verification status

| Item | 2024 capture | Phase 1 (fill in) |
|---|---|---|
| Firmware | v4.21 | |
| Temperature layout (28 fields) | observed | |
| No-probe sentinel `-63.0,3` | observed | |
| Probe config layout | observed (probes 1 & 4) | |
| Device info: battery at field 1 | inferred | |
| Unit flag location | unknown | |
| Any characteristic notifies? | unknown | |
| Read latency for 7 reads on ESP32 proxy | unknown | |

## Open questions

1. Where is the °F/°C flag? Candidates: device-info field 0 or 2, or one of the unknown characteristics.
2. Does `32` as a low alarm mean "disabled" (32 °F = 0 °C is the device default)?
3. Do the 7 unknown characteristics carry `write` or `notify` properties? (The dump script records properties without writing.)
```

- [ ] **Step 4: Write `docs/protocol/phase1-verification.md`**

```markdown
# Phase 1 — Signals protocol verification checklist

Hardware: Signals unit (powered, Bluetooth on, **ThermoWorks app closed on every phone** — the app holds the only BLE connection), a PC/Mac with Bluetooth, repo venv with `bleak`.

Each scenario produces one JSON file in `docs/captures/`. Run from the repo root.

| # | Scenario flag | Device setup before running | What it answers |
|---|---|---|---|
| 1 | `baseline` | 1 probe in channel 1, others empty, unit in °F | layout still matches 2024; notify properties |
| 2 | `probe2` | add a probe to channel 2 | state field and probe ordering |
| 3 | `celsius` | switch unit to °C on the device | unit flag location (diff vs #1) |
| 4 | `alarm-high` | set channel 1 high alarm to a new value (e.g. 150) | probe-config field 0 |
| 5 | `alarm-low` | set channel 1 low alarm to e.g. 40 | field 1 and the meaning of `32` |
| 6 | `wifi-off` | disable WiFi on the unit (or block its MAC on UniFi) | wifi flag semantics |

Command per scenario:

```powershell
.venv\Scripts\python scripts/dump_signals.py --scan
.venv\Scripts\python scripts/dump_signals.py <ADDRESS> --scenario baseline --listen 60
```

## Results (fill in)

| # | File | Findings |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |

## Hand-off to Task 8

After all six captures: diff the `ascii` values between scenarios, record findings in `docs/protocol/signals-ble.md` ("Verification status" and "Open questions"), then execute Task 8 of the plan.
```

- [ ] **Step 5: Commit**

```powershell
New-Item -ItemType Directory -Force docs/captures | Out-Null; New-Item -ItemType File -Force docs/captures/.gitkeep | Out-Null
git add scripts/dump_signals.py docs/protocol docs/captures/.gitkeep
git commit -m "docs(signals): protocol reference, Phase 1 checklist, read-only dump script" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Apply Phase 1 findings (requires hardware captures)

**Prerequisite (met 2026-09-04):** captures available — `docs/captures/signals-v4.21-20260904T220115Z-baseline.json` (dump script, probe 1 attached), `docs/captures/recon-2026-09-04-v4.21-probe1-fault.txt` (state-2 fault sample), `recon-2026-09-04-v4.21-noprobe.txt`, `recon-2026-09-04-v4.21-probe1-ok.txt`. The owner declined the °C, alarm-change, and WiFi-off scenarios; the battery-off-charger comparison is deferred (unit is charging). Findings are recorded in the spec §3 and the ledger; this task applies them.

**Files:**
- Modify: `tests/fixtures/signals/` (add real captures), `custom_components/thermoworks_bt/ble/signals.py`, `tests/ble/test_signals.py`
- Possibly modify: `custom_components/thermoworks_bt/config_flow.py`, `custom_components/thermoworks_bt/coordinator.py`, `custom_components/thermoworks_bt/const.py`, `custom_components/thermoworks_bt/strings.json`

- [ ] **Step 1: Promote the baseline capture to a fixture**

Copy `docs/captures/signals-v4.21-20260904T220115Z-baseline.json` to `tests/fixtures/signals/capture-2026-09-v4.21-baseline.json` (keep the file as produced; `load_capture` reads `hex` when present). Add to `tests/ble/test_signals.py`:

```python
@pytest.mark.parametrize(
    "name",
    [
        "capture-2024-01-v4.21.json",
        "capture-2026-09-v4.21-noprobe.json",
        "capture-2026-09-v4.21-baseline.json",
        "capture-2026-09-v4.21-probe1-fault.json",
    ],
)
def test_every_fixture_parses_end_to_end(name) -> None:
    chars = load_capture(name)
    probes = parse_temperatures(chars[UUID_TEMPERATURES], fahrenheit=True)
    assert len(probes) == 4
    for uuid in UUID_PROBE_CONFIG:
        parse_probe_config(chars[uuid], fahrenheit=True)
    parse_device_info(chars[UUID_DEVICE_INFO])
    parse_wifi(chars[UUID_WIFI])
```

Run: `.venv\Scripts\python -m pytest tests/ble/test_signals.py -q`. If the new capture fails, the layout changed: update the parser and the 2024 fixture expectations together, keeping the 2024 test cases only if the old layout is still worth supporting (it is not — replace them with the new capture's values).

- [ ] **Step 2: Units — owner decision (2026-09-04): no unit detection, no config option**

The owner declined the °C capture; the device is assumed to display °F. Keep `SignalsDevice(fahrenheit=True)` as the default and make the assumption explicit for users: in `custom_components/thermoworks_bt/ble/signals.py` change the `SignalsDevice.__init__` docstring's `fahrenheit` line to "Device display unit. Signals sends temperatures in its display unit with no unit marker; v1 assumes °F. If the unit is set to °C every temperature will be off by the F→C transform (obvious in HA)." No code-path change, no config flow change. Task 9 adds the same sentence to `README.md` and `info.md`.

- [ ] **Step 2b: Per-field state flags (finding from `docs/captures/recon-2026-09-04-v4.21-probe1-fault.txt`)**

A probe that is attached but faulted reports `573.0,2,81.0,0,77.3,0,0`: state `2` on the current temperature while max/min keep state `0`. Change `parse_temperatures` so each value honours its own state flag and "connected" means "not state 3":

```python
PROBE_FAULT_STATE = 2

def _valid(fields: list[str], base: int, value_index: int, fahrenheit: bool) -> float | None:
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
```

Add fixture `tests/fixtures/signals/capture-2026-09-v4.21-probe1-fault.json` (temperatures `"573.0,2,81.0,0,77.3,0,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,-63.0,3,-63.0,3,-63.0,3,0,"`, device info `"84,0,0,24:0a:c4:ec:2e:0e,v4.21,"`, other characteristics as in the `noprobe` fixture) and tests:

```python
class TestProbeFaultState:
    def test_faulted_probe_is_connected_with_unknown_temperature(self) -> None:
        chars = load_capture("capture-2026-09-v4.21-probe1-fault.json")
        p1 = parse_temperatures(chars[UUID_TEMPERATURES], fahrenheit=True)[0]
        assert p1.connected is True
        assert p1.temperature_c is None
        assert p1.max_c == pytest.approx(27.2, abs=0.05)   # 81.0F
        assert p1.min_c == pytest.approx(25.2, abs=0.05)   # 77.3F

    def test_alarm_state_with_unknown_temperature_is_not_alarming(self) -> None:
        probe = ProbeTemps(connected=True, temperature_c=None, max_c=27.2, min_c=25.2)
        assert alarm_state(probe, CFG) == (False, False)
```

`alarm_state` already returns `(False, False)` when `temperature_c is None`; confirm rather than change. Update the existing `test_fixture_empty_probes_are_disconnected_with_none` only if it fails (it should not: state 3 still yields the all-None `ProbeTemps`).

- [ ] **Step 3: Resolve the `32` low-alarm question**

Resolved from the baseline capture without a dedicated scenario: probe 1 (user-configured "Gril") reads `360,225`, probes 2–4 read `120,32` / `160,32` — `32` (°F) is simply the factory-default low setpoint, not a "disabled" marker. Keep `alarm_state` as written. Add one sentence to `docs/protocol/signals-ble.md` Open questions: "`32` is the factory default low setpoint (0 °C); a low alarm at that value never fires in practice."

- [ ] **Step 4: Record notify findings (already captured)**

The baseline capture (`docs/captures/signals-v4.21-20260904T220115Z-baseline.json`, `notifications: []`, and the controller's run log) shows that **every** notify subscription is refused by the device with `GATT Protocol Error: Write Not Permitted` on the CCCD — notifications are gated behind the app's handshake on the write-only `4E8A02FE…` channel. In `docs/protocol/signals-ble.md`: set the "Any characteristic notifies?" row to "advertised, but CCCD write refused (Write Not Permitted) — read polling is the only local path", and add a short "Subscribe instead of poll" note under Open questions saying it would require reverse-engineering the app handshake (Phase 3 scope). Do not change the driver.

- [ ] **Step 5: Run BLE suite, commit, push, check CI**

Run: `.venv\Scripts\python -m pytest tests/ble -q` and `.venv\Scripts\python -m ruff check .`
Expected: all pass.

```powershell
git add -A
git commit -m "feat(signals): apply Phase 1 protocol verification findings" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin feature/signals
```

Then confirm CI as in Task 6 Step 8.

---

### Task 9: Docs, version, validation, hardware acceptance, PR

**Files:**
- Modify: `README.md`, `info.md`, `CHANGELOG.md`, `custom_components/thermoworks_bt/manifest.json`, `pyproject.toml`

- [ ] **Step 1: `README.md`** — under "Supported Devices" add:

```markdown
- **Signals** - 4-channel Wi-Fi/Bluetooth thermometer (read-only: temperatures, session min/max, alarm setpoints, derived alarm state, battery, WiFi status). Requires an active-connection-capable Bluetooth proxy (ESP32/ESPHome) or a local adapter; Shelly proxies cannot connect. Close the ThermoWorks phone app — it holds the only BLE connection.
```

Under "Configuration" add a Signals entity list:

```markdown
For Signals, per probe (1–4): **Temperature**, **Probe** (connected), **High Alarm** / **Low Alarm** (computed in Home Assistant as *temperature ≥ high setpoint* / *≤ low setpoint*; the device does not expose its own alarm flag over BLE), and diagnostic **Session Max/Min**, **High/Low Alarm Setpoint**, **Channel Label**. Device-level: **Battery**, **WiFi** (diagnostic), **Signal Strength**.
```

Update the "Development" bullets: test counts, and add `scripts/dump_signals.py` and `docs/protocol/`. Replace the HACS repository URL with the fork's until upstreamed: `https://github.com/sjmotew/thermoworks-ha`.

- [ ] **Step 2: `info.md`** — add `- **Signals** - 4-channel thermometer (read-only)` under Supported Devices and a one-line note: "Signals alarms are computed by Home Assistant from the device's setpoints."

- [ ] **Step 3: `CHANGELOG.md`** — add at the top:

```markdown
## [0.10.0] - <date>

### Added
- ThermoWorks Signals support (local name `TMW022*`): 4 probe temperatures, probe presence, session min/max, alarm setpoints, derived high/low alarm binary sensors, battery, WiFi status.
- `DeviceDriver` abstraction (`ble/device.py`) so additional ThermoWorks BLE devices can be added as a single module.
- `scripts/dump_signals.py` read-only protocol dump and `docs/protocol/` reference.

### Changed
- `parser.py` now only manages the BLE connection; device parsing lives in per-device drivers. BlueDOT behaviour is unchanged.
```

- [ ] **Step 4: Version bump** — `manifest.json` `"version": "0.10.0"`; `pyproject.toml` `version = "0.10.0"`.

- [ ] **Step 5: Verification**

```powershell
.venv\Scripts\python -m pytest tests/ble -q
.venv\Scripts\python -m ruff check .
```

Expected: all pass, ruff clean.

- [ ] **Step 6: Commit and push**

```powershell
git add README.md info.md CHANGELOG.md custom_components/thermoworks_bt/manifest.json pyproject.toml
git commit -m "docs: Signals support, changelog, bump to 0.10.0" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin feature/signals
```

CI (`.github/workflows/validate.yaml`) runs hassfest + HACS validation + tests on push. Fix anything it reports (remember the HA-test step needs its log read — it never turns the run red).

- [ ] **Step 7: Hardware acceptance on the live Home Assistant (record results in the PR description)**

Owner does the physical steps; the agent checks state through the HA MCP tools.

1. Re-deploy the final files exactly as in Task 6 Step 9 (`ha_write_file` each file, `ha_restart`), then `ha_get_logs(level="ERROR")` → no `thermoworks_bt` entries.
2. Owner: power an ESP32 Bluetooth proxy within ~5 m of the Signals. Agent: `ha_get_entity_state` on the proxy's entity shows it available (e.g. `update.esp32_bluetooth_proxy_a93148_firmware` is no longer `unavailable`).
3. Owner: Signals on, Bluetooth on, ThermoWorks app closed on every phone; in HA UI accept the discovered "Signals XXXX". Agent: `ha_list_entities(search="signals")` lists the probe/battery/wifi entities.
4. Within 60 s: `ha_get_entity_state("sensor.signals_xxxx_probe_1_temperature")` has a numeric state and `unit_of_measurement` is °C or °F per the HA unit system (native °C).
5. Owner pulls probe 1. Within 60 s: temperature → `unknown`; `binary_sensor.signals_xxxx_probe_1` → `off`.
6. Owner sets channel 1 high alarm below current temperature on the unit. Within 60 s: `binary_sensor.signals_xxxx_probe_1_high_alarm` → `on`; raise it → `off`.
7. `ha_get_logs(level="DEBUG", limit=200)` after adding `logger: logs: custom_components.thermoworks_bt: debug` to `configuration.yaml` (via `ha_write_file` on a merged copy — read it first with `ha_read_file`): note the time between "Polling" and "Disconnected" lines. If polls regularly exceed ~5 s, open an issue to read configs every Nth poll.

- [ ] **Step 8: Open the PR against the fork's `main`** (and later, upstream) with title `feat: ThermoWorks Signals support (read-only BLE)`, body summarising the driver refactor, entity list, derived-alarm caveat, Phase 1 findings, and acceptance results.

---

## Self-review

**Spec coverage:** §3 protocol → Task 3 constants + Task 7 docs. §4.1 entities → Task 4 keys + Task 6 descriptions (battery, diagnostic temps, channel label text, wifi). §4.2 derived alarms → Task 4 `alarm_state`. §4.3 unit handling → Task 4 default + Task 8 branches A/B. §4.4 polling → Task 2 per-driver interval. §5 driver layer → Tasks 1, 2, 5. §5.3 failure policy and read order → Task 5. §6 HA wiring → Task 6 (config-flow title via `device_name`, no config-flow code change). §7 testing → each task. §8 Phase 1 → Task 7 script + checklist, Task 8 application. §9 handoff → this document, `CLAUDE.md`, `docs/protocol/`. §10 future write support → deliberately unplanned. §11 risks → Task 8 and Task 9 step 7.

**Placeholder scan:** none remaining after the 2026-09-04 Phase 1 rewrite of Task 8.

**Type consistency:** `DeviceDriver.async_read(client, *, timeout)` is used identically in Tasks 1, 2, 5. `SignalsReading` field names (`probes`, `configs`, `info`, `wifi`) match between Tasks 4 and 5. Entity keys in Task 4 match `SENSOR_DESCRIPTION_OVERRIDES` in Task 6 and the entity IDs checked on the live instance in Task 9 Step 7. `driver_for(local_name, **options)` signature is the same in Tasks 1, 2, 5.
