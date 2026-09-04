# thermoworks-ha (fork) — Signals BLE support

Home Assistant custom integration `thermoworks_bt` for ThermoWorks Bluetooth thermometers. Upstream supports BlueDOT; this fork adds **Signals** (4-channel, local name `TMW022*`), read-only, no cloud.

## Read first

- `docs/superpowers/specs/2026-09-04-signals-ble-design.md` — approved design. Do not deviate without updating it.
- `docs/superpowers/plans/2026-09-04-signals-ble-plan.md` — ordered tasks; execute one at a time, test-first.
- `docs/protocol/signals-ble.md` — UUIDs, payload layouts, sentinels, open questions.
- `docs/protocol/phase1-verification.md` — hardware checklist that produces the parser fixtures.

## Layout

```
custom_components/thermoworks_bt/
  ble/device.py     DeviceDriver ABC: matches(), device_name(), async_read(client, timeout=), apply(reading, data); all_drivers(), driver_for()
  ble/bluedot.py    BlueDOT driver (notify-based) — upstream code, keep behavior identical
  ble/signals.py    Signals driver (GATT reads, ASCII CSV parsing) — pure parse_* functions + SignalsDevice
  ble/parser.py     connection lifecycle only; picks driver via driver_for(name)
  coordinator.py    ActiveBluetoothProcessorCoordinator, connect-per-poll + 60 s fallback timer (upstream)
  sensor.py / binary_sensor.py   description maps; per-key overrides for diagnostic entities
scripts/dump_signals.py          Phase 1 read-only characteristic dump → docs/captures/*.json
tests/ble/                       pure parsing + driver tests (fake BleakClient)
tests/ha/                        config flow / coordinator / sensor tests (pytest-homeassistant-custom-component)
tests/fixtures/signals/          real device captures used by parser tests
```

## Rules

- **Read-only.** Never call `write_gatt_char` on a Signals device. The 7 unknown characteristics are presumed writes; do not probe them.
- HA entities are always native °C; convert at parse time.
- Emit `None` for any key whose value is unknown this poll — never a fabricated `False`/`0`, and never omit the key (HA merges updates, so an omitted key keeps its stale value).
- Existing BlueDOT tests must pass unchanged after any refactor. That is the regression guard.
- Entity keys are fixed (`probe_{n}_temperature` …); channel labels never affect entity IDs.
- Match upstream style: ruff (E,F,I,W), line length 88, docstrings on public functions, `_LOGGER.debug` over prints.

## Commands (Windows; venv is `.venv`)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install pytest pytest-asyncio bleak bleak-retry-connector bluetooth-data-tools bluetooth-sensor-state-data sensor-state-data ruff
.venv\Scripts\python -m pytest tests/ble -q      # local unit tests (no Home Assistant needed)
.venv\Scripts\python -m ruff check .
.venv\Scripts\python scripts/dump_signals.py --scan   # Phase 1, needs Bluetooth adapter + Signals powered on
```

**Do not install `homeassistant` or `pytest-homeassistant-custom-component` locally** (HA does not run on Windows; owner decision). `tests/ha/` runs in GitHub CI on push to `origin feature/signals` — CI's HA-test step uses `|| true`, so read its log. Live-instance verification uses the Home Assistant MCP tools (`ha_write_file` → `custom_components/thermoworks_bt/...`, `ha_restart`, `ha_get_logs`, `ha_get_entity_state`).

## Upstream

Fork of https://github.com/jamesshannon/thermoworks-ha (MIT). Goal is a clean PR back; keep changes to BlueDOT paths minimal and behavior-preserving.
