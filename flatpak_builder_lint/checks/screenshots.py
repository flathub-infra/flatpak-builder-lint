import os
import tempfile

from .. import appstream, ostree
from . import Check


class ScreenshotsCheck(Check):
    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        if appid.endswith(".BaseApp"):
            return

        refs_cmd = ostree.cli(path, "refs", "--list")
        if refs_cmd["returncode"] != 0:
            raise RuntimeError("Failed to list refs")
        refs = refs_cmd["stdout"].splitlines()

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "files/share", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")

            appstream_path = f"{tmpdir}/app-info/xmls/{appid}.xml.gz"
            if not os.path.exists(appstream_path):
                return

            if len(appstream.components(appstream_path)) != 1:
                return

            if appstream.component_type(appstream_path) not in (
                "desktop",
                "desktop-application",
            ):
                return

            metainfo_dirs = [f"{tmpdir}/metainfo", f"{tmpdir}/appdata"]
            metainfo_exts = [".appdata.xml", ".metainfo.xml"]

            metainfo_path = None
            for metainfo_dir in metainfo_dirs:
                for ext in metainfo_exts:
                    metainfo_dirext = f"{metainfo_dir}/{appid}{ext}"
                    if os.path.exists(metainfo_dirext):
                        metainfo_path = metainfo_dirext

            if metainfo_path is None:
                self.errors.add("appstream-metainfo-missing")
                self.info.add(
                    f"appstream-metainfo-missing: No metainfo file for {appid} was found in"
                    + " /app/share/metainfo or /app/share/appdata"
                )
                return

            if not appstream.metainfo_is_screenshot_image_present(metainfo_path):
                self.errors.add("metainfo-missing-screenshots")
                self.info.add(
                    "metainfo-missing-screenshots: The metainfo file is missing screenshots"
                    + " or it is not present under the screenshots/screenshot/image tag"
                )
                return

            sc_allowed_urls = (
                "https://dl.flathub.org/repo/screenshots",
                "https://dl.flathub.org/media",
            )

            screenshots = appstream.components(appstream_path)[0].xpath(
                "screenshots/screenshot/image"
            )

            sc_values = list(
                appstream.components(appstream_path)[0].xpath(
                    "screenshots/screenshot/image/text()"
                )
            )

            if not sc_values:
                self.errors.add("appstream-missing-screenshots")
                self.info.add(
                    "appstream-missing-screenshots: Catalogue file has no screenshots."
                    + " Please check if screenshot URLs are reachable"
                )
                return

            if not any(s.startswith(sc_allowed_urls) for s in sc_values):
                self.errors.add("appstream-external-screenshot-url")
                self.info.add(
                    "appstream-external-screenshot-url: Screenshots are not mirrored to"
                    + " https://dl.flathub.org/media"
                )
                return

            arches = {ref.split("/")[2] for ref in refs if len(ref.split("/")) == 4}
            for arch in arches:
                if f"screenshots/{arch}" not in refs:
                    self.errors.add("appstream-screenshots-not-mirrored-in-ostree")
                    return

                ostree_screenshots_cmd = ostree.cli(
                    path, "ls", "-R", f"screenshots/{arch}"
                )
                if ostree_screenshots_cmd["returncode"] != 0:
                    raise RuntimeError("Failed to list screenshots")

                ostree_screenshots = []
                for ostree_screenshot in ostree_screenshots_cmd["stdout"].splitlines():
                    (
                        mode,
                        _,
                        _,
                        _,
                        ostree_screenshot_filename,
                    ) = ostree_screenshot.split()
                    if mode[0] != "-":
                        continue
                    ostree_screenshots.append(ostree_screenshot_filename[1:])

                for screenshot in screenshots:
                    if screenshot.attrib.get("type") == "thumbnail":
                        if screenshot.text.startswith("https://dl.flathub.org/media/"):
                            screenshot_fn = "/".join(screenshot.text.split("/")[4:])
                        else:
                            screenshot_fn = "/".join(screenshot.text.split("/")[5:])

                        if f"{screenshot_fn}" not in ostree_screenshots:
                            self.warnings.add(
                                "appstream-screenshots-files-not-found-in-ostree"
                            )
                            return
