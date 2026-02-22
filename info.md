# ThermoWorks Bluetooth Integration

Integrate your ThermoWorks Bluetooth thermometers with Home Assistant.

## Supported Devices

- **BlueDOT** - Bluetooth thermometer with probe and alarm functionality

## Key Features

- 🌡️ Real-time temperature monitoring
- 🔌 Probe connection status
- 🔔 Alarm state tracking
- 📊 Signal strength monitoring
- 🔄 Reliable polling with automatic fallback
- 🏠 Smart handling of intermittent devices (entities persist when device is off)

## Perfect For

- Meat thermometers used intermittently
- Battery-operated devices that may be out of range
- Outdoor cooking monitoring

## Setup

1. Turn on your ThermoWorks device
2. Go to **Settings** → **Devices & Services**
3. Click **+ Add Integration**
4. Search for "ThermoWorks"
5. Select your device

The integration will automatically discover your device and create temperature, probe status, and alarm sensors.

## Technical Details

Uses Home Assistant's native Bluetooth integration with:
- Active polling (connect-per-poll pattern)
- Dual polling strategy (advertisement + timer fallback)
- Local processing (no cloud required)
- Efficient connection management

For more details, see the [README](https://github.com/jamesshannon/thermoworks-ha).
