import glob
import gzip
import os
import shutil
import struct
import subprocess
from typing import Any

from flatpak_builder_lint import checks, cli


def create_catalogue(test_dir: str, xml_fname: str) -> None:
    catalogue_path = os.path.join(test_dir, "files/share/app-info/xmls")
    os.makedirs(catalogue_path, exist_ok=True)
    source_xml = os.path.join(catalogue_path, xml_fname)
    target_gzip = os.path.join(catalogue_path, xml_fname + ".gz")

    with open(source_xml, "rb") as xml_file, gzip.open(target_gzip, "wb") as gzip_file:
        gzip_file.write(xml_file.read())


def create_catalogue_icon(
    test_dir: str,
    icon_fname: str,
    size: str = "128x128",
) -> None:
    icon_dir = os.path.join(test_dir, f"files/share/app-info/icons/flatpak/{size}")
    os.makedirs(icon_dir, exist_ok=True)
    with open(os.path.join(icon_dir, icon_fname), "w", encoding="utf-8"):
        pass


def create_app_icon(
    test_dir: str,
    icon_fname: str,
    size: str = "128x128",
    scalable: bool = False,
    hicolor: bool = True,
) -> None:
    if scalable:
        icon_dir = os.path.join(test_dir, "files/share/icons/hicolor/scalable/apps")
    if hicolor:
        icon_dir = os.path.join(test_dir, f"files/share/icons/hicolor/{size}/apps")

    os.makedirs(icon_dir, exist_ok=True)
    with open(os.path.join(icon_dir, icon_fname), "w", encoding="utf-8"):
        pass


def create_file(path: str, fname: str) -> None:
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, fname)
    if os.path.exists(file_path):
        return
    with open(file_path, "w", encoding="utf-8"):
        pass


def create_elf(test_dir: str, arch: str, fname: str = "test.elf") -> None:
    dest = os.path.join(test_dir, "files/bin")
    os.makedirs(dest, exist_ok=True)

    archmap = {
        "x86_64": 0x3E,
        "aarch64": 0xB7,
        "riscv64": 0xF3,
    }

    if arch not in archmap:
        raise ValueError(f"Unsupported architecture: {arch}")

    elf_header = struct.pack(
        "<4s5B7x2H5I6Q",
        b"\x7fELF",
        2,
        1,
        1,
        0,
        0,
        2,
        archmap[arch],
        1,
        0x400000,
        0x40,
        0,
        0,
        64,
        0,
        0,
        0,
        0,
        0,
    )

    with open(os.path.join(dest, fname), "wb") as f:
        f.write(elf_header)


def move_files(testdir: str) -> None:
    paths = {
        "desktopfiles_path": os.path.join(testdir, "files/share/applications"),
        "cataloguefiles_path": os.path.join(testdir, "files/share/app-info/xmls"),
        "metainfofiles_path": os.path.join(testdir, "files/share/metainfo"),
        "flathubjson_path": os.path.join(testdir, "files"),
    }

    for path in paths.values():
        os.makedirs(path, exist_ok=True)

    flathubjson = os.path.join(testdir, "flathub.json")
    if os.path.exists(flathubjson) and os.path.isfile(flathubjson):
        shutil.move(flathubjson, paths["flathubjson_path"])

    for file in glob.glob(os.path.join(testdir, "*.desktop")):
        shutil.move(file, paths["desktopfiles_path"])

    for file in glob.glob(os.path.join(testdir, "*.xml")):
        if file.endswith((".metainfo.xml", ".appdata.xml")):
            shutil.move(file, paths["metainfofiles_path"])
        else:
            shutil.move(file, paths["cataloguefiles_path"])


def create_git_repo(path: str) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/flathub-infra/flatpak-builder-lint.git",
        ],
        cwd=path,
        check=True,
    )


def set_git_remote_url(path: str, new_url: str) -> None:
    subprocess.run(["git", "remote", "remove", "origin"], cwd=path, check=False)
    subprocess.run(["git", "remote", "add", "origin", new_url], cwd=path, check=True)


def create_large_file(path: str, size_mb: int = 10) -> None:
    filepath = os.path.join(path, "file.txt")
    with open(filepath, "wb") as f:
        f.seek(size_mb * 1024 * 1024 - 1)
        f.write(b"\0")


def run_checks(
    path: str,
    check_type: str = "manifest",
    enable_exceptions: bool = False,
) -> dict[str, Any]:
    checks.Check.errors = set()
    checks.Check.warnings = set()
    checks.Check.jsonschema = set()
    checks.Check.appstream = set()
    checks.Check.desktopfile = set()
    checks.Check.info = set()
    checks.Check.repo_primary_refs = set()

    if check_type == "builddir":
        return cli.run_checks("builddir", path)

    return cli.run_checks("manifest", path, enable_exceptions)
