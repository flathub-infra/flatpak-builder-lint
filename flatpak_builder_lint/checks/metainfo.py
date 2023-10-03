import os
import tempfile
from typing import Optional

from .. import appstream, builddir, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str, flathub_json: Optional[dict]) -> None:
        if not flathub_json:
            flathub_json = {}

        appstream_path = f"{path}/app-info/xmls/{appid}.xml.gz"
        icon_path = f"{path}/app-info/icons/flatpak/128x128/{appid}.png"
        metainfo_dirs = [
            f"{path}/metainfo",
            f"{path}/appdata",
        ]
        metainfo_exts = [".appdata.xml", ".metainfo.xml"]
        metainfo_path = None

        for dir in metainfo_dirs:
            for ext in metainfo_exts:
                metainfo_dirext = f"{dir}/{appid}{ext}"
                if os.path.exists(metainfo_dirext):
                    metainfo_path = metainfo_dirext

        if not flathub_json.get("skip-appstream-check"):
            if not os.path.exists(appstream_path):
                self.errors.add("appstream-missing-appinfo-file")

            if not metainfo_path:
                self.errors.add("appstream-metainfo-missing")

            if metainfo_path:
                appinfo_validation = appstream.validate(metainfo_path)
                if appinfo_validation["returncode"] != 0:
                    self.errors.add("appstream-failed-validation")

                if not appstream.is_developer_name_present(appstream_path):
                    self.errors.add("appstream-missing-developer-name")

        if not flathub_json.get("skip-icons-check"):
            if not os.path.exists(icon_path):
                self.errors.add("appstream-missing-icon-file")

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return
        flathub_json = builddir.get_flathub_json(path)
        self._validate(f"{path}/files/share", appid, flathub_json)

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        flathub_json = ostree.get_flathub_json(path, ref)

        with tempfile.TemporaryDirectory() as tmpdir:
            ret = ostree.extract_subpath(path, ref, "files/share", tmpdir)
            if ret["returncode"] != 0:
                raise RuntimeError("Failed to extract ostree repo")
            self._validate(tmpdir, appid, flathub_json)
