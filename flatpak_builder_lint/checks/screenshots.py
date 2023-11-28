import os
import tempfile

from lxml import etree  # type: ignore

from .. import ostree
from . import Check


class ScreenshotsCheck(Check):
    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        flathub_json = ostree.get_flathub_json(path, ref)
        if not flathub_json:
            flathub_json = {}

        refs_cmd = ostree.cli(path, "refs", "--list")
        if refs_cmd["returncode"] != 0:
            raise RuntimeError("Failed to list refs")
        refs = refs_cmd["stdout"].splitlines()

        if flathub_json.get("skip-appstream-check"):
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "files/share/app-info", tmpdir)
            if ret["returncode"] != 0:
                self.errors.add("appstream-missing-appinfo")
                return

            appstream_path = f"{tmpdir}/xmls/{appid}.xml.gz"
            if not os.path.exists(appstream_path):
                self.errors.add("appstream-missing-appinfo-file")

            root = etree.parse(appstream_path)
            components = root.xpath("/components/component")

            if len(components) != 1:
                self.errors.add("appstream-multiple-components")
                return

            type = components[0].get("type")
            if type not in ("desktop", "desktop-application"):
                return

            screenshots = components[0].xpath("screenshots/screenshot/image")
            if not screenshots:
                self.errors.add("appstream-missing-screenshots")
                return

            for screenshot in screenshots:
                if screenshot.attrib.get("type") != "source":
                    if not screenshot.text.startswith(
                        "https://dl.flathub.org/repo/screenshots"
                    ):
                        self.errors.add("appstream-external-screenshot-url")
                        return

            arches = {ref.split("/")[2] for ref in refs if len(ref.split("/")) == 4}
            for arch in arches:
                if f"screenshots/{arch}" not in refs:
                    self.errors.add("appstream-screenshots-not-mirrored-in-ostree")
                    return

                ostree_screenshots_cmd = ostree.cli(path, "ls", "-R", "screenshots/{arch}")
                if ostree_screenshots_cmd["returncode"] != 0:
                    raise RuntimeError("Failed to list screenshots")

                ostree_screenshots = []
                for ostree_screenshot in ostree_screenshots_cmd["stdout"].splitlines():
                    mode, _, _, _, ostree_screenshot_filename = ostree_screenshot.split()
                    if mode[0] != "-":
                        continue
                    ostree_screenshots.append(ostree_screenshot_filename[1:])

                for screenshot in screenshots:
                    if screenshot.attrib.get("type") != "source":
                        screenshot_filename = "/".join(screenshot.text.split("/")[5:])
                        if f"{screenshot_filename}" not in ostree_screenshots:
                            self.warnings.add(
                                "appstream-screenshots-files-not-found-in-ostree"
                            )
                            return
