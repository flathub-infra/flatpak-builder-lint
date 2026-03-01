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

    ## Gitlab
    # Basic image at a commit
    assert not giturl.is_branch(
        "https://gitlab.com/user/project/-/raw/ab5356ba2ce36e3ee0bab6e30cc051ad07c49ecd/img/logo.svg"
    )
    assert giturl.is_branch("https://gitlab.com/user/project/-/raw/main/screenshots/small.png")
    assert giturl.is_branch(
        "https://gitlab.com/user3/project3/-/raw/master/src/images/screenshot.png"
    )
    # With org/group/project URL
    assert giturl.is_branch("https://gitlab.com/user4/group1/app2/-/raw/master/screenshot.png")
    assert not giturl.is_branch(
        "https://gitlab.com/user4/group1/app2/-/raw/30f79bec32243c31dd91a05c0ad7b80f1e301aea/screenshot.png"
    )
    # old syntax (no `-`)
    assert not giturl.is_branch(
        "https://gitlab.com/user2/project3/raw/1.0.0b1/data/image/org.flathub.Builder.svg"
    )
    assert not giturl.is_branch(
        "https://gitlab.com/user2/project2/raw/30f79bec32243c31dd91a05c0ad7b80f1e301aea/data/image/org.flathub.Builder.svg"
    )
    assert giturl.is_branch(
        "https://gitlab.com/user2/project2/raw/main/data/image/org.flathub.Builder.svg"
    )
    # This is a tree. Doesn't lead to a file.
    assert not giturl.is_branch("https://gitlab.com/user4/project6/-/tree/master/po")
    # Blob is the webpage.
    assert not giturl.is_branch(
        "https://gitlab.com/user/project3/-/blob/main/screenshots/pic-1.png"
    )
    # Other top-level: issues
    assert not giturl.is_branch("https://gitlab.com/user3/project2/issues")
    # Other top-level: CI artifact
    assert not giturl.is_branch(
        "https://gitlab.com/user6/core/-/jobs/7109755574/artifacts/raw/app2/tarball123.zip"
    )
    # Repositories
    assert not giturl.is_branch("https://gitlab.com/user1/group2tools/app3.git")
    assert not giturl.is_branch("https://gitlab.com/user2/project4.git")
