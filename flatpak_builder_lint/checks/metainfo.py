import glob
import os
import tempfile

from .. import appstream, builddir, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str, ref_type: str) -> None:
        skip = False
        if appid.endswith(".BaseApp") or ref_type == "runtime":
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
                + " /app/share/metainfo or /app/share/appdata"
            )
            return

        for file in metainfo_files:
            metainfo_validation = appstream.validate(file, "--no-net")
            if metainfo_validation["returncode"] != 0:
                self.errors.add("appstream-failed-validation")
                self.info.add(
                    f"appstream-failed-validation: Metainfo file {file} has failed"
                    + " validation. Please see the errors in appstream block"
                )

                for err in metainfo_validation["stderr"].splitlines():
                    self.appstream.add(err.strip())
                stdout: list[str] = list(
                    filter(
                        lambda x: x.startswith(("E:", "W:")),
                        metainfo_validation["stdout"].splitlines()[:-1],
                    )
                )
                for out in stdout:
                    self.appstream.add(out.strip())

            if not appstream.metainfo_components(file):
                self.errors.add("metainfo-missing-component-tag")
                return

            if appstream.metainfo_components(file)[0].attrib.get("type") is None:
                self.errors.add("metainfo-missing-component-type")

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        ref_type = builddir.infer_type(path)
        if not (appid and ref_type):
            return

        self._validate(f"{path}/files/share", appid, ref_type)

    def check_repo(self, path: str) -> None:
        for ref in ostree.get_all_refs_filtered(path):
            parts = ref.split("/")
            ref_type, appid = parts[0], parts[1]

            if not (appid and ref_type):
                return

            with tempfile.TemporaryDirectory() as tmpdir:
                for subdir in ("appdata", "metainfo"):
                    os.makedirs(os.path.join(tmpdir, subdir), exist_ok=True)
                    ostree.extract_subpath(
                        path, ref, f"files/share/{subdir}", os.path.join(tmpdir, subdir), True
                    )

                self._validate(tmpdir, appid, ref_type)
