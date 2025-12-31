import glob
import os
import tempfile

from .. import appstream, builddir, config, ostree
from . import Check


def should_skip_mirror_check(has_test_ref: bool) -> bool:
    return has_test_ref and config.is_flathub_pipeline()


class ScreenshotsCheck(Check):
    def _validate(self, path: str, appid: str, ref_type: str, has_test_ref: bool) -> None:
        appstream_path = f"{path}/app-info/xmls/{appid}.xml.gz"

        skip = False
        if appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER) or ref_type == "runtime":
            skip = True
        metainfo_dirs = [f"{path}/metainfo", f"{path}/appdata"]
        patterns = [
            f"{appid}.metainfo.xml",
            f"{appid}.*.metainfo.xml",
            f"{appid}.appdata.xml",
            f"{appid}.*.appdata.xml",
        ]
        metainfo_files = [
            os.path.abspath(file)
            for metainfo_dir in metainfo_dirs
            if os.path.isdir(metainfo_dir)
            for pattern in patterns
            for file in glob.glob(os.path.join(metainfo_dir, pattern))
            if os.path.isfile(file)
        ]
        exact_metainfo = next(
            (
                file
                for file in metainfo_files
                if file.endswith((f"{appid}.metainfo.xml", f"{appid}.appdata.xml"))
            ),
            None,
        )

        if not skip and exact_metainfo is None:
            self.errors.add("appstream-metainfo-missing")
            self.info.add(
                f"appstream-metainfo-missing: No metainfo file for {appid} was found in"
                + " $FLATPAK_DEST/share/metainfo or $FLATPAK_DEST/share/appdata"
            )
            return

        if ref_type != "app":
            return

        if exact_metainfo is not None:
            metainfo_sc = appstream.get_screenshot_images(exact_metainfo)
            metainfo_svg_sc_values = [i for i in metainfo_sc if i.endswith((".svg", ".svgz"))]

            metainfo_ctype = appstream.component_type(exact_metainfo)

            if metainfo_ctype in config.FLATHUB_APPSTREAM_TYPES_DESKTOP and not metainfo_sc:
                self.errors.add("metainfo-missing-screenshots")
                self.info.add(
                    "metainfo-missing-screenshots: The metainfo file is missing screenshots"
                    + " or it is not present under the screenshots/screenshot/image tag"
                )
                return

            if metainfo_svg_sc_values:
                self.errors.add("metainfo-svg-screenshots")
                self.info.add("metainfo-svg-screenshots: The metainfo has a SVG screenshot")
                return

        if not skip and not os.path.exists(appstream_path):
            self.errors.add("appstream-missing-appinfo-file")
            self.info.add(
                "appstream-missing-appinfo-file: Appstream catalogue file is missing."
                + " Perhaps no Metainfo file was installed with correct name"
            )
            return

        if os.path.exists(appstream_path):
            if len(appstream.components(appstream_path)) != 1:
                self.errors.add("appstream-multiple-components")
                return

            aps_ctype = appstream.component_type(appstream_path)

            sc_values = appstream.get_screenshot_images(appstream_path)

            sc_allowed_urls = (config.FLATHUB_MEDIA_BASE_URL,)

            if aps_ctype in config.FLATHUB_APPSTREAM_TYPES_DESKTOP and not sc_values:
                self.errors.add("appstream-missing-screenshots")
                self.info.add(
                    "appstream-missing-screenshots: Catalogue file has no screenshots."
                    + " Please check if screenshot URLs are reachable"
                )
                return

            if (
                not should_skip_mirror_check(has_test_ref)
                and sc_values
                and not any(s.startswith(sc_allowed_urls) for s in sc_values)
            ):
                self.errors.add("appstream-external-screenshot-url")
                self.info.add(
                    "appstream-external-screenshot-url: Screenshots are not mirrored to"
                    + f" {', '.join(sc_allowed_urls)}"
                )
                return

    def check_build(self, path: str) -> None:
        ref_type, appid = builddir.infer_type(path), builddir.infer_appid(path)
        if not (appid and ref_type):
            return

        # ref branch is not exposed in builddir metadata
        self._validate(f"{path}/files/share", appid, ref_type, has_test_ref=False)

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        refs.update({r for r in ostree.get_refs(path, None) if r.startswith("screenshots/")})
        app_refs = {ref for ref in refs if ref.startswith("app/") and len(ref.split("/")) == 4}
        if not app_refs:
            return

        has_test_ref = False
        for ref in app_refs:
            appid = ref.split("/")[1]
            arch = ref.split("/")[2]
            branch = ref.split("/")[3]

            if branch == "test":
                has_test_ref = True

            with tempfile.TemporaryDirectory() as tmpdir:
                for subdir in ("appdata", "metainfo", "app-info"):
                    os.makedirs(os.path.join(tmpdir, subdir), exist_ok=True)
                    ostree.extract_subpath(
                        path, ref, f"files/share/{subdir}", os.path.join(tmpdir, subdir), True
                    )

                self._validate(tmpdir, appid, "app", has_test_ref)
                appstream_path = f"{tmpdir}/app-info/xmls/{appid}.xml.gz"

                if not should_skip_mirror_check(has_test_ref) and os.path.exists(appstream_path):
                    aps_ctype = appstream.component_type(appstream_path)

                    if aps_ctype in config.FLATHUB_APPSTREAM_TYPES_DESKTOP:
                        if f"screenshots/{arch}" not in refs:
                            self.errors.add("appstream-screenshots-not-mirrored-in-ostree")
                            return

                        media_path = os.path.join(tmpdir, "app-info", f"screenshots-{arch}")
                        media_glob_path = f"{media_path}/**"
                        ostree.extract_subpath(path, f"screenshots/{arch}", "/", media_path)

                        ref_sc_files = {
                            os.path.basename(path)
                            for path in glob.glob(media_glob_path, recursive=True)
                            if path.endswith(".png")
                        }

                        if not ref_sc_files:
                            self.errors.add("appstream-screenshots-files-not-found-in-ostree")
