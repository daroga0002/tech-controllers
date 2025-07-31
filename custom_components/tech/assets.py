"""Assets for translations and utilities."""

import logging
from typing import Any, Optional, Union

from .const import DEFAULT_ICON, ICON_BY_ID, ICON_BY_TYPE, TXT_ID_BY_TYPE

_LOGGER = logging.getLogger(__name__)


class TranslationManager:
    """Manages translations for the Tech integration."""

    def __init__(self) -> None:
        """Initialize the translation manager."""
        self._translations: Optional[dict[str, Any]] = None
        self._reverse_lookup: Optional[dict[str, int]] = None

    @property
    def is_loaded(self) -> bool:
        """Check if translations are loaded."""
        return self._translations is not None

    async def load_translations(self, language: str, api) -> None:
        """Load translations for the specified language.

        Args:
            language: The language code for the translations.
            api: API object to use for fetching translations.

        Raises:
            Exception: If translation loading fails.

        """
        try:
            self._translations = await api.get_translations(language)
            # Build reverse lookup cache for better performance
            if self._translations and "data" in self._translations:
                self._reverse_lookup = {
                    value: int(key) for key, value in self._translations["data"].items()
                }
            _LOGGER.debug("Loaded translations for language: %s", language)
        except Exception as exc:
            _LOGGER.error("Failed to load translations for %s: %s", language, exc)
            raise

    def get_text(self, text_id: Union[int, str]) -> str:
        """Get text by id.

        Args:
            text_id: The text identifier.

        Returns:
            The translated text or a fallback string.

        """
        if not self.is_loaded or text_id == 0:
            return f"txtId {text_id}"

        try:
            text_id_str = str(text_id)
            if self._translations and "data" in self._translations:
                return self._translations["data"].get(text_id_str, f"txtId {text_id}")
        except (KeyError, TypeError) as exc:
            _LOGGER.warning("Error getting text for ID %s: %s", text_id, exc)

        return f"txtId {text_id}"

    def get_id_from_text(self, text: str) -> int:
        """Get id from text (reverse lookup).

        Args:
            text: The text to look up.

        Returns:
            The text ID or 0 if not found.

        """
        if not text or not self.is_loaded:
            return 0

        try:
            if self._reverse_lookup:
                return self._reverse_lookup.get(text, 0)

            # Fallback to direct lookup if reverse cache is not available
            if self._translations and "data" in self._translations:
                for key, value in self._translations["data"].items():
                    if value == text:
                        return int(key)
        except (ValueError, TypeError) as exc:
            _LOGGER.warning("Error getting ID for text '%s': %s", text, exc)

        return 0

    def get_text_by_type(self, text_type: int) -> str:
        """Get text by type.

        Args:
            text_type: The text type identifier.

        Returns:
            The translated text or a fallback string.

        """
        text_id = TXT_ID_BY_TYPE.get(text_type)
        if text_id is None:
            return f"type {text_type}"
        return self.get_text(text_id)

    def clear_translations(self) -> None:
        """Clear loaded translations."""
        self._translations = None
        self._reverse_lookup = None
        _LOGGER.debug("Cleared translations")

    def get_translation_count(self) -> int:
        """Get the number of loaded translations.

        Returns:
            The number of translations or 0 if not loaded.

        """
        if (
            not self.is_loaded
            or not self._translations
            or "data" not in self._translations
        ):
            return 0
        return len(self._translations["data"])


# Global instance for backward compatibility
_translation_manager = TranslationManager()


def redact(entry_data: dict[str, Any], keys: list[str]) -> str:
    """Return a copy of entry_data with the specified fields redacted.

    Args:
        entry_data: The data to redact.
        keys: The list of keys to redact.

    Returns:
        The redacted data as a string.

    """
    if not entry_data:
        return str(entry_data)

    sanitized_data = entry_data.copy()
    for key in keys:
        if key in sanitized_data:
            sanitized_data[key] = "***HIDDEN***"
    return str(sanitized_data)


def get_icon(icon_id: Union[int, str]) -> str:
    """Get icon by id.

    Args:
        icon_id: The icon identifier.

    Returns:
        The icon string or default icon.

    """
    if icon_id is None:
        return DEFAULT_ICON

    try:
        # Convert to int if it's a string representation of a number
        if isinstance(icon_id, str):
            icon_id = int(icon_id)
        return ICON_BY_ID.get(icon_id, DEFAULT_ICON)
    except (ValueError, TypeError):
        return DEFAULT_ICON


def get_icon_by_type(icon_type: Union[int, str]) -> str:
    """Get icon by type.

    Args:
        icon_type: The icon type identifier.

    Returns:
        The icon string or default icon.

    """
    if not icon_type:
        return DEFAULT_ICON

    try:
        # Convert to int if it's a string representation of a number
        if isinstance(icon_type, str):
            icon_type = int(icon_type)
        return ICON_BY_TYPE.get(icon_type, DEFAULT_ICON)
    except (ValueError, TypeError):
        return DEFAULT_ICON


def get_translation_manager() -> TranslationManager:
    """Get the global translation manager instance.

    Returns:
        The global TranslationManager instance.

    """
    return _translation_manager
