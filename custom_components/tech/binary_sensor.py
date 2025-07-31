"""Platform for binary sensor integration."""

import logging
from typing import Any

from homeassistant.components import binary_sensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PARAMS, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from . import TechCoordinator, assets
from .const import (
    CONTROLLER,
    DOMAIN,
    TYPE_ADDITIONAL_PUMP,
    TYPE_FIRE_SENSOR,
    TYPE_RELAY,
    UDID,
    VISIBILITY,
)
from .entity import TileEntity

_LOGGER = logging.getLogger(__name__)

# Mapping of tile types to device classes
TILE_TYPE_TO_DEVICE_CLASS = {
    TYPE_FIRE_SENSOR: binary_sensor.BinarySensorDeviceClass.MOTION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up binary sensor entities")
    controller = config_entry.data[CONTROLLER]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    controller_udid = controller[UDID]
    tiles = await coordinator.api.get_module_tiles(controller_udid)

    entities = []
    supported_types = {TYPE_RELAY, TYPE_FIRE_SENSOR, TYPE_ADDITIONAL_PUMP}

    for tile_id, tile in tiles.items():
        if not tile.get(VISIBILITY, True):
            continue

        tile_type = tile[CONF_TYPE]
        if tile_type not in supported_types:
            continue

        # Get device class for specific tile types
        device_class = TILE_TYPE_TO_DEVICE_CLASS.get(tile_type)

        entity = RelaySensor(tile, coordinator, config_entry, device_class)
        entities.append(entity)

        _LOGGER.debug(
            "Added binary sensor entity for tile %s (type: %s)", tile_id, tile_type
        )

    if entities:
        async_add_entities(entities, True)
        _LOGGER.debug("Successfully added %d binary sensor entities", len(entities))


class TileBinarySensor(TileEntity, binary_sensor.BinarySensorEntity):
    """Representation of a TileBinarySensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: TechCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the tile binary sensor."""
        super().__init__(device, coordinator, config_entry)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._unique_id}_tile_binary_sensor"

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return bool(self._state) if self._state is not None else None

    def get_state(self, device: dict[str, Any]) -> bool:
        """Get the state of the device.

        Args:
            device: The device data dictionary

        Returns:
            bool: The binary state of the device

        """
        # Default implementation - can be overridden by subclasses
        return bool(device.get(CONF_PARAMS, {}).get("workingStatus", False))


class RelaySensor(TileBinarySensor):
    """Representation of a RelaySensor."""

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: TechCoordinator,
        config_entry: ConfigEntry,
        device_class: binary_sensor.BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the tile relay sensor.

        Args:
            device: The device data dictionary
            coordinator: The coordinator instance
            config_entry: The config entry
            device_class: Optional binary sensor device class

        """
        super().__init__(device, coordinator, config_entry)
        self._attr_device_class = device_class
        self._setup_icon(device)

    def _setup_icon(self, device: dict[str, Any]) -> None:
        """Set up the icon for the sensor.

        Args:
            device: The device data dictionary

        """
        params = device.get(CONF_PARAMS, {})
        icon_id = params.get("iconId")

        if icon_id:
            self._attr_icon = assets.get_icon(icon_id)
        else:
            self._attr_icon = assets.get_icon_by_type(device[CONF_TYPE])

    def get_state(self, device: dict[str, Any]) -> bool:
        """Get device state.

        Args:
            device: The device data dictionary

        Returns:
            bool: The working status of the device

        """
        params = device.get(CONF_PARAMS, {})
        working_status = params.get("workingStatus", False)
        return bool(working_status)
