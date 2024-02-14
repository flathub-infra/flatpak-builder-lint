import os
import subprocess
from typing import Optional

from lxml import etree

# for mypy
Element = etree._Element
ElementTree = etree._ElementTree


def validate(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")

    overrides = {
        "all-categories-ignored": "error",
        "category-invalid": "error",
        "cid-desktopapp-is-not-rdns": "error",
        "cid-has-number-prefix": "error",
        "cid-maybe-not-rdns": "error",
        "cid-missing-affiliation-gnome": "error",
        "cid-rdns-contains-hyphen": "error",
        "content-rating-missing": "error",
        "desktop-app-launchable-omitted": "error",
        "desktop-file-not-found": "error",
        "developer-id-missing": "error",
        "invalid-child-tag-name": "error",
        "metainfo-filename-cid-mismatch": "error",
        "metainfo-legacy-path": "error",
        "metainfo-multiple-components": "error",
        "name-has-dot-suffix": "error",
        "releases-info-missing": "error",
        "spdx-license-unknown": "error",
        "unknown-tag": "error",
    }

    overrides_value = ",".join([f"{k}={v}" for k, v in overrides.items()])

    cmd = subprocess.run(
        ["appstreamcli", "validate", "--no-net", f"--override={overrides_value}", path],
        capture_output=True,
    )

    ret = {
        "stdout": cmd.stdout.decode("utf-8"),
        "stderr": cmd.stderr.decode("utf-8"),
        "returncode": cmd.returncode,
    }

    return ret


def parse_xml(path: str) -> ElementTree:
    return etree.parse(path)


def components(path: str) -> list:
    components = parse_xml(path).xpath("/components/component")
    return list(components)


def is_developer_name_present(path: str) -> bool:
    developer = components(path)[0].xpath("developer_name")
    return bool(developer)


def is_project_license_present(path: str) -> bool:
    plicense = components(path)[0].xpath("project_license")
    return bool(plicense)


def component_type(path: str) -> str:
    return str(components(path)[0].attrib.get("type"))


def is_valid_component_type(path: str) -> bool:
    if component_type(path) in (
        "addon",
        "console-application",
        "desktop",
        "desktop-application",
        "runtime",
    ):
        return True
    return False


def name(path: str) -> Optional[str]:
    for name in parse_xml(path).findall("component/name"):
        if not name.attrib.get(r"{http://www.w3.org/XML/1998/namespace}lang"):
            return str(name.text)
    return None


def summary(path: str) -> Optional[str]:
    for summary in parse_xml(path).findall("component/summary"):
        if not summary.attrib.get(r"{http://www.w3.org/XML/1998/namespace}lang"):
            return str(summary.text)
    return None


def check_caption(path: str) -> bool:
    exp = "//screenshot[not(caption/text()) or not(caption)]"
    return not any(e is not None for e in parse_xml(path).xpath(exp))


def has_manifest_key(path: str) -> bool:
    metadata = parse_xml(path).xpath("/components/component/metadata")
    for key in metadata:
        if key.attrib.get("key") == "flathub::manifest":
            return True
    return False
