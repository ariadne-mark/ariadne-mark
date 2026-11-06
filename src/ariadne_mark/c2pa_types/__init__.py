"""Shared C2PA source vocabulary and passive declaration inspection.

Declarations describe what an issuer says; they do not establish truth or trust.
"""

from .source_types import DigitalSourceType


def declared_source_types(manifest: dict) -> list[str]:
    """Read recognized source types from active-manifest actions only.

    No ingredients, resolver calls, unknown URI fetching or trust decisions.
    Historical declarations are returned without inferring the final asset's
    generation method from a potentially mixed editing history.
    """
    found = []
    assertions = manifest.get("assertions", [])
    if not isinstance(assertions, list):
        return found
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        if assertion.get("label") not in {"c2pa.actions", "c2pa.actions.v2"}:
            continue
        data = assertion.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
            continue
        for action in data["actions"]:
            if not isinstance(action, dict):
                continue
            value = action.get("digitalSourceType")
            if not isinstance(value, str):
                continue
            try:
                source = DigitalSourceType(value).value
            except ValueError:
                continue
            if source not in found:
                found.append(source)
    return found
