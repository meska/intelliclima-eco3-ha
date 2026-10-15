# Modified from Home Assistant Core; see PROVENANCE.md for scope and sources.
"""Sensor platform for IntelliClima VMC."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyintelliclima import IntelliClimaECO2, IntelliClimaECO3

from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntelliClimaSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[IntelliClimaECO2 | IntelliClimaECO3], int | float | str | None]


INTELLICLIMA_SENSORS: tuple[IntelliClimaSensorEntityDescription, ...] = (
    IntelliClimaSensorEntityDescription(
        key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device_data: float(device_data.tamb),
    ),
    IntelliClimaSensorEntityDescription(
        key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device_data: float(device_data.rh),
    ),
    IntelliClimaSensorEntityDescription(
        key="voc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda device_data: float(device_data.voc_state),
    ),
)


# ECO3 reports VOC-derived equivalent CO2 in voc_state, not the co2 register.
ECO3_SENSORS = (
    *INTELLICLIMA_SENSORS[:2],
    IntelliClimaSensorEntityDescription(
        key="equivalent_co2",
        name="Equivalent CO2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda device_data: float(device_data.voc_state),
    ),
    IntelliClimaSensorEntityDescription(
        key="air_quality_index",
        name="Air quality index",
        value_fn=lambda device_data: float(device_data.aqi),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliClima Sensors."""
    coordinator = entry.runtime_data.devices_coordinator

    entities: list[IntelliClimaSensor] = [
        IntelliClimaSensor(coordinator=coordinator, device=ecocomfort2, description=description)
        for ecocomfort2 in coordinator.data.ecocomfort2_devices.values()
        for description in INTELLICLIMA_SENSORS
    ]

    entities.extend(
        IntelliClimaSensor(coordinator, device, description)
        for device in coordinator.data.ecocomfort3_devices.values()
        for description in ECO3_SENSORS
    )
    async_add_entities(entities)


class IntelliClimaSensor(IntelliClimaECOEntity, SensorEntity):
    """Extends IntelliClimaEntity with Sensor specific logic."""

    entity_description: IntelliClimaSensorEntityDescription

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2 | IntelliClimaECO3,
        description: IntelliClimaSensorEntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self.entity_description = description

        self._attr_unique_id = f"{self._identity}_{description.key}"

    @property
    @override
    def native_value(self) -> int | float | str | None:
        """Use this to get the correct value."""
        try:
            value = self.entity_description.value_fn(self._device_data)
            if value is None:
                return None
            value = float(value)
        except TypeError, ValueError:
            return None
        if not math.isfinite(value):
            return None
        key = self.entity_description.key
        if key == "air_quality_index" and value not in (1, 2, 3, 4, 5):
            return None
        if key == "temperature" and value == 327.67:
            return None
        if key == "humidity" and not 0 <= value <= 100:
            return None
        if key in ("voc", "equivalent_co2") and not 0 <= value < 65535:
            return None
        return value
