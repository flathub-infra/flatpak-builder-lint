from flatpak_builder_lint import giturl


def test_is_branch() -> None:
    assert giturl.is_branch(
        "https://raw.githubusercontent.com/user/project/refs/heads/my_other_branch/somefile"
    )
    assert giturl.is_branch(
        "https://raw.github.com/user/project/refs/heads/my_other_branch/somefile"
    )
    assert giturl.is_branch("https://github.com/user/project/raw/refs/heads/my_branch/somefile")
    assert giturl.is_branch("https://github.com/user/project/archive/refs/heads/my_branch.tar.gz")
    assert giturl.is_branch(
        "https://github.com/user/project/blob/master/screenshots/Screenshot.png?raw=true"
    )
    assert not giturl.is_branch(
        "https://github.com/user/project/blob/30f79bec32243c31dd91a05c0ad7b80f1e301aea/screenshots/Screenshot.png?raw=true"
    )
    assert not giturl.is_branch("https://github.com/user/project/raw/refs/tags/my_tag/somefile")
    assert not giturl.is_branch("https://github.com/user/project/archive/refs/tags/0.20.2.tar.gz")
    # This are pages, not the files.
    assert not giturl.is_branch("https://github.com/user/project/blob/refs/heads/my_tag/somefile")
    assert not giturl.is_branch(
        "https://github.com/user/project/blob/master/screenshots/Screenshot.png"
    )
