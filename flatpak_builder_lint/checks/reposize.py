import os

from .. import config
from . import Check


class RepoSizeCheck(Check):
    @staticmethod
    def get_dir_size(path: str) -> int:
        size = 0
        for dirpath, _, filenames in os.walk(path, onerror=lambda _: None):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        size += os.path.getsize(fp)
                except (FileNotFoundError, PermissionError):
                    continue
        return size

    def _validate(self, path: str, primary_ref_count: int = 1) -> None:
        BASE = 12 * 1024 * 1024 * 1024
        MAX = BASE * primary_ref_count if primary_ref_count > 1 else BASE

        repo_size = self.get_dir_size(path)

        if (
            config.is_flathub_build_pipeline() or config.is_flatmgr_pipeline()
        ) and repo_size >= MAX:
            size_gb = repo_size / (1024**3)
            max_gb = MAX / (1024**3)
            self.errors.add("flatpak-repo-too-large")
            self.info.add(
                f"flatpak-repo-too-large: Flatpak repo size is {size_gb:.2f} GB"
                + f" exceeds limit of {max_gb:.2f} GB"
            )

    def check_repo(self, path: str) -> None:
        self._populate_refs(path)
        primary_ref_count = len(self.repo_primary_refs)
        self._validate(path, primary_ref_count)
