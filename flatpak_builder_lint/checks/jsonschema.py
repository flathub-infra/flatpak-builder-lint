import importlib.resources
import json
from collections.abc import Mapping
from typing import Any

import jsonschema
import jsonschema.exceptions

from .. import staticfiles
from . import Check


class JSONSchemaCheck(Check):
    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        with (
            importlib.resources.files(staticfiles)
            .joinpath("flatpak-manifest.schema.json")
            .open() as f
        ):
            schema = json.load(f)

        try:
            jsonschema.validate(dict(manifest), schema)
        except jsonschema.exceptions.SchemaError:
            self.errors.add("jsonschema-schema-error")
        except jsonschema.exceptions.ValidationError as exc:
            self.errors.add("jsonschema-validation-error")
            self.jsonschema.add(exc.message)
