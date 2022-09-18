import jsonschema
import jsonschema.exceptions
import json
import importlib.resources

from . import Check


class JSONSchemaCheck(Check):
    type = "manifest"

    def check(self, manifest: dict) -> None:
        with importlib.resources.open_text(__package__, "flatpak-manifest.schema.json") as f:
            schema = json.load(f)

        try:
            jsonschema.validate(manifest, schema)
        except jsonschema.exceptions.SchemaError:
            pass
        except jsonschema.exceptions.ValidationError:
            self.errors.append("jsonschema-validation-error")
