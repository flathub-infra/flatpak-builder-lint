import os
import subprocess
from typing import List, Optional, TypedDict, cast

from lxml import etree


class SubprocessResult(TypedDict):
    stdout: str
    stderr: str
    returncode: int


def validate(path: str, *args: str) -> SubprocessResult:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")

    overrides = {
        "all-categories-ignored": "error",
        "category-invalid": "error",
        "cid-desktopapp-is-not-rdns": "error",
        "cid-domain-not-lowercase": "info",
        "cid-has-number-prefix": "error",
        "cid-missing-affiliation-gnome": "error",
        "cid-rdns-contains-hyphen": "error",
        "component-name-too-long": "info",
        "content-rating-missing": "error",
        "description-has-plaintext-url": "info",
        "desktop-app-launchable-omitted": "error",
        "desktop-file-not-found": "error",
        "developer-id-invalid": "info",
        "developer-id-missing": "error",
        "invalid-child-tag-name": "error",
        "metainfo-filename-cid-mismatch": "error",
        "metainfo-legacy-path": "error",
        "metainfo-multiple-components": "error",
        "name-has-dot-suffix": "error",
        "releases-info-missing": "error",
        "summary-too-long": "info",
        "unknown-tag": "error",
    }

    overrides_value = ",".join([f"{k}={v}" for k, v in overrides.items()])

    cmd = subprocess.run(
        ["appstreamcli", "validate", f"--override={overrides_value}", *args, path],
        capture_output=True,
        check=False,
    )

    ret: SubprocessResult = {
        "stdout": cmd.stdout.decode("utf-8"),
        "stderr": cmd.stderr.decode("utf-8"),
        "returncode": cmd.returncode,
    }

    return ret


def parse_xml(path: str) -> etree._ElementTree:
    return etree.parse(path)


def components(path: str) -> List[etree._Element]:
    return cast(List[etree._Element], parse_xml(path).xpath("/components/component"))


def metainfo_components(path: str) -> List[etree._Element]:
    return cast(List[etree._Element], parse_xml(path).xpath("/component"))


def appstream_id(path: str) -> Optional[str]:
    aps_cid = components(path)[0].xpath("id/text()")[0]
    return str(aps_cid)


def get_launchable(path: str) -> List[str]:
    launchable = components(path)[0].xpath("launchable[@type='desktop-id']/text()")
    return list(launchable)


def is_categories_present(path: str) -> bool:
    categories = components(path)[0].xpath("categories")
    return bool(categories)


def is_developer_name_present(path: str) -> bool:
    developer_name = components(path)[0].xpath("developer/name")
    legacy_developer_name = components(path)[0].xpath("developer_name")
    return bool(developer_name or legacy_developer_name)


def is_project_license_present(path: str) -> bool:
    plicense = components(path)[0].xpath("project_license")
    return bool(plicense)


def metainfo_is_screenshot_image_present(path: str) -> bool:
    img = metainfo_components(path)[0].xpath("screenshots/screenshot/image/text()")
    return bool(img)


def component_type(path: str) -> str:
    return str(components(path)[0].attrib.get("type"))


def is_valid_component_type(path: str) -> bool:
    return bool(
        component_type(path)
        in (
            "addon",
            "console-application",
            "desktop",
            "desktop-application",
            "runtime",
        )
    )


def check_caption(path: str) -> bool:
    exp = "//screenshot[not(caption/text()) or not(caption)]"
    return not any(e is not None for e in parse_xml(path).xpath(exp))


def has_manifest_key(path: str) -> bool:
    custom = parse_xml(path).xpath("//custom/value[@key='flathub::manifest']/text()")
    metadata = parse_xml(path).xpath("//metadata/value[@key='flathub::manifest']/text()")
    return bool(custom or metadata)


def has_icon_key(path: str) -> bool:
    return bool(components(path)[0].xpath("icon"))


def icon_no_type(path: str) -> bool:
    icon_types = {icon.attrib.get("type") for icon in components(path)[0].xpath("icon")}
    return None in icon_types


def is_remote_icon_mirrored(path: str) -> bool:
    remote_icons = parse_xml(path).xpath("//icon[@type='remote']/text()")
    return all(icon.startswith("https://dl.flathub.org/media/") for icon in remote_icons)


def get_icon_filename(path: str) -> Optional[str]:
    if icons := parse_xml(path).xpath("/components/component[1]/icon[@type='cached']"):
        return str(icons[0].text)
    return None
