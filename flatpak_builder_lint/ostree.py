import json
import logging
import os
from functools import cache

import gi

from . import config

gi.require_version("OSTree", "1.0")
from gi.repository import Gio, GLib, OSTree  # noqa: E402

logger = logging.getLogger(__name__)


def open_ostree_repo(repo_path: str) -> OSTree.Repo:
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Could not find repo directory: {repo_path}")

    repo = OSTree.Repo.new(Gio.File.new_for_path(repo_path))

    try:
        repo.open(None)
    except GLib.Error as err:
        raise GLib.Error("Failed to open OSTree repo") from err

    return repo


@cache
def get_refs(repo_path: str, ref_prefix: str | None) -> set[str]:
    repo = open_ostree_repo(repo_path)
    _, refs = repo.list_refs(ref_prefix, None)

    logger.debug("Found refs %s in repo %s", set(refs.keys()), os.path.abspath(repo_path))
    return set(refs.keys())


@cache
def get_all_refs_filtered(repo_path: str) -> set[str]:
    refs = get_refs(repo_path, None)

    return {
        r
        for r in refs
        if (parts := r.split("/"))
        and len(parts) == 4
        and parts[2] in config.FLATHUB_SUPPORTED_ARCHES
        and not parts[1].endswith(config.IGNORE_REF_SUFFIXES)
    }


@cache
def get_primary_refs(repo_path: str) -> set[str]:
    primary_refs = {
        r
        for r in get_refs(repo_path, None)
        if (parts := r.split("/"))
        and len(parts) == 4
        and parts[0] == "app"
        and parts[2] in config.FLATHUB_SUPPORTED_ARCHES
    }
    logger.debug("Found primary refs %s in repo %s", primary_refs, os.path.abspath(repo_path))
    return primary_refs


@cache
def infer_appid(path: str) -> str | None:
    refs = get_primary_refs(path)
    if refs:
        # Assume refs share the same ref_id
        # refs with different ref_id in a
        # single repo is not a supported case
        ref = next(iter(refs))
        return ref.split("/")[1]

    return None


def extract_subpath(
    repo_path: str,
    ref: str,
    subpath: str,
    dest: str,
    should_pass: bool = False,
) -> None:
    repo = open_ostree_repo(repo_path)
    opts = OSTree.RepoCheckoutAtOptions()
    # https://gitlab.gnome.org/GNOME/pygobject/-/issues/639
    opts.mode = int(OSTree.RepoCheckoutMode.USER)  # type: ignore
    opts.overwrite_mode = int(OSTree.RepoCheckoutOverwriteMode.ADD_FILES)  # type: ignore
    opts.subpath = subpath

    _, rev = repo.resolve_rev(ref, True)

    # https://sourceware.org/git/?p=glibc.git;a=blob;f=io/fcntl.h;h=f157991782681caabe9bd7edb46ec205731965af;hb=HEAD#l149
    AT_FDCWD = -100
    if rev:
        if should_pass:
            try:
                logger.debug(
                    "Checking out subpath %s with G_IO_ERROR_NOT_FOUND allowed "
                    "for ref %s at dest %s",
                    subpath,
                    ref,
                    dest,
                )
                repo.checkout_at(opts, AT_FDCWD, dest, rev, None)
            except GLib.Error as err:
                if err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
                    pass
                else:
                    raise
        else:
            logger.debug("Checking out subpath %s for ref %s at dest %s", subpath, ref, dest)
            repo.checkout_at(opts, AT_FDCWD, dest, rev, None)


def get_flathub_json(repo_path: str, ref: str, dest: str) -> dict[str, str | bool | list[str]]:
    flathubjsonfile = config.FLATHUB_JSON_FILE
    extract_subpath(repo_path, ref, f"/files/{flathubjsonfile}", dest, True)
    flathub_json_path = os.path.join(dest, flathubjsonfile)
    flathub_json: dict[str, str | bool | list[str]] = {}

    if os.path.exists(flathub_json_path):
        with open(flathub_json_path) as fp:
            flathub_json = json.load(fp)

    return flathub_json
