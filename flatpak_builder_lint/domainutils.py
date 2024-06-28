import subprocess
from typing import List

import requests


def check_url(url: str) -> bool:
    assert url.startswith(("https://", "http://"))
    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
        if r.ok:
            ret = True
    except requests.exceptions.RequestException:
        pass
    return ret


def check_git(url: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "ls-remote", "-q", "--exit-code", url, "HEAD"],
            timeout=10,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def demangle(name: str) -> str:
    if name.startswith("_"):
        name = name[1:]
    name = name.replace("_", "-")
    return name


def get_domain(appid: str) -> str | None:
    assert not appid.startswith(
        (
            "io.github.",
            "io.gitlab.",
            "io.frama.",
            "page.codeberg.",
            "io.sourceforge.",
            "net.sourceforge.",
            "org.gnome.gitlab.",
            "org.freedesktop.gitlab.",
        )
    )
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
        tld = appid.split(".")[0]
        demangled = [demangle(i) for i in appid.split(".")[:-1][1:]]
        demangled.insert(0, tld)
        domain = ".".join(reversed(demangled)).lower()

    return domain


def get_code_hosting_url(appid: str) -> str | List[str] | None:
    assert appid.startswith(
        (
            "io.github.",
            "io.gitlab.",
            "io.frama.",
            "page.codeberg.",
            "io.sourceforge.",
            "net.sourceforge.",
            "org.gnome.gitlab.",
            "org.freedesktop.gitlab.",
        )
    )
    code_host: str | None | List[str] = None
    if appid.startswith(("io.sourceforge.", "net.sourceforge.")):
        sf_proj = appid.split(".")[2:3][0]
        code_host = f"https://sourceforge.net/projects/{sf_proj}".lower()
    if appid.startswith("org.gnome.gitlab."):
        [user, proj] = appid.split(".")[3:5]
        user = demangle(user)
        code_host = f"https://gitlab.gnome.org/{user}/{proj}.git".lower()
    if appid.startswith("org.freedesktop.gitlab."):
        [user, proj] = appid.split(".")[3:5]
        user = demangle(user)
        code_host = f"https://gitlab.freedesktop.org/{user}/{proj}.git".lower()
    if len(appid.split(".")) == 4:
        [sld, user, proj] = appid.split(".")[1:4]
        sld = demangle(sld)
        user = demangle(user)

        if appid.startswith("io.github."):
            code_host = f"https://github.com/{user}/{proj}.git".lower()
        if appid.startswith("io.gitlab."):
            code_host = f"https://gitlab.com/{user}/{proj}.git".lower()
        if appid.startswith("io.frama."):
            code_host = f"https://framagit.org/{user}/{proj}.git".lower()
        if appid.startswith("page.codeberg."):
            code_host = f"https://codeberg.org/{user}/{proj}.git".lower()

    if len(appid.split(".")) == 5:
        [sld, user, proj1, proj2] = appid.split(".")[1:5]
        sld = demangle(sld)
        user = demangle(user)
        proj1 = demangle(proj1)

        if appid.startswith("io.github."):
            code_host = [
                f"https://github.com/{user}/{proj1}.git".lower(),
                f"https://github.com/{user}/{proj2}.git".lower(),
            ]
        if appid.startswith("io.gitlab."):
            code_host = [
                f"https://gitlab.com/{user}/{proj1}.git".lower(),
                f"https://gitlab.com/{user}/{proj2}.git".lower(),
            ]
        if appid.startswith("io.frama."):
            code_host = [
                f"https://framagit.org/{user}/{proj1}.git".lower(),
                f"https://framagit.org/{user}/{proj2}.git".lower(),
            ]
        if appid.startswith("page.codeberg."):
            code_host = [
                f"https://codeberg.org/{user}/{proj1}.git".lower(),
                f"https://codeberg.org/{user}/{proj2}.git".lower(),
            ]
    return code_host


def is_app_on_flathub(appid: str) -> bool:
    return check_url(f"https://flathub.org/api/v2/summary/{appid}")
