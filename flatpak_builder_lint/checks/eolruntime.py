import tempfile
from collections.abc import Mapping
from typing import Any

from .. import builddir, domainutils, ostree
from . import Check


class EolRuntimeCheck(Check):
    def _validate(self, runtime_ref: str) -> None:
        splits = runtime_ref.split("/")
        decomp_ref = f"{splits[0]}//{splits[2]}"
        eols_runtimes = domainutils.get_eol_runtimes_on_flathub()

        if decomp_ref in eols_runtimes:
            self.warnings.add(f"runtime-is-eol-{splits[0]}-{splits[2]}")

    def check_manifest(self, manifest: Mapping[str, Any]) -> None:
        runtime_id = manifest.get("runtime")
        runtime_br = manifest.get("runtime-version")

        if runtime_id is None or runtime_br is None:
            return

        runtime_ref = f"{runtime_id}/x86_64/{runtime_br}"
        self._validate(runtime_ref)

    def check_build(self, path: str) -> None:
        runtime_ref = builddir.get_runtime(path)
        if not runtime_ref:
            return

        self._validate(runtime_ref)

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return

        for ref in refs:
            with tempfile.TemporaryDirectory() as tmpdir:
                ostree.extract_subpath(path, ref, "/metadata", tmpdir)
                runtime_ref = builddir.get_runtime(tmpdir)
                if not runtime_ref:
                    return

                self._validate(runtime_ref)
