# Modified from Home Assistant Core; see PROVENANCE.md for scope and sources.
"""Platform for shared base classes for sensors."""

from typing import override

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyintelliclima import IntelliClimaC800, IntelliClimaECO2, IntelliClimaECO3

from .const import DOMAIN
from .coordinator import IntelliClimaCoordinator


def eco_device_info(device: IntelliClimaECO2 | IntelliClimaECO3) -> DeviceInfo:
    """Return the device info shared by all entities of an ECOCOMFORT 2.0."""
    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"eco3_{device.id}" if isinstance(device, IntelliClimaECO3) else device.id,
            )
        },
        manufacturer="Fantini Cosmi",
        name=device.name,
        serial_number=device.crono_sn,
        model="ECOCOMFORT 3" if isinstance(device, IntelliClimaECO3) else "ECOCOMFORT 2.0",
        sw_version=device.fw,
        connections={
            (CONNECTION_BLUETOOTH, device.mac),
            (CONNECTION_NETWORK_MAC, device.macwifi),
        },
    )


class IntelliClimaEntity(CoordinatorEntity[IntelliClimaCoordinator]):
    """Define a generic class for IntelliClima entities."""

    _attr_has_entity_name = True
    _attr_device_info: DeviceInfo

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2 | IntelliClimaECO3 | IntelliClimaC800,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        # Make this HA "device" use the IntelliClima device name.
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"eco3_{device.id}" if isinstance(device, IntelliClimaECO3) else device.id,
                )
            },
            manufacturer="Fantini Cosmi",
            name=device.name,
            serial_number=device.crono_sn,
        )

        self._device_id = device.id
        self._device_sn = device.crono_sn


class IntelliClimaECOEntity(IntelliClimaEntity):
    """Specific entity for the ECOCOMFORT 2.0."""

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2 | IntelliClimaECO3,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._attr_device_info = eco_device_info(device)
        # Mantiene separate le famiglie anche durante i successivi aggiornamenti.
        self._is_eco3 = isinstance(device, IntelliClimaECO3)
        self._identity = f"eco3_{device.id}" if self._is_eco3 else device.id

    @property
    def _devices(self) -> dict[str, IntelliClimaECO2] | dict[str, IntelliClimaECO3]:
        data = self.coordinator.data
        return data.ecocomfort3_devices if self._is_eco3 else data.ecocomfort2_devices

    @property
    def _device_data(self) -> IntelliClimaECO2 | IntelliClimaECO3:
        return self._devices[self._device_id]

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self._device_id in self._devices
            and (not self._is_eco3 or self._device_data.online_status)
        )
