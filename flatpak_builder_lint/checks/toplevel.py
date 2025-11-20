from collections.abc import Mapping
from typing import Any

from .. import config
from . import Check


class TopLevelCheck(Check):
    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        yaml_failed = manifest.get("x-manifest-yaml-failed")
        if yaml_failed:
            self.errors.add("manifest-invalid-yaml")
            self.info.add(f"manifest-invalid-yaml: {yaml_failed}")

        unknown_propeties = manifest.get("x-manifest-unknown-properties")

        if unknown_propeties:
            self.errors.add("manifest-unknown-properties")
            for p in unknown_propeties:
                self.info.add(
                    f"manifest-unknown-properties: Invalid property "
                    f"'{p.get('property')}' in context '{p.get('context')}'"
                )

        json_warnings = manifest.get("x-manifest-json-warnings")

        if json_warnings:
            self.errors.add("manifest-json-warnings")
            self.info.add(f"manifest-json-warnings: {json_warnings}")

        if config.is_flathub_build_pipeline():
            build_args = manifest.get("build-options", {}).get("build-args", [])
            if build_args and "--share=network" in build_args:
                self.errors.add("manifest-toplevel-build-network-access")

        build_extension = manifest.get("build-extension")
        build_runtime = manifest.get("build-runtime")
        appid = manifest.get("id")
        is_baseapp = bool(
            isinstance(appid, str) and appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)
        )

        if not any([build_extension, is_baseapp, build_runtime]):
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

            if branch:
                self.errors.add("toplevel-unnecessary-branch")
                self.info.add(
                    "toplevel-unnecessary-branch: Please remove the toplevel"
                    + " branch property in the manifest"
                )

        cleanup = manifest.get("cleanup")
        if cleanup:
            for c in cleanup:
                if c == "/lib/debug" or c.startswith("/lib/debug/"):
                    self.errors.add("toplevel-cleanup-debug")
                    break

        if not manifest.get("modules"):
            self.errors.add("toplevel-no-modules")

        gitmodules = manifest.get("x-gitmodules", [])
        ext_gitmodules = [
            m for m in gitmodules if not m.startswith(config.FLATHUB_ALLOWED_GITMODULE_URLS)
        ]
        if ext_gitmodules:
            self.errors.add("external-gitmodule-url-found")
            self.info.add(
                "external-gitmodule-url-found: Only flatpak, flathub, and flathub-infra "
                f"gitmodules are allowed in manifest git repo: {ext_gitmodules}"
            )

        if manifest.get("x-manifest-dir-large"):
            self.errors.add("manifest-directory-too-large")
            self.info.add("manifest-directory-too-large: Manifest directory is more than 25 MB")
