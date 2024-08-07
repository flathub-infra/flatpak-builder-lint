import glob
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

        refs = ostree.get_refs(path, None)

        with tempfile.TemporaryDirectory() as tmpdir:
            ostree.extract_subpath(path, ref, "files/share", tmpdir)

            appstream_path = f"{tmpdir}/app-info/xmls/{appid}.xml.gz"
            if not os.path.exists(appstream_path):
                return

            if len(appstream.components(appstream_path)) != 1:
                self.errors.add("appstream-multiple-components")
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

            if not appstream.metainfo_components(metainfo_path):
                self.errors.add("metainfo-missing-component-tag")
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

            sc_values = [
                i
                for i in appstream.components(appstream_path)[0].xpath(
                    "screenshots/screenshot/image/text()"
                )
                if i.endswith(".png")
            ]

            sc_values_basename = set([os.path.basename(i) for i in sc_values])

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
                media_path = os.path.join(tmpdir, "app-info", f"screenshots-{arch}")
                media_glob_path = f"{media_path}/**"
                ostree.extract_subpath(path, f"screenshots/{arch}", "/", media_path)

                ref_sc_files = set(
                    [
                        os.path.basename(path)
                        for path in glob.glob(media_glob_path, recursive=True)
                        if path.endswith(".png")
                    ]
                )

                if not (ref_sc_files & sc_values_basename):
                    self.errors.add("appstream-screenshots-files-not-found-in-ostree")
