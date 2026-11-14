"""Where Ariadne keeps downloaded runtime resources (ISS-08).

Precedence: an explicit option/variable (``--cache-dir``, ``ARIADNE_VIDEO_DATA``,
``ARIADNE_VIDEOSEAL_MODEL``) > ``$XDG_CACHE_HOME/ariadne-mark`` when set to an
absolute path > ``~/.cache/ariadne-mark``. An existing resource at the previous
default location keeps being used while the XDG location has none: user caches
are never moved or duplicated automatically.
"""
import os
from pathlib import Path

LEGACY_ROOT = Path('~/.cache/ariadne-mark')


def cache_root():
    xdg = os.environ.get('XDG_CACHE_HOME', '')
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / '.cache'
    return base / 'ariadne-mark'


def cache_path(name):
    preferred = cache_root() / name
    legacy = LEGACY_ROOT.expanduser() / name
    if preferred != legacy and not preferred.exists() and legacy.exists():
        return legacy
    return preferred
