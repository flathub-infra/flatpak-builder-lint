from unittest.mock import patch

from flatpak_builder_lint import checks
from flatpak_builder_lint.checks.reposize import RepoSizeCheck


def reset_check_state() -> None:
    checks.Check.errors = set()
    checks.Check.info = set()


def test_repo_too_large_triggers_error() -> None:
    reset_check_state()

    check: RepoSizeCheck = RepoSizeCheck()

    with (
        patch.object(RepoSizeCheck, "get_dir_size", return_value=13 * 1024**3),
        patch("flatpak_builder_lint.checks.reposize.config.is_flathub_pipeline", return_value=True),
    ):
        check._validate("/fake/repo", primary_ref_count=1)

    assert "flatpak-repo-too-large" in check.errors


def test_repo_small_does_not_trigger_error() -> None:
    reset_check_state()

    check: RepoSizeCheck = RepoSizeCheck()

    with (
        patch.object(RepoSizeCheck, "get_dir_size", return_value=100 * 1024**2),
        patch("flatpak_builder_lint.checks.reposize.config.is_flathub_pipeline", return_value=True),
    ):
        check._validate("/fake/repo", primary_ref_count=1)

    assert "flatpak-repo-too-large" not in check.errors
