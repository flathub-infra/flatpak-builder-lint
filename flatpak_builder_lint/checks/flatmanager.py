import gzip
import json
import logging
import os
import shutil
import tempfile

import requests

from .. import appstream, config, domainutils
from . import Check

REQUEST_TIMEOUT = domainutils.REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class FlatManagerCheck(Check):
    def check_repo(self, path: str) -> None:
        flathub_hooks_cfg_paths = [
            "/run/host/etc/flathub-hooks.json",
            "/etc/flathub-hooks.json",
        ]

        if build_id := os.getenv("FLAT_MANAGER_BUILD_ID"):
            flathub_hooks_cfg = {}
            for flathub_hooks_cfg_path in flathub_hooks_cfg_paths:
                if os.path.exists(flathub_hooks_cfg_path):
                    with open(flathub_hooks_cfg_path) as f:
                        flathub_hooks_cfg = json.load(f)
                    break

            flatmgr_url = os.getenv("FLAT_MANAGER_URL")
            if not flatmgr_url:
                flatmgr_url = flathub_hooks_cfg.get("flat_manager_url")
            if not flatmgr_url:
                raise RuntimeError("No flat-manager URL configured")

            flatmgr_token = os.getenv("FLAT_MANAGER_TOKEN")
            if not flatmgr_token:
                flatmgr_token = flathub_hooks_cfg.get("flat_manager_token")
            if not flatmgr_token:
                raise RuntimeError("No flat-manager token configured")

            headers = {
                "Authorization": f"Bearer {flatmgr_token}",
                "Content-Type": "application/json",
            }

            flat_mgr_extended_api = f"{flatmgr_url}/api/v1/build/{build_id}/extended"
            r = requests.get(
                flat_mgr_extended_api,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            logger.debug(
                "Request headers for %s: %s",
                flat_mgr_extended_api,
                domainutils.filter_request_headers(dict(r.request.headers)),
            )
            logger.debug("Response headers for %s: %s", flat_mgr_extended_api, dict(r.headers))

            if r.status_code != 200:
                raise RuntimeError(f"Failed to fetch build info from flat-manager: {r.status_code}")

            build_extended = r.json()
            build_info = build_extended["build"]
            token_type = build_info["token_type"]
            target_repo = build_info["repo"]

            refs = [build_ref["ref_name"] for build_ref in build_extended.get("build_refs", [])]
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
