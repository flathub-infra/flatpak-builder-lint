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
                return

            if domainutils.is_app_on_flathub(appid):
                return

            if (
                appid.startswith(
                    (
                        "io.github.",
                        "page.codeberg.",
                        "io.sourceforge.",
                        "net.sourceforge.",
                    )
                )
                and domainutils.get_user_url(appid) is not None
            ):
                url = f"https://{domainutils.get_user_url(appid)}"
                if not domainutils.check_url(url):
                    self.errors.add("appid-url-not-reachable")
                    self.info.add(f"appid-url-not-reachable: Tried {url}")

            if appid.startswith(
                (
                    "io.gitlab.",
                    "io.frama.",
                    "org.gnome.gitlab.",
                    "org.freedesktop.gitlab.",
                )
            ):
                # Toplevel group names cannot be the same as username
                if (
                    domainutils.get_gitlab_user(appid) is not None
                    and domainutils.get_gitlab_group(appid) is not None
                ):
                    url_user = f"https://{domainutils.get_gitlab_user(appid)}"
                    url_group = f"https://{domainutils.get_gitlab_group(appid)}"
                    if not (
                        domainutils.check_gitlab_user(url_user)
                        or domainutils.check_gitlab_group(url_group)
                    ):
                        self.errors.add("appid-url-not-reachable")
                        self.info.add(
                            f"appid-url-not-reachable: Tried {url_user}, {url_group}"
                        )

            if (
                not appid.startswith(
                    (
                        "io.github.",
                        "io.frama.",
                        "page.codeberg.",
                        "io.sourceforge.",
                        "net.sourceforge.",
                        "io.gitlab.",
                        "org.gnome.gitlab.",
                        "org.freedesktop.gitlab.",
                    )
                )
                and domainutils.get_domain(appid) is not None
            ):
                url_http = f"http://{domainutils.get_domain(appid)}"
                url_https = f"https://{domainutils.get_domain(appid)}"
                if not (
                    domainutils.check_url(url_https) or domainutils.check_url(url_http)
                ):
                    self.errors.add("appid-url-not-reachable")
                    self.info.add(
                        f"appid-url-not-reachable: Tried {url_http}, {url_https}"
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
