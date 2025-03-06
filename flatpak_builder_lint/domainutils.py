import os
from functools import cache

import gi
import requests
from requests_cache import CachedSession

from . import config

gi.require_version("OSTree", "1.0")
from gi.repository import GLib, OSTree  # noqa: E402

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

REQUEST_TIMEOUT = (120.05, 10800)


CACHEFILE = os.path.join(config.CACHEDIR, "requests_cache")

os.makedirs(config.CACHEDIR, exist_ok=True)

session = CachedSession(CACHEFILE, backend="sqlite", expire_after=3600)


def ignore_ref(ref: str) -> bool:
    parts = ref.split("/")
    return (
        len(parts) != 4
        or parts[2] not in config.FLATHUB_SUPPORTED_ARCHES
        or parts[1].endswith((".Debug", ".Locale", ".Sources"))
        or parts[0] != "app"
    )


@cache
def fetch_summary_bytes(url: str) -> bytes:
    try:
        r = session.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200 and r.headers.get("Content-Type") == "application/octet-stream":
            return r.content
    except requests.exceptions.RequestException:
        pass

    raise Exception("Failed to fetch summary")


@cache
def get_summary_obj(url: str) -> tuple[dict, dict]:
    summary = GLib.Bytes.new(fetch_summary_bytes(url))
    refs, metadata = GLib.Variant.new_from_bytes(
        GLib.VariantType.new(OSTree.SUMMARY_GVARIANT_STRING), summary, True
    ).unpack()

    return refs, metadata


@cache
def get_appids_from_summary(url: str) -> set:
    refs, _ = get_summary_obj(url)
    return {ref.split("/")[1] for ref, _ in (refs or []) if not ignore_ref(ref)}


@cache
def get_all_apps_on_flathub() -> set[str]:
    return get_appids_from_summary(
        f"{config.FLATHUB_STABLE_REPO_URL}/summary"
    ) | get_appids_from_summary(f"{config.FLATHUB_BETA_REPO_URL}/summary")


@cache
def get_eol_runtimes(url: str) -> set[str]:
    eols = set()
    _, metadata = get_summary_obj(url)
    for ref, eol_dict in metadata["xa.sparse-cache"].items():
        ref_type, ref_id, _, branch = ref.split("/")

        if ref_id.endswith((".Debug", ".Locale", ".Sources")) or ref_type != "runtime":
            continue

        if any(key in eol_dict for key in ("eolr", "eol")):
            eolid = f"{ref_id}//{branch}"
            eols.add(eolid)

    return eols


def get_eol_runtimes_on_flathub() -> set[str]:
    return get_eol_runtimes(f"{config.FLATHUB_STABLE_REPO_URL}/summary")


@cache
def check_url(url: str, strict: bool = False) -> bool:
    if not url.startswith(("https://", "http://")):
        raise Exception("Invalid input")

    try:
        r = requests.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        return r.ok and not strict or strict and r.status_code == 200
    except requests.exceptions.RequestException:
        return False


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
    except requests.exceptions.RequestException:
        pass

    return set()


def demangle(name: str) -> str:
    if name.startswith("_"):
        name = name[1:]
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
            third_cpt = appid.split(".")[3]
            # needs root path "/" otherwise HTTP 308
            url = f"sr.ht/~{second_cpt}/{third_cpt}/"
        else:
            third_cpt = demangle(appid.split(".")[3])
            url = f"sr.ht/~{second_cpt}/{third_cpt}/"

    # not case-sensitive -> lower
    elif appid.startswith("io.github."):
        second_cpt = demangle(appid.split(".")[2])
        if appid.count(".") == 3:
            third_cpt = appid.split(".")[3]
            url = f"github.com/{second_cpt}/{third_cpt}".lower()
        else:
            third_cpt = demangle(appid.split(".")[3])
            url = f"github.com/{second_cpt}/{third_cpt}".lower()

    # not case-sensitive -> lower
    elif appid.startswith("page.codeberg."):
        second_cpt = demangle(appid.split(".")[2])
        if appid.count(".") == 3:
            third_cpt = appid.split(".")[3]
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
                third_cpt = appid.split(".")[3]
                url = f"gitlab.com/{second_cpt}/{third_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][2:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"gitlab.com/{proj}"

        if appid.startswith("io.frama."):
            if appid.count(".") == 3:
                third_cpt = appid.split(".")[3]
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
                fourth_cpt = appid.split(".")[4]
                url = f"gitlab.gnome.org/{third_cpt}/{fourth_cpt}"
            else:
                demangled = [demangle(i) for i in appid.split(".")[:-1][3:]]
                demangled.insert(len(demangled), appid.split(".")[-1])
                proj = "/".join(demangled)
                url = f"gitlab.gnome.org/{proj}"

        if appid.startswith("org.freedesktop.gitlab."):
            if appid.count(".") == 4:
                fourth_cpt = appid.split(".")[4]
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
        demangled = [demangle(i) for i in appid.split(".")[:-1]]
        domain = ".".join(reversed(demangled)).lower()

    return domain


@cache
def is_app_on_flathub_api(appid: str) -> bool:
    return check_url(f"{config.FLATHUB_API_URL}/summary/{appid}", strict=True)


@cache
def is_app_on_flathub_summary(appid: str) -> bool:
    return bool(appid in get_all_apps_on_flathub())
