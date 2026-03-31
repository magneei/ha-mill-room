"""The Mill Room integration."""

from __future__ import annotations

import logging

import mill

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import MillRoomCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

type MillRoomConfigEntry = ConfigEntry[MillRoomCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MillRoomConfigEntry) -> bool:
    """Set up Mill Room from a config entry."""
    mill_client = mill.Mill(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )

    if not await mill_client.connect():
        _LOGGER.error("Failed to connect to Mill API")
        return False

    coordinator = MillRoomCoordinator(hass, mill_client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MillRoomConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
