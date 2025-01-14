import gzip
import json
import os
import shutil
import tempfile

import requests

from .. import appstream, domainutils
from . import Check

REQUEST_TIMEOUT = domainutils.REQUEST_TIMEOUT


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
            r = requests.get(
                f"{flatmgr_url}/api/v1/build/{build_id}/extended",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

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
                    if manifest_key and not domainutils.check_url(manifest_key[0], strict=False):
                        self.errors.add("appstream-flathub-manifest-url-not-reachable")

            else:
                appref_list = [ref for ref in refs if ref.startswith("app/")]
                if not appref_list:
                    return

                appref = appref_list[0]
                _, appid, _, branch = appref.split("/")

                if (
                    appid.split(".")[-1] == "BaseApp"
                    or appid.startswith("org.freedesktop.Platform.")
                    or appid == "org.winehq.Wine"
                ):
                    return

                if target_repo == "test" and branch in ("stable", "beta", "test"):
                    return

                if branch != target_repo:
                    self.errors.add("flat-manager-branch-repo-mismatch")
