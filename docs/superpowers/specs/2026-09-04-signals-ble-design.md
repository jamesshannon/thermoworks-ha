# ThermoWorks Signals — Local BLE Integration for Home Assistant

**Status:** Approved design, v1 (read-only)
**Date:** 2026-09-04
**Repo:** fork of [jamesshannon/thermoworks-ha](https://github.com/jamesshannon/thermoworks-ha) (MIT), domain `thermoworks_bt`
**Owner:** Steve Motew

## 1. Goal

Expose a ThermoWorks Signals 4-channel thermometer to Home Assistant **without the ThermoWorks cloud**, over Bluetooth Low Energy, using HA's native Bluetooth stack and existing ESPHome ESP32 Bluetooth proxies. v1 is read-only: temperatures, probe presence, alarm setpoints, derived alarm state, battery, WiFi status. The downstream use case (Recteq smoker reacting when a probe hits its alarm) is an HA automation and is out of scope for the integration itself.

### Non-goals (v1)

- Writing to the device (set alarms, units, Billows pit target) — Phase 3, see §10.
- Billows fan entities (user does not own one).
- Cloud fallback / history import.
- Options flow (poll interval, unit override) unless Phase 1 forces the unit override (§4.3).
- Any Recteq-specific logic.

## 2. Research summary

| Project | Path | Signals? | Status | Use |
|---|---|---|---|---|
| [a2hill/ha-thermoworks-cloud](https://github.com/a2hill/ha-thermoworks-cloud) + [python-thermoworks-cloud](https://github.com/a2hill/python-thermoworks-cloud) | Cloud: Firebase Auth → Firestore REST, polled | Yes, 4 channels confirmed ([discussion #6](https://github.com/a2hill/ha-thermoworks-cloud/discussions/6)) | Active, v0.1.16 Jul 2026 | Reference for field semantics only; cloud-dependent |
| [jamesshannon/thermoworks-ha](https://github.com/jamesshannon/thermoworks-ha) | Local BLE, `ActiveBluetoothProcessorCoordinator`, connect-per-poll | No (BlueDOT only) | v0.9.2 Feb 2026, HACS, 50 tests | **Base we extend** |
| [wnoisephx/thermoworks-ble](https://github.com/wnoisephx/thermoworks-ble) | Packet captures + bleak POC | **Yes — read protocol captured** (Jan 2024) | Dormant | Protocol source, see §3 |
| `thermoworks_smoke` (HA core) | Cloud | No | Removed in HA 2026.7 | None |
| [ha-thermoworks-cloud discussion #11](https://github.com/a2hill/ha-thermoworks-cloud/discussions/11) | Firmware dump of Signals (ESP32) | — | Stalled | Confirms hardware; author concluded BLE proxy is the practical route |

Rejected alternatives: WiFi/cloud interception (device talks TLS to `iotservice.thermoworks.com`; unknown pinning, brittle across firmware updates); custom ESP32 firmware (already failed by others); ESPHome-native `ble_client` YAML (ties device to one proxy, holds the connection open, no discovery, brittle lambda parsing).

## 3. Signals BLE protocol (firmware v4.21)

Sources: `wnoisephx/thermoworks-ble/Docs/Signals.txt` (Jan 2024) and a read-only GATT enumeration of the owner's unit on 2026-09-04 (`docs/captures/recon-2026-09-04-v4.21-noprobe.txt`; same firmware). **Remaining unknowns are resolved in Phase 1 (§8).**

- **Advertisement:** local name `TMW022`; manufacturer data key = first two MAC bytes little-endian (`0x0A24` for `24:0A:…`, `0x6224` for `24:62:…`), payload = remaining four MAC bytes. The advertisement is static — no sensor data — so an **active GATT connection** is required for every read. ESP32 ESPHome proxies support active connections; Shelly proxies do not.
- **Service:** `0000a002-0000-1000-8000-00805f9b34fb` holds every ThermoWorks characteristic.
- **Payload encoding:** ASCII, comma-separated, usually with a **trailing comma** (so `split(",")` yields one extra empty field — parsers must tolerate extra fields). Not binary.
- **Every data characteristic below also has `notify`** — v1 polls with reads; a later version can subscribe instead.

| Purpose | UUID | 2026 example | Layout |
|---|---|---|---|
| Temperatures, all probes | `5F5F9010-0E0D-4BD4-B5DC-E4FF47A45984` (read, notify) | `-63.0,3,-63.0,3,-63.0,3,0,` ×4 (no probes); 2024 with probe: `71.4,0,71.7,0,70.2,0,0,…` | 7 fields per probe × 4 = 28 fields (+ trailing empty). Per probe at offset `p*7`: `[0]` current temp, `[1]` state, `[2]` session max, `[3]` state, `[4]` session min, `[5]` state, `[6]` `0`. State `0` = probe attached, `3` = no probe; temp reads `-63.0` when no probe. |
| Probe 1 config | `0A990C1F-B61A-441C-8F7D-F775B6FF9400` (read, write, notify) | `360,225,0,Gril,0.0,` | `[0]` high alarm, `[1]` low alarm, `[2]` **flag, meaning unknown** (`0`/`1`; NOT a channel number — observed `0,1,1,0` across probes 1–4), `[3]` label (**device truncates to 4 chars**: `Gril`, `Roas`), `[4]` unknown (`0.0`) |
| Probe 2 config | `F7C21D1C-5CB9-4B9B-AB7E-E1D8E7A51724` | `120,32,1,Roas,0.0,` | same |
| Probe 3 config | `CFACB2D0-2D81-4C82-A168-13314E38A338` | `120,32,1,Roas,0.0,` | same |
| Probe 4 config | `C99C943F-DA4B-4EE3-92EC-C806006E9E7F` | `160,32,0,CH 4,0.0,225,0` (2024: `160,32,1,CH 4,0,0,255,0`) | same, plus trailing `<n>,0` — `225` strongly suggests the pit/Billows target for channel 4; unused in v1 |
| Device info | `3CE0C366-691F-43E6-B625-3F0912FF6EA7` (read, notify) | `66,0,0,24:0a:c4:ec:2e:0e,v4.21,` (2024: `100,67,0,…,v4.21`) | `[0]` **battery % (provisional** — 2024 notes guessed `[1]`, but `[1]` reads `0` on a running unit), `[1]` unknown, `[2]` unknown, `[3]` MAC, `[4]` firmware. Phase 1 confirms by comparing `[0]` with the app's battery display. |
| WiFi | `B4F1D66A-ECAB-4E03-8B43-B9DF904EBCDF` (read, write, notify) | `Mo2Net,1,iotservice.thermoworks.com,1` | `[0]` SSID, `[1]` flag (1 = connected?), `[2]` cloud host, `[3]` flag |
| Unknown ×6 | `7633F5BB-…` (`1`), `01817E20-…`, `E6DB3978-…`, `DB28403A-…`, `E32E526F-…`, `90BC0C13-…` (all `\x00`) | read, write, notify | Presumed settings/command side (units, alarm arming, Billows). `7633F5BB` = `1` in both captures — candidate unit flag. **Never written in v1.** |
| Unknown | `4E8A02FE-BB42-452D-B573-E0645F03C230` | write, notify only | Command channel. **Never written in v1.** |
| Generic | `00002a00` in service `a002` | read, write | `'0'` — unknown |

Open questions (answered by Phase 1): unit flag location (°F vs °C) — candidates: `7633F5BB`, device-info `[1]`/`[2]`; confirm battery = device-info `[0]`; meaning of probe-config `[2]`; whether the low-alarm value `32` means "disabled/default".

## 4. Entities and data model

One HA device per Signals, identified by BLE MAC. Entity keys are stable and do not depend on channel labels.

### 4.1 Entities

| Key | Platform | Class / Unit | Source | Category |
|---|---|---|---|---|
| `probe_{n}_temperature` (n=1..4) | sensor | temperature, °C | temps `[p*7+0]`; **emitted as `None` when state ≠ 0** so HA shows `unknown` rather than −63 (HA's passive processor merges updates, so a key must be sent as `None` to clear it — omitting it would freeze the last value) | primary |
| `probe_{n}_connected` | binary_sensor | connectivity | temps `[p*7+1] == 0` | primary |
| `probe_{n}_max`, `probe_{n}_min` | sensor | temperature, °C | temps `[+2]`, `[+4]`; `None` when no probe | diagnostic |
| `probe_{n}_alarm_high_setpoint`, `probe_{n}_alarm_low_setpoint` | sensor | temperature, °C | probe-config `[0]`, `[1]` | diagnostic |
| `probe_{n}_alarm_high` | binary_sensor | problem | **derived in driver:** `connected and temp >= high_setpoint` | primary — the automation hook |
| `probe_{n}_alarm_low` | binary_sensor | problem | **derived:** `connected and temp <= low_setpoint` (see open question on `32`) | primary |
| `battery` | sensor | battery, % | device-info `[1]` | diagnostic |
| `wifi_connected` | binary_sensor | connectivity | wifi `[1] == 1` | diagnostic |
| RSSI | sensor | dBm | advertisement (already provided by base class) | diagnostic, disabled by default |

| `probe_{n}_channel_label` | sensor | text (no class) | probe-config `[3]` (`CH 1` or user-renamed; the device truncates custom labels to 4 characters) | diagnostic |

Device info (firmware, MAC) goes into the HA device registry via `set_device_sw_version` / connections. SSID is not surfaced (low value, mild privacy). Battery is read from device-info field 0 (provisional, see §3).

### 4.2 Derived alarms

The device exposes setpoints but the capture shows no "alarm active" flag on the read side. HA computes it. This is documented in `info.md` so users understand it may differ slightly from the on-device alarm (e.g., if the device applies hysteresis). If Phase 1 reveals a device-side alarm flag, the driver uses it instead and the derivation is dropped.

### 4.3 Units

Device reports temperatures in its configured display unit with no observed unit flag. Phase 1 toggles °F/°C on the unit and re-reads everything to locate the flag. Outcomes:

- **Flag found** (expected): driver reads it and converts to °C at parse time.
- **No flag:** add a `device_unit` (°F/°C, default °F) field to the config flow's confirm step. This is the only case in which v1 gains configuration.

All HA entities are native °C; HA handles display conversion. Matches the BlueDOT driver.

### 4.4 Polling

Connect-per-poll, advertisement-triggered with a 60 s timer fallback (unchanged from upstream). `min_poll_interval` becomes a per-driver value; Signals = 30 s. Each poll performs 7 GATT reads inside one connection then disconnects.

## 5. BLE driver layer

### 5.1 Driver protocol — `custom_components/thermoworks_bt/ble/device.py` (new)

```python
class DeviceDriver(ABC):
    device_type: ClassVar[str]            # "BlueDOT" | "Signals"
    min_poll_interval: ClassVar[float]    # seconds

    def __init__(self, **options: Any) -> None: ...          # drivers ignore options they don't use
    @classmethod
    @abstractmethod
    def matches(cls, local_name: str | None) -> bool: ...
    def device_name(self, local_name: str | None, address: str) -> str: ...  # default: local_name or device_type
    @abstractmethod
    async def async_read(self, client: BleakClient, *, timeout: float) -> Any: ...   # client already connected
    @abstractmethod
    def apply(self, reading: Any, data: SensorData) -> None: ...                    # emit sensor/binary keys
```

`ble/device.py` also holds `all_drivers() -> tuple[type[DeviceDriver], ...]` (function-local imports of the driver modules, to avoid a circular import) and `driver_for(local_name, **options) -> DeviceDriver | None`. `timeout` is passed by `parser.py` from its module-level `NOTIFICATION_TIMEOUT` so the existing upstream test that patches `parser.NOTIFICATION_TIMEOUT` keeps working without modification.

### 5.2 `parser.py` (refactor)

`ThermoWorksBluetoothDeviceData` owns connection lifecycle only:

1. `_start_update`: pick driver via `driver_for(name)`; set device type/name/manufacturer.
2. `poll_needed`: uses `driver.min_poll_interval`.
3. `async_poll`: `establish_connection` → `driver.async_read(client)` → `driver.apply(reading, self)` → disconnect (in `finally`) → `_finish_update()`.

BlueDOT's notify-subscribe-wait-one logic moves verbatim into `bluedot.py::BlueDOTDevice.async_read`. Parsing functions and tests for BlueDOT are untouched.

### 5.3 `signals.py` (new)

Pure parsing, no I/O, one function per characteristic. Each: decode ASCII (`errors="replace"`), split on `,`, validate minimum field count, raise `ValueError` with the raw payload in the message on failure.

```python
@dataclass(frozen=True, slots=True)
class ProbeTemps:   connected: bool; temperature_c: float | None; max_c: float | None; min_c: float | None
@dataclass(frozen=True, slots=True)
class ProbeConfig:  alarm_high_c: float | None; alarm_low_c: float | None; flag: int; label: str   # flag = field [2], semantics unknown
@dataclass(frozen=True, slots=True)
class DeviceInfo:   battery_pct: int; mac: str; firmware: str; raw_fields: tuple[str, ...]   # battery from field [0], provisional
@dataclass(frozen=True, slots=True)
class WifiInfo:     ssid: str; connected: bool; cloud_host: str   # ssid/host parsed for tests/debug, not surfaced as entities
@dataclass(frozen=True, slots=True)
class SignalsReading: probes: tuple[ProbeTemps, ...]; configs: tuple[ProbeConfig | None, ...]; info: DeviceInfo | None; wifi: WifiInfo | None

def parse_temperatures(data: bytes, fahrenheit: bool) -> tuple[ProbeTemps, ...]
def parse_probe_config(data: bytes, fahrenheit: bool) -> ProbeConfig
def parse_device_info(data: bytes) -> DeviceInfo
def parse_wifi(data: bytes) -> WifiInfo
def is_signals(name: str | None) -> bool          # name.startswith("TMW022")
def alarm_state(probe: ProbeTemps, cfg: ProbeConfig | None) -> tuple[bool, bool]  # (high, low)
```

`SignalsDevice.async_read` read order and failure policy:

| Read | On failure |
|---|---|
| temperatures | raise — poll fails (nothing useful without it) |
| device info | log at debug, `info=None`; battery emitted as `None` this poll |
| wifi | log at debug, `wifi=None`; `wifi_connected` emitted as `None` |
| probe config ×4 | log at debug, that probe's `config=None`; setpoints, label, and derived alarms for that probe emitted as `None` (unknown ≠ `False`) |

`apply()` always emits the full key set; unknown values are `None`. HA's `PassiveBluetoothDataProcessor` merges each update into the previous one, so a key that is simply omitted would keep its stale value — `None` is the only way to say "unknown now".

Read order: device info first (so a unit flag, if Phase 1 finds one there, is known before temperatures are parsed), then temperatures, wifi, probe configs. Each read is wrapped in `asyncio.wait_for(..., timeout)` where `timeout` is passed in by `parser.py`.

## 6. Home Assistant wiring

| File | Change |
|---|---|
| `manifest.json` | add `{"local_name": "TMW022*", "connectable": true}`; version `0.10.0` |
| `config_flow.py` | `device.supported()` already delegates to `_start_update`; no structural change once `parser.py` uses `driver_for`. Title: `f"{device_type} {address[-5:].replace(':','')}"` |
| `coordinator.py` | unchanged (poll interval flows through `poll_needed`) |
| `sensor.py` | `SENSOR_DESCRIPTIONS` stays keyed by `(device_class, unit)` for defaults; add `SENSOR_DESCRIPTION_OVERRIDES: dict[str, SensorEntityDescription]` keyed by entity key for the diagnostic-category entities (`probe_{n}_max/min/alarm_*_setpoint`, `battery`). Lookup: override by key first, then class/unit. Add a `(DeviceClass.BATTERY, Units.PERCENTAGE)` default. `probe_{n}_channel_label` is a text sensor (no device class, diagnostic) via the override map; `ThermoWorksBluetoothSensorEntity.native_value` type widens to `str \| int \| float \| None`. |
| `binary_sensor.py` | add per-key override map for diagnostic `wifi_connected`; otherwise unchanged (CONNECTIVITY / PROBLEM already mapped) |
| `strings.json`, `translations/en.json` | names for new keys |
| `info.md`, `README.md` | Signals supported; requirements (ESP32 proxy or local adapter, unit powered with BT on); derived-alarm caveat; no Billows/write support |
| `CHANGELOG.md` | 0.10.0 entry |

Preserved upstream behaviors: entities persist as `unavailable` when out of range; immediate disconnect after read; BlueZ "Notify acquired" recovery (BlueDOT only).

## 7. Testing

Framework: upstream pytest layout (`tests/ble/` pure, `tests/ha/` with `pytest-homeassistant-custom-component`). TDD per task.

**Where tests run (owner decision, 2026-09-04):** Home Assistant does not install on Windows and the owner does not want the HA test harness installed locally. Therefore:

| Layer | Runs where | How |
|---|---|---|
| `tests/ble/` | Locally, lean venv (bleak, sensor-state-data, pytest, ruff) | `tests/ble/conftest.py` registers synthetic parent packages so the `ble` sub-package imports without HA |
| `tests/ha/` | GitHub CI only (`validate.yaml`, on push to the fork) | CI runs HA tests with `\|\| true` — the step log must be read |
| HA integration behaviour | Owner's live HA via the HA MCP tools | `ha_write_file` the component, `ha_restart`, `ha_get_logs`, `ha_get_entity_state` |

Consequently `tests/ha/` additions are kept minimal (config-flow discovery, entry loads); entity-level assertions are done against the live instance.

| File | Coverage |
|---|---|
| `tests/ble/test_signals.py` | every `parse_*`: happy path from real fixture bytes; no-probe sentinel; probe-4 trailing fields; short/garbage payloads → `ValueError`; °F→°C; `alarm_state` truth table (connected × temp vs setpoint × config None) |
| `tests/ble/test_signals.py` (driver) | `SignalsDevice.async_read` with a fake `BleakClient` (`read_gatt_char` keyed by UUID): full success; each partial-failure case in §5.3; temperature failure raises |
| `tests/ble/test_parser.py` | `driver_for`: `BlueDOT*`, `TMW022*`, unknown, `None`; **all existing BlueDOT tests pass unchanged** (regression guard for the refactor) |
| `tests/ha/test_config_flow.py` | `TMW022` discovery creates entry with Signals title; unknown name aborts `not_supported` |
| `tests/ha/test_sensor.py` | Signals update produces expected entity keys; diagnostic categories applied; unavailable path |

Fixtures: `tests/fixtures/signals/*.json` generated by the Phase 1 dump script (raw hex per UUID + firmware + scenario name), plus the 2024 capture transcribed as `capture-2024-01-v4.21.json`.

CI: upstream `validate.yaml` (hassfest + HACS action) + pytest. Green before upstream PR.

Hardware acceptance (manual): install via HACS custom repository → ESP32 proxy near unit → discovery prompt appears → temps update within 60 s → pull probe → `unavailable` → set high alarm below current temp on the unit → `probe_n_alarm_high` on.

## 8. Phase 1 — protocol verification (precedes parser fixtures)

`scripts/dump_signals.py` (bleak; runs on MO2_PC or MBP; no HA):

1. Scan 10 s; select device whose name starts with `TMW022` (arg or sole match).
2. Connect; enumerate all services/characteristics with properties.
3. Read every readable characteristic; print hex + ASCII.
4. Subscribe to every notify-capable characteristic for 60 s; log arrivals.
5. Write `docs/captures/signals-<firmware>-<timestamp>-<scenario>.json`.

**Read-only guarantee:** the script never calls `write_gatt_char`.

Manual scenarios (checklist in `docs/protocol/phase1-verification.md`): baseline (1 probe); attach probe 2; toggle °F→°C; change probe-1 high alarm on unit; set a low alarm to confirm `32` semantics; disconnect WiFi; read the battery % shown in the ThermoWorks app (then close the app) to confirm device-info field 0. Each scenario = one JSON capture.

## 9. Handoff documentation

| Artifact | Path |
|---|---|
| This spec | `docs/superpowers/specs/2026-09-04-signals-ble-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-04-signals-ble-plan.md` |
| Protocol reference (living) | `docs/protocol/signals-ble.md` |
| Phase 1 checklist | `docs/protocol/phase1-verification.md` |
| Agent guidance | `CLAUDE.md` at repo root |

Execution model: plan tasks are sized for `superpowers:subagent-driven-development` (Sonnet/Opus per task) or `executing-plans` in one Opus session. Tasks that do not depend on Phase 1 (driver interface refactor, `driver_for`, matcher, BlueDOT regression) are marked so they can start before the hardware step.

## 10. Future: write support (Phase 3, not planned)

Capture app→device writes with an Android HCI snoop log (Developer options → Bluetooth HCI snoop log, then `btsnoop_hci.log` in Wireshark) or an nRF52840 dongle running nRF Sniffer, while changing an alarm and units in the ThermoWorks app. Map writes to the 7 unknown UUIDs, then add `number` entities for setpoints. Only after that does an options flow or Billows target make sense.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Firmware changed the CSV layout since 2024 | Phase 1 before fixtures; parser validates field counts and fails loudly |
| Unit flag absent | Config-flow `device_unit` fallback (§4.3) |
| 7 reads per poll too slow on a proxy | Measure in Phase 1; fall back to reading temps only on most polls and config/info every Nth poll |
| ESP32 proxies currently offline in HA | One must be powered near the cook area; not a code issue |
| Upstream refactor breaks BlueDOT | Existing 50 tests run unchanged; PR to upstream keeps maintainer in the loop |
