from functools import cache

import gi
import requests
from requests_cache import CachedSession

gi.require_version("OSTree", "1.0")
from gi.repository import GLib, OSTree  # noqa: E402

code_hosts = (
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

REQUEST_TIMEOUT = (120.05, None)

FLATHUB_API_URL = "https://flathub.org/api/v2"
FLATHUB_STABLE_REPO_URL = "https://dl.flathub.org/repo"
FLATHUB_BETA_REPO_URL = "https://dl.flathub.org/beta-repo"

session = CachedSession("cache", backend="sqlite", use_temp=True, expire_after=3600)


def ignore_ref(ref: str) -> bool:
    ref_splits = ref.split("/")

    if len(ref_splits) != 4:
        return True

    if ref_splits[2] not in ("x86_64", "aarch64") or ref_splits[1].endswith(
        (".Debug", ".Locale", ".Sources")
    ):
        return True
    return False


@cache
def fetch_summary_bytes(url: str) -> bytes:
    summary_bytes = b""
    try:
        r = session.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        if (
            r.status_code == 200
            and r.headers.get("Content-Type") == "application/octet-stream"
        ):
            summary_bytes = r.content
    except requests.exceptions.RequestException:
        pass

    if not summary_bytes:
        raise Exception("Failed to fetch summary")

    return summary_bytes


@cache
def get_appids_from_summary(url: str) -> set[str]:

    appids = set()
    summary = GLib.Bytes.new(fetch_summary_bytes(url))

    data = GLib.Variant.new_from_bytes(
        GLib.VariantType.new(OSTree.SUMMARY_GVARIANT_STRING), summary, True
    )

    refs, _ = data.unpack()

    if refs:
        for ref, _ in refs:
            if ignore_ref(ref):
                continue
            appid = ref.split("/")[1]
            appids.add(appid)

    return appids


@cache
def get_all_apps_on_flathub() -> set[str]:
    return get_appids_from_summary(
        f"{FLATHUB_STABLE_REPO_URL}/summary"
    ) | get_appids_from_summary(f"{FLATHUB_BETA_REPO_URL}/summary")


@cache
def check_url(url: str, strict: bool) -> bool:
    assert url.startswith(("https://", "http://"))

    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        if r.ok and not strict:
            ret = True
        # For known code hosting sites
        # they return 300s on non-existent repo/users
        # 200 is the only way to make sure target exists
        if strict and r.status_code == 200:
            ret = True
    except requests.exceptions.RequestException:
        pass

    return ret


@cache
def get_remote_exceptions(appid: str) -> set[str]:

    ret = set()
    try:
        # exception updates should be reflected immediately
        r = requests.get(
            f"{FLATHUB_API_URL}/exceptions/{appid}",
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200 and r.headers.get("Content-Type") == "application/json":
            ret = set(r.json())
    except requests.exceptions.RequestException:
        pass

    return ret


def demangle(name: str) -> str:
    if name.startswith("_"):
        name = name[1:]
    name = name.replace("_", "-")
    return name


def get_proj_url(appid: str) -> str | None:
    assert appid.startswith(code_hosts)
    assert appid.count(".") >= 2

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
    assert not appid.startswith(code_hosts)
    assert appid.count(".") >= 2

    domain = None
    if appid.startswith("org.gnome.") and not appid.startswith("org.gnome.gitlab."):
        domain = "gnome.org"
    elif appid.startswith("org.kde."):
        domain = "kde.org"
    elif appid.startswith("org.freedesktop.") and not appid.startswith(
        "org.freedesktop.gitlab."
    ):
        domain = "freedesktop.org"
    else:
        demangled = [demangle(i) for i in appid.split(".")[:-1]]
        domain = ".".join(reversed(demangled)).lower()

    return domain


@cache
def is_app_on_flathub_api(appid: str) -> bool:
    return check_url(f"{FLATHUB_API_URL}/summary/{appid}", strict=True)


@cache
def is_app_on_flathub_summary(appid: str) -> bool:

    if appid in get_all_apps_on_flathub():
        return True
    return False
