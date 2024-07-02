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


def check_gitlab_user(url: str) -> bool:
    assert url.startswith("https://")
    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
        if len(r.json()) > 0 and isinstance(r.json()[0].get("id"), int):
            ret = True
    except requests.exceptions.RequestException:
        pass
    return ret


def check_gitlab_group(url: str) -> bool:
    assert url.startswith("https://")
    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
        if len(r.json()) > 0 and isinstance(r.json().get("id"), int):
            ret = True
    except requests.exceptions.RequestException:
        pass
    return ret


def demangle(name: str) -> str:
    if name.startswith("_"):
        name = name[1:]
    name = name.replace("_", "-")
    return name


def get_user_url(appid: str) -> str | None:
    assert appid.startswith(
        ("io.github.", "page.codeberg.", "io.sourceforge.", "net.sourceforge.")
    )
    assert appid.count(".") >= 2

    url = None
    # None of these have subdomains so all
    # we need is the third or fourth component of appid
    # to get user url
    # as long as the user exists, only they can deploy a pages site
    # at user.github.io
    third_cpt = demangle(appid.split(".")[2]).lower()

    if appid.startswith("io.github."):
        url = f"github.com/{third_cpt}"
    elif appid.startswith("page.codeberg."):
        url = f"codeberg.org/{third_cpt}"
    # third component is project name in case of sourceforge
    elif appid.startswith(("io.sourceforge.", "net.sourceforge.")):
        url = f"sourceforge.net/projects/{third_cpt}"

    return url


def get_gitlab_user(appid: str) -> str | None:
    assert appid.startswith(
        ("io.gitlab.", "io.frama.", "org.gnome.gitlab.", "org.freedesktop.gitlab.")
    )
    assert appid.count(".") >= 2

    url = None
    third_cpt = demangle(appid.split(".")[2]).lower()
    fourth_cpt = demangle(appid.split(".")[3]).lower()

    # The third component/fourth component can be the username
    # or a toplevel group name.  Return the username API url here

    # API is used because gitlab returns HTTP 200 on non existent
    # user URLs. This is to be passed in check_gitlab_user()

    if appid.startswith("io.gitlab."):
        url = f"gitlab.com/api/v4/users?username={third_cpt}"
    elif appid.startswith("io.frama."):
        url = f"framagit.org/api/v4/users?username={third_cpt}"
    elif appid.startswith("org.gnome.gitlab."):
        url = f"gitlab.gnome.org/api/v4/users?username={fourth_cpt}"
    elif appid.startswith("org.freedesktop.gitlab."):
        url = f"gitlab.freedesktop.org/api/v4/users?username={fourth_cpt}"

    return url


def get_gitlab_group(appid: str) -> str | None:
    assert appid.startswith(
        ("io.gitlab.", "io.frama.", "org.gnome.gitlab.", "org.freedesktop.gitlab.")
    )
    assert appid.count(".") >= 2

    url = None
    third_cpt = demangle(appid.split(".")[2]).lower()
    fourth_cpt = demangle(appid.split(".")[3]).lower()

    # The third component/fourth component can be the toplevel
    # group name. Return the groupname API url here

    # API is used because gitlab returns HTTP 200 on non existent
    # user URLs. This is to be passed in check_gitlab_group()

    if appid.startswith("io.gitlab."):
        url = f"gitlab.com/api/v4/groups/{third_cpt}"
    elif appid.startswith("io.frama."):
        url = f"framagit.org/api/v4/groups/{third_cpt}"
    elif appid.startswith("org.gnome.gitlab."):
        url = f"gitlab.gnome.org/api/v4/groups/{fourth_cpt}"
    elif appid.startswith("org.freedesktop.gitlab."):
        url = f"gitlab.freedesktop.org/api/v4/groups/{fourth_cpt}"

    return url


def get_domains(appid: str) -> tuple[str]:
    assert not appid.startswith(
        (
            "io.github.",
            "io.frama.",
            "io.gitlab.",
            "page.codeberg.",
            "io.sourceforge.",
            "net.sourceforge.",
            "org.gnome.gitlab.",
            "org.freedesktop.gitlab.",
        )
    )
    assert appid.count(".") >= 2

    domains = []
    if appid.startswith("org.gnome.") and not appid.startswith("org.gnome.gitlab."):
        domains.append("gnome.org")
    elif appid.startswith("org.kde."):
        domains.append("kde.org")
    elif appid.startswith("org.freedesktop.") and not appid.startswith(
        "org.freedesktop.gitlab."
    ):
        domains.append("freedesktop.org")
    else:
        tld = appid.split(".")[0]
        demangled = [demangle(i) for i in appid.split(".")[:-1][1:]]
        demangled.insert(0, tld)
        demangled_domain = ".".join(reversed(demangled)).lower()
        domains.append(demangled_domain)

    if appid.count(".") == 2:
        demangled = [demangle(i) for i in appid.split(".")[:-1]]
        demangled_domain = ".".join(reversed(demangled)).lower()
        domains.append(demangled_domain)

    return tuple(domains)


def is_app_on_flathub(appid: str) -> bool:
    return check_url(f"https://flathub.org/api/v2/summary/{appid}")
