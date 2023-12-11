import os
import subprocess

from lxml import etree  # type: ignore


def validate(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")
    cmd = subprocess.run(
        ["appstream-util", "validate", "--nonet", path],
        capture_output=True,
    )

    ret = {
        "stdout": cmd.stdout.decode("utf-8"),
        "stderr": cmd.stderr.decode("utf-8"),
        "returncode": cmd.returncode,
    }

    return ret


def parse_appinfo_xml(path: str) -> list:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream app-info file not found")

    root = etree.parse(path)
    components = root.xpath("/components/component")

    return list(components)


def is_developer_name_present(path: str) -> bool:
    developer = parse_appinfo_xml(path)[0].xpath("developer_name")

    return bool(developer)


def component_type(path: str) -> str:
    type = parse_appinfo_xml(path)[0].attrib.get("type")

    return str(type)


def is_console(path: str) -> bool:
    if component_type(path) == "console-application":
        return True
    return False
