"""Installed distribution version; core imports do not load media engines."""
from importlib.metadata import version, PackageNotFoundError

def sdk_version():
    try:
        return version("ariadne-mark")
    except PackageNotFoundError:
        return "uninstalled"


def installed_identity():
    """Version plus a digest of the installed file list (RECORD) for image pinning.

    RECORD lists the SHA-256 of every installed file, so its digest identifies
    the installed package contents, not just the version string.
    """
    import hashlib
    from importlib.metadata import distribution, PackageNotFoundError
    try:
        dist = distribution("ariadne-mark")
    except PackageNotFoundError:
        return {"sdk_version": "uninstalled", "record_sha256": None}
    record = dist.read_text("RECORD")
    return {"sdk_version": dist.version,
            "record_sha256": hashlib.sha256(record.encode()).hexdigest() if record else None}
