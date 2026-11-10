"""Qualified C2PA runtime preflight, with no downloads or repair on requests.

Inspect the wrapper's actual ctypes handle, not an assumed package filename:
upstream also searches cwd/LD_LIBRARY_PATH and supports C2PA_LIBRARY_NAME.
This is compatibility/provisioning-drift detection after loading, not a sandbox
or protection against malicious native code / an attacker controlling the host.
"""
import hashlib
import ctypes
import importlib
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import sys

from ariadne_mark.errors import C2paRuntimeMismatch

PINS = json.loads((Path(__file__).parent / 'c2pa-bootstrap.json').read_text())
# PID + handle + file stat identity. No inherited lock after fork. Concurrent
# first callers may duplicate a hash, but cannot reuse an unvalidated entry.
_cache = {}


def _safe_version(value):
    value = str(value).strip()
    return value if re.fullmatch(r'[0-9A-Za-z.+_-]{1,64}', value) else 'unknown'


def _stat_key(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _mapped_identity(library):
    # Match the file backing an actual exported function. A pathname may have
    # been atomically replaced since dlopen; hashing that new file is not proof
    # about the old mapping. This uses the qualified Linux /proc interface.
    address = ctypes.cast(library.c2pa_version, ctypes.c_void_p).value
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        start, end = (int(x, 16) for x in fields[0].split('-'))
        if start <= address < end:
            major, minor = (int(x, 16) for x in fields[3].split(':'))
            return os.makedev(major, minor), int(fields[4])
    raise RuntimeError('Native function mapping unavailable')


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def runtime_info():
    """Return a safe operator diagnostic; never expose loader paths/errors."""
    report = {'status': 'not_checked', 'reason': None,
              'expected': {'python_package': PINS['python_version'],
                           'native_version': PINS['native_version'],
                           'native_sha256': PINS['native']['library_sha256'],
                           'platform': 'Linux x86-64 / Python 3.12'},
              'python_package': None, 'native_version': None}
    if (platform.system() != 'Linux' or platform.machine().lower() not in {'x86_64', 'amd64'}
            or sys.version_info[:2] != (3, 12)):
        report['reason'] = 'unsupported_platform'
        return report
    try:
        module = importlib.import_module('c2pa')
        binding = importlib.import_module('c2pa.c2pa')
        library = binding._lib
        name = library._name
        if not isinstance(name, str) or not Path(name).is_absolute():
            report['reason'] = 'native_path_unverifiable'
            return report
        path = Path(name).resolve(strict=True)
        before = _stat_key(path)
        if not 0 < before[2] <= 512 * 1024 * 1024:
            report['reason'] = 'native_file_size'
            return report
        if _mapped_identity(library) != before[:2]:
            report['reason'] = 'native_file_identity_mismatch'
            return report
        key = (os.getpid(), id(module), id(library), library._handle,
               str(path), before, getattr(module, '__version__', None))
        if key in _cache:
            return json.loads(json.dumps(_cache[key]))
        report['python_package'] = _safe_version(version('c2pa-python'))
        report['native_version'] = _safe_version(module.sdk_version())
        if (report['python_package'] != PINS['python_version']
                or getattr(module, '__version__', None) != PINS['python_version']):
            report['reason'] = 'python_package_mismatch'
            return report
        if report['native_version'] != PINS['native_version']:
            report['reason'] = 'native_version_mismatch'
            return report
        report['native_sha256'] = _digest(path)
        if before != _stat_key(path):
            report['reason'] = 'native_changed_during_check'
            return report
        if report['native_sha256'] != PINS['native']['library_sha256']:
            report['reason'] = 'native_hash_mismatch'
            return report
    except ModuleNotFoundError:
        report['reason'] = 'dependency_missing'
        return report
    except Exception:
        report['reason'] = 'native_inspection_failed'
        return report
    report.update(status='qualified', reason=None)
    if len(_cache) >= 8:
        _cache.clear()
    _cache[key] = json.loads(json.dumps(report))
    return report


def require_runtime():
    report = runtime_info()
    if report['status'] != 'qualified':
        raise C2paRuntimeMismatch(report)
    return report


def check_if_installed():
    """Keep dependency-free SDK construction lazy; reject an installed mismatch.

    Media commands, signing and the supplied verifier still require preflight.
    Record/profile-only core operations do not load optional native packages.
    """
    if importlib.util.find_spec('c2pa') is None:
        return None
    return require_runtime()
