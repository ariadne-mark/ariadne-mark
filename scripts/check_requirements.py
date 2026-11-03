"""Validate traceability metadata, not implementation or legal compliance."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
requirements = json.loads((root / "compliance/requirements.json").read_text())["requirements"]
sources = {x["id"] for x in json.loads((root / "compliance/sources/index.json").read_text())["sources"]}
errors = []
seen = set()
for item in requirements:
    rid = item["id"]
    if rid in seen:
        errors.append(f"duplicate ID: {rid}")
    seen.add(rid)
    for key in ("implementation_path", "test_path", "documentation_path"):
        path = (root / item[key]).resolve()
        if not path.is_relative_to(root) or not path.exists():
            errors.append(f"{rid}: invalid/missing {key}: {item[key]}")
    if set(item["source_ids"]) - sources:
        errors.append(f"{rid}: unknown source")
    if item["implementation_status"] not in {"planned", "in_progress", "implemented"}:
        errors.append(f"{rid}: invalid implementation status")
    if item["verification_status"] not in {"not_run", "failed", "passed"}:
        errors.append(f"{rid}: invalid verification status")
    if item["verification_status"] == "passed" and (not item["evidence"] or item["implementation_status"] != "implemented"):
        errors.append(f"{rid}: passed requires implementation and evidence")
if errors:
    raise SystemExit("\n".join(errors))
print(f"OK: {len(requirements)} requirement records; local paths and source IDs resolve.")
print("Structure check only. No SDK tests or compliance certification performed.")
