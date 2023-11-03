import json
import os

import requests

from . import Check


class FlatManagerCheck(Check):
    def check_repo(self, path: str) -> None:
        if build_id := os.getenv("FLAT_MANAGER_BUILD_ID"):
            with open("/etc/flathub-hooks.json") as f:
                flathub_hooks_cfg = json.load(f)

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
                f"{flatmgr_url}/api/v1/build/{build_id}/extended", headers=headers
            )

            if r.status_code != 200:
                raise RuntimeError(
                    f"Failed to fetch build info from flat-manager: {r.status_code}"
                )

            build_info = r.json()
            token_type = build_info.get("token_type")
            target_repo = build_info.get("target_repo")

            if token_type == "app":
                refs = [
                    build_ref["ref_name"]
                    for build_ref in build_info.get("build_refs", [])
                ]
                has_app_ref = any(ref.startswith("app/") for ref in refs)
                if not has_app_ref:
                    self.errors.add("flat-manager-no-app-ref-uploaded")

                for ref in refs:
                    ref_branch = ref.split("/")[-1]
                    if ref_branch != target_repo:
                        self.errors.add("flat-manager-branch-repo-mismatch")
                        break
