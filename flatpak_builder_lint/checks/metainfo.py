import os
import re
import tempfile

from .. import appstream, builddir, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str) -> None:
        appstream_path = f"{path}/files/share/app-info/xmls/{appid}.xml.gz"
        icon_path = f"{path}/files/share/app-info/icons/flatpak/128x128/{appid}.png"
        metainfo_dirs = [
            f"{path}/files/share/metainfo",
            f"{path}/files/share/appdata",
        ]
        metainfo_exts = [".appdata.xml", ".metainfo.xml"]
        metainfo_path = None

        if appid.endswith(".BaseApp"):
            return

        if not os.path.exists(appstream_path):
            self.errors.add("appstream-missing-appinfo-file")
            return

        if len(appstream.components(appstream_path)) != 1:
            self.errors.add("appstream-multiple-components")
            return

        if appstream.component_type(appstream_path) not in (
            "desktop",
            "desktop-application",
            "console-application",
        ):
            return

        if not os.path.exists(icon_path) and appstream.component_type(
            appstream_path
        ) in ("desktop", "desktop-application"):
            self.errors.add("appstream-missing-icon-file")

        if not appstream.is_developer_name_present(appstream_path):
            self.warnings.add("appstream-missing-developer-name")
        if not appstream.is_project_license_present(appstream_path):
            self.warnings.add("appstream-missing-project-license")
        # for mypy
        name = appstream.name(appstream_path)
        summary = appstream.summary(appstream_path)
        if name is not None and len(name) > 20:
            self.warnings.add("appstream-name-too-long")
        if summary is not None and len(summary) > 35:
            self.warnings.add("appstream-summary-too-long")
        if not appstream.check_caption(appstream_path):
            self.warnings.add("appstream-screenshot-missing-caption")

        for metainfo_dir in metainfo_dirs:
            for ext in metainfo_exts:
                metainfo_dirext = f"{metainfo_dir}/{appid}{ext}"
                if os.path.exists(metainfo_dirext):
                    metainfo_path = metainfo_dirext

        if not os.path.exists(appstream_path):
            self.errors.add("appstream-missing-appinfo-file")

            if not metainfo_path:
                self.errors.add("appstream-metainfo-missing")

            if metainfo_path is not None:
                appinfo_validation = appstream.validate(metainfo_path)
                if appinfo_validation["returncode"] != 0:
                    self.errors.add("appstream-failed-validation")
                    for err in appinfo_validation["stderr"].split(":", 1)[1:]:
                        self.appstream.add(err.strip())
                    for out in appinfo_validation["stdout"].splitlines()[1:]:
                        self.appstream.add(re.sub("^\u2022", "", out).strip())

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return

        metadata = builddir.get_metadata(path)
        if not metadata:
            return
        if metadata.get("extension"):
            return

        self._validate(f"{path}", appid)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "/", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")

            self._validate(tmpdir, appid)
