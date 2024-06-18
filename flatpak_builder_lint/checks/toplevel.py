from . import Check


class TopLevelCheck(Check):
    def check_manifest(self, manifest: dict) -> None:
        build_extension = manifest.get("build-extension")
        appid = manifest.get("id")
        if isinstance(appid, str):
            is_baseapp = appid.endswith(".BaseApp")
        else:
            is_baseapp = False

        if not build_extension and not is_baseapp:
            command = manifest.get("command")
            if not command:
                self.errors.add("toplevel-no-command")
            elif command.startswith("/"):
                self.warnings.add("toplevel-command-is-path")
                self.info.add(
                    "toplevel-command-is-path: Command in manifest is a path"
                    + f" {command}"
                )

            branch = manifest.get("branch")
            if branch in ("stable", "master"):
                self.warnings.add("toplevel-unnecessary-branch")
                self.info.add(
                    "toplevel-unnecessary-branch: Found an unnecessary use of"
                    + " branch property in the manifest"
                )

        cleanup = manifest.get("cleanup")
        if cleanup and "/lib/debug" in cleanup:
            self.errors.add("toplevel-cleanup-debug")

        if not manifest.get("modules"):
            self.errors.add("toplevel-no-modules")
