import os
import subprocess
from typing import TypedDict, cast

from lxml import etree

from . import config


class SubprocessResult(TypedDict):
    stdout: str
    stderr: str
    returncode: int


def validate(path: str, *args: str) -> SubprocessResult:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")

    cmd = subprocess.run(
        ["appstreamcli", "validate", *args, path],
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
    if not os.path.isfile(path):
        raise FileNotFoundError(f"XML file not found: {path}")
    try:
        return etree.parse(path)
    except etree.XMLSyntaxError as e:
        raise RuntimeError(f"XML syntax error in {path}: {e}") from None


def xpath_list(path: str, query: str) -> list[str]:
    tree = parse_xml(path)
    return cast(list[str], tree.xpath(query))


def is_present(path: str, query: str) -> bool:
    return bool(xpath_list(path, query))


def component_type(path: str) -> str:
    types = xpath_list(path, "//component/@type")
    return types[0] if types else "generic"


def get_icon_filename(path: str) -> str | None:
    icons = xpath_list(path, "//icon[@type='cached']/text()")
    return icons[0] if icons else None


# Boolean returns


def is_categories_present(path: str) -> bool:
    return is_present(path, "//categories/category")


def is_developer_name_present(path: str) -> bool:
    return is_present(path, "//developer[@id]/name/text()") or is_present(
        path, "//developer_name/text()"
    )


def is_project_license_present(path: str) -> bool:
    return is_present(path, "//project_license/text()")


def has_icon_key(path: str) -> bool:
    return is_present(path, "//icon")


def icon_no_type(path: str) -> bool:
    return is_present(path, "//icon[not(@type)]")


def check_caption(path: str) -> bool:
    return not is_present(path, "//screenshot[not(caption/text()) or not(caption)]")


def all_release_has_timestamp(path: str) -> bool:
    return not is_present(path, "//releases/release[not(@timestamp)]")


def is_remote_icon_mirrored(path: str) -> bool:
    return all(
        icon.startswith(f"{config.FLATHUB_MEDIA_BASE_URL}/")
        for icon in xpath_list(path, "//icon[@type='remote']/text()")
    )


def is_valid_component_type(path: str) -> bool:
    return component_type(path) in config.FLATHUB_APPSTREAM_TYPES


# List returns


def components(path: str) -> list[str]:
    return xpath_list(path, "/components/component")


def metainfo_components(path: str) -> list[str]:
    return xpath_list(path, "/component")


def appstream_id(path: str) -> list[str]:
    return xpath_list(path, "//component/id/text()")


def get_launchable(path: str) -> list[str]:
    return xpath_list(path, "//launchable[@type='desktop-id']/text()")


def get_screenshot_images(path: str) -> list[str]:
    return xpath_list(path, "//screenshots/screenshot/image/text()")


def get_manifest_key(path: str) -> list[str]:
    return xpath_list(path, "//custom/value[@key='flathub::manifest']/text()") + xpath_list(
        path, "//metadata/value[@key='flathub::manifest']/text()"
    )
