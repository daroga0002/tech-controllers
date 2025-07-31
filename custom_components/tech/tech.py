"""Python wrapper for getting interaction with Tech devices."""

import asyncio
from collections.abc import Callable
from functools import wraps
import json
import logging
import time
from typing import Any, Optional

import aiohttp

from .const import TECH_SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)


def handle_api_errors(func: Callable) -> Callable:
    """Handle common API errors."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.authenticated and func.__name__ not in ["authenticate"]:
            raise TechError(401, "Not authenticated")
        try:
            return await func(self, *args, **kwargs)
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error in %s: %s", func.__name__, err)
            raise TechError(500, f"HTTP client error: {err}") from err
        except TimeoutError as err:
            _LOGGER.error("Timeout error in %s: %s", func.__name__, err)
            raise TechError(408, "Request timeout") from err

    return wrapper


class Tech:
    """Main class to perform Tech API requests."""

    TECH_API_URL = "https://emodul.eu/api/v1/"
    DEFAULT_TIMEOUT = 30
    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
    }

    def __init__(
        self,
        session: aiohttp.ClientSession,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
        base_url: str = TECH_API_URL,
    ) -> None:
        """Initialize the Tech object.

        Args:
            session: The aiohttp client session.
            user_id: The user ID.
            token: The authentication token.
            base_url: The base URL for the API.

        """
        _LOGGER.debug("Initializing Tech API client")
        self.base_url = base_url.rstrip("/") + "/"
        self.session = session
        self.headers = self.DEFAULT_HEADERS.copy()

        # Authentication setup
        if user_id and token:
            self.user_id = user_id
            self.token = token
            self.headers["Authorization"] = f"Bearer {token}"
            self.authenticated = True
        else:
            self.user_id = None
            self.token = None
            self.authenticated = False

        # State management
        self.last_update: Optional[float] = None
        self.update_lock = asyncio.Lock()
        self.modules: dict[str, dict[str, Any]] = {}

    async def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            data: Optional data for POST requests
            timeout: Request timeout in seconds

        Returns:
            JSON response data

        Raises:
            TechError: If the request fails

        """
        url = self.base_url + path.lstrip("/")

        request_kwargs = {
            "headers": self.headers,
            "timeout": aiohttp.ClientTimeout(total=timeout),
        }

        if data is not None:
            request_kwargs["data"] = (
                json.dumps(data) if isinstance(data, dict) else data
            )

        _LOGGER.debug("Making %s request to: %s", method, url)

        try:
            async with getattr(self.session, method.lower())(
                url, **request_kwargs
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    _LOGGER.warning(
                        "API request failed with status %s: %s",
                        response.status,
                        response_text,
                    )
                    raise TechError(response.status, response_text)

                try:
                    return await response.json()
                except json.JSONDecodeError as err:
                    _LOGGER.error("Failed to decode JSON response: %s", response_text)
                    raise TechError(500, f"Invalid JSON response: {err}") from err

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error: %s", err)
            raise TechError(500, f"HTTP client error: {err}") from err

    @handle_api_errors
    async def get(self, path: str) -> dict[str, Any]:
        """Perform a GET request to the specified path.

        Args:
            path: The API endpoint path.

        Returns:
            The JSON response data.

        """
        return await self._make_request("GET", path)

    @handle_api_errors
    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request to the specified path with the given data.

        Args:
            path: The API endpoint path.
            data: The data to be sent with the request.

        Returns:
            The JSON response from the request.

        """
        return await self._make_request("POST", path, data)

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate the user with the given username and password.

        Args:
            username: The username of the user.
            password: The password of the user.

        Returns:
            True if authentication was successful, False otherwise.

        Raises:
            TechLoginError: If authentication fails.

        """
        _LOGGER.debug("Attempting to authenticate user: %s", username)

        auth_data = {"username": username, "password": password}

        try:
            result = await self._make_request("POST", "authentication", auth_data)

            self.authenticated = result.get("authenticated", False)

            if self.authenticated:
                self.user_id = str(result["user_id"])
                self.token = result["token"]
                self.headers["Authorization"] = f"Bearer {self.token}"
                _LOGGER.debug("Authentication successful for user: %s", username)
            else:
                _LOGGER.warning("Authentication failed for user: %s", username)

        except TechError as err:
            _LOGGER.error("Authentication error for user %s: %s", username, err)
            raise TechLoginError(401, "Authentication failed") from err

        return self.authenticated

    @handle_api_errors
    async def list_modules(self) -> dict[str, Any]:
        """Retrieve the list of modules for the authenticated user.

        Returns:
            The list of modules for the authenticated user.

        """
        path = f"users/{self.user_id}/modules"
        return await self.get(path)

    @handle_api_errors
    async def get_module_data(self, module_udid: str) -> dict[str, Any]:
        """Retrieve module data for a given module ID.

        Args:
            module_udid: The unique ID of the module to retrieve.

        Returns:
            The data of the retrieved module.

        """
        _LOGGER.debug("Getting module data for: %s", module_udid)
        path = f"users/{self.user_id}/modules/{module_udid}"
        return await self.get(path)

    @handle_api_errors
    async def get_translations(self, language: str) -> dict[str, Any]:
        """Retrieve language pack for a given language.

        If language doesn't exist, it will return default "en".
        This is required assumption as Tech API returns
        400 error for non-existent languages.

        Args:
            language: Language code.

        Returns:
            The data of the retrieved language pack with translations.

        """
        if language not in TECH_SUPPORTED_LANGUAGES:
            _LOGGER.debug("Language %s not supported. Switching to default", language)
            language = "en"

        _LOGGER.debug("Getting %s language pack", language)
        path = f"i18n/{language}"
        return await self.get(path)

    def _initialize_module_data(self, module_udid: str) -> None:
        """Initialize module data structure if not exists.

        Args:
            module_udid: The module UDID.

        """
        if module_udid not in self.modules:
            self.modules[module_udid] = {"last_update": None, "zones": {}, "tiles": {}}

    def _filter_zones(self, zones: list[dict]) -> list[dict]:
        """Filter zones to include only valid ones.

        Args:
            zones: List of zone data.

        Returns:
            Filtered list of valid zones.

        """
        return [
            zone
            for zone in zones
            if (
                zone is not None
                and "zone" in zone
                and zone["zone"] is not None
                and "visibility" in zone["zone"]
                and zone["zone"].get("zoneState") != "zoneUnregistered"
            )
        ]

    def _filter_tiles(self, tiles: list[dict]) -> list[dict]:
        """Filter tiles to include only visible ones.

        Args:
            tiles: List of tile data.

        Returns:
            Filtered list of visible tiles.

        """
        return [tile for tile in tiles if tile.get("visibility", False)]

    @handle_api_errors
    async def get_module_zones(self, module_udid: str) -> dict[int, dict[str, Any]]:
        """Return Tech module zones.

        Args:
            module_udid: The Tech module udid.

        Returns:
            Dictionary of zones indexed by zone ID.

        """
        _LOGGER.debug("Updating module zones for: %s", module_udid)
        self._initialize_module_data(module_udid)

        result = await self.get_module_data(module_udid)
        zones = result.get("zones", {}).get("elements", [])

        if not zones:
            _LOGGER.debug("No zones found for module: %s", module_udid)
            return self.modules[module_udid]["zones"]

        filtered_zones = self._filter_zones(zones)

        for zone in filtered_zones:
            zone_id = zone["zone"]["id"]
            self.modules[module_udid]["zones"][zone_id] = zone

        _LOGGER.debug(
            "Updated %d zones for module: %s", len(filtered_zones), module_udid
        )
        return self.modules[module_udid]["zones"]

    @handle_api_errors
    async def get_module_tiles(self, module_udid: str) -> dict[int, dict[str, Any]]:
        """Return Tech module tiles.

        Args:
            module_udid: The Tech module udid.

        Returns:
            Dictionary of tiles indexed by tile ID.

        """
        _LOGGER.debug("Updating module tiles for: %s", module_udid)
        self._initialize_module_data(module_udid)

        result = await self.get_module_data(module_udid)
        tiles = result.get("tiles", [])

        if not tiles:
            _LOGGER.debug("No tiles found for module: %s", module_udid)
            return self.modules[module_udid]["tiles"]

        filtered_tiles = self._filter_tiles(tiles)

        for tile in filtered_tiles:
            tile_id = tile["id"]
            self.modules[module_udid]["tiles"][tile_id] = tile

        _LOGGER.debug(
            "Updated %d tiles for module: %s", len(filtered_tiles), module_udid
        )
        return self.modules[module_udid]["tiles"]

    @handle_api_errors
    async def module_data(self, module_udid: str) -> dict[str, Any]:
        """Update Tech module zones and tiles.

        Update all the values for Tech module. It includes
        zones and tiles data.

        Args:
            module_udid: The Tech module udid.

        Returns:
            Dictionary of zones and tiles indexed by their IDs.

        """
        async with self.update_lock:
            now = time.time()
            self._initialize_module_data(module_udid)

            _LOGGER.debug("Updating module zones & tiles for: %s", module_udid)

            result = await self.get_module_data(module_udid)

            # Process zones
            zones = result.get("zones", {}).get("elements", [])
            if zones:
                filtered_zones = self._filter_zones(zones)
                _LOGGER.debug(
                    "Updating %d zones for controller: %s",
                    len(filtered_zones),
                    module_udid,
                )

                for zone in filtered_zones:
                    zone_id = zone["zone"]["id"]
                    self.modules[module_udid]["zones"][zone_id] = zone

            # Process tiles
            tiles = result.get("tiles", [])
            if tiles:
                filtered_tiles = self._filter_tiles(tiles)
                _LOGGER.debug(
                    "Updating %d tiles for controller: %s",
                    len(filtered_tiles),
                    module_udid,
                )

                for tile in filtered_tiles:
                    tile_id = tile["id"]
                    self.modules[module_udid]["tiles"][tile_id] = tile

            self.modules[module_udid]["last_update"] = now
            return self.modules[module_udid]

    async def get_zone(self, module_udid: str, zone_id: int) -> dict[str, Any]:
        """Return zone from Tech API.

        Args:
            module_udid: The Tech module udid.
            zone_id: The Tech module zone ID.

        Returns:
            Dictionary of zone data.

        Raises:
            KeyError: If zone is not found.

        """
        await self.get_module_zones(module_udid)

        if zone_id not in self.modules[module_udid]["zones"]:
            raise KeyError(f"Zone {zone_id} not found in module {module_udid}")

        return self.modules[module_udid]["zones"][zone_id]

    async def get_tile(self, module_udid: str, tile_id: int) -> dict[str, Any]:
        """Return tile from Tech API.

        Args:
            module_udid: The Tech module udid.
            tile_id: The Tech module tile ID.

        Returns:
            Dictionary of tile data.

        Raises:
            KeyError: If tile is not found.

        """
        await self.get_module_tiles(module_udid)

        if tile_id not in self.modules[module_udid]["tiles"]:
            raise KeyError(f"Tile {tile_id} not found in module {module_udid}")

        return self.modules[module_udid]["tiles"][tile_id]

    @handle_api_errors
    async def set_const_temp(
        self, module_udid: str, zone_id: int, target_temp: float
    ) -> dict[str, Any]:
        """Set constant temperature of the zone.

        Args:
            module_udid: The Tech module udid.
            zone_id: The Tech module zone ID.
            target_temp: The target temperature to be set within the zone.

        Returns:
            JSON object with the result.

        """
        _LOGGER.debug(
            "Setting zone %d constant temperature to %.1f°C", zone_id, target_temp
        )

        # Ensure we have the zone data
        await self.get_module_zones(module_udid)

        if zone_id not in self.modules[module_udid]["zones"]:
            raise KeyError(f"Zone {zone_id} not found in module {module_udid}")

        zone_data = self.modules[module_udid]["zones"][zone_id]

        path = f"users/{self.user_id}/modules/{module_udid}/zones"
        data = {
            "mode": {
                "id": zone_data["mode"]["id"],
                "parentId": zone_id,
                "mode": "constantTemp",
                "constTempTime": 60,
                "setTemperature": int(target_temp * 10),
                "scheduleIndex": 0,
            }
        }

        _LOGGER.debug("Sending temperature data: %s", data)
        result = await self.post(path, data)
        _LOGGER.debug("Temperature set result: %s", result)

        return result

    @handle_api_errors
    async def set_zone(
        self, module_udid: str, zone_id: int, on: bool = True
    ) -> dict[str, Any]:
        """Turn the zone on or off.

        Args:
            module_udid: The Tech module udid.
            zone_id: The Tech module zone ID.
            on: Flag indicating to turn the zone on if True or off if False.

        Returns:
            JSON object with the result.

        """
        zone_state = "zoneOn" if on else "zoneOff"
        _LOGGER.debug("Setting zone %d state to: %s", zone_id, zone_state)

        path = f"users/{self.user_id}/modules/{module_udid}/zones"
        data = {"zone": {"id": zone_id, "zoneState": zone_state}}

        _LOGGER.debug("Sending zone state data: %s", data)
        result = await self.post(path, data)
        _LOGGER.debug("Zone state result: %s", result)

        return result

    def is_authenticated(self) -> bool:
        """Check if the client is authenticated.

        Returns:
            True if authenticated, False otherwise.

        """
        return self.authenticated and self.token is not None

    def get_module_last_update(self, module_udid: str) -> Optional[float]:
        """Get the last update timestamp for a module.

        Args:
            module_udid: The module UDID.

        Returns:
            Last update timestamp or None if module not found.

        """
        return self.modules.get(module_udid, {}).get("last_update")

    def clear_module_cache(self, module_udid: Optional[str] = None) -> None:
        """Clear cached module data.

        Args:
            module_udid: Specific module to clear, or None to clear all.

        """
        if module_udid:
            if module_udid in self.modules:
                self.modules[module_udid] = {
                    "last_update": None,
                    "zones": {},
                    "tiles": {},
                }
                _LOGGER.debug("Cleared cache for module: %s", module_udid)
        else:
            self.modules.clear()
            _LOGGER.debug("Cleared all module cache")

    async def close(self) -> None:
        """Close the client session.

        This should be called when the client is no longer needed.
        """
        if hasattr(self.session, "close") and not self.session.closed:
            await self.session.close()
            _LOGGER.debug("Tech API client session closed")


class TechError(Exception):
    """Raised when Tech API request ended in error.

    Attributes:
        status_code: Error code returned by Tech API.
        message: More detailed description.

    """

    def __init__(self, status_code: int, message: str) -> None:
        """Initialize the status code and message of the error.

        Args:
            status_code: The HTTP status code.
            message: The error message.

        """
        super().__init__(f"Tech API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class TechLoginError(TechError):
    """Raised when Tech API login fails.

    Attributes:
        status_code: Error code returned by Tech API.
        message: More detailed description.

    """

    def __init__(self, status_code: int, message: str) -> None:
        """Initialize the status code and message of the login error.

        Args:
            status_code: The HTTP status code.
            message: The error message.

        """
        super().__init__(status_code, f"Login failed: {message}")


class TechTimeoutError(TechError):
    """Raised when Tech API request times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        """Initialize the timeout error.

        Args:
            message: The error message.

        """
        super().__init__(408, message)
