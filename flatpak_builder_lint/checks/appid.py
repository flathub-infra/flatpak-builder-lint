import os
from typing import Optional

from .. import builddir
from . import Check


class AppIDCheck(Check):
    def _validate(self, appid: Optional[str]) -> None:
        if not appid:
            self.errors.add("appid-not-defined")
            return

        split = appid.split(".")
        if split[-1] == "desktop":
            self.errors.add("appid-ends-with-lowercase-desktop")

        domain = split[1].lower()
        tld = split[0].lower()
        if domain in ("github", "gitlab", "codeberg"):
            if tld != "io" and domain in ("github", "gitlab"):
                self.errors.add("appid-uses-code-hosting-domain")
            if tld != "page" and domain == "codeberg":
                self.errors.add("appid-uses-code-hosting-domain")
            if len(split) < 4:
                self.errors.add("appid-code-hosting-too-few-components")

    def check_manifest(self, manifest: dict) -> None:
        appid = manifest.get("id")

        if filename := manifest.get("x-manifest-filename"):
            (manifest_basename, _) = os.path.splitext(filename)
            manifest_basename = os.path.basename(manifest_basename)

            if appid != manifest_basename:
                self.errors.add("appid-filename-mismatch")

        self._validate(appid)

    def check_build(self, path: str) -> None:
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        appid = metadata.get("name")
        self._validate(appid)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]
        self._validate(appid)
