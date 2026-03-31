"""Sensor entities for Mill Room integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mill import Heater, Socket

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature

from . import MillRoomConfigEntry
from .const import DOMAIN
from .coordinator import MillRoomCoordinator
from .entity import MillDeviceEntity


@dataclass(frozen=True, kw_only=True)
class MillSensorEntityDescription(SensorEntityDescription):
    """Describes a Mill sensor entity."""

    value_fn: Callable[[Heater | Socket], float | None]
    available_fn: Callable[[Heater | Socket], bool] = lambda _: True


SENSOR_DESCRIPTIONS: tuple[MillSensorEntityDescription, ...] = (
    MillSensorEntityDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        name="Ambient temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.current_temp,
    ),
    MillSensorEntityDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        name="Floor temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.floor_temperature,
        available_fn=lambda device: device.floor_temperature is not None,
    ),
    MillSensorEntityDescription(
        key="daily_energy",
        translation_key="daily_energy",
        name="Daily energy consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.day_consumption,
    ),
)


async def async_setup_entry(
    hass, entry: MillRoomConfigEntry, async_add_entities
) -> None:
    """Set up Mill sensor entities."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for device_id, device in coordinator.data.devices.items():
        if not isinstance(device, (Heater, Socket)):
            continue
        for description in SENSOR_DESCRIPTIONS:
            if description.available_fn(device):
                entities.append(
                    MillDeviceSensor(coordinator, device_id, description)
                )

    async_add_entities(entities)


class MillDeviceSensor(MillDeviceEntity, SensorEntity):
    """Sensor entity for a Mill heater."""

    entity_description: MillSensorEntityDescription

    def __init__(
        self,
        coordinator: MillRoomCoordinator,
        device_id: str,
        description: MillSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        device = self.device_data
        if not device:
            return None
        return self.entity_description.value_fn(device)
