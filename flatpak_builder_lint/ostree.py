import errno
import os
import subprocess
from typing import Optional, TypedDict

from .builddir import parse_metadata


class CliResult(TypedDict):
    stdout: str
    stderr: str
    returncode: int


def cli(repo: str, *args: str) -> CliResult:
    if not os.path.exists(repo):
        raise OSError(errno.ENOENT)

    ret = subprocess.run(
        ["ostree", f"--repo={repo}", *args],
        capture_output=True,
    )

    return {
        "stdout": ret.stdout.decode("utf-8"),
        "stderr": ret.stderr.decode("utf-8"),
        "returncode": ret.returncode,
    }


def get_primary_ref(repo: str) -> Optional[str]:
    refs_cmd = cli(repo, "refs", "--list")
    if refs_cmd["returncode"] != 0:
        raise RuntimeError("Failed to list refs")

    refs = refs_cmd["stdout"].splitlines()

    for ref in refs:
        if ref.startswith("app/"):
            return ref

    return None


def get_text_file(repo: str, ref: str, path: str) -> Optional[str]:
    cmd = cli(repo, "cat", ref, path)
    if cmd["returncode"] == 0:
        return cmd["stdout"]

    return None


def get_metadata(repo: str) -> Optional[dict]:
    ref = get_primary_ref(repo)
    if not ref:
        return None

    cat_metadata_cmd = cli(repo, "cat", ref, "/metadata")
    if cat_metadata_cmd["returncode"] == 0:
        metadata = parse_metadata(cat_metadata_cmd["stdout"])
        return metadata

    return None


def infer_appid(path: str) -> Optional[str]:
    metadata = get_metadata(path)
    if metadata:
        return metadata.get("name")

    return None
