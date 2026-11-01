import gzip
import json
import logging
import os
import shutil
import tempfile
from typing import Any

from .. import appstream, config
from . import Check

logger = logging.getLogger(__name__)


def _load_build_info(raw: str) -> dict[str, Any]:
    try:
        build_extended: Any = json.loads(raw)
    except ValueError as e:
        raise RuntimeError(f"FLAT_MANAGER_BUILD_INFO is not valid JSON: {e}") from e

    if not isinstance(build_extended, dict):
        raise RuntimeError("FLAT_MANAGER_BUILD_INFO must be a JSON object")

    build_info = build_extended.get("build")
    if not isinstance(build_info, dict):
        raise RuntimeError("FLAT_MANAGER_BUILD_INFO is missing the build object")
    if not isinstance(build_info.get("repo"), str):
        raise RuntimeError("FLAT_MANAGER_BUILD_INFO build is missing the repo name")

    build_refs = build_extended.get("build_refs")
    if not isinstance(build_refs, list):
        raise RuntimeError("FLAT_MANAGER_BUILD_INFO is missing the build_refs list")
    for build_ref in build_refs:
        if not isinstance(build_ref, dict) or not isinstance(build_ref.get("ref_name"), str):
            raise RuntimeError("FLAT_MANAGER_BUILD_INFO build_refs entries need a ref_name")

    return build_extended


def get_build_extended() -> dict[str, Any] | None:
    if not config.is_flatmgr_pipeline():
        return None

    raw = os.getenv("FLAT_MANAGER_BUILD_INFO")
    if not raw:
        raise RuntimeError("FLAT_MANAGER_BUILD_INFO is not set in a flat-manager pipeline")

    return _load_build_info(raw)


def is_direct_upload_build() -> bool:
    try:
        build_extended = get_build_extended()
    except (RuntimeError, TypeError, ValueError):
        logger.debug(
            "Failed to load build provenance from the flat-manager pipeline", exc_info=True
        )
        return False

    if build_extended is None:
        return False

    build_info: dict[str, Any] = build_extended["build"]
    return bool(build_info.get("token_type") == "app")


class FlatManagerCheck(Check):
    def check_repo(self, path: str) -> None:
        build_extended = get_build_extended()
        if build_extended is not None:
            build_info: dict[str, Any] = build_extended["build"]
            token_type = build_info.get("token_type")
            target_repo = build_info["repo"]

            refs = [build_ref["ref_name"] for build_ref in build_extended["build_refs"]]
            arches = {ref.split("/")[2] for ref in refs if len(ref.split("/")) == 4}

            if token_type == "app":
                has_app_ref = any(ref.startswith("app/") for ref in refs)
                if not has_app_ref:
                    self.errors.add("flat-manager-no-app-ref-uploaded")
                    return

                for ref in refs:
                    if ref.startswith("screenshots/"):
                        continue
                    ref_branch = ref.split("/")[-1]
                    if ref_branch != target_repo:
                        self.errors.add("flat-manager-branch-repo-mismatch")
                        break

                with tempfile.TemporaryDirectory() as tmpdir:
                    with (
                        gzip.open(
                            f"{path}/appstream/{arches.pop()}/appstream.xml.gz", "rb"
                        ) as appstream_gz,
                        open(f"{tmpdir}/appstream.xml", "wb") as appstream_file,
                    ):
                        shutil.copyfileobj(appstream_gz, appstream_file)

                    manifest_key = appstream.get_manifest_key(f"{tmpdir}/appstream.xml")
                    if not manifest_key:
                        self.errors.add("appstream-no-flathub-manifest-key")

            else:
                ref_branches: set[str] = {
                    parts[-1]
                    for ref in refs
                    if not ref.startswith(
                        (
                            "runtime/org.freedesktop.Platform.GL.",
                            "runtime/org.freedesktop.Platform.GL32.",
                        )
                    )
                    and (parts := ref.strip("/").split("/"))
                    and len(parts) >= 3
                }

                if not ref_branches:
                    return

                all_branches_beta = all(
                    branch.endswith(("beta", "beta-extra")) for branch in ref_branches
                )

                any_branches_beta = any(
                    branch.endswith(("beta", "beta-extra")) for branch in ref_branches
                )

                if target_repo == "beta" and not all_branches_beta:
                    self.errors.add("flat-manager-wrong-ref-branch-for-beta-repo")
                    self.info.add(
                        "flat-manager-wrong-ref-branch-for-beta-repo: If the target repo is 'beta' "
                        + "then all refs must have branches ending with 'beta' or 'beta-extra'"
                    )

                if target_repo == "stable" and any_branches_beta:
                    self.errors.add("flat-manager-wrong-ref-branch-for-stable-repo")
                    self.info.add(
                        "flat-manager-wrong-ref-branch-for-stable-repo: If the target repo is "
                        + "'stable' then no ref must have branches ending "
                        + "with 'beta' or 'beta-extra'"
                    )

                appref_list = [ref for ref in refs if ref.startswith("app/")]
                if not appref_list:
                    return

                appref = appref_list[0]
                _, appid, _, branch = appref.split("/")

                if (
                    appid.endswith(config.FLATHUB_BASEAPP_IDENTIFIER)
                    or appid.startswith("org.freedesktop.Platform.")
                    or appid == "org.winehq.Wine"
                ):
                    return

                if target_repo == "test" and branch in ("stable", "beta", "test"):
                    return

                if branch != target_repo:
                    self.errors.add("flat-manager-branch-repo-mismatch")
