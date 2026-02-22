# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-11

### Added
- Initial release
- BlueDOT thermometer support
- Bluetooth Low Energy (BLE) connectivity
- Real-time temperature monitoring (Celsius)
- Probe connection status monitoring
- Alarm state tracking
- Signal strength (RSSI) monitoring
- Dual polling mechanism:
  - Primary: Advertisement-driven polling (30s minimum interval)
  - Fallback: Timer-based polling (60s interval)
- Smart unavailable handling (entities persist when device is off/out of range)
- Automatic Bluetooth discovery and config flow
- Comprehensive test suite (41 BLE tests, 9 HA integration tests)

### Technical Details
- Active polling with connect-per-poll pattern
- Efficient connection management (immediate disconnect after reading)
- BlueZ notification error recovery
- Support for intermittent/battery-operated devices
- Based on Home Assistant's ActiveBluetoothProcessorCoordinator pattern

[0.1.0]: https://github.com/jamesshannon/thermoworks-ha/releases/tag/v0.1.0
