import tempfile

from .. import builddir, config, ostree
from . import Check


class FlathubJsonCheck(Check):
    arches = config.FLATHUB_SUPPORTED_ARCHES

    def _check_if_extra_data(self, modules: list) -> bool:
        for module in modules:
            if sources := module.get("sources"):
                for source in sources:
                    if source.get("type") == "extra-data":
                        return True

            if nested_modules := module.get("modules"):
                return self._check_if_extra_data(nested_modules)

        return False

    def _validate(
        self, appid: str, flathub_json: dict, is_extra_data: bool, is_extension: bool
    ) -> None:
        is_baseapp = appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)

        eol = flathub_json.get("end-of-life")
        eol_rebase = flathub_json.get("end-of-life-rebase")
        automerge = flathub_json.get("automerge-flathubbot-prs")
        skip_appstream = flathub_json.get("skip-appstream-check")
        only_arches = flathub_json.get("only-arches")
        skip_arches = flathub_json.get("skip-arches")
        publish_delay = flathub_json.get("publish-delay-hours")

        if skip_appstream and not (is_extension or is_baseapp):
            self.errors.add("flathub-json-skip-appstream-check")

        if automerge:
            self.errors.add("flathub-json-automerge-enabled")

        if eol_rebase and not eol:
            self.errors.add("flathub-json-eol-rebase-without-message")

        if only_arches is not None and len(only_arches) == 0:
            self.errors.add("flathub-json-only-arches-empty")

        if skip_arches is not None and len(set(self.arches).intersection(skip_arches)) == len(
            self.arches
        ):
            self.errors.add("flathub-json-excluded-all-arches")

        if isinstance(publish_delay, int) and publish_delay < 3 and not is_extra_data:
            self.errors.add("flathub-json-modified-publish-delay")

    def check_manifest(self, manifest: dict) -> None:
        flathub_json = manifest.get("x-flathub")
        appid = manifest.get("id")
        if not (flathub_json and appid):
            return

        is_extra_data = (
            self._check_if_extra_data(modules) if (modules := manifest.get("modules")) else False
        )
        is_extension = manifest.get("build-extension", False)

        self._validate(appid, flathub_json, is_extra_data, is_extension)

    def check_build(self, path: str) -> None:
        appid, ref_type = builddir.infer_appid(path), builddir.infer_type(path)
        if not (appid and ref_type):
            return
        metadata = builddir.parse_metadata(path)
        if not metadata:
            return
        is_extra_data = bool(metadata.get("extra-data", False))

        flathub_json = builddir.get_flathub_json(path)
        if not flathub_json:
            return

        self._validate(appid, flathub_json, is_extra_data, ref_type != "app")

    def check_repo(self, path: str) -> None:
        self._populate_ref(path)
        ref = self.repo_primary_ref
        if not ref:
            return
        appid = ref.split("/")[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            ostree.extract_subpath(path, ref, "/metadata", tmpdir)
            metadata = builddir.parse_metadata(tmpdir)
            if not metadata:
                return
            flathub_json = ostree.get_flathub_json(path, ref, tmpdir)
            if not flathub_json:
                return
            is_extra_data = bool(metadata.get("extra-data", False))
            self._validate(appid, flathub_json, is_extra_data, False)
