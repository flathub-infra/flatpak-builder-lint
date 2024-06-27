import os
import re
import tempfile
from typing import Optional

from .. import builddir, domainutils, ostree
from . import Check


class AppIDCheck(Check):
    def _validate(self, appid: Optional[str], is_extension: bool) -> None:
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

        is_baseapp = appid.endswith(".BaseApp")

        if not (is_extension or is_baseapp) and len(split) >= 6:
            self.errors.add("appid-too-many-components-for-app")
            self.info.add(
                "appid-too-many-components-for-app: appid has 6 or more"
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
            if tld != "page" and domain == "codeberg":
                self.errors.add("appid-uses-code-hosting-domain")
                self.info.add(f"appid-uses-code-hosting-domain: {domain}.{tld}")
            if len(split) < 4:
                self.errors.add("appid-code-hosting-too-few-components")
                return

        if appid:
            if is_extension or is_baseapp:
                self.info.add("Domain check skipped for runtimes and baseapps")
                return
            if domainutils.is_app_on_flathub(appid):
                self.info.add("Domain check skipped, app is on Flathub")
                return
            if appid.startswith(
                (
                    "io.github.",
                    "io.gitlab.",
                    "io.frama.",
                    "page.codeberg.",
                    "io.sourceforge.",
                    "net.sourceforge.",
                    "org.gnome.gitlab.",
                    "org.freedesktop.gitlab.",
                )
            ):
                appid_code_host = domainutils.get_code_hosting_url(appid)
                if appid_code_host is None:
                    self.errors.add("appid-code-host-not-found")
                    self.info.add(
                        f"appid-code-hosting-url-not-found: Code hosting url for {appid}"
                        + " cannot be determined"
                    )
                    return
                else:
                    if isinstance(appid_code_host, list):
                        if not (
                            domainutils.check_git(appid_code_host[0])
                            or domainutils.check_git(appid_code_host[1])
                        ):
                            self.errors.add("appid-code-host-not-reachable")
                            self.info.add(
                                f"appid-code-host-not-reachable: {appid_code_host} not reachable"
                            )
                    else:
                        if appid_code_host.startswith(
                            "https://sourceforge.net/projects/"
                        ):
                            if not domainutils.check_url(appid_code_host):
                                self.errors.add("appid-code-host-not-reachable")
                                self.info.add(
                                    f"appid-code-host-not-reachable: {appid_code_host}"
                                    + " not reachable"
                                )
                        else:
                            if not domainutils.check_git(appid_code_host):
                                self.errors.add("appid-code-host-not-reachable")
                                self.info.add(
                                    f"appid-code-host-not-reachable: {appid_code_host}"
                                    + " not reachable"
                                )
            else:
                appid_domain = domainutils.get_domain(appid)
                if appid_domain is None:
                    self.errors.add("appid-domain-not-found")
                    self.info.add(
                        f"appid-domain-not-found: Domain for {appid}"
                        + " cannot be determined"
                    )
                    return
                else:
                    if appid_domain.endswith(
                        (".ch", ".es", ".gr", ".my", ".pk", ".vn")
                    ):
                        if not (
                            domainutils.check_resv(appid_domain)
                            and domainutils.is_domain_regd(appid_domain)
                        ):
                            self.errors.add("appid-domain-not-resolvable")
                            self.info.add(
                                f"appid-domain-not-resolvable: {appid_domain}"
                            )
                    else:
                        if not domainutils.is_domain_regd(appid_domain):
                            self.errors.add("appid-domain-not-registered")
                            self.info.add(
                                f"appid-domain-not-registered: {appid_domain}"
                            )

    def check_manifest(self, manifest: dict) -> None:
        appid = manifest.get("id")
        is_extension = manifest.get("build-extension", False)

        if filename := manifest.get("x-manifest-filename"):
            (manifest_basename, _) = os.path.splitext(filename)
            manifest_basename = os.path.basename(manifest_basename)

            if appid != manifest_basename:
                self.errors.add("appid-filename-mismatch")
                self.info.add(
                    f"appid-filename-mismatch: Appid is {appid} but"
                    + f" Manifest filename is: {manifest_basename}"
                )

        self._validate(appid, is_extension)

    def check_build(self, path: str) -> None:
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        appid = metadata.get("name")
        is_extension = metadata.get("type", False) != "application"
        self._validate(appid, is_extension)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")

            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return
            is_extension = metadata.get("type", False) != "application"
            self._validate(appid, is_extension)
