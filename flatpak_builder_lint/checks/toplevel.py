from . import Check


class TopLevelCheck(Check):
    type = "manifest"

    def check(self, manifest: dict) -> None:
        build_extension = manifest.get("build-extension")
        # This logic copied from finish_args.py
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

            branch = manifest.get("branch")
            if branch in ("stable", "master"):
                self.warnings.add("toplevel-unnecessary-branch")

        cleanup = manifest.get("cleanup")
        if cleanup and "/lib/debug" in cleanup:
            self.errors.add("toplevel-cleanup-debug")

        if not manifest.get("modules"):
            self.errors.add("toplevel-no-modules")
