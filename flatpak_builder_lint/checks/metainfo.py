import glob
import os
import tempfile

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .. import appstream, builddir, config, ostree
from . import Check


class MetainfoCheck(Check):
    def _validate(self, path: str, appid: str, ref_type: str) -> None:
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
                + " /app/share/metainfo or /app/share/appdata"
            )
            return

        for file in metainfo_files:
            metainfo_validation = appstream.validate(file, "--no-net", "--format", "yaml")
            if metainfo_validation["returncode"] != 0:
                self.errors.add("appstream-failed-validation")
                self.info.add(
                    f"appstream-failed-validation: Metainfo file {file} has failed"
                    + " validation. Please see the errors in appstream block"
                )

                for err in metainfo_validation["stderr"].splitlines():
                    self.appstream.add(err.strip())

                yaml = YAML()

                try:
                    validation_data = yaml.load(metainfo_validation["stdout"])
                    filename = validation_data.get("File", file)
                    issues = validation_data.get("Issues", [])
                    for issue in issues:
                        severity = issue.get("severity", "").lower()
                        if severity in ("warning", "error"):
                            sev_prefix = "W" if severity == "warning" else "E"
                            tag = issue.get("tag")
                            line = issue.get("line")
                            explanation = issue.get("explanation")
                            parts = [sev_prefix, filename]
                            if tag:
                                parts.append(tag.strip())
                            if line:
                                parts.append(str(line).strip())
                            message = ":".join(parts)
                            if explanation:
                                message += f" {explanation.strip()}"
                            self.appstream.add(message.strip())
                except YAMLError as e:
                    self.appstream.add(f"Failed to parse appstream validate YAML output: {e}")

            if not appstream.metainfo_components(file):
                self.errors.add("metainfo-missing-component-tag")
                return

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
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
