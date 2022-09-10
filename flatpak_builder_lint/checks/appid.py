import os

from . import Check


class AppIDCheck(Check):
    type = "manifest"

    def check(self, manifest):
        appid = manifest.get("id")
        if not appid:
            self.errors.append("appid-not-defined")
            return

        (manifest_filename, _) = os.path.splitext(manifest.get("x-manifest-filename"))
        manifest_filename = os.path.basename(manifest_filename)
        if appid != manifest_filename:
            self.errors.append("appid-filename-mismatch")

        split = appid.split(".")
        if len(split) < 3:
            self.errors.append("appid-too-few-components")

        if split[-1] == "desktop":
            self.errors.append("appid-ends-with-lowercase-desktop")

        if split[1].lower() in ("github", "gitlab") and split[0].lower() != "io":
            self.warnings.append("appid-uses-code-hosting-domain")
