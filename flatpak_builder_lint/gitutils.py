import logging
import os
import re
import subprocess
from functools import cache

logger = logging.getLogger(__name__)


@cache
def is_git_directory(path: str) -> bool:
    if not os.path.exists(path):
        logger.debug("Failed to determine git directory as path does not exist: %s", path)
        return False

    result = subprocess.run(
        ["git", "rev-parse"], cwd=path, capture_output=True, text=True, check=False
    )

    if result.returncode != 0:
        logger.debug(
            "Failed to determine git directory as git rev-parse failed with %s: %s",
            result.returncode,
            result.stderr.strip(),
        )

    return result.returncode == 0


@cache
def get_git_toplevel(path: str) -> str | None:
    if not is_git_directory(path):
        return None

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.debug(
            "Failed to get git toplevel with %s: %s", result.returncode, result.stderr.strip()
        )
        return None

    return result.stdout.strip()


@cache
def get_github_repo_namespace(path: str) -> str | None:
    namespace = None

    if not is_git_directory(path):
        return None

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.debug(
            "Failed to get git remote URL with %s: %s", result.returncode, result.stderr.strip()
        )
        return None

    remote_url = result.stdout.strip()

    https_pattern = r"https://github\.com/([^/]+/[^/.]+)"
    ssh_pattern = r"git@github\.com:([^/]+/[^.]+)"

    https_match = re.search(https_pattern, remote_url)
    ssh_match = re.search(ssh_pattern, remote_url)

    if https_match and "/" in https_match.group(1):
        namespace = https_match.group(1).split("/")[0]
    elif ssh_match and "/" in ssh_match.group(1):
        namespace = ssh_match.group(1).split("/")[0]

    if namespace is None:
        logger.debug("Failed to parse GitHub namespace from remote URL: %s", remote_url)
    else:
        logger.debug("GitHub namespace for remote %s is %s", remote_url, namespace)

    return namespace


@cache
def get_repo_tree_size(path: str) -> int:
    if not is_git_directory(path):
        return 0

    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "-l", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        total = 0
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[-2].isdigit():
                total += int(parts[-2])

        logger.debug("Git repo tree size for %s: %s bytes", path, total)
        return total
    except subprocess.CalledProcessError as e:
        logger.debug(
            "Failed to get git repo tree size with %s: %s",
            e.returncode,
            e.stderr.strip(),
        )
        return 0
