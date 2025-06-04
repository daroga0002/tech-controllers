"""Python wrapper for getting interaction with Tech devices."""

import asyncio
from collections.abc import Callable
from functools import wraps
import json
import logging
import time

import aiohttp

from .const import TECH_SUPPORTED_LANGUAGES

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


def require_auth(func: Callable) -> Callable:
    """Check authentication before API calls.

    This decorator ensures the user is authenticated before making API calls.

    Args:
        func: The function to decorate

    Returns:
        The wrapped function that checks authentication

    Raises:
        TechError: If not authenticated

    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.authenticated:
            raise TechError(401, "Unauthorized")
        return await func(self, *args, **kwargs)

    return wrapper


class Tech:
    """Main class to perform Tech API requests."""

    TECH_API_URL = "https://emodul.eu/api/v1/"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        user_id=None,
        token=None,
        base_url=TECH_API_URL,
    ) -> None:
        """Initialize the Tech object.

        Args:
        session (aiohttp.ClientSession): The aiohttp client session.
        user_id (str): The user ID.
        token (str): The authentication token.
        base_url (str): The base URL for the API.

        """
        _LOGGER.debug("Init Tech")
        self.headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
        self.base_url = base_url
        self.session = session
        if user_id and token:
            self.user_id = user_id
            self.token = token
            self.headers.setdefault("Authorization", f"Bearer {token}")
            self.authenticated = True
        else:
            self.authenticated = False
        self.last_update = None
        self.update_lock = asyncio.Lock()
        self.modules = {}

    def _filter_zones(self, zones: list[dict]) -> list[dict]:
        """Filter valid zones from the list.

        Args:
            zones: List of zone dictionaries

        Returns:
            List of filtered valid zones

        """
        return [
            z
            for z in zones
            if z and "zone" in z and z["zone"] and "visibility" in z["zone"]
        ]

    def _filter_tiles(self, tiles: list[dict]) -> list[dict]:
        """Filter visible tiles from the list.

        Args:
            tiles: List of tile dictionaries

        Returns:
            List of filtered visible tiles

        """
        return [t for t in tiles if t.get("visibility")]

    async def get(self, request_path):
        """Perform a GET request to the specified request path.

        Args:
        request_path (str): The path to send the GET request to.

        Returns:
        dict: The JSON response data.

        Raises:
        TechError: If the response status is not 200.

        """
        url = self.base_url + request_path
        _LOGGER.debug("Sending GET request: %s", url)
        async with self.session.get(url, headers=self.headers) as response:
            if response.status != 200:
                _LOGGER.warning("Invalid response from Tech API: %s", response.status)
                raise TechError(response.status, await response.text())

            return await response.json()

    async def post(self, request_path, post_data):
        """Send a POST request to the specified URL with the given data.

        Args:
        request_path: The path for the request.
        post_data: The data to be sent with the request.

        Returns:
        The JSON response from the request.

        Raises:
        TechError: If the response status is not 200.

        """
        url = self.base_url + request_path
        _LOGGER.debug("Sending POST request: %s", url)
        headers = self.headers.copy()
        if isinstance(post_data, str):
            headers["Content-Type"] = "application/json"
        async with self.session.post(url, data=post_data, headers=headers) as response:
            if response.status != 200:
                _LOGGER.warning("Invalid response from Tech API: %s", response.status)
                raise TechError(response.status, await response.text())

            return await response.json()

    async def authenticate(self, username, password):
        """Authenticate the user with the given username and password.

        Args:
        username: str, the username of the user
        password: str, the password of the user

        Returns:
        bool, indicating whether the user was authenticated successfully

        """
        path = "authentication"
        post_data = json.dumps({"username": username, "password": password})
        try:
            result = await self.post(path, post_data)
            self.authenticated = result["authenticated"]
            if self.authenticated:
                self.user_id = str(result["user_id"])
                self.token = result["token"]
                self.headers = {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "Authorization": f"Bearer {self.token}",
                }
        except TechError as err:
            raise TechLoginError(401, "Unauthorized") from err
        return result["authenticated"]

    @require_auth
    async def list_modules(self):
        """Retrieve the list of modules for the authenticated user.

        Returns:
            result: The list of modules for the authenticated user.

        Raises:
            TechError: If the user is not authenticated.

        """
        path = f"users/{self.user_id}/modules"
        return await self.get(path)

    @require_auth
    async def get_module_data(self, module_udid):
        """Retrieve module data for a given module ID.

        Args:
        module_udid (str): The unique ID of the module to retrieve.

        Returns:
        dict: The data of the retrieved module.

        Raises:
        TechError: If not authenticated, raise 401 Unauthorized error.

        """
        path = f"users/{self.user_id}/modules/{module_udid}"
        return await self.get(path)

    @require_auth
    async def get_translations(self, language):
        """Retrieve language pack for a given language.

        If language doesnt exists it will return default "en".
        This is required assumption as Tech API is returning
        400 error for non-existent languages.

        Args:
        language (str): Language code.

        Returns:
        dict: The data of the retrieved language pack with translations.

        Raises:
        TechError: If not authenticated, raise 401 Unauthorized error.

        """

        if language not in TECH_SUPPORTED_LANGUAGES:
            _LOGGER.debug("Language %s not supported. Switching to default", language)
            language = "en"

        _LOGGER.debug("Getting %s language", language)

        path = f"i18n/{language}"
        return await self.get(path)

    @require_auth
    async def get_module_zones(self, module_udid):
        """Return Tech module zones.

        Return Tech module zones for given module udid.

        Args:
        self (Tech): The instance of the Tech API.
        module_udid (string): The Tech module udid.

        Returns:
        Dictionary of zones indexed by zone ID.

        """

        _LOGGER.debug("Updating module zones ... %s", module_udid)
        if module_udid not in self.modules:
            self.modules[module_udid] = {"last_update": None, "zones": {}, "tiles": {}}
        result = await self.get_module_data(module_udid)
        zones = self._filter_zones(result["zones"]["elements"])
        self.modules[module_udid]["zones"].clear()
        for zone in zones:
            self.modules[module_udid]["zones"][zone["zone"]["id"]] = zone
        return self.modules[module_udid]["zones"]

    @require_auth
    async def get_module_tiles(self, module_udid):
        """Return Tech module tiles.

        Return Tech module tiles for given module udid.

        Args:
        self (Tech): The instance of the Tech API.
        module_udid (string): The Tech module udid.

        Returns:
        Dictionary of zones indexed by zone ID.

        """

        _LOGGER.debug("Updating module tiles ... %s", module_udid)
        if module_udid not in self.modules:
            self.modules[module_udid] = {"last_update": None, "zones": {}, "tiles": {}}
        result = await self.get_module_data(module_udid)
        tiles = self._filter_tiles(result["tiles"])
        self.modules[module_udid]["tiles"].clear()
        for tile in tiles:
            self.modules[module_udid]["tiles"][tile["id"]] = tile
        return self.modules[module_udid]["tiles"]

    @require_auth
    async def module_data(self, module_udid):
        """Update Tech module zones and tiles.

        Update all the values for Tech module. It includes
        zones and tiles data.

        Args:
            module_udid (string): The Tech module udid.

        Returns:
            Dictionary of zones and tiles indexed by zone ID.

        """
        now = time.time()
        self.modules.setdefault(
            module_udid, {"last_update": None, "zones": {}, "tiles": {}}
        )
        _LOGGER.debug("Updating module zones & tiles ... %s", module_udid)
        result = await self.get_module_data(module_udid)
        zones_elements = result.get("zones", {}).get("elements", [])
        if zones_elements:
            zones = self._filter_zones(zones_elements)
            registered_zones = [
                z
                for z in zones
                if z
                and "zone" in z
                and z["zone"]
                and z["zone"].get("zoneState") != "zoneUnregistered"
            ]
            zones_dict = self.modules[module_udid]["zones"]
            zones_dict.clear()
            for zone in registered_zones:
                zones_dict[zone["zone"]["id"]] = zone
        tiles = result.get("tiles", [])
        if tiles:
            visible_tiles = self._filter_tiles(tiles)
            tiles_dict = self.modules[module_udid]["tiles"]
            tiles_dict.clear()
            for tile in visible_tiles:
                tiles_dict[tile["id"]] = tile
        self.modules[module_udid]["last_update"] = now
        return self.modules[module_udid]

    async def get_zone(self, module_udid, zone_id):
        """Return zone from Tech API.

        Args:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.

        Returns:
        Dictionary of zone.

        """
        if (
            module_udid in self.modules
            and zone_id in self.modules[module_udid]["zones"]
        ):
            return self.modules[module_udid]["zones"][zone_id]
        await self.get_module_zones(module_udid)
        return self.modules[module_udid]["zones"][zone_id]

    async def get_tile(self, module_udid, tile_id):
        """Return tile from Tech API.

        Args:
        module_udid (string): The Tech module udid.
        tile_id (int): The Tech module zone ID.

        Returns:
        Dictionary of tile.

        """
        if (
            module_udid in self.modules
            and tile_id in self.modules[module_udid]["tiles"]
        ):
            return self.modules[module_udid]["tiles"][tile_id]
        await self.get_module_tiles(module_udid)
        return self.modules[module_udid]["tiles"][tile_id]

    @require_auth
    async def set_const_temp(self, module_udid, zone_id, target_temp):
        """Set constant temperature of the zone.

        Args:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.
        target_temp (float): The target temperature to be set within the zone.

        Returns:
        JSON object with the result.

        """
        _LOGGER.debug("Setting zone constant temperature…")
        if (
            module_udid not in self.modules
            or zone_id not in self.modules[module_udid]["zones"]
        ):
            await self.get_zone(module_udid, zone_id)
        path = f"users/{self.user_id}/modules/{module_udid}/zones"
        data = {
            "mode": {
                "id": self.modules[module_udid]["zones"][zone_id]["mode"]["id"],
                "parentId": zone_id,
                "mode": "constantTemp",
                "constTempTime": 60,
                "setTemperature": int(target_temp * 10),
                "scheduleIndex": 0,
            }
        }
        _LOGGER.debug(data)
        result = await self.post(path, json.dumps(data))
        _LOGGER.debug(result)
        return result

    @require_auth
    async def set_zone(self, module_udid, zone_id, on=True):
        """Turn the zone on or off.

        Args:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.
        on (bool): Flag indicating to turn the zone on if True or off if False.

        Returns:
        JSON object with the result.

        """
        _LOGGER.debug("Turing zone on/off: %s", on)
        path = f"users/{self.user_id}/modules/{module_udid}/zones"
        data = {"zone": {"id": zone_id, "zoneState": "zoneOn" if on else "zoneOff"}}
        _LOGGER.debug(data)
        result = await self.post(path, json.dumps(data))
        _LOGGER.debug(result)
        return result


class TechError(Exception):
    """Raised when Tech API request ended in error.

    Attributes:
        status_code - error code returned by Tech API
        status - more detailed description

    """

    def __init__(self, status_code, status) -> None:
        """Initialize the status code and status of the object.

        Args:
            status_code (int): The status code to be assigned.
            status (str): The status to be assigned.

        """
        self.status_code = status_code
        self.status = status


class TechLoginError(Exception):
    """Raised when Tech API login fails.

    Attributes:
        status_code - error code returned by Tech API
        status - more detailed description

    """

    def __init__(self, status_code, status) -> None:
        """Initialize the status code and status of the object.

        Args:
            status_code (int): The status code to be assigned.
            status (str): The status to be assigned.

        """
        self.status_code = status_code
        self.status = status
