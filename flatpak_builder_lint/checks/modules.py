from . import Check


class ModuleCheck(Check):
    type = "manifest"

    def check_source(self, module_name: str, source: dict) -> None:
        source_type = source.get("type")
        dest_filename = source.get("dest-filename")

        if dest_filename and dest_filename.find("/") != -1:
            self.errors.add(f"module-{module_name}-source-dest-filename-is-path")

        if source_type == "archive" or source_type == "file":
            if source.get("sha1"):
                self.warnings.add(f"module-{module_name}-source-sha1-deprecated")
            if source.get("md5"):
                self.warnings.add(f"module-{module_name}-source-md5-deprecated")

        if source_type == "git":
            if branch := source.get("branch"):
                if len(branch) != 40 or not (source.get("tag") or source.get("commit")):
                    self.errors.add(f"module-{module_name}-source-git-branch")
            else:
                if not source.get("tag") and not source.get("commit"):
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

        if buildsystem == "autotools":
            if config_opts := module.get("config-opts"):
                for opt in config_opts:
                    if opt.startswith("--prefix="):
                        self.warnings.add(f"module-{name}-autotools-redundant-prefix")
                    elif opt.startswith("--enable-debug"):
                        self.errors.add(f"module-{name}-autotools-non-release-build")

        if buildsystem == "cmake":
            self.warnings.add(f"module-{name}-buildsystem-is-plain-cmake")

        if buildsystem in ("cmake-ninja", "cmake"):
            if config_opts := module.get("config-opts"):
                for opt in config_opts:
                    if opt.startswith("-DCMAKE_INSTALL_PREFIX"):
                        self.warnings.add(f"module-{name}-cmake-redundant-prefix")
                    elif opt.startswith("-DCMAKE_BUILD_TYPE"):
                        split = opt.split("=")
                        if split[1] == "Release":
                            # we shouldn't emit this on an extension
                            self.warnings.add(f"module-{name}-cmake-no-debuginfo")
                        elif split[1] != "RelWithDebInfo":
                            self.errors.add(f"module-{name}-cmake-non-release-build")

        if sources := module.get("sources"):
            for source in sources:
                if name := module.get("name"):
                    self.check_source(name, source)
        # else:
        #     self.errors.add(f"module-{name}-no-sources")

        if nested_modules := module.get("modules"):
            for nested_module in nested_modules:
                self.check_module(nested_module)

    def check(self, manifest: dict) -> None:
        if modules := manifest.get("modules"):
            for module in modules:
                self.check_module(module)
