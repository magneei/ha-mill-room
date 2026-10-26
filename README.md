# Mill Heaters - Room Control

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for [Mill](https://www.millheat.com/) heaters with **room-level control**.

## Why this integration?

The official Mill integration exposes individual heater devices and polls every 30 seconds, which triggers Mill's API rate limits. This integration takes a different approach:

- **Room-centric**: Each Mill room becomes a climate entity with Comfort/Sleep/Away presets
- **Rate-limit friendly**: Polls every 120 seconds with exponential backoff (up to 30 min) on errors
- **Mode control**: Read and set the active mode per room via the Mill room override API

## Features

- **Room climate entities** with preset modes (Comfort, Sleep, Away)
- **Room mode override** — change the active mode per room, syncs with the Mill app
- **Individual device entities** for heaters set to "control individually"
- **Sensors** for ambient temperature, floor temperature, and daily energy consumption per device
- Works with both Gen 2 and Gen 3 Mill heaters via the cloud API

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ menu → **Custom repositories**
2. Add `magneei/ha-mill-room` with category **Integration**
3. Install "Mill Heaters (Room Control)"
4. Restart Home Assistant

### Manual

Copy `custom_components/mill_room/` to your Home Assistant `config/custom_components/` directory and restart.

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Mill Heaters (Room Control)"
3. Enter your Mill app email and password

Rooms and devices are discovered automatically. Mill room names are suggested as Home Assistant areas for easy organization.

## How it works

### Room entities

Each Mill room appears as a climate entity. The preset mode (Comfort/Sleep/Away) reflects the active mode from the Mill API — if you change it in the Mill app, it updates in HA within 2 minutes.

Setting a preset in HA calls the Mill room override API (`POST /rooms/{roomId}/mode/override`), which overrides the house-level program for that specific room.

### Timed overrides

The service `mill_room.set_override` overrides a room's preset, optionally for a fixed time:

```yaml
action: mill_room.set_override
target:
  entity_id: climate.kjellerstue_climate
data:
  preset_mode: Comfort
  duration: "04:00:00"
```

With `duration` this is the same timed override as in the Mill app (`overrideModeType: not_continuous` with
`overrideEndDate`): the app shows the end time, and Mill returns the room to its program by itself, even if
Home Assistant is down. Without `duration` the override lasts until the room is set back to Program.

Each room entity exposes `override_type` (`timed`, `continuous` or empty) and `override_end` (ISO time for timed
overrides), also for overrides set in the Mill app.

### Temperature control

Setting the temperature adjusts the setpoint for the currently active preset. For example, if the room is in Comfort mode and you set 23°C, it updates the comfort temperature for that room.

### Rate limiting

The Mill API allows 2500 requests per hour. This integration:

- Polls every **120 seconds** (vs 30s in the official integration)
- Uses the `millheater` library's built-in response caching (20 min TTL)
- Applies **exponential backoff** on rate limit errors (240s → 480s → ... → 1800s)
- Falls back to cached data when rate-limited

## Compatibility

- Mill Gen 2 and Gen 3 heaters (cloud API)
- Home Assistant 2024.1+
- Can be installed alongside the official `mill` integration (different domain: `mill_room`)
