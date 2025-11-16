import tempfile
from collections.abc import Mapping
from typing import Any

from .. import builddir, config, ostree
from . import Check


class FlathubJsonCheck(Check):
    arches = config.FLATHUB_SUPPORTED_ARCHES

    def _check_if_extra_data(self, modules: list[dict[str, Any]]) -> bool:
        for module in modules:
            if sources := module.get("sources"):
                for source in sources:
                    if source.get("type") == "extra-data":
                        return True

            if nested_modules := module.get("modules"):
                return self._check_if_extra_data(nested_modules)

        return False

    def _validate(
        self,
        appid: str,
        flathub_json: dict[str, str | bool | list[str]],
        is_extension: bool,
    ) -> None:
        is_baseapp = appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)

        eol = flathub_json.get("end-of-life")
        eol_rebase = flathub_json.get("end-of-life-rebase")
        automerge = flathub_json.get("automerge-flathubbot-prs")
        skip_appstream = flathub_json.get("skip-appstream-check")
        only_arches = flathub_json.get("only-arches")
        skip_arches = flathub_json.get("skip-arches")

        if skip_appstream and not (is_extension or is_baseapp):
            self.errors.add("flathub-json-skip-appstream-check")

        if automerge:
            self.errors.add("flathub-json-automerge-enabled")

        if eol_rebase and not eol:
            self.errors.add("flathub-json-eol-rebase-without-message")

        if only_arches is not None and not isinstance(only_arches, bool) and len(only_arches) == 0:
            self.errors.add("flathub-json-only-arches-empty")

        if (
            skip_arches is not None
            and isinstance(skip_arches, set)
            and len(set(self.arches).intersection(skip_arches)) == len(self.arches)
        ):
            self.errors.add("flathub-json-excluded-all-arches")

    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        flathub_json = manifest.get("x-flathub")
        appid = manifest.get("id")
        if not (flathub_json and appid):
            return

        is_extension = manifest.get("build-extension", False)

        self._validate(appid, flathub_json, is_extension)

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type):
            return
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return

        flathub_json = builddir.get_flathub_json(path)
        if not flathub_json:
            return

        self._validate(appid, flathub_json, ref_type != "app")

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return

        for ref in refs:
            appid = ref.split("/")[1]

            with tempfile.TemporaryDirectory() as tmpdir:
                ostree.extract_subpath(path, ref, "/metadata", tmpdir)
                metadata = builddir.parse_metadata(tmpdir)
                if not metadata:
                    return
                flathub_json = ostree.get_flathub_json(path, ref, tmpdir)
                if not flathub_json:
                    return
                self._validate(appid, flathub_json, False)
