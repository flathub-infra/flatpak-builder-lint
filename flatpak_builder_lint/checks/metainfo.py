import json
import os
from typing import Set
import errno
import subprocess

from .. import builddir, appstream
from . import Check

class MetainfoCheck(Check):
    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)

        appstream_path = f"{path}/files/share/app-info/xmls/{appid}.xml.gz"
        icon_path = f"{path}/files/share/app-info/icons/flatpak/128x128/{appid}.png"
        metainfo_dirs =[
                f"{path}/files/share/metainfo",
                f"{path}/files/share/appdata",
        ]
        metainfo_exts = [
            ".appdata.xml", ".metainfo.xml"
        ]
        metainfo_path = None

        for dir in metainfo_dirs:
            for ext in metainfo_exts:
                metainfo_dirext = f"{dir}/{appid}{ext}"
                if os.path.exists(metainfo_dirext):
                    metainfo_path = metainfo_dirext

        flathub_json = builddir.get_flathub_json(path)
        if not flathub_json:
            flathub_json = {}

        if not flathub_json.get("skip-appstream-check"):
            if not os.path.exists(appstream_path):
                self.errors.add("appstream-missing-appinfo-file")

            if not metainfo_path:
                self.errors.add("appstream-metainfo-missing")

            appinfo_validation = appstream.validate(metainfo_path)
            if appinfo_validation["returncode"] != 0:
                self.errors.add("appstream-failed-validation")

        if not flathub_json.get("skip-icons-check"):
            if not os.path.exists(icon_path):
                self.errors.add("appstream-missing-icon-file")
