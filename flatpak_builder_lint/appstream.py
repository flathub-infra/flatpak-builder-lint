import os
import subprocess

from lxml import etree  # type: ignore


def validate(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")
    cmd = subprocess.run(
        ["appstream-util", "validate", path],
        capture_output=True,
    )

    ret = {
        "stdout": cmd.stdout.decode("utf-8"),
        "stderr": cmd.stderr.decode("utf-8"),
        "returncode": cmd.returncode,
    }

    return ret


def is_developer_name_present(path: str) -> bool:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")

    root = etree.parse(path)
    components = root.xpath("/components/component")

    developer = components[0].xpath("developer_name")

    return bool(developer)
