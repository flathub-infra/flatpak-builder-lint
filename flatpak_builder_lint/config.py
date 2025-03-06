import os

FLATHUB_REPO_BASE_URL = "https://dl.flathub.org"
FLATHUB_API_URL = "https://flathub.org/api/v2"
FLATHUB_MEDIA_BASE_URL = f"{FLATHUB_REPO_BASE_URL}/media"
FLATHUB_STABLE_REPO_URL = f"{FLATHUB_REPO_BASE_URL}/repo"
FLATHUB_BETA_REPO_URL = f"{FLATHUB_REPO_BASE_URL}/beta-repo"

FLATHUB_SUPPORTED_ARCHES = ("x86_64", "aarch64")

FLATHUB_JSON_FILE = "flathub.json"

FLATHUB_BASEAPP_IDENTIFIER = ".BaseApp"

FLATHUB_APPSTREAM_TYPES_APPS = (
    "desktop",
    "desktop-application",
    "console-application",
)

FLATHUB_APPSTREAM_TYPES_DESKTOP = (
    "desktop",
    "desktop-application",
)

FLATHUB_APPSTREAM_TYPES_CONSOLE = "console-application"

FLATHUB_APPSTREAM_TYPES = (
    "addon",
    "runtime",
    *FLATHUB_APPSTREAM_TYPES_APPS,
)


# Keep root URL path
FLATHUB_ALLOWED_GITMODULE_URLS = (
    "https://github.com/flathub/",
    "https://github.com/flathub-infra/",
    "https://github.com/flatpak/",
    "git@github.com:flathub/",
    "git@github.com:flatpak/",
    "git@github.com:flathub-infra/",
)

XDG_CACHE_HOME = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
CACHEDIR = os.path.join(XDG_CACHE_HOME, "flatpak-builder-lint")
