"""Installed distribution version; core imports do not load media engines."""
from importlib.metadata import version, PackageNotFoundError

def sdk_version():
    try:
        return version("ariadne-mark")
    except PackageNotFoundError:
        return "uninstalled"
