import re
from collections.abc import Mapping
from typing import Any

from .. import config
from . import Check


def _is_git_commit_hash(s: str) -> bool:
    return re.match(r"[a-f0-9]{4,40}", s) is not None


def _get_bundled_extensions_not_prefixed_with_appid(manifest: Mapping[str, Any]) -> list[str]:
    appid = manifest.get("id", "")
    extensions = manifest.get("add-extensions", {})
    return [
        ext_id
        for ext_id, ext in extensions.items()
        if ext.get("bundle") is True and not ext_id.startswith(appid)
    ]


class ModuleCheck(Check):
    def check_source(self, module_name: str, source: dict[str, str]) -> None:
        source_type = source.get("type")
        dest_filename = source.get("dest-filename")
        src_url = source.get("url", "")

        if dest_filename and dest_filename.find("/") != -1:
            self.errors.add(f"module-{module_name}-source-dest-filename-is-path")

        if source_type in ("archive", "file"):
            if source.get("sha1") and not src_url.startswith(
                ("https://registry.npmjs.org/", "https://registry.yarnpkg.com/")
            ):
                self.errors.add(f"module-{module_name}-source-sha1-deprecated")
            if source.get("md5"):
                self.errors.add(f"module-{module_name}-source-md5-deprecated")

        if source_type == "git":
            commit = source.get("commit")
            branch = source.get("branch")
            tag = source.get("tag")
            url = source.get("url")

            if not url:
                self.errors.add(f"module-{module_name}-source-git-no-url")
                return

            if url and not url.startswith(("http://", "https://")):
                self.errors.add(f"module-{module_name}-source-git-url-not-http")

            if not any([commit, branch, tag]):
                self.errors.add(f"module-{module_name}-source-git-no-tag-commit-branch")
                return

            if branch and not _is_git_commit_hash(branch):
                self.errors.add(f"module-{module_name}-source-git-branch")

    def check_module(self, module: dict[str, Any]) -> None:
        name = module.get("name")

        if config.is_flathub_build_pipeline():
            build_args = module.get("build-options", {}).get("build-args", [])
            if build_args and "--share=network" in build_args:
                self.errors.add(f"module-{name}-build-network-access")

        buildsystem = module.get("buildsystem", "autotools")

        if buildsystem == "autotools" and (config_opts := module.get("config-opts")):
            for opt in config_opts:
                if opt.startswith("--enable-debug") and not opt.endswith("=no"):
                    self.errors.add(f"module-{name}-autotools-non-release-build")

        if sources := module.get("sources"):
            for source in sources:
                if name := module.get("name"):
                    self.check_source(name, source)
                if "commit-query" in source.get("x-checker-data", {}):
                    self.errors.add(f"module-{name}-checker-tracks-commits")

        if nested_modules := module.get("modules"):
            for nested_module in nested_modules:
                self.check_module(nested_module)

        cleanup = module.get("cleanup")
        if cleanup:
            for c in cleanup:
                if c == "/lib/debug" or c.startswith("/lib/debug/"):
                    self.errors.add(f"module-{name}-cleanup-debug")
                    break

    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        if manifest:
            for ext in _get_bundled_extensions_not_prefixed_with_appid(manifest):
                self.errors.add(f"appid-unprefixed-bundled-extension-{ext}")

        if modules := manifest.get("modules"):
            for module in modules:
                self.check_module(module)
