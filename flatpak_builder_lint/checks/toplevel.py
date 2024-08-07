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
                self.errors.add("toplevel-command-is-path")
                self.info.add(
                    "toplevel-command-is-path: Command in manifest is a path"
                    + f" {command}. Please install the executable to"
                    + " $FLATPAK_DEST/bin and change command to just the name"
                )

            branch = manifest.get("branch")
            def_branch = manifest.get("default-branch")
            if branch in ("stable", "master") or def_branch in ("stable", "master"):
                self.errors.add("toplevel-unnecessary-branch")
                self.info.add(
                    "toplevel-unnecessary-branch: Please remove the toplevel"
                    + " branch or default-branch property in the manifest"
                )

        cleanup = manifest.get("cleanup")
        if cleanup and "/lib/debug" in cleanup:
            self.errors.add("toplevel-cleanup-debug")

        if not manifest.get("modules"):
            self.errors.add("toplevel-no-modules")
