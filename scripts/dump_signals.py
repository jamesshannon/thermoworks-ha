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
    """Decode raw bytes as ASCII, replacing undecodable bytes."""
    return raw.decode("ascii", errors="replace")


async def scan(timeout: float) -> list[tuple[str, str]]:
    """Scan for Signals units advertising the TMW022 local name prefix."""
    print(f"Scanning {timeout:.0f}s for {PREFIX}* ...")
    found = []
    discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for dev, adv in discovered.values():
        if dev.name and dev.name.startswith(PREFIX):
            found.append((dev.address, dev.name))
            print(
                f"  {dev.name}  {dev.address}  RSSI {adv.rssi}  "
                f"mfr={adv.manufacturer_data}"
            )
    if not found:
        print(
            "  none found (is the unit on, Bluetooth enabled, "
            "and the phone app closed?)"
        )
    return found


async def dump(address: str, scenario: str, listen: float) -> Path:
    """Connect, read every readable characteristic, listen for notifications.

    Read-only: only read_gatt_char and start_notify/stop_notify are used.
    Never calls write_gatt_char.
    """
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
            svc = {
                "uuid": service.uuid,
                "description": service.description,
                "chars": [],
            }
            for ch in service.characteristics:
                svc["chars"].append(
                    {"uuid": ch.uuid, "properties": list(ch.properties)}
                )
                entry: dict = {
                    "properties": list(ch.properties),
                    "service": service.uuid,
                }
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
            ch
            for s in client.services
            for ch in s.characteristics
            if "notify" in ch.properties or "indicate" in ch.properties
        ]
        if notify_chars and listen > 0:
            print(
                f"Subscribing to {len(notify_chars)} notify-capable "
                f"characteristics for {listen:.0f}s ..."
            )

            def _handler_for(uuid: str):
                def _h(_sender, data: bytearray) -> None:
                    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                    raw = bytes(data)
                    result["notifications"].append(
                        {
                            "time": ts,
                            "uuid": uuid,
                            "hex": raw.hex(),
                            "ascii": _ascii(raw),
                        }
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
    """Parse CLI args and dispatch to --scan or dump()."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("address", nargs="?", help="BLE address (or omit with --scan)")
    p.add_argument(
        "--scan", action="store_true", help="scan for Signals units and exit"
    )
    p.add_argument("--scenario", default="baseline", help="label for this capture")
    p.add_argument(
        "--listen", type=float, default=60.0, help="seconds to listen for notifications"
    )
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
