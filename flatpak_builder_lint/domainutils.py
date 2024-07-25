import os

import gi
import requests

gi.require_version("OSTree", "1.0")
from gi.repository import Gio, GLib, OSTree  # noqa: E402

code_hosts = (
    "io.github.",
    "io.frama.",
    "io.gitlab.",
    "page.codeberg.",
    "io.sourceforge.",
    "net.sourceforge.",
    "org.gnome.gitlab.",
    "org.freedesktop.gitlab.",
)


def ignore_ref(ref: str) -> bool:
    ref_splits = ref.split("/")

    if len(ref_splits) != 4:
        return True

    if ref_splits[2] not in ("x86_64", "aarch64") or ref_splits[1].endswith(
        (".Debug", ".Locale", ".Sources")
    ):
        return True
    return False


def get_appid(remote: str) -> set:

    flatpak_user_path = os.path.join(GLib.get_user_data_dir(), "flatpak", "repo")
    flatpak_system_path = "/var/lib/flatpak/repo"
    repo_path = None

    if os.path.exists(flatpak_user_path):
        repo_path = flatpak_user_path
    elif os.path.exists(flatpak_system_path):
        repo_path = flatpak_system_path
    else:
        raise FileNotFoundError(
            "Flatpak repo does not exist at system or user location"
        )

    repo_file = Gio.File.new_for_path(repo_path)
    repo = OSTree.Repo.new(repo_file)
    repo.open(None)

    _, summary, _ = repo.remote_fetch_summary(remote, None)
    data = GLib.Variant.new_from_bytes(
        GLib.VariantType.new(OSTree.SUMMARY_GVARIANT_STRING), summary, True
    )

    refs, _ = data.unpack()

    appids = set()

    for ref, _ in refs:

        if ignore_ref(ref):
            continue

        appid = ref.split("/")[1]
        appids.add(appid)

    return appids


def check_url(url: str, strict: bool) -> bool:
    assert url.startswith(("https://", "http://"))
    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
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


def is_app_on_flathub(appid: str) -> bool:
    return check_url(f"https://flathub.org/api/v2/summary/{appid}", strict=True)


def is_appid_on_flathub(appid: str) -> bool:

    all_appids = get_appid("flathub") | get_appid("flathub-beta")
    if appid in all_appids:
        return True
    return False
