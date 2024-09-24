import re

from . import Check


class ModuleCheck(Check):
    def check_source(self, module_name: str, source: dict) -> None:
        source_type = source.get("type")
        dest_filename = source.get("dest-filename")

        if dest_filename and dest_filename.find("/") != -1:
            self.errors.add(f"module-{module_name}-source-dest-filename-is-path")

        if source_type in ("archive", "file"):
            if source.get("sha1"):
                self.warnings.add(f"module-{module_name}-source-sha1-deprecated")
            if source.get("md5"):
                self.warnings.add(f"module-{module_name}-source-md5-deprecated")

        if source_type == "git":
            commit = source.get("commit")
            branch = source.get("branch")
            tag = source.get("tag")
            branch_committish = False

            if branch:
                if len(branch) != 40:
                    self.errors.add(f"module-{module_name}-source-git-branch")
                else:
                    branch_committish = True

            if not branch_committish and not commit and not tag:
                self.errors.add(f"module-{module_name}-source-git-no-commit-or-tag")

            if source.get("path"):
                self.errors.add(f"module-{module_name}-source-git-local-path")

            url = source.get("url")
            if not url:
                self.errors.add(f"module-{module_name}-source-git-no-url")
            elif not url.startswith("https:") and not url.startswith("http:"):
                self.errors.add(f"module-{module_name}-source-git-url-not-http")

    def check_module(self, module: dict) -> None:
        name = module.get("name")
        buildsystem = module.get("buildsystem", "autotools")

        if buildsystem == "autotools" and (config_opts := module.get("config-opts")):
            for opt in config_opts:
                if re.match(
                    "^--prefix=(/(usr|app)|\\$FLATPAK_DEST|\\${FLATPAK_DEST})/?$",
                    opt,
                ):
                    self.warnings.add(f"module-{name}-autotools-redundant-prefix")
                elif opt.startswith("--enable-debug") and not opt.endswith("=no"):
                    self.errors.add(f"module-{name}-autotools-non-release-build")

        if buildsystem == "cmake":
            self.warnings.add(f"module-{name}-buildsystem-is-plain-cmake")

        cm_reg = "^-DCMAKE_INSTALL_PREFIX(:PATH)?=(/(usr|app)|\\$FLATPAK_DEST|\\${FLATPAK_DEST})/?$"
        if buildsystem in ("cmake-ninja", "cmake") and (config_opts := module.get("config-opts")):
            for opt in config_opts:
                if re.match(cm_reg, opt):
                    self.warnings.add(f"module-{name}-cmake-redundant-prefix")
                elif opt.startswith("-DCMAKE_BUILD_TYPE"):
                    split = opt.split("=")
                    # There is too many possible choices and customizations.
                    # So just make this a warning.
                    # Issues:
                    #  https://github.com/flathub/flatpak-builder-lint/issues/47
                    #  https://github.com/flathub/flatpak-builder-lint/issues/41
                    if split[1] not in ("Release", "RelWithDebInfo", "MinSizeRel"):
                        self.warnings.add(f"module-{name}-cmake-non-release-build")

        if sources := module.get("sources"):
            for source in sources:
                if name := module.get("name"):
                    self.check_source(name, source)

        if nested_modules := module.get("modules"):
            for nested_module in nested_modules:
                self.check_module(nested_module)

    def check_manifest(self, manifest: dict) -> None:
        if modules := manifest.get("modules"):
            for module in modules:
                self.check_module(module)
