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
                raise RuntimeError("Failed to extract ostree repo")

            appstream_path = f"{tmpdir}/xmls/{appid}.xml.gz"
            if not os.path.exists(appstream_path):
                self.errors.add("appstream-missing-appinfo-file")

            #   import ipdb; ipdb.set_trace()
            root = etree.parse(appstream_path)
            components = root.xpath("/components/component")

            if len(components) != 1:
                self.errors.add("appstream-multiple-components")
                return

            type = components[0].get("type")
            if type not in ("desktop", "desktop-application", "console-application"):
                return

            screenshots = components[0].xpath("screenshots/screenshot")
            if not screenshots:
                self.errors.add("appstream-missing-screenshots")
                return

            if "screenshots/x86_64" not in refs:
                self.errors.add("appstream-screenshots-not-mirrored")
                return

            ostree_screenshots_cmd = ostree.cli(path, "ls", "-R", "screenshots/x86_64")
            if ostree_screenshots_cmd["returncode"] != 0:
                raise RuntimeError("Failed to list screenshots")

            ostree_screenshots = []
            for ostree_screenshot in ostree_screenshots_cmd["stdout"].splitlines():
                mode, _, _, _, ostree_screenshot_filename = ostree_screenshot.split()
                if mode != "-":
                    continue
                ostree_screenshots.append(ostree_screenshot_filename[1:])

            print(ostree_screenshots)

            for screenshot in screenshots:
                if not screenshot.startswith("https://dl.flathub.org/repo/screenshots"):
                    self.errors.add("appstream-external-screenshot-url")
                    return

                screenshot_filename = "/".join(screenshot.split("/")[5:])
                print(screenshot_filename)
                if f"/{screenshot_filename}" not in ostree_screenshots:
                    self.errors.add("appstream-screenshots-not-mirrored")
                    return
