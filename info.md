# ThermoWorks Bluetooth Integration

Integrate your ThermoWorks Bluetooth thermometers with Home Assistant.

## Supported Devices

- **BlueDOT** - Bluetooth thermometer with probe and alarm functionality
- **Signals** - 4-channel thermometer (read-only; device must be set to °F)

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
4. Search for "ThermoWorks Bluetooth"
5. Select your device

The integration will automatically discover your device and create temperature, probe status, and alarm sensors.

Signals alarms are computed by Home Assistant from the device's setpoints (low alarms read *on* from a cold start); close the ThermoWorks app while Home Assistant is polling. Disable the Signals entry before running a firmware update in the app.

## Technical Details

Uses Home Assistant's native Bluetooth integration with:
- Active polling (connect-per-poll pattern)
- Dual polling strategy (advertisement + timer fallback)
- Local processing (no cloud required)
- Efficient connection management

For more details, see the [README](https://github.com/sjmotew/thermoworks-ha).
