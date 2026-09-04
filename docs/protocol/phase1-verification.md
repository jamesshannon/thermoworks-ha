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
| 7 | `battery` | unplug the unit from AC, open the ThermoWorks app, note the battery % it shows, close the app, then run the dump | confirms device-info field 0 = battery |

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
| 7 | | |

## Hand-off to Task 8

After all seven captures: diff the `ascii` values between scenarios, record findings in `docs/protocol/signals-ble.md` ("Verification status" and "Open questions"), then execute Task 8 of the plan.
