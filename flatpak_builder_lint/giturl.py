import re
import urllib


def is_git_commit_hash(s: str) -> bool:
    return re.match(r"[a-f0-9]{4,40}", s) is not None


# Is path a github branch?
def _is_path_gh_branch(components: list[str]) -> bool:
    if is_git_commit_hash(components[0]):
        return False
    if components[0] == "refs" and components[1] == "heads":
        return True
    # we don't have a reliable way to know if that is a branch
    # or not.
    return components[0] in ("main", "master")


# Check if the URL to code hosting an a branch
def is_branch(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    if u is None:
        return False
    hostname = u.hostname
    path_components = u.path.split("/")
    path_components.pop(0)  # remove the empty one, always
    if hostname == "github.com":
        path_components.pop(0)  # user / org
        path_components.pop(0)  # project / repo
        raw = path_components.pop(0)
        if raw in ("raw", "archive"):
            return _is_path_gh_branch(path_components)
        if raw in "blob":
            query = u.query
            if query:
                q = urllib.parse.parse_qs(query)
                return q["raw"] == ["true"] and _is_path_gh_branch(path_components)

        return False
    if hostname in ("raw.githubusercontent.com", "raw.github.com"):
        path_components.pop(0)  # user / org
        path_components.pop(0)  # project / repo
        return _is_path_gh_branch(path_components)
    return False
