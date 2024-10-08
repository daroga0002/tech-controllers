"""Ruckus DataUpdateCoordinator."""

import asyncio
import logging

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, CONTROLLER, DOMAIN, SCAN_INTERVAL, UDID
from .tech import Tech, TechError, TechLoginError

_LOGGER = logging.getLogger(__package__)


class TechCoordinator(DataUpdateCoordinator):
    """TECH API data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, session: ClientSession, user_id: str, token: str
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        self.api = Tech(session, user_id, token)

    async def _async_update_data(self) -> dict:
        """Fetch data from TECH API endpoint(s)."""

        _LOGGER.debug(
            "Updating data for: %s", str(self.config_entry.data[CONTROLLER][CONF_NAME])
        )

        try:
            async with asyncio.timeout(API_TIMEOUT):
                return await self.api.module_data(
                    self.config_entry.data[CONTROLLER][UDID]
                )
        except TechLoginError as err:
            raise ConfigEntryAuthFailed from err
        except TechError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
