import logging
import os
from functools import cache
from importlib.resources import files
from typing import Any

import gi
import requests
from publicsuffixlist import PublicSuffixList  # type: ignore[import-untyped]
from requests_cache import CachedSession

from . import config, staticfiles

gi.require_version("OSTree", "1.0")
from gi.repository import GLib, OSTree  # noqa: E402

logger = logging.getLogger(__name__)

CODE_HOSTS = (
    "io.github.",
    "io.frama.",
    "io.gitlab.",
    "page.codeberg.",
    "io.sourceforge.",
    "net.sourceforge.",
    "org.gnome.gitlab.",
    "org.freedesktop.gitlab.",
    "site.srht.",
)

REQUEST_TIMEOUT = (10, 60)


CACHEFILE = os.path.join(config.CACHEDIR, "requests_cache")

os.makedirs(config.CACHEDIR, exist_ok=True)

session = CachedSession(CACHEFILE, backend="sqlite", expire_after=3600)


def ignore_ref(ref: str) -> bool:
    parts = ref.split("/")
    return (
        len(parts) != 4
        or parts[2] not in config.FLATHUB_SUPPORTED_ARCHES
        or parts[1].endswith(config.IGNORE_REF_SUFFIXES)
    )


@cache
def fetch_summary_bytes(url: str) -> bytes:
    try:
        r = session.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200 and r.headers.get("Content-Type") == "application/octet-stream":
            return r.content
        logger.debug(
            "Failed to fetch summary from %s. Status: %s, Content-Type: %s",
            url,
            r.status_code,
            r.headers.get("Content-Type"),
        )
    except requests.exceptions.RequestException as e:
        logger.debug("Request exception when fetching %s: %s: %s", url, type(e).__name__, e)

    if url.startswith(config.FLATHUB_BETA_REPO_URL):
        local_summary_file = "flathub-beta.summary"
    else:
        local_summary_file = "flathub-stable.summary"

    try:
        resource_path = files(staticfiles).joinpath(local_summary_file)
        if resource_path.is_file():
            with resource_path.open("rb") as f:
                return f.read()
    except (OSError, FileNotFoundError) as e:
        logger.debug("Exception loading local summary file: %s: %s", type(e).__name__, e)

    raise Exception("Failed to load fallback local summary file")


@cache
def get_summary_obj(
    url: str,
) -> tuple[list[tuple[str, tuple[int, list[int], dict[str, str | int]]]], dict[str, Any]]:
    summary = GLib.Bytes.new(fetch_summary_bytes(url))
    refs, metadata = GLib.Variant.new_from_bytes(
        GLib.VariantType.new(OSTree.SUMMARY_GVARIANT_STRING), summary, True
    ).unpack()

    return refs, metadata


@cache
def get_refs_from_summary(url: str) -> set[str]:
    refs, _ = get_summary_obj(url)
    return {ref for ref, _ in (refs or []) if not ignore_ref(ref)}


@cache
def get_appids_from_summary(url: str) -> set[str]:
    return {ref.split("/")[1] for ref in get_refs_from_summary(url) if ref.startswith("app/")}


@cache
def get_all_apps_on_flathub() -> set[str]:
    return get_appids_from_summary(
        f"{config.FLATHUB_STABLE_REPO_URL}/summary"
    ) | get_appids_from_summary(f"{config.FLATHUB_BETA_REPO_URL}/summary")


@cache
def get_all_runtimes(url: str) -> set[str]:
    runtimes: set[str] = set()

    for ref in get_refs_from_summary(url):
        parts = ref.split("/")
        if len(parts) < 4:
            continue

        ref_type, ref_id, _, branch = parts

        if (
            ref_type == "runtime"
            and ref_id.startswith(config.FLATHUB_RUNTIME_PREFIXES)
            and ref_id.endswith(config.FLATHUB_RUNTIME_SUFFIXES)
            and not ref_id.endswith(config.IGNORE_REF_SUFFIXES)
        ):
            runtimes.add(f"{ref_id}//{branch}")

    return runtimes


@cache
def get_eol_runtimes(url: str) -> set[str]:
    eols = set()

    _, metadata = get_summary_obj(url)

    for ref, eol_dict in metadata["xa.sparse-cache"].items():
        parts = ref.split("/")
        if len(parts) < 4:
            continue

        ref_type, ref_id, _, branch = parts

        if (
            ref_type == "runtime"
            and ref_id.startswith(config.FLATHUB_RUNTIME_PREFIXES)
            and ref_id.endswith(config.FLATHUB_RUNTIME_SUFFIXES)
            and not ref_id.endswith(config.IGNORE_REF_SUFFIXES)
            and any(key in eol_dict for key in ("eolr", "eol"))
        ):
            eols.add(f"{ref_id}//{branch}")

    extra = (
        "org.gnome.Platform//3.38",
        "org.gnome.Sdk//3.38",
        "org.kde.Sdk//5.14",
        "org.kde.Platform//5.14",
    )

    eols.update(extra)

    return eols


def get_all_runtimes_on_flathub() -> set[str]:
    return get_all_runtimes(f"{config.FLATHUB_STABLE_REPO_URL}/summary")


def get_eol_runtimes_on_flathub() -> set[str]:
    return get_eol_runtimes(f"{config.FLATHUB_STABLE_REPO_URL}/summary")


def get_active_runtimes_on_flathub() -> set[str]:
    return get_all_runtimes_on_flathub() - get_eol_runtimes_on_flathub()


@cache
def check_url(url: str, strict: bool = False) -> tuple[bool, str | None]:
    if not url.startswith(("https://", "http://")):
        raise Exception("Invalid input")

    resp_info = None
    try:
        with requests.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT, stream=True) as r:
            ok = r.status_code == 200 if strict else r.ok
            if ok:
                return True, None
            try:
                chunk = next(r.iter_content(512))
                body = chunk.decode(errors="replace").replace("\n", " ").strip()
            except StopIteration:
                body = ""

            resp_info = " | ".join(
                [
                    f"Status: {r.status_code}",
                    f"Headers: {dict(r.headers)}",
                    f"Body: {body}",
                ]
            )
            return False, resp_info
    except requests.exceptions.RequestException as e:
        logger.debug("Request exception when fetching %s: %s: %s", url, type(e).__name__, e)
        return False, None


@cache
def get_remote_exceptions(appid: str) -> set[str]:
    try:
        # exception updates should be reflected immediately
        r = requests.get(
            f"{config.FLATHUB_API_URL}/exceptions/{appid}",
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200 and r.headers.get("Content-Type") == "application/json":
            return set(r.json())
    except requests.exceptions.RequestException as e:
        logger.debug(
            "Request exception when fetching exceptions for %s: %s: %s", appid, type(e).__name__, e
        )

    return set()


def demangle_leading_underscore(name: str) -> str:
    if name[:1] == "_" and name[1:2].isdigit():
        return name[1:]
    return name


def demangle(name: str) -> str:
    name = demangle_leading_underscore(name)
    return name.replace("_", "-")


def get_proj_url(appid: str) -> str | None:
    if not (appid.startswith(CODE_HOSTS) or appid.count(".") >= 2):
        raise Exception("Invalid input")

    url = None

    if appid.startswith(("io.sourceforge.", "net.sourceforge.")):
        second_cpt = demangle(appid.split(".")[2])
        # needs root path "/" otherwise HTTP 302
        # not case-sensitive
        url = f"sourceforge.net/projects/{second_cpt}/".lower()

    if appid.startswith("site.srht."):
        second_cpt = demangle(appid.split(".")[2])
        if appid.count(".") == 3:
            third_cpt = demangle_leading_underscore(appid.split(".")[3])
            # needs root path "/" otherwise HTTP 308
            url = f"sr.ht/~{second_cpt}/{third_cpt}/"
        else:
            third_cpt = demangle(appid.split(".")[3])
            url = f"sr.ht/~{second_cpt}/{third_cpt}/"

    # not case-sensitive -> lower
    elif appid.startswith("io.github."):
        second_cpt = demangle(appid.split(".")[2])
        if appid.count(".") == 3:
            third_cpt = demangle_leading_underscore(appid.split(".")[3])
            url = f"github.com/{second_cpt}/{third_cpt}".lower()
        else:
            third_cpt = demangle(appid.split(".")[3])
            url = f"github.com/{second_cpt}/{third_cpt}".lower()

    # not case-sensitive -> lower
    elif appid.startswith("page.codeberg."):
        second_cpt = demangle(appid.split(".")[2])
        if appid.count(".") == 3:
            third_cpt = demangle_leading_underscore(appid.split(".")[3])
            url = f"codeberg.org/{second_cpt}/{third_cpt}".lower()
        else:
            third_cpt = demangle(appid.split(".")[3])
            url = f"codeberg.org/{second_cpt}/{third_cpt}".lower()

    # Gitlab is case-sensitive, so no lower()
    # gitlab.gnome.org/world is a 302, World is 200
    elif appid.startswith(("io.gitlab.", "io.frama.")):
        second_cpt = demangle(appid.split(".")[2])
        if appid.startswith("io.gitlab."):
            if appid.count(".") == 3:
                third_cpt = demangle_leading_underscore(appid.split(".")[3])
                url = f"gitlab.com/{second_cpt}/{third_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][2:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"gitlab.com/{proj}"

        if appid.startswith("io.frama."):
            if appid.count(".") == 3:
                third_cpt = demangle_leading_underscore(appid.split(".")[3])
                url = f"framagit.org/{second_cpt}/{third_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][2:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"framagit.org/{proj}"

    elif appid.startswith(("org.gnome.gitlab.", "org.freedesktop.gitlab.")):
        third_cpt = demangle(appid.split(".")[3])
        if appid.startswith("org.gnome.gitlab."):
            if appid.count(".") == 4:
                fourth_cpt = demangle_leading_underscore(appid.split(".")[4])
                url = f"gitlab.gnome.org/{third_cpt}/{fourth_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][3:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"gitlab.gnome.org/{proj}"

        if appid.startswith("org.freedesktop.gitlab."):
            if appid.count(".") == 4:
                fourth_cpt = demangle_leading_underscore(appid.split(".")[4])
                url = f"gitlab.freedesktop.org/{third_cpt}/{fourth_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][3:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"gitlab.freedesktop.org/{proj}"

    return url


def get_domain(appid: str) -> str | None:
    if not (appid.startswith(CODE_HOSTS) or appid.count(".") >= 2):
        raise Exception("Invalid input")

    domain = None
    if appid.startswith("org.gnome.") and not appid.startswith("org.gnome.gitlab."):
        domain = "gnome.org"
    elif appid.startswith("org.kde."):
        domain = "kde.org"
    elif appid.startswith("org.freedesktop.") and not appid.startswith("org.freedesktop.gitlab."):
        domain = "freedesktop.org"
    else:
        fqdn = ".".join(reversed(appid.split("."))).lower()
        psl = PublicSuffixList()
        if psl.is_private(fqdn):
            domain = demangle(psl.privatesuffix(fqdn))
        else:
            domain = ".".join(reversed([demangle(i) for i in appid.split(".")[:-1]])).lower()

    return domain


@cache
def is_app_on_flathub_api(appid: str) -> bool:
    ok, _ = check_url(f"{config.FLATHUB_API_URL}/summary/{appid}", strict=True)
    return ok


@cache
def is_app_on_flathub_summary(appid: str) -> bool:
    return bool(appid in get_all_apps_on_flathub())
