import importlib.resources
import json

import jsonschema
import jsonschema.exceptions

from .. import staticfiles
from . import Check


class JSONSchemaCheck(Check):
    def check_manifest(self, manifest: dict) -> None:
        with importlib.resources.open_text(
            staticfiles, "flatpak-manifest.schema.json"
        ) as f:
            schema = json.load(f)

        try:
            jsonschema.validate(manifest, schema)
        except jsonschema.exceptions.SchemaError:
            self.errors.add("jsonschema-schema-error")
        except jsonschema.exceptions.ValidationError as exc:
            self.errors.add("jsonschema-validation-error")
            self.jsonschema.add(exc.message)
