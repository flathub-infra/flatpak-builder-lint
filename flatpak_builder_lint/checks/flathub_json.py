from typing import Set

from . import Check


class FlathubJsonCheck(Check):
    arches: Set[str] = {"x86_64", "aarch64"}

    def _check_if_extra_data(self, modules: list) -> bool:
        for module in modules:
            if sources := module.get("sources"):
                for source in sources:
                    if source.get("type") == "extra-data":
                        return True

            if nested_modules := module.get("modules"):
                return self._check_if_extra_data(nested_modules)

        return False

    def validate(
        self, appid: str, flathub_json: dict, is_extra_data: bool, is_extension: bool
    ) -> None:
        if flathub_json.get("skip-appstream-check"):
            is_baseapp = appid.endswith(".BaseApp")
            if not (is_extension or is_baseapp):
                self.errors.add("flathub-json-skip-appstream-check")

        eol = flathub_json.get("end-of-life")
        eol_rebase = flathub_json.get("end-of-life-rebase")

        if eol_rebase and not eol:
            self.errors.add("flathub-json-eol-rebase-without-message")

        if eol and eol_rebase:
            if eol_rebase not in eol:
                self.errors.add("flathub-json-eol-rebase-misses-new-id")

        if only_arches := flathub_json.get("only-arches"):
            if "arm" in only_arches:
                self.warnings.add("flathub-json-deprecated-arm-arch-included")
            if "i386" in only_arches:
                self.warnings.add("flathub-json-deprecated-i386-arch-included")
            if len(only_arches) == 0:
                self.errors.add("flathub-json-only-arches-empty")
            if len(self.arches.intersection(only_arches)) == len(self.arches):
                self.warnings.add("flathub-json-redundant-only-arches")

        if exclude_arches := flathub_json.get("exclude-arches"):
            if "arm" in exclude_arches:
                self.warnings.add("flathub-json-deprecated-arm-arch-excluded")
            if "i386" in exclude_arches:
                self.warnings.add("flathub-json-deprecated-i386-arch-excluded")
            if len(exclude_arches) == 0:
                self.warnings.add("flathub-json-exclude-arches-empty")
            if len(self.arches.intersection(exclude_arches)) == len(self.arches):
                self.errors.add("flathub-json-excluded-all-arches")

        publish_delay = flathub_json.get("publish-delay-hours")
        if isinstance(publish_delay, int):
            if publish_delay < 3 and not is_extra_data:
                self.errors.add("flathub-json-modified-publish-delay")

    def check_manifest(self, manifest: dict) -> None:
        flathub_json = manifest.get("x-flathub")
        if not flathub_json:
            return

        appid = manifest.get("id")
        if not appid:
            return

        is_extra_data = False
        if modules := manifest.get("modules"):
            is_extra_data = self._check_if_extra_data(modules)

        is_extension = manifest.get("build-extension", False)

        self.validate(appid, flathub_json, is_extra_data, is_extension)
