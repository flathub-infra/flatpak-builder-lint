import os

GITHUB_API = "https://api.github.com"
GITHUB_CONTENT_CDN = "https://raw.githubusercontent.com"

LINTER_FULL_REPO = "flathub-infra/flatpak-builder-lint"

FLATHUB_REPO_BASE_URL = "https://dl.flathub.org"
FLATHUB_API_URL = "https://flathub.org/api/v2"
FLATHUB_MEDIA_BASE_URL = f"{FLATHUB_REPO_BASE_URL}/media"
FLATHUB_STABLE_REPO_URL = f"{FLATHUB_REPO_BASE_URL}/repo"
FLATHUB_BETA_REPO_URL = f"{FLATHUB_REPO_BASE_URL}/beta-repo"
FLATHUB_BUILD_BASE_URL = "https://hub.flathub.org"
FLATHUB_BUILD_API_URL = f"{FLATHUB_BUILD_BASE_URL}/api/v1"
FLATHUB_GITHUB_ORG_URL = "https://github.com/flathub/"

FLATHUB_SUPPORTED_ARCHES = ("x86_64", "aarch64")

FLATHUB_RUNTIME_PREFIXES = ("org.freedesktop.", "org.gnome.", "org.kde.")
FLATHUB_RUNTIME_SUFFIXES = (".Platform", ".Sdk")

IGNORE_REF_SUFFIXES = (".Locale", ".Debug", ".Sources")

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
    "generic",
    "addon",
    "runtime",
    *FLATHUB_APPSTREAM_TYPES_APPS,
)


# Keep root URL path
FLATHUB_ALLOWED_GITMODULE_URLS = (
    FLATHUB_GITHUB_ORG_URL,
    "https://github.com/flathub-infra/",
    "https://github.com/flatpak/",
    "git@github.com:flathub/",
    "git@github.com:flatpak/",
    "git@github.com:flathub-infra/",
)

XDG_CACHE_HOME = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
CACHEDIR = os.path.join(XDG_CACHE_HOME, "flatpak-builder-lint")


def is_flathub_build_pipeline() -> bool:
    return os.getenv("REPO", "").startswith(FLATHUB_GITHUB_ORG_URL)


def is_flatmgr_pipeline() -> bool:
    return bool(os.getenv("FLAT_MANAGER_BUILD_ID"))


def is_flathub_pipeline() -> bool:
    return is_flathub_build_pipeline() or is_flatmgr_pipeline()
