import subprocess as sp
from typing import Any

from flatpak_builder_lint import gitutils


class TestIsGitDirectory:
    def test_nonexistent_path_returns_false(self, tmp_path: Any) -> None:
        gitutils.is_git_directory.cache_clear()
        assert gitutils.is_git_directory(str(tmp_path / "nonexistent")) is False

    def test_non_git_dir_returns_false(self, tmp_path: Any) -> None:
        gitutils.is_git_directory.cache_clear()
        assert gitutils.is_git_directory(str(tmp_path)) is False

    def test_git_dir_returns_true(self, tmp_path: Any) -> None:
        gitutils.is_git_directory.cache_clear()
        sp.run(
            ["git", "init"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        assert gitutils.is_git_directory(str(tmp_path)) is True

        gitutils.is_git_directory.cache_clear()


class TestGetRepoTreeSize:
    def test_non_git_returns_zero(self, tmp_path: Any) -> None:
        gitutils.get_repo_tree_size.cache_clear()

        assert gitutils.get_repo_tree_size(str(tmp_path)) == 0

        gitutils.get_repo_tree_size.cache_clear()
