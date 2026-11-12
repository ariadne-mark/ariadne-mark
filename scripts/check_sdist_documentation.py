"""Check documentation/UI resources from the built sdist, not the checkout."""
from pathlib import Path
import json, subprocess, sys, tarfile, tempfile
artifacts=Path(sys.argv[1]).resolve()
archive,=artifacts.glob('ariadne_mark-*.tar.gz')
with tempfile.TemporaryDirectory(prefix='ariadne-sdist-check-') as folder:
    with tarfile.open(archive) as stream:
        stream.extractall(folder, filter='data')
    source,=Path(folder).iterdir()
    assert (source/'docs/compliance/requirements-matrix.csv').is_file()
    assert (source/'scripts/check_verifier_ui.mjs').is_file()
    subprocess.run([sys.executable, str(source/'scripts/check_documentation.py')], cwd=source, check=True)
    subprocess.run(['node', str(source/'scripts/check_verifier_ui.mjs')], cwd=source, check=True)
print(json.dumps({'ok': True, 'archive': archive.name, 'scope': 'Extracted source documentation/UI resources; no SDK/model execution'}))
