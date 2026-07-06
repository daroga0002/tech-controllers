"""Unit tests for the translation and menu helpers in ``assets.py``.

Like :mod:`test_widget_logic`, these tests stub the ``homeassistant``
package just enough to import :mod:`custom_components.tech.const` (which
only needs ``homeassistant.const.Platform``) and then load ``assets.py``
under its real package name so its relative import of ``const`` resolves.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

_ha = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
_ha_const = sys.modules.setdefault(
    "homeassistant.const", types.ModuleType("homeassistant.const")
)


class _Platform:
    """Stand-in for homeassistant.const.Platform; only the names matter."""

    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    CLIMATE = "climate"
    NUMBER = "number"
    SELECT = "select"
    SENSOR = "sensor"
    SWITCH = "switch"


if not hasattr(_ha_const, "Platform"):
    _ha_const.Platform = _Platform


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TECH_DIR = _REPO_ROOT / "custom_components" / "tech"


def _load_tech_module(name: str):
    """Load ``custom_components.tech.<name>`` without executing __init__.py.

    Fake parent packages are registered in ``sys.modules`` so that the
    relative imports inside the module resolve, while the integration's
    ``__init__.py`` (which needs a full Home Assistant install) is skipped.
    """
    full_name = f"custom_components.tech.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    for pkg, path in (
        ("custom_components", _REPO_ROOT / "custom_components"),
        ("custom_components.tech", _TECH_DIR),
    ):
        if pkg not in sys.modules:
            mod = types.ModuleType(pkg)
            mod.__path__ = [str(path)]
            sys.modules[pkg] = mod
    spec = importlib.util.spec_from_file_location(full_name, _TECH_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load_tech_module("const")
assets = _load_tech_module("assets")


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------


def test_get_text_resolves_known_id() -> None:
    """A text id present in the catalog resolves to its translation."""
    translations = assets.Translations({"data": {"100": "Pompa"}})
    assert translations.get_text(100) == "Pompa"


def test_get_text_falls_back_for_unknown_and_zero_ids() -> None:
    """Unknown and zero text ids fall back to the txtId placeholder."""
    translations = assets.Translations({"data": {"100": "Pompa"}})
    assert translations.get_text(101) == "txtId 101"
    assert translations.get_text(0) == "txtId 0"


def test_empty_catalog_degrades_to_fallback() -> None:
    """An empty Translations() still answers with the placeholder."""
    translations = assets.Translations()
    assert translations.get_text(100) == "txtId 100"


def test_get_text_by_type_resolves_mapped_type() -> None:
    """A tile type mapped in TXT_ID_BY_TYPE resolves via the catalog."""
    fan_txt_id = const.TXT_ID_BY_TYPE[const.TYPE_FAN]
    translations = assets.Translations({"data": {str(fan_txt_id): "Wentylator"}})
    assert translations.get_text_by_type(const.TYPE_FAN) == "Wentylator"


def test_get_text_by_type_unmapped_type_returns_type_label() -> None:
    """An unmapped tile type yields 'type N', not 'txtId type N'."""
    translations = assets.Translations({"data": {}})
    assert 9999 not in const.TXT_ID_BY_TYPE
    # Regression: the old module-level implementation fed the string
    # fallback back into get_text and produced "txtId type 9999".
    assert translations.get_text_by_type(9999) == "type 9999"


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------


def _menu_item(item_id, parent_id=0, menu_type="MU", item_type=None, txt_id=0):
    item = {"id": item_id, "parentId": parent_id, "menuType": menu_type}
    if item_type is not None:
        item["type"] = item_type
    if txt_id:
        item["txtId"] = txt_id
    return item


def test_menu_entity_name_prepends_parent_group_label() -> None:
    """Items in a non-root group get the group label prepended."""
    translations = assets.Translations({"data": {"1": "Pompa", "2": "On"}})
    group = _menu_item(
        10, item_type=const.MENU_ITEM_TYPE_GROUP, txt_id=1, menu_type="MU"
    )
    leaf = _menu_item(11, parent_id=10, txt_id=2, menu_type="MU")
    menus = {"MU_10": group, "MU_11": leaf}

    group_names = assets.build_menu_group_names(menus, translations)
    assert group_names[("MU", 10)] == "Pompa"
    assert assets.menu_entity_name(leaf, group_names, translations) == "Pompa - On"
    assert assets.menu_entity_name(group, group_names, translations) == "Pompa"


def test_build_menu_context_bundles_all_lookups() -> None:
    """build_menu_context returns group names, assignments and depths."""
    translations = assets.Translations({"data": {"1": "Grupa"}})
    group = _menu_item(10, item_type=const.MENU_ITEM_TYPE_GROUP, txt_id=1)
    leaf = _menu_item(11, parent_id=10)
    menus = {"MU_10": group, "MU_11": leaf}

    ctx = assets.build_menu_context(menus, {}, translations)
    assert ctx.group_names == {("MU", 10): "Grupa"}
    assert ctx.zone_assignments == {}
    assert ctx.depths == {"MU_10": 0, "MU_11": 1}
