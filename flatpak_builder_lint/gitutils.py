import os
import re
import subprocess


def is_git_directory(path: str) -> bool:
    if not os.path.exists(path):
        return False
    return (
        subprocess.run(
            ["git", "rev-parse"],
            cwd=path,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


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

    return result.stdout.strip() if result.returncode == 0 else None


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

    return namespace


def get_repo_tree_size(path: str) -> int:
    if not is_git_directory(path):
        return 0

    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "-l", "HEAD"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        total = 0
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[-2].isdigit():
                total += int(parts[-2])
        return total
    except subprocess.CalledProcessError:
        return 0
