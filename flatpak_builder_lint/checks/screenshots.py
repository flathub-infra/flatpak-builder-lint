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
            ret = ostree.extract_subpath(path, ref, "files/share/app-info", tmpdir)
            if ret["returncode"] != 0:
                self.errors.add("appstream-missing-appinfo")
                return

            appstream_path = f"{tmpdir}/xmls/{appid}.xml.gz"
            if not os.path.exists(appstream_path):
                self.errors.add("appstream-missing-appinfo-file")
                return

            if len(appstream.components(appstream_path)) != 1:
                self.errors.add("appstream-multiple-components")
                return

            if not appstream.is_valid_component_type(appstream_path):
                self.errors.add("appstream-unsupported-component-type")

            if appstream.component_type(appstream_path) not in (
                "desktop",
                "desktop-application",
            ):
                return

            screenshots = appstream.components(appstream_path)[0].xpath(
                "screenshots/screenshot/image"
            )
            thumbnails = [
                elem for elem in screenshots if elem.attrib.get("type") == "thumbnail"
            ]
            if not thumbnails:
                self.errors.add("appstream-missing-screenshots")
                return

            for screenshot in screenshots:
                if screenshot.attrib.get("type") != "source":
                    allowed_urls = [
                        "https://dl.flathub.org/repo/screenshots",
                        "https://dl.flathub.org/media",
                    ]
                    if not any(screenshot.text.startswith(url) for url in allowed_urls):
                        self.errors.add("appstream-external-screenshot-url")
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
