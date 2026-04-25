import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _pytest.config import Config

pytestmark = pytest.mark.integration


ARCH = subprocess.check_output(["flatpak", "--default-arch"], text=True).strip()
SOURCE_DIR = Path(__file__).parent.parent


def _find_builder() -> str | None:
    for branch in ("localtest", "master", "stable"):
        ref = f"org.flatpak.Builder//{branch}"
        result = subprocess.run(["flatpak", "info", ref], capture_output=True, check=False)
        if result.returncode == 0:
            return ref
    return None


BUILDER = _find_builder()
LINT = (
    [
        "flatpak",
        "run",
        "--filesystem=/tmp",
        "--env=FLATPAK_BUILDER_LINT=skip-eol-runtime-checks",
        "--command=flatpak-builder-lint",
        BUILDER,
    ]
    if BUILDER
    else []
)
FB = ["flatpak", "run", "--filesystem=/tmp", BUILDER] if BUILDER else []


def _build(
    manifest: str,
    repo: str,
    builddir: str,
    *,
    extra_args: list[str] | None = None,
    mirror_screenshots: bool = False,
    cwd: str | None = None,
) -> None:
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    cmd = [
        *(["dbus-run-session"] if in_ci else []),
        *FB,
        "--verbose",
        "--user",
        "--force-clean",
        f"--arch={ARCH}",
        f"--repo={repo}",
        f"--state-dir={cwd}/state",
        "--install-deps-from=flathub",
        "--ccache",
    ]
    if mirror_screenshots:
        cmd += [
            "--mirror-screenshots-url=https://dl.flathub.org/media",
            "--compose-url-policy=full",
        ]
    if extra_args:
        cmd += extra_args
    cmd += [builddir, manifest]
    subprocess.run(cmd, check=True, cwd=cwd)


def _lint(
    kind: str,
    path: str,
    *,
    exceptions: bool = False,
    ref: str | None = None,
    cwd: str | None = None,
) -> Any:
    cmd = [*LINT]
    if exceptions:
        cmd.append("--exceptions")
    if ref:
        cmd += ["--ref", ref]
    cmd += [kind, path]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)


def _lint_ok(kind: str, path: str, **kwargs: Any) -> None:
    result = _lint(kind, path, **kwargs)
    assert result.returncode == 0, f"lint {kind} {path} failed:\n{result.stdout}\n{result.stderr}"


def _lint_fail(kind: str, path: str, expected_error: str, **kwargs: Any) -> None:
    result = _lint(kind, path, **kwargs)
    assert expected_error in result.stdout or expected_error in result.stderr, (
        f"Expected {expected_error!r} in lint output for {kind} {path}:\n"
        f"{result.stdout}\n{result.stderr}"
    )


@pytest.fixture(scope="session")
def flatpak_builder_installed() -> None:
    if BUILDER is None:
        pytest.skip("org.flatpak.Builder not installed in any branch (localtest, master, stable)")


@pytest.fixture()
def workdir(tmp_path: Path, pytestconfig: Config) -> Path:
    repo_root = Path(pytestconfig.rootpath)

    shutil.copytree(
        repo_root / "tests" / "repo" / "min_success_metadata",
        tmp_path / "tests" / "repo" / "min_success_metadata",
    )

    return Path(tmp_path)


@pytest.mark.usefixtures("flatpak_builder_installed")
class TestGuiApp:
    BASE = "tests/repo/min_success_metadata/gui-app"
    MANIFEST = "org.flathub.gui.yaml"

    def test_manifest_lint(self) -> None:
        _lint_ok("manifest", f"{self.BASE}/{self.MANIFEST}", exceptions=True)

    def test_builddir_and_repo(self, workdir: Path) -> None:
        manifest = str(workdir / self.BASE / self.MANIFEST)
        _build(manifest, "repo", "builddir", mirror_screenshots=True, cwd=str(workdir))
        media = workdir / "builddir" / "files" / "share" / "app-info" / "media"
        media.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ostree",
                "commit",
                "--repo=repo",
                "--canonical-permissions",
                f"--branch=screenshots/{ARCH}",
                str(media),
            ],
            check=True,
            cwd=str(workdir),
        )
        _lint_ok("builddir", "builddir", exceptions=True, cwd=str(workdir))
        _lint_ok("repo", "repo", exceptions=True, cwd=str(workdir))


@pytest.mark.usefixtures("flatpak_builder_installed")
class TestConsoleApp:
    BASE = "tests/repo/min_success_metadata/console-app"
    MANIFEST = "org.flathub.cli.yaml"
    METAINFO = "org.flathub.cli.metainfo.xml"

    def test_manifest_lint(self) -> None:
        _lint_ok("manifest", f"{self.BASE}/{self.MANIFEST}", exceptions=True)

    def test_appstream_lint(self) -> None:
        _lint_ok("appstream", f"{self.BASE}/{self.METAINFO}")

    def test_builddir_and_repo(self, workdir: Path) -> None:
        manifest = str(workdir / self.BASE / self.MANIFEST)
        _build(manifest, "repo", "builddir", cwd=str(workdir))
        _lint_ok("builddir", "builddir", exceptions=True, cwd=str(workdir))
        _lint_ok("repo", "repo", exceptions=True, cwd=str(workdir))


@pytest.mark.usefixtures("flatpak_builder_installed")
class TestBaseApp:
    BASE = "tests/repo/min_success_metadata/baseapp"
    MANIFEST = "org.flathub.BaseApp.yaml"

    def test_manifest_lint(self) -> None:
        _lint_ok("manifest", f"{self.BASE}/{self.MANIFEST}", exceptions=True)

    def test_builddir_and_repo(self, workdir: Path) -> None:
        manifest = str(workdir / self.BASE / self.MANIFEST)
        _build(manifest, "repo", "builddir", cwd=str(workdir))
        _lint_ok("builddir", "builddir", exceptions=True, cwd=str(workdir))
        _lint_ok("repo", "repo", exceptions=True, cwd=str(workdir))


@pytest.mark.usefixtures("flatpak_builder_installed")
class TestExtension:
    BASE = "tests/repo/min_success_metadata/extension"
    MANIFEST = "org.freedesktop.Sdk.Extension.flathub.yaml"

    def test_manifest_lint(self) -> None:
        _lint_ok("manifest", f"{self.BASE}/{self.MANIFEST}", exceptions=True)

    def test_builddir_and_repo(self, workdir: Path) -> None:
        manifest = str(workdir / self.BASE / self.MANIFEST)
        _build(manifest, "repo", "builddir", cwd=str(workdir))
        _lint_ok("builddir", "builddir", exceptions=True, cwd=str(workdir))
        _lint_ok("repo", "repo", exceptions=True, cwd=str(workdir))


@pytest.mark.usefixtures("flatpak_builder_installed")
class TestRefOverride:
    BASE = "tests/repo/min_success_metadata/gui-app"
    MANIFEST = "org.flathub.gui.yaml"

    def test_ref_override_selects_correct_ref(self, workdir: Path) -> None:
        src = workdir / self.BASE
        manifest = str(src / self.MANIFEST)

        _build(manifest, "repo", "builddir", mirror_screenshots=True, cwd=str(workdir))

        for ext in ("metainfo.xml", "yaml", "desktop"):
            path = src / f"org.flathub.gui.{ext}"
            path.write_text(path.read_text().replace("org.flathub.gui", "com.foo.bar"))

        bar_desktop = src / "com.foo.bar.desktop"
        shutil.copy(src / "org.flathub.gui.desktop", bar_desktop)
        bar_desktop.write_text(
            "\n".join(
                line
                for line in bar_desktop.read_text().splitlines()
                if not line.startswith("Exec=")
            )
            + "\n"
        )

        shutil.copy(src / "org.flathub.gui.metainfo.xml", src / "com.foo.bar.metainfo.xml")
        shutil.copy(src / "org.flathub.gui.png", src / "com.foo.bar.png")

        _build(manifest, "repo", "builddir2", mirror_screenshots=True, cwd=str(workdir))

        media = workdir / "builddir" / "files" / "share" / "app-info" / "media"
        media.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ostree",
                "commit",
                "--repo=repo",
                "--canonical-permissions",
                f"--branch=screenshots/{ARCH}",
                str(media),
            ],
            check=True,
            cwd=str(workdir),
        )

        _lint_ok(
            "repo",
            "repo",
            exceptions=True,
            ref=f"app/org.flathub.gui/{ARCH}/master",
            cwd=str(workdir),
        )
        _lint_fail(
            "repo",
            "repo",
            "desktop-file-exec-key-absent",
            exceptions=True,
            cwd=str(workdir),
        )
