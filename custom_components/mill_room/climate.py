"""Climate entities for Mill Room integration."""

from __future__ import annotations

import logging
from typing import Any

from mill import Heater

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from . import MillRoomConfigEntry
from .const import DOMAIN, PRESET_AWAY, PRESET_COMFORT, PRESET_SLEEP
from .coordinator import MillRoomCoordinator
from .entity import MillDeviceEntity, MillRoomEntity

_LOGGER = logging.getLogger(__name__)

# Maps our preset names to RoomData attribute names
PRESET_TO_TEMP_KEY = {
    PRESET_COMFORT: "comfort_temp",
    PRESET_SLEEP: "sleep_temp",
    PRESET_AWAY: "away_temp",
}

# Maps our preset names to the API keyword args for set_room_temperatures
PRESET_TO_API_KEY = {
    PRESET_COMFORT: "comfort_temp",
    PRESET_SLEEP: "sleep_temp",
    PRESET_AWAY: "away_temp",
}

# Maps Mill API mode strings to our preset names
API_MODE_TO_PRESET = {
    "comfort": PRESET_COMFORT,
    "sleep": PRESET_SLEEP,
    "away": PRESET_AWAY,
}

# Maps our preset names to Mill API mode strings
PRESET_TO_API_MODE = {v: k for k, v in API_MODE_TO_PRESET.items()}


async def async_setup_entry(
    hass, entry: MillRoomConfigEntry, async_add_entities
) -> None:
    """Set up Mill climate entities."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = []

    for room_id in coordinator.data.rooms:
        entities.append(MillRoomClimate(coordinator, room_id))

    for device_id, device in coordinator.data.devices.items():
        if isinstance(device, Heater) and device.independent_device:
            entities.append(MillIndividualClimate(coordinator, device_id))

    async_add_entities(entities)


class MillRoomClimate(MillRoomEntity, ClimateEntity):
    """Climate entity representing a Mill room."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_COMFORT, PRESET_SLEEP, PRESET_AWAY]
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: MillRoomCoordinator, room_id: str) -> None:
        """Initialize room climate entity."""
        super().__init__(coordinator, room_id)
        self._attr_unique_id = f"{DOMAIN}_{room_id}_climate"

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return "Climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        room = self.room_data
        return room.avg_temp if room else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for the active preset."""
        room = self.room_data
        if not room:
            return None
        preset = self.preset_mode
        if preset:
            key = PRESET_TO_TEMP_KEY.get(preset)
            if key:
                return getattr(room, key, None)
        return room.comfort_temp

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode from the API."""
        room = self.room_data
        if not room or not room.active_mode:
            return PRESET_COMFORT
        return API_MODE_TO_PRESET.get(room.active_mode)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        room = self.room_data
        if not room:
            return HVACMode.OFF

        # If the active mode is "off", report OFF
        if room.active_mode == "off":
            return HVACMode.OFF

        for device_id in room.device_ids:
            device = self.coordinator.data.devices.get(device_id)
            if device and device.power_status:
                return HVACMode.HEAT

        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        room = self.room_data
        if not room:
            return HVACAction.OFF

        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        for device_id in room.device_ids:
            device = self.coordinator.data.devices.get(device_id)
            if device and device.is_heating:
                return HVACAction.HEATING

        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the active preset."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        preset = self.preset_mode or PRESET_COMFORT
        api_key = PRESET_TO_API_KEY[preset]
        await self.coordinator.async_set_room_temperatures(
            self._room_id, **{api_key: temperature}
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode via room override API."""
        api_mode = PRESET_TO_API_MODE.get(preset_mode)
        if not api_mode:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return
        await self.coordinator.async_set_room_mode_override(
            self._room_id, api_mode
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_room_mode_override(
                self._room_id, "off"
            )
        elif hvac_mode == HVACMode.HEAT:
            # Turning on: set to comfort mode (or clear override to resume program)
            await self.coordinator.async_set_room_mode_override(
                self._room_id, "comfort"
            )


class MillIndividualClimate(MillDeviceEntity, ClimateEntity):
    """Climate entity for an individually-controlled Mill heater."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5

    def __init__(
        self, coordinator: MillRoomCoordinator, device_id: str
    ) -> None:
        """Initialize individual climate entity."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{DOMAIN}_{device_id}_climate"

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return "Climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device = self.device_data
        return device.current_temp if device else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        device = self.device_data
        return device.set_temp if device else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self.device_data
        if device and device.power_status:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        device = self.device_data
        if not device or not device.power_status:
            return HVACAction.OFF
        if device.is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_set_heater_temp(
            self._device_id, temperature
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        power_on = hvac_mode == HVACMode.HEAT
        await self.coordinator.async_heater_control(self._device_id, power_on)
        self.async_write_ha_state()
