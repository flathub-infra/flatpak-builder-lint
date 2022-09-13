from . import Check


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
                self.errors.append("flathub-json-skip-appstream-check")

        eol = manifest.get("end-of-life")
        eol_rebase = manifest.get("end-of-life-rebase")

        if eol and not eol_rebase:
            self.errors.append("flathub-json-eol-message-without-rebase")

        if eol_rebase and not eol:
            self.errors.append("flathub-json-eol-rebase-without-message")

        if eol and eol_rebase:
            if eol_rebase not in eol:
                self.errors.append("flathub-json-eol-rebase-misses-new-id")

        if publish_delay := flathub_json.get("publish-delay-hours"):
            if publish_delay < 3:
                if modules := manifest.get("modules"):
                    if self._check_if_extra_data(modules):
                        self.errors.append("flathub-json-modified-publish-delay")
