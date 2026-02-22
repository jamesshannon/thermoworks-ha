# ThermoWorks Bluetooth Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Validate](https://github.com/jamesshannon/thermoworks-ha/actions/workflows/validate.yaml/badge.svg)](https://github.com/jamesshannon/thermoworks-ha/actions/workflows/validate.yaml)

Home Assistant custom integration for ThermoWorks Bluetooth thermometers.

## Supported Devices

- **BlueDOT** - Bluetooth thermometer with probe and alarm functionality

## Features

- 🌡️ Real-time temperature monitoring (always reported in Celsius, converted from device unit if needed)
- 📡 Bluetooth Low Energy (BLE) connectivity with automatic discovery
- 🔌 Probe connection status monitoring
- 🔔 Alarm state tracking
- 📊 Signal strength (RSSI) monitoring
- ⚡ Local polling (no cloud required)
- 🔄 Dual polling mechanism: advertisement-driven + timer fallback (60s)
- 🏠 Smart unavailable handling - entities persist when device is off/out of range
- 🔋 Battery-friendly - disconnects immediately after reading

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/jamesshannon/thermoworks-ha`
5. Select category: "Integration"
6. Click "Add"
7. Find "ThermoWorks" in HACS and install
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/thermoworks_bt` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

The integration supports automatic Bluetooth discovery:

1. Make sure your ThermoWorks device is powered on and nearby
2. Go to **Settings** → **Devices & Services**
3. Click **+ Add Integration**
4. Search for "ThermoWorks Bluetooth"
5. Select your device from the list
6. Click **Submit**

Your device will be added with the following entities:

- **Temperature** sensor (in Celsius)
- **Signal Strength** sensor (RSSI in dBm)
- **Probe Connected** binary sensor
- **Alarm Active** binary sensor

## Technical Details

- **Communication**: BLE GATT notifications via active polling (connect-per-poll pattern)
- **Polling Strategy**:
  - Primary: Advertisement-driven (polls when device advertises + 30s elapsed)
  - Fallback: Timer-based (60s interval) for when advertisements aren't frequent
- **Temperature Unit**: Always Celsius (device F→C conversion handled automatically)
- **Dependencies**: Requires Home Assistant's Bluetooth integration
- **Device Availability**: Entities persist as "unavailable" when device is off or out of range
- **Connection Management**: Connects only when needed, immediately disconnects to free connection slots

## Differentiation from Core Integration

This integration (`thermoworks_bt`) is for **Bluetooth thermometers** (BlueDOT, etc.) and is separate from the core `thermoworks_smoke` integration which uses IP/API communication for Smoke thermometers.

## Development

This integration includes:
- Independent BLE parsing library (`custom_components/thermoworks_bt/ble/`)
- Comprehensive test suite (39 BLE tests, 9 HA integration tests)
- CLI testing script (`scripts/test_bluedot.py`)

### Running Tests

```bash
# Set up development environment
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run tests
pytest tests/
```

## Architecture

The integration follows Home Assistant's `ActiveBluetoothProcessorCoordinator` pattern:
- Advertisements trigger device identification
- Periodic polls establish GATT connections to read temperature data
- Automatic reconnection on connection loss
- No persistent BLE connections (conserves connection slots)

Based on the Inkbird integration pattern from Home Assistant core.

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Acknowledgments

- Inspired by the [Inkbird integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/inkbird)
- Built using Home Assistant's Bluetooth integration framework

## Support

- 🐛 [Report bugs](https://github.com/jamesshannon/thermoworks-ha/issues)
- 💡 [Request features](https://github.com/jamesshannon/thermoworks-ha/issues)
- 📖 [Documentation](https://github.com/jamesshannon/thermoworks-ha)
