import os
import re
from collections.abc import Mapping
from typing import Any

from .. import builddir, config, domainutils
from . import Check


class AppIDCheck(Check):
    def _validate(self, appid: str | None, is_extension: bool) -> None:
        if not appid:
            self.errors.add("appid-not-defined")
            return

        if len(appid) > 255:
            self.errors.add("appid-length-more-than-255-chars")
            return

        split = appid.split(".")

        if len(split) < 3:
            self.errors.add("appid-less-than-3-components")
            return

        if not all(re.match("^[A-Za-z_][\\w\\-]*$", sp) for sp in split):
            self.errors.add("appid-component-wrong-syntax")
            return

        is_baseapp = appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)

        if not (is_extension or is_baseapp) and len(split) > 5:
            self.errors.add("appid-too-many-components-for-app")
            self.info.add(
                "appid-too-many-components-for-app: appid has more than 5"
                + " components for an app"
            )
            return

        if split[-1] == "desktop":
            self.errors.add("appid-ends-with-lowercase-desktop")

        domain = split[1].lower()
        tld = split[0].lower()
        if domain in ("github", "gitlab", "codeberg"):
            if tld != "io" and domain in ("github", "gitlab"):
                self.errors.add("appid-uses-code-hosting-domain")
                self.info.add(f"appid-uses-code-hosting-domain: {domain}.{tld}")
                return
            if tld != "page" and domain == "codeberg":
                self.errors.add("appid-uses-code-hosting-domain")
                self.info.add(f"appid-uses-code-hosting-domain: {domain}.{tld}")
                return
            if len(split) < 4:
                self.errors.add("appid-code-hosting-too-few-components")
                return

        if appid:
            if is_extension or is_baseapp:
                return
            if domainutils.is_app_on_flathub_summary(appid):
                return
            if appid.startswith(domainutils.CODE_HOSTS):
                proj_url = domainutils.get_proj_url(appid)
                if proj_url is None:
                    self.errors.add("appid-url-check-internal-error")
                    return
                url = f"https://{proj_url}"
                ok, resp = domainutils.check_url(url, strict=True)
                if not ok:
                    self.errors.add("appid-url-not-reachable")
                    message = f"appid-url-not-reachable: Tried {url}"
                    if resp:
                        message += f" | {resp}"
                    self.info.add(message)
            else:
                domain_from_appid = domainutils.get_domain(appid)
                if domain_from_appid is None:
                    self.errors.add("appid-url-check-internal-error")
                    return
                url_https = f"https://{domain_from_appid}"
                ok, resp = domainutils.check_url(url_https, strict=False)
                if not ok:
                    self.errors.add("appid-url-not-reachable")
                    message = f"appid-url-not-reachable: Tried {url_https}"
                    if resp:
                        message += f" | {resp}"
                    self.info.add(message)

    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        appid = manifest.get("id")
        is_extension = manifest.get("build-extension", False)

        if filename := manifest.get("x-manifest-filename"):
            (manifest_basename, _) = os.path.splitext(filename)
            manifest_basename = os.path.basename(manifest_basename)

            if os.path.exists(filename) and os.path.islink(filename):
                self.errors.add("manifest-file-is-symlink")

            if appid != manifest_basename:
                self.errors.add("appid-filename-mismatch")
                self.info.add(
                    f"appid-filename-mismatch: Appid is {appid} but"
                    + f" Manifest filename is: {manifest_basename}"
                )

        self._validate(appid, is_extension)

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type):
            return

        self._validate(appid, ref_type != "app")

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return

        for ref in refs:
            appid = ref.split("/")[1]
            self._validate(appid, False)
