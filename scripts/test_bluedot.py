#!/usr/bin/env python3
"""Standalone CLI script to connect to a real BlueDOT and print readings.

Usage:
    python scripts/test_bluedot.py <BLE_ADDRESS>

Example:
    python scripts/test_bluedot.py AA:BB:CC:DD:EE:FF

Requires: bleak (pip install bleak)
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

# Allow running from project root without installing the package.
# Import the BLE sub-package directly to avoid the HA-dependent parent __init__.
_ble_path = Path(__file__).resolve().parent.parent / "custom_components" / "thermoworks"
sys.path.insert(0, str(_ble_path))

from ble.bluedot import (  # noqa: E402
    CHARACTERISTIC_UUID,
    parse_notification_data,
)

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Error: bleak is required. Install with: pip install bleak")
    sys.exit(1)


async def scan_for_bluedots(timeout: float = 10.0) -> None:
    """Scan for BlueDOT devices and print them."""
    print(f"Scanning for BlueDOT devices ({timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout)
    found = False
    for device in devices:
        if device.name and device.name.startswith("BlueDOT"):
            print(f"  Found: {device.name} ({device.address})")
            found = True
    if not found:
        print("  No BlueDOT devices found.")


async def connect_and_read(address: str, duration: float = 60.0) -> None:
    """Connect to a BlueDOT and print notification data.

    Args:
        address: BLE address of the BlueDOT device.
        duration: How long to listen for notifications in seconds.
    """
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        print("\nStopping...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, _signal_handler)
    loop.add_signal_handler(signal.SIGTERM, _signal_handler)

    reading_count = 0

    def _on_notification(_sender: int, data: bytearray) -> None:
        nonlocal reading_count
        reading_count += 1
        raw_hex = data.hex()

        try:
            reading = parse_notification_data(bytes(data))
            unit_str = "F" if reading.device_unit_fahrenheit else "C"
            probe_str = "connected" if reading.probe_connected else "DISCONNECTED"
            alarm_str = "ACTIVE" if reading.alarm_active else "inactive"
            mac_str = ":".join(f"{b:02X}" for b in reading.mac_address)

            print(
                f"[{reading_count:4d}] "
                f"Temp: {reading.temperature_celsius:6.1f}C "
                f"(device: {unit_str}) | "
                f"Probe: {probe_str} | "
                f"Alarm: {alarm_str} "
                f"(target: {reading.alarm_temperature_celsius:.1f}C, "
                f"silenced: {reading.alarm_silenced}, "
                f"disabled: {reading.alarm_disabled}) | "
                f"MAC: {mac_str}"
            )
        except ValueError as e:
            print(f"[{reading_count:4d}] Parse error: {e} | Raw: {raw_hex}")

    print(f"Connecting to {address}...")
    async with BleakClient(address) as client:
        print(f"Connected! Subscribing to notifications...")
        print(f"Characteristic: {CHARACTERISTIC_UUID}")
        print("-" * 100)

        await client.start_notify(CHARACTERISTIC_UUID, _on_notification)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=duration)
        except asyncio.TimeoutError:
            print(f"\nDuration ({duration}s) reached.")
        finally:
            await client.stop_notify(CHARACTERISTIC_UUID)

    print(f"\nDisconnected. Total readings: {reading_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect to a ThermoWorks BlueDOT and print readings."
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="BLE address of the BlueDOT (e.g., AA:BB:CC:DD:EE:FF)",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan for BlueDOT devices instead of connecting",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="How long to listen for notifications (default: 60s)",
    )
    args = parser.parse_args()

    if args.scan:
        asyncio.run(scan_for_bluedots())
    elif args.address:
        asyncio.run(connect_and_read(args.address, args.duration))
    else:
        parser.print_help()
        print("\nExample:")
        print("  python scripts/test_bluedot.py --scan")
        print("  python scripts/test_bluedot.py AA:BB:CC:DD:EE:FF")


if __name__ == "__main__":
    main()
