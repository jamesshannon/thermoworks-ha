"""Make the ``ble`` sub-package importable without Home Assistant installed.

``custom_components/thermoworks_bt/__init__.py`` imports Home Assistant, which
does not install on Windows. The BLE tests only need the ``ble`` sub-package,
so when ``homeassistant`` is absent we register synthetic parent packages that
point at the source directories without executing the parent ``__init__``.
CI (which has Home Assistant) takes the normal import path.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

try:
    import homeassistant  # noqa: F401
except ImportError:
    _root = Path(__file__).resolve().parents[2]
    _cc_dir = _root / "custom_components"
    _pkg_dir = _cc_dir / "thermoworks_bt"

    if "custom_components" not in sys.modules:
        _cc = types.ModuleType("custom_components")
        _cc.__path__ = [str(_cc_dir)]
        sys.modules["custom_components"] = _cc

    if "custom_components.thermoworks_bt" not in sys.modules:
        _pkg = types.ModuleType("custom_components.thermoworks_bt")
        _pkg.__path__ = [str(_pkg_dir)]
        sys.modules["custom_components.thermoworks_bt"] = _pkg
