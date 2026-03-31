"""Base entity classes for Mill Room integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MillRoomCoordinator


class MillRoomEntity(CoordinatorEntity[MillRoomCoordinator]):
    """Base entity for a Mill room."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MillRoomCoordinator, room_id: str) -> None:
        """Initialize the room entity."""
        super().__init__(coordinator)
        self._room_id = room_id

    @property
    def room_data(self):
        """Return the room data from the coordinator."""
        return self.coordinator.data.rooms.get(self._room_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the room."""
        room = self.room_data
        return DeviceInfo(
            identifiers={(DOMAIN, self._room_id)},
            name=room.room_name if room else "Unknown Room",
            manufacturer="Mill",
            suggested_area=room.room_name if room else None,
        )


class MillDeviceEntity(CoordinatorEntity[MillRoomCoordinator]):
    """Base entity for an individual Mill device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillRoomCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device entity."""
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_data(self):
        """Return the device data from the coordinator."""
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the heater."""
        device = self.device_data
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device.name if device else "Unknown Device",
            manufacturer="Mill",
            model=device.model if device else None,
        )
        # Link to room device if this device belongs to a room
        if device and device.room_id and not device.independent_device:
            info["via_device"] = (DOMAIN, device.room_id)
        return info
