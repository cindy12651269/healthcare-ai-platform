"""
FHIR R4 validation (Issue #42) against the official HL7 FHIR R4 (4.0.1) JSON Schema,
vendored and pinned by SHA-256: interoperability/fhir/fhir.schema.json.zip from
https://hl7.org/fhir/R4/fhir.schema.json.zip. Offline; no network at runtime or in CI.

The JSON Schema checks structure, datatypes, primitive formats and code enumerations. It does
not mark 1..1 primitive elements as required (they may be carried by `_element` extensions),
and it does not evaluate FHIRPath invariants or terminology bindings. So two supplementary
checks run as well: R4 1..1 primitives of the resources exported here (REQUIRED_PRIMITIVES,
from the R4 specification), and internal reference resolution (check_references).
"""
from __future__ import annotations
import hashlib
import json
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft6Validator

SCHEMA_ZIP = Path(__file__).resolve().parent / "fhir" / "fhir.schema.json.zip"
SCHEMA_SHA256 = "75e5560da3cf503895a44c8ca7af17a83b4cca6c2cb5ba1883d2aec0d1cb5ac6"
FHIR_VERSION = "4.0.1"


class FHIRValidationError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_schema() -> Dict[str, Any]:
    data = SCHEMA_ZIP.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SCHEMA_SHA256:
        raise FHIRValidationError(f"FHIR R4 schema checksum mismatch: {digest}")
    with zipfile.ZipFile(SCHEMA_ZIP) as z:
        return json.loads(z.read("fhir.schema.json"))


def _validator_for(resource_type: str) -> Draft6Validator:
    schema = load_schema()
    if resource_type not in schema["discriminator"]["mapping"]:
        raise FHIRValidationError(f"Unknown R4 resourceType {resource_type!r}")
    # Validate against the one resource definition, resolving $refs within the full schema
    return Draft6Validator({"$ref": f"#/definitions/{resource_type}", "definitions": schema["definitions"]})


def validate_resource(resource: Dict[str, Any]) -> List[str]:
    errors = sorted(_validator_for(resource.get("resourceType", "")).iter_errors(resource), key=str)
    return [f"{resource.get('resourceType')}/{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors]


# R4 elements with cardinality 1..1 that the JSON Schema does not enforce, for the exported resources
REQUIRED_PRIMITIVES: Dict[str, List[str]] = {
    "Bundle": ["type"],
    "Task": ["status", "intent"],
    "QuestionnaireResponse": ["status"],
    "Provenance": ["recorded"],
    "Questionnaire": ["status"],
}
REQUIRED_ITEM_PRIMITIVES: Dict[str, List[str]] = {
    "QuestionnaireResponse": ["linkId"],
    "Questionnaire": ["linkId", "type"],
}


def check_required(resource: Dict[str, Any]) -> List[str]:
    rtype = resource.get("resourceType")
    missing = [f"{rtype}/{k}: required" for k in REQUIRED_PRIMITIVES.get(rtype, []) if k not in resource]
    for i, item in enumerate(resource.get("item") or []):
        missing += [f"{rtype}/item/{i}/{k}: required" for k in REQUIRED_ITEM_PRIMITIVES.get(rtype, []) if k not in item]
    return missing


def check_references(bundle: Dict[str, Any]) -> List[str]:
    """Every Reference.reference in the Bundle must resolve to an entry fullUrl."""
    full_urls = {e.get("fullUrl") for e in bundle.get("entry", [])}
    problems: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("reference")
            if isinstance(ref, str) and ref not in full_urls:
                problems.append(f"unresolved reference {ref}")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk([e.get("resource") for e in bundle.get("entry", [])])
    return problems


def validate_bundle(bundle: Dict[str, Any]) -> List[str]:
    """Bundle plus every entry resource, and internal reference resolution."""
    errors = validate_resource(bundle) + check_required(bundle)
    for entry in bundle.get("entry", []):
        resource = entry.get("resource") or {}
        errors.extend(validate_resource(resource) + check_required(resource))
    return errors + check_references(bundle)
