"""RunPod v2 request and response bodies, and the schemas they follow, from fixtures/runpod_v2/.

schemas.json holds the components of https://api.runpod.io/v2/openapi.json that pods and the catalog use,
with the date it was fetched and the sha256 of the spec. The other files are the spec's own examples.
"""

import copy
import functools
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent / "fixtures" / "runpod_v2"


@functools.cache
def _read(name: str) -> dict:
    return json.loads((ROOT / f"{name}.json").read_text())


def load(name: str) -> dict:
    """A copy of one fixture body, such as get_pod or list_pods."""
    return copy.deepcopy(_read(name))


def pod(**fields) -> dict:
    """The spec's example pod with fields replaced."""
    return load("get_pod") | fields


def check(body: object, schema: str) -> None:
    """Raise jsonschema.ValidationError when body does not match the spec's schema of this name."""
    spec = _read("schemas")
    root = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": spec["components"],
        "$ref": f"#/components/schemas/{schema}",
    }
    jsonschema.Draft202012Validator(root).validate(body)
