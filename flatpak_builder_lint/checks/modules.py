from . import Check


class ModuleCheck(Check):
    type = "manifest"

    def check(self, module):
        name = module.get("name")
        buildsystem = module.get("buildsystem", "autotools")

        if buildsystem == "autotools":
            config_opts = module.get("config-opts")
            for opt in config_opts:
                if opt.startswith("--prefix="):
                    self.errors.append("module-autotools-redundant-prefix")
                elif opt.startswith("--enable-debug"):
                    self.errors.append("module-autotools-non-release-build")

        if buildsystem == "cmake":
            self.warnings.append("module-buildsystem-is-cmake")

        if buildsystem in ("cmake-ninja", "cmake"):
            config_opts = module.get("config-opts")
            for opt in config_opts:
                if opt.startswith("-DCMAKE_INSTALL_PREFIX"):
                    self.errors.append("module-cmake-redundant-prefix")
                elif opt.startswith("-DCMAKE_BUILD_TYPE"):
                    split = opt.split("=")
                    if split[1] == "Release":
                        # we shouldn't emit this on an extension
                        self.warnings.append("module-cmake-no-debuginfo")
                    elif split[1] != "RelWithDebInfo":
                        self.errors.append("module-cmake-non-release-build")

        if sources := module.get("sources"):
            for source in sources:
                source_type = source.get("type")
                dest_filename = source.get("dest-filename")

                if dest_filename and dest_filename.find("/") != -1:
                    self.errors.append("source-dest-filename-is-path")

                if source_type == "archive" or source_type == "file":
                    if source.get("sha1"):
                        self.errors.append("source-sha1-deprecated")
                    if source.get("md5"):
                        self.errors.append("source-md5-deprecated")

                if source_type == "git":
                    if source.get("branch"):
                        self.errors.append("source-git-branch")
                    if not source.get("tag") and not source.get("commit"):
                        self.errors.append("source-git-no-commit-or-tag")
                    if source.get("path"):
                        self.errors.append("source-git-path")
                    url = source.get("url")
                    if not url:
                        self.errors.append("source-git-no-url")
                    elif not url.startswith("https:") and not url.startswith("http:"):
                        self.errors.append("source-git-url-not-http")

                        for checkclass in checks.ALL:
                            check = checkclass()

                            if check.type == "source":
                                check.check(source)
        else:
            self.errors.append("module-no-sources")
