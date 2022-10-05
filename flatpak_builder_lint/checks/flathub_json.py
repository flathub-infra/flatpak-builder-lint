from . import ARCHES, Check


class FlathubJsonCheck(Check):
    type = "manifest"

    def _check_if_extra_data(self, modules: list) -> bool:
        for module in modules:
            if sources := module.get("sources"):
                for source in sources:
                    if source.get("type") == "extra-data":
                        return True

            if nested_modules := module.get("modules"):
                return self._check_if_extra_data(nested_modules)

        return False

    def check(self, manifest: dict) -> None:
        flathub_json = manifest.get("x-flathub")
        if not flathub_json:
            return

        if flathub_json.get("skip-appstream-check"):
            if not manifest.get("build-extension"):
                self.errors.add("flathub-json-skip-appstream-check")

        eol = flathub_json.get("end-of-life")
        eol_rebase = flathub_json.get("end-of-life-rebase")

        if eol and not eol_rebase:
            self.errors.add("flathub-json-eol-message-without-rebase")

        if eol_rebase and not eol:
            self.errors.add("flathub-json-eol-rebase-without-message")

        if eol and eol_rebase:
            if eol_rebase not in eol:
                self.errors.add("flathub-json-eol-rebase-misses-new-id")

        publish_delay = flathub_json.get("publish-delay-hours")
        if isinstance(publish_delay, int):
            if publish_delay < 3:
                if modules := manifest.get("modules"):
                    if not self._check_if_extra_data(modules):
                        self.errors.add("flathub-json-modified-publish-delay")

        if only_arches := flathub_json.get("only-arches"):
            if "arm" in only_arches:
                self.warnings.add("flathub-json-deprecated-arm-arch-included")
            if "i386" in only_arches:
                self.warnings.add("flathub-json-deprecated-i386-arch-included")
            if len(only_arches) == 0:
                self.errors.add("flathub-json-only-arches-empty")
            if len(ARCHES.intersection(only_arches)) == len(ARCHES):
                self.warnings.add("flathub-json-redundant-only-arches")

        if exclude_arches := flathub_json.get("exclude-arches"):
            if "arm" in exclude_arches:
                self.warnings.add("flathub-json-deprecated-arm-arch-excluded")
            if "i386" in exclude_arches:
                self.warnings.add("flathub-json-deprecated-i386-arch-excluded")
            if len(exclude_arches) == 0:
                self.warnings.add("flathub-json-exclude-arches-empty")
            if len(ARCHES.intersection(exclude_arches)) == len(ARCHES):
                self.errors.add("flathub-json-excluded-all-arches")
