import tempfile
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .. import builddir, domainutils, ostree
from . import Check


class EolRuntimeCheck(Check):
    def _get_latest_runtime_verdict(self, active_runtimes: set[str]) -> dict[str, str]:
        runtime_groups: dict[str, set[str]] = {
            "fdsdk": {"org.freedesktop.Sdk", "org.freedesktop.Platform"},
            "gnome": {"org.gnome.Platform", "org.gnome.Sdk"},
            "kde5": {"org.kde.Platform", "org.kde.Sdk"},
            "kde6": {"org.kde.Platform", "org.kde.Sdk"},
        }

        def split_version(v: str) -> tuple[int, ...]:
            if "-" in v:
                base, suffix = v.split("-", 1)
                return tuple(map(int, base.split("."))) + tuple(map(int, suffix.split(".")))
            return tuple(map(int, v.split(".")))

        latest_versions = defaultdict(list)

        for entry in active_runtimes:
            if "//" not in entry:
                continue
            ref_id, ref_branch = entry.split("//", 1)

            if ref_id in runtime_groups["fdsdk"]:
                latest_versions["fdsdk"].append(ref_branch)
            elif ref_id in runtime_groups["gnome"]:
                latest_versions["gnome"].append(ref_branch)
            elif ref_id in runtime_groups["kde5"] and ref_branch.startswith("5."):
                latest_versions["kde5"].append(ref_branch)
            elif ref_id in runtime_groups["kde6"] and ref_branch.startswith("6."):
                latest_versions["kde6"].append(ref_branch)

        return {key: max(vals, key=split_version) for key, vals in latest_versions.items() if vals}

    def _get_latest_runtime_version(self, comp_ref: str, active_runtimes: set[str]) -> str | None:
        if "//" not in comp_ref:
            return None

        ref_id, ref_branch = comp_ref.split("//", 1)

        if ref_id in ("org.freedesktop.Platform", "org.freedesktop.Sdk"):
            grp_name = "fdsdk"
        elif ref_id in ("org.gnome.Platform", "org.gnome.Sdk"):
            grp_name = "gnome"
        elif ref_id in ("org.kde.Platform", "org.kde.Sdk"):
            if ref_branch.startswith("5."):
                grp_name = "kde5"
            elif ref_branch.startswith("6."):
                grp_name = "kde6"
            else:
                return None
        else:
            return None

        latest_versions = self._get_latest_runtime_verdict(active_runtimes)
        return latest_versions.get(grp_name)

    def _is_eol_by_n_versions(
        self, comp_ref: str, active_runtimes: set[str], lapse_threshold: int = 3
    ) -> None | bool:
        if "//" not in comp_ref:
            return None

        ref_id, ref_branch = comp_ref.split("//", 1)

        short_rules: dict[tuple[str, ...], Callable[[str], bool]] = {
            ("org.freedesktop.Sdk", "org.freedesktop.Platform"): lambda v: v.startswith("1.6"),
            ("org.gnome.Sdk", "org.gnome.Platform"): lambda v: v.startswith("3."),
            ("org.kde.Sdk", "org.kde.Platform"): lambda v: not (v.startswith(("5.15-", "6."))),
        }

        for keys, cond in short_rules.items():
            if ref_id in keys and cond(ref_branch):
                return True

        latest_branch = self._get_latest_runtime_version(comp_ref, active_runtimes)
        if latest_branch is None:
            return None

        def version_str_to_scaled_int(v: str) -> float | None:
            try:
                if "-" in v:
                    v = v.split("-", 1)[1]
                parts = list(map(int, v.split(".")))
                if not parts:
                    return None
                major = parts[0]
                minor = parts[1] if len(parts) > 1 else 0
                val = major * 100 + minor
                if major < 10:
                    val *= 100
                return val
            except ValueError:
                return None

        current_ver = version_str_to_scaled_int(ref_branch)
        latest_ver = version_str_to_scaled_int(latest_branch)

        if current_ver is None or latest_ver is None:
            return False

        diff = int(abs(latest_ver - current_ver))

        return diff >= lapse_threshold * 100

    def _validate(self, runtime_ref: str) -> None:
        splits = runtime_ref.split("/")
        comp_ref = f"{splits[0]}//{splits[2]}"
        base_msg = f"runtime-is-eol-{splits[0]}-{splits[2]}"
        eols_runtimes = domainutils.get_eol_runtimes_on_flathub()
        active_runtimes = domainutils.get_active_runtimes_on_flathub()

        if comp_ref in eols_runtimes:
            if self._is_eol_by_n_versions(comp_ref, active_runtimes) is True:
                self.errors.add(base_msg)
                return
            self.warnings.add(base_msg)
            self.info.add(f"{base_msg}: Please update to a supported runtime version")

    def check_manifest(self, manifest: dict[str, Any]) -> None:
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
