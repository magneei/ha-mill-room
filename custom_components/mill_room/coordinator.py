"""Data update coordinator for Mill Room integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from mill import API_ENDPOINT, Heater, Mill, Socket, TooManyRequestsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, MAX_BACKOFF_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoomData:
    """Aggregated data for a Mill room."""

    room_id: str
    room_name: str
    home_id: str | None = None
    avg_temp: float | None = None
    comfort_temp: float | None = None
    sleep_temp: float | None = None
    away_temp: float | None = None
    active_mode: str | None = None
    override_mode: str | None = None
    override_mode_type: str | None = None
    device_ids: list[str] = field(default_factory=list)


@dataclass
class MillData:
    """Container for all Mill data."""

    rooms: dict[str, RoomData] = field(default_factory=dict)
    devices: dict[str, Heater | Socket] = field(default_factory=dict)
    house_modes: dict[str, str] = field(default_factory=dict)


class MillRoomCoordinator(DataUpdateCoordinator[MillData]):
    """Coordinator that fetches Mill data with rate limit backoff."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, mill_client: Mill) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Mill Room",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.mill = mill_client
        self._consecutive_errors = 0
        self._house_data: list[dict] = []

    async def _async_update_data(self) -> MillData:
        """Fetch data from Mill API."""
        try:
            # Fetch houses first to get house modes
            houses_resp = await self.mill.cached_request("houses")
            if houses_resp:
                self._house_data = houses_resp.get("ownHouses", [])

            await self.mill.fetch_heater_and_sensor_data()
        except TooManyRequestsError:
            self._consecutive_errors += 1
            backoff = min(
                DEFAULT_SCAN_INTERVAL * (2 ** self._consecutive_errors),
                MAX_BACKOFF_INTERVAL,
            )
            self.update_interval = timedelta(seconds=backoff)
            _LOGGER.warning(
                "Mill rate limited, backing off to %s seconds", backoff
            )
            if self.data:
                return self.data
            raise UpdateFailed("Rate limited with no cached data")
        except Exception as err:
            if "Incorrect login or password" in str(err):
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(f"Error communicating with Mill API: {err}") from err

        self._consecutive_errors = 0
        self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        return self._build_data()

    def _build_data(self) -> MillData:
        """Build MillData from the mill client's device dict."""
        data = MillData()

        # Extract house modes
        for house in self._house_data:
            house_id = house.get("id")
            if house_id:
                data.house_modes[house_id] = house.get("mode") or "weekly_program"

        for device_id, device in self.mill.devices.items():
            if not isinstance(device, (Heater, Socket)):
                continue

            data.devices[device_id] = device

            if device.independent_device or not device.room_id:
                continue

            if device.room_id not in data.rooms:
                room = RoomData(
                    room_id=device.room_id,
                    room_name=device.room_name or "Unknown Room",
                    home_id=device.home_id,
                    avg_temp=device.room_avg_temp,
                )
                if device.room_data:
                    room.comfort_temp = device.room_data.get(
                        "roomComfortTemperature"
                    )
                    room.sleep_temp = device.room_data.get(
                        "roomSleepTemperature"
                    )
                    room.away_temp = device.room_data.get(
                        "roomAwayTemperature"
                    )
                    # Room-level override mode (if the room overrides the house)
                    room.override_mode = device.room_data.get("overrideMode")
                    room.override_mode_type = device.room_data.get(
                        "overrideModeType"
                    )

                # Determine the effective active mode for this room
                house_mode = data.house_modes.get(device.home_id)
                if room.override_mode:
                    room.active_mode = room.override_mode
                elif house_mode:
                    room.active_mode = house_mode

                data.rooms[device.room_id] = room

            data.rooms[device.room_id].device_ids.append(device_id)

        return data

    async def async_set_room_temperatures(
        self,
        room_id: str,
        comfort_temp: float | None = None,
        sleep_temp: float | None = None,
        away_temp: float | None = None,
    ) -> None:
        """Set room temperatures and schedule a refresh."""
        await self.mill.set_room_temperatures(
            room_id,
            sleep_temp=sleep_temp,
            comfort_temp=comfort_temp,
            away_temp=away_temp,
        )
        await asyncio.sleep(5)
        await self.async_request_refresh()

    async def async_set_room_mode_override(
        self,
        room_id: str,
        mode: str,
    ) -> None:
        """Override the room mode (comfort/sleep/away/off etc)."""
        payload = {
            "mode": mode,
            "overrideModeType": "continuous",
        }
        self.mill._cache.clear()
        await self.mill.request(
            f"rooms/{room_id}/mode/override", payload
        )
        await asyncio.sleep(2)
        await self.async_request_refresh()

    async def async_clear_room_mode_override(self, room_id: str) -> None:
        """Remove room mode override, falling back to house mode."""
        self.mill._cache.clear()
        url = f"{API_ENDPOINT}rooms/{room_id}/mode/override"
        headers = self.mill._build_headers(include_auth=True)
        async with asyncio.timeout(self.mill._timeout):
            await self.mill.websession.delete(url, headers=headers)
        await asyncio.sleep(2)
        await self.async_request_refresh()

    async def async_heater_control(
        self, device_id: str, power_status: bool
    ) -> None:
        """Control a heater/socket power status.

        Tries setting operation_mode directly first. If the API returns
        409 (device is on a program), falls back to overriding the
        weekly program instead.
        """
        device = self.mill.devices.get(device_id)
        if not device:
            return

        # Sockets support always_on/always_off via additional_socket_mode
        if isinstance(device, Socket):
            socket_mode = "always_on" if power_status else "always_off"
            payload = {
                "deviceType": device.device_type,
                "enabled": True,
                "settings": {
                    "additional_socket_mode": socket_mode,
                },
            }
        else:
            payload = {
                "deviceType": device.device_type,
                "enabled": power_status,
                "settings": {
                    "operation_mode": (
                        "control_individually" if power_status else "off"
                    ),
                },
            }

        result = await self.mill.request(
            f"devices/{device_id}/settings", payload, patch=True
        )
        if result is not None:
            self.mill._cache.clear()
            device.power_status = power_status

    async def async_set_heater_temp(
        self, device_id: str, temperature: float
    ) -> None:
        """Set an individual heater's temperature."""
        await self.mill.set_heater_temp(device_id, temperature)
