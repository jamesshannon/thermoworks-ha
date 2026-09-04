# ThermoWorks Signals BLE protocol

Sources: `wnoisephx/thermoworks-ble/Docs/Signals.txt` (Jan 2024) and a read-only GATT enumeration of the owner's unit on 2026-09-04 (`docs/captures/recon-2026-09-04-v4.21-noprobe.txt`; same firmware). **Remaining unknowns are resolved in Phase 1 (§8).**

- **Advertisement:** local name `TMW022`; manufacturer data key = first two MAC bytes little-endian (`0x0A24` for `24:0A:…`, `0x6224` for `24:62:…`), payload = remaining four MAC bytes. The advertisement is static — no sensor data — so an **active GATT connection** is required for every read. ESP32 ESPHome proxies support active connections; Shelly proxies do not.
- **Service:** `0000a002-0000-1000-8000-00805f9b34fb` holds every ThermoWorks characteristic.
- **Payload encoding:** ASCII, comma-separated, usually with a **trailing comma** (so `split(",")` yields one extra empty field — parsers must tolerate extra fields). Not binary.
- **Every data characteristic below also has `notify`** — v1 polls with reads; a later version can subscribe instead.

| Purpose | UUID | 2026 example | Layout |
|---|---|---|---|
| Temperatures, all probes | `5F5F9010-0E0D-4BD4-B5DC-E4FF47A45984` (read, notify) | `-63.0,3,-63.0,3,-63.0,3,0,` ×4 (no probes); 2024 with probe: `71.4,0,71.7,0,70.2,0,0,…` | 7 fields per probe × 4 = 28 fields (+ trailing empty). Per probe at offset `p*7`: `[0]` current temp, `[1]` its state, `[2]` session max, `[3]` its state, `[4]` session min, `[5]` its state, `[6]` `0`. **Each value has its own state flag.** State `0` = valid, `2` = fault/out-of-range (probe attached; observed `573.0,2,81.0,0,77.3,0` — current faulted while max/min stayed valid), `3` = no probe (`-63.0`). |
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

## Verification status

| Item | 2024 capture | Phase 1 (fill in) |
|---|---|---|
| Firmware | v4.21 | confirmed |
| Temperature layout (28 fields) | observed | confirmed |
| No-probe sentinel `-63.0,3` | observed | confirmed |
| Probe config layout | observed (probes 1 & 4) | confirmed (field 2 = flag) |
| Device info: battery at field 1 | inferred | field 0, provisional (unit charging, app comparison pending) |
| Unit flag location | unknown | unknown |
| Probe state 2 = fault (attached, value invalid) | not observed | observed 2026-09-04 (`573.0,2,81.0,0,77.3,0` while max/min stayed state 0); cleared after reseating the probe |
| Any characteristic notifies? | unknown | advertised on all data characteristics, but CCCD write refused (`Write Not Permitted`) — read polling is the only local path |
| Read latency for 7 reads on ESP32 proxy | unknown | unknown |

## Open questions

1. Where is the °F/°C flag? Candidates: device-info field 0 or 2, or one of the unknown characteristics. The owner declined the °C capture; v1 assumes °F with no detection and no config option.
2. Does `32` as a low alarm mean "disabled" (32 °F = 0 °C is the device default)? Resolved from the baseline capture: `32` is the factory default low setpoint (0 °C); a low alarm at that value never fires in practice.
3. Do the 7 unknown characteristics carry `write` or `notify` properties? (The dump script records properties without writing.)
4. Subscribe instead of poll: every data characteristic advertises `notify`, but subscribing (CCCD write) is refused with `Write Not Permitted` — the device gates notifications behind the app's handshake on the write-only `4E8A02FE…` channel. Reverse-engineering that handshake is Phase 3 scope.
