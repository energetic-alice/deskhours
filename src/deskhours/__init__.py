"""deskhours — count computer activity hours from keyboard/mouse idle state."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("deskhours")
except PackageNotFoundError:  # pragma: no cover - editable/source tree fallback
    __version__ = "0.1.0"

__all__ = ["__version__"]
