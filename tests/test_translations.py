"""Tests ensuring all translation files share the same JSON key structure.

Every file under ``custom_components/tech/translations`` must contain exactly
the same set of (nested) keys. Only the string values may differ between
languages.
"""

from __future__ import annotations

import json
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TRANSLATIONS_DIR = _REPO_ROOT / "custom_components" / "tech" / "translations"
_REFERENCE_LANG = "en"


def _collect_keys(data: object, prefix: str = "") -> set[str]:
    """Return the set of dotted key paths for every leaf/branch in ``data``."""
    keys: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.add(path)
            keys |= _collect_keys(value, path)
    return keys


def _load(path: pathlib.Path) -> dict:
    """Load and parse a JSON translation file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _translation_files() -> list[pathlib.Path]:
    """Return the sorted list of translation JSON files."""
    return sorted(_TRANSLATIONS_DIR.glob("*.json"))


def test_translation_files_exist() -> None:
    """There should be translation files and a reference language present."""
    files = _translation_files()
    assert files, f"No translation files found in {_TRANSLATIONS_DIR}"
    assert (_TRANSLATIONS_DIR / f"{_REFERENCE_LANG}.json").exists(), (
        f"Missing reference translation file '{_REFERENCE_LANG}.json'"
    )


@pytest.mark.parametrize(
    "path",
    [f for f in _translation_files() if f.stem != _REFERENCE_LANG],
    ids=lambda p: p.stem,
)
def test_translation_keys_match_reference(path: pathlib.Path) -> None:
    """Each translation file must share the exact key set of the reference."""
    reference_keys = _collect_keys(_load(_TRANSLATIONS_DIR / f"{_REFERENCE_LANG}.json"))
    keys = _collect_keys(_load(path))

    missing = reference_keys - keys
    extra = keys - reference_keys

    assert not missing and not extra, (
        f"Translation '{path.name}' key mismatch vs '{_REFERENCE_LANG}.json':\n"
        f"  missing: {sorted(missing)}\n"
        f"  extra:   {sorted(extra)}"
    )
