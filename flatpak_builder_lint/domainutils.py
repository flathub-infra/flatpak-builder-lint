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


def check_url_ok(url: str) -> bool:
    assert url.endswith(".gitlab.io")
    ret = False
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
        if r.status_code == 200:
            ret = True
    except requests.exceptions.RequestException:
        pass
    return ret


def demangle(name: str) -> str:
    if name.startswith("_"):
        name = name[1:]
    name = name.replace("_", "-")
    return name


def get_domain(appid: str) -> str | None:
    domain = None
    if appid.startswith("org.gnome."):
        domain = "gnome.org"
    elif appid.startswith("org.kde."):
        domain = "kde.org"
    elif appid.startswith("org.freedesktop."):
        domain = "freedesktop.org"
    elif appid.startswith(("io.github.", "io.gitlab.", "page.codeberg.", "io.frama.")):
        tld = appid.split(".")[0]
        demangled = [demangle(i) for i in appid.split(".")[1:3]]
        demangled.insert(0, tld)
        domain = ".".join(reversed(demangled)).lower()
    elif appid.startswith(("io.sourceforge.", "net.sourceforge.")):
        proj = demangle(appid.split(".")[2])
        domain = f"sourceforge.net/projects/{proj}".lower()
    else:
        tld = appid.split(".")[0]
        demangled = [demangle(i) for i in appid.split(".")[:-1][1:]]
        demangled.insert(0, tld)
        domain = ".".join(reversed(demangled)).lower()

    return domain


def is_app_on_flathub(appid: str) -> bool:
    return check_url(f"https://flathub.org/api/v2/summary/{appid}")
