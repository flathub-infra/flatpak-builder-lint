import re
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
            "kde5lts": {"org.kde.Platform", "org.kde.Sdk"},
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
            elif ref_id in runtime_groups["kde5lts"] and ref_branch.startswith("5.15-"):
                latest_versions["kde5lts"].append(ref_branch)
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
            if ref_branch.startswith("5.15-"):
                grp_name = "kde5lts"
            elif ref_branch.startswith("6."):
                grp_name = "kde6"
            else:
                return None
        else:
            return None

        latest_versions = self._get_latest_runtime_verdict(active_runtimes)
        return latest_versions.get(grp_name)

    def _parse_fdsdk_gnome_ver_offset(self, v1: str, v2: str) -> int | None:
        def parse(v: str) -> int | None:
            if re.fullmatch(r"\d+", v):
                return int(v)
            if re.fullmatch(r"\d+\.08", v):
                return int(v.split(".")[0])
            return None

        a = parse(v1)
        b = parse(v2)
        if a is not None and b is not None:
            return abs(b - a)
        return None

    def _parse_kde_ver_offset(self, v1: str, v2: str) -> int | None:
        def parse(v: str) -> tuple[int, int] | None:
            m = re.fullmatch(r"(\d+)\.(\d+)", v)
            if m:
                return int(m.group(1)), int(m.group(2))
            return None

        a = parse(v1)
        b = parse(v2)
        if a is None or b is None:
            return None
        maj1, min1 = a
        maj2, min2 = b
        return abs(abs(maj2 - maj1) * 100 + abs(min2 - min1))

    def _is_eol_by_n_versions(
        self, comp_ref: str, active_runtimes: set[str], lapse_threshold: int = 3
    ) -> None | bool:
        if "//" not in comp_ref:
            return None

        latest_branch = self._get_latest_runtime_version(comp_ref, active_runtimes)
        if latest_branch is None:
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

        offset: int | None = None

        if ref_id in (
            "org.freedesktop.Sdk",
            "org.freedesktop.Platform",
            "org.gnome.Sdk",
            "org.gnome.Platform",
        ):
            offset = self._parse_fdsdk_gnome_ver_offset(ref_branch, latest_branch)
        elif ref_id in ("org.kde.Sdk", "org.kde.Platform"):
            if ref_branch.startswith("5.15-"):
                ref_branch_s = ref_branch.split("-", 1)[-1]
                latest_branch_s = latest_branch.split("-", 1)[-1]
                offset = self._parse_fdsdk_gnome_ver_offset(ref_branch_s, latest_branch_s)
            elif ref_branch.startswith("6."):
                offset = self._parse_kde_ver_offset(ref_branch, latest_branch)

        if offset is None:
            return None

        return bool(offset >= lapse_threshold)

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
