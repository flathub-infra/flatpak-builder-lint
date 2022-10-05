from . import Check


class TopLevelCheck(Check):
    type = "manifest"

    def check(self, manifest: dict) -> None:
        build_extension = manifest.get("build-extension")

        if not build_extension:
            command = manifest.get("command")
            if not command:
                self.errors.add("toplevel-no-command")
            elif command.startswith("/"):
                self.warnings.add("toplevel-command-is-path")

            branch = manifest.get("branch")
            if branch == "stable" or branch == "master":
                self.warnings.add("toplevel-unecessary-branch")

        cleanup = manifest.get("cleanup")
        if cleanup and "/lib/debug" in cleanup:
            self.errors.add("toplevel-cleanup-debug")

        if not manifest.get("modules"):
            self.errors.add("toplevel-no-modules")
