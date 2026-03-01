from collections.abc import Mapping
from typing import Any

from .. import config, giturl
from . import Check


def _get_bundled_extensions_not_prefixed_with_appid(manifest: Mapping[str, Any]) -> list[str]:
    appid = manifest.get("id", "")
    extensions = manifest.get("add-extensions", {})
    return [
        ext_id
        for ext_id, ext in extensions.items()
        if ext.get("bundle") is True and not ext_id.startswith(appid)
    ]


class ModuleCheck(Check):
    def check_stacked_git_source(
        self,
        module_name: str,
        sources: list[dict[str, Any]],
    ) -> None:
        git_dests: dict[str, list[str]] = {}

        for source in sources:
            if source.get("type") != "git":
                continue

            dest = source.get("dest", ".")
            url = source.get("url")

            if url:
                git_dests.setdefault(dest, []).append(url)

        error_id = f"module-{module_name}-multiple-git-sources-stacked"

        for _, urls in git_dests.items():
            if len(urls) > 1:
                self.errors.add(error_id)
                self.info.add(
                    f"{error_id}: The module is stacking multiple git sources "
                    "in the same destination. Consider separating them or using "
                    "'dest' to unstack the sources."
                )

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

            url = source.get("url")
            if url and giturl.is_branch(url):
                self.errors.add(f"module-{module_name}-source-git-file-branch")

        if source_type == "dir" and config.is_flathub_pipeline():
            self.errors.add(f"module-{module_name}-source-dir-not-allowed")

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

            if tag and not commit:
                err_s = f"module-{module_name}-source-git-no-commit-with-tag"
                if config.is_flathub_new_submission_build_pipeline():
                    self.errors.add(err_s)
                else:
                    self.warnings.add(err_s)
                return

            # We should actually not even need to check if this is a commit.
            # `commit` should be used instead.
            if branch and not giturl.is_git_commit_hash(branch):
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
            if name := module.get("name"):
                self.check_stacked_git_source(name, sources)

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
