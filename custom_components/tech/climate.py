"""The Tech Controllers Coordinator."""

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DESCRIPTION,
    CONF_ID,
    CONF_NAME,
    CONF_ZONE,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONTROLLER, DOMAIN, INCLUDE_HUB_IN_NAME, MANUFACTURER, UDID, VER
from .coordinator import TechCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_TEMP = 5
DEFAULT_MAX_TEMP = 35
SUPPORT_HVAC = [HVACMode.HEAT, HVACMode.OFF]

# Constants for device zone data keys
ZONE_SET_TEMP = "setTemperature"
ZONE_CURRENT_TEMP = "currentTemperature"
ZONE_HUMIDITY = "humidity"
ZONE_DURING_CHANGE = "duringChange"
ZONE_FLAGS = "flags"
ZONE_RELAY_STATE = "relayState"
ZONE_ALGORITHM = "algorithm"
ZONE_STATE = "zoneState"
ZONE_ID = "id"

# Zone state constants
ZONE_ON = "zoneOn"
NO_ALARM = "noAlarm"
ALGORITHM_HEATING = "heating"
ALGORITHM_COOLING = "cooling"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    udid = config_entry.data[CONTROLLER][UDID]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Setting up entry, controller udid: %s", udid)
    zones = await coordinator.api.get_module_zones(udid)
    thermostats = [
        TechThermostat(zones[zone], coordinator, config_entry) for zone in zones
    ]

    async_add_entities(thermostats, True)


class TechThermostat(ClimateEntity, CoordinatorEntity):
    """Representation of a Tech climate."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, device, coordinator: TechCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the Tech device."""
        _LOGGER.debug("Init TechThermostat…")
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._udid = config_entry.data[CONTROLLER][UDID]
        self._coordinator = coordinator
        self._id = device[CONF_ZONE][CONF_ID]
        self._unique_id = f"{self._udid}_{device[CONF_ZONE][CONF_ID]}"
        self.device_name = (
            device[CONF_DESCRIPTION][CONF_NAME]
            if not self._config_entry.data[INCLUDE_HUB_IN_NAME]
            else f"{self._config_entry.title} {device[CONF_DESCRIPTION][CONF_NAME]}"
        )

        self.manufacturer = MANUFACTURER
        self.model = f"{config_entry.data[CONTROLLER][CONF_NAME]}: {config_entry.data[CONTROLLER][VER]}"
        self._temperature = None
        self._target_temperature = None
        self._humidity = None
        self._state = HVACAction.OFF
        self._mode = HVACMode.OFF

        # Cache device info to avoid recreating it on every access
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self.device_name,
            model=self.model,
            manufacturer=self.manufacturer,
        )

        self.update_properties(device)
        # Remove the line below after HA 2025.1
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Returns device information in a dictionary format."""
        return self._device_info

    def update_properties(self, device):
        """Update the properties of the HVAC device based on the data from the device.

        Args:
            device (dict): The device data containing information about the device's properties.

        """
        zone_data = device[CONF_ZONE]

        # Update target temperature
        set_temp = zone_data.get(ZONE_SET_TEMP)
        if set_temp is not None:
            if not zone_data.get(ZONE_DURING_CHANGE, False):
                self._target_temperature = set_temp / 10
            else:
                _LOGGER.debug(
                    "Zone ID %s is duringChange so ignore to update target temperature",
                    zone_data.get(ZONE_ID),
                )
        else:
            self._target_temperature = None

        # Update current temperature
        current_temp = zone_data.get(ZONE_CURRENT_TEMP)
        self._temperature = current_temp / 10 if current_temp is not None else None

        # Update humidity
        humidity = zone_data.get(ZONE_HUMIDITY)
        self._humidity = humidity if humidity is not None and humidity >= 0 else None

        # Update HVAC state and mode
        flags = zone_data.get(ZONE_FLAGS, {})
        relay_state = flags.get(ZONE_RELAY_STATE)
        algorithm = flags.get(ZONE_ALGORITHM)

        if relay_state == STATE_ON:
            if algorithm == ALGORITHM_HEATING:
                self._state = HVACAction.HEATING
            elif algorithm == ALGORITHM_COOLING:
                self._state = HVACAction.COOLING
            else:
                self._state = HVACAction.IDLE
        elif relay_state == STATE_OFF:
            self._state = HVACAction.IDLE
        else:
            self._state = HVACAction.OFF

        # Update HVAC mode
        zone_state = zone_data.get(ZONE_STATE)
        if zone_state in (ZONE_ON, NO_ALARM):
            self._mode = HVACMode.HEAT
        else:
            self._mode = HVACMode.OFF

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle updated data from the coordinator."""
        try:
            zone_data = self._coordinator.data["zones"][self._id]
            self.update_properties(zone_data)
            self.async_write_ha_state()
        except KeyError:
            _LOGGER.warning(
                "Zone %s not found in coordinator data for %s",
                self._id,
                self.device_name,
            )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._unique_id}_zone_climate"

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return self._mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return self._state

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return 0.1

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._temperature

    @property
    def current_humidity(self) -> float | None:
        """Return current humidity."""
        return self._humidity

    @property
    def min_temp(self) -> float:
        """Return the minimal allowed temperature value."""
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum allowed temperature value."""
        return DEFAULT_MAX_TEMP

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            # Validate temperature bounds
            if not (self.min_temp <= temperature <= self.max_temp):
                _LOGGER.warning(
                    "%s: Temperature %s is out of bounds [%s, %s]",
                    self.device_name,
                    temperature,
                    self.min_temp,
                    self.max_temp,
                )
                return

            _LOGGER.debug(
                "%s: Setting temperature to %s", self.device_name, temperature
            )
            await self._coordinator.api.set_const_temp(
                self._udid, self._id, temperature
            )
            self._target_temperature = temperature
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("%s: Setting hvac mode to %s", self.device_name, hvac_mode)
        if hvac_mode == HVACMode.OFF:
            await self._coordinator.api.set_zone(self._udid, self._id, False)
            self._mode = HVACMode.OFF
        elif hvac_mode == HVACMode.HEAT:
            await self._coordinator.api.set_zone(self._udid, self._id, True)
            self._mode = HVACMode.HEAT

        await self.coordinator.async_request_refresh()
