import os
import tempfile

from .. import builddir, config, manifest, ostree
from . import Check


class LicenseCheck(Check):
    def _validate(self, appid: str, manifest_json_path: str, path: str) -> None:
        if appid.startswith(config.FLATHUB_RUNTIME_PREFIXES) and appid.endswith(
            config.FLATHUB_RUNTIME_SUFFIXES
        ):
            return

        if not os.path.isfile(manifest_json_path):
            return

        license_root_dir = f"{path}/licenses"

        if not os.path.isdir(license_root_dir):
            self.errors.add("missing-license-root-dir")
            self.info.add(
                "missing-license-root-dir: Missing '/app/share/licenses'. "
                + "Please install some licenses in subdirs named by module names. "
                + "Allowed filenames (case insensitive): licen*, copyright*, copying*"
            )
            return

        manifest_data = manifest.parse_manifest_json(appid, manifest_json_path)

        module_names: set[str] = set()
        modules_missing_license: set[str] = set()

        if manifest_data:
            modules_to_check = manifest_data.get("modules", [])
            while modules_to_check:
                module = modules_to_check.pop()
                if "sources" in module:
                    module_names.add(module["name"])
                if "modules" in module:
                    modules_to_check.extend(module["modules"])

        if module_names:
            for name in sorted(module_names):
                license_dir = f"{license_root_dir}/{name}"
                has_license = False
                if os.path.isdir(license_dir):
                    for fname in os.listdir(license_dir):
                        if fname.lower().startswith(("licen", "copying", "copyright")):
                            has_license = True
                            break
                if not has_license:
                    modules_missing_license.add(name)

        if modules_missing_license:
            for name in sorted(modules_missing_license):
                base_err = f"missing-installed-license-module-{name}"
                self.errors.add(base_err)
                self.info.add(
                    f"{base_err}: Please install a license file to '/app/share/licenses/{name}'. "
                    + "Allowed filenames (case insensitive): licen*, copyright*, copying*"
                )

    def check_build(self, path: str) -> None:
        appid = builddir.infer_appid(path)
        if not appid:
            return

        manifest_json_path = os.path.join(path, "files", "manifest.json")
        self._validate(appid, manifest_json_path, f"{path}/files/share")

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return

        for ref in refs:
            appid = ref.split("/")[1]
            with tempfile.TemporaryDirectory() as tmpdir:
                ostree.extract_subpath(path, ref, "files/manifest.json", tmpdir)
                manifest_json_path = os.path.join(tmpdir, "manifest.json")
                os.makedirs(os.path.join(tmpdir, "licenses"), exist_ok=True)
                ostree.extract_subpath(
                    path, ref, "files/share/licenses", os.path.join(tmpdir, "licenses"), True
                )
                self._validate(appid, manifest_json_path, tmpdir)
