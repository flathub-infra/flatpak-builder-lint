import socket

import pytest
from urllib3.util import connection as urllib3_connection

from flatpak_builder_lint import domainutils


class TestIPv4OnlyResolution:
    def test_allowed_gai_family_uses_ipv4(self) -> None:
        assert urllib3_connection.allowed_gai_family() == socket.AF_INET


class TestDemangle:
    def test_plain(self) -> None:
        assert domainutils.demangle("foo_bar") == "foo-bar"

    def test_leading_underscore_digit(self) -> None:
        assert domainutils.demangle_leading_underscore("_1foo") == "1foo"

    def test_leading_underscore_non_digit(self) -> None:
        assert domainutils.demangle_leading_underscore("_foo") == "_foo"

    def test_demangle_preserves_leading_non_digit_underscore(self) -> None:
        assert domainutils.demangle("_foo_bar") == "-foo-bar"


class TestGetProjUrl:
    def test_github(self) -> None:
        assert domainutils.get_proj_url("io.github.user.repo") == "github.com/user/repo"

    def test_github_leading_underscore(self) -> None:
        assert domainutils.get_proj_url("io.github.user._1repo") == "github.com/user/1repo"

    def test_github_nested(self) -> None:
        assert domainutils.get_proj_url("io.github.user.repo.extra") == "github.com/user/repo"

    def test_gitlab(self) -> None:
        assert domainutils.get_proj_url("io.gitlab.user.repo") == "gitlab.com/user/repo"

    def test_codeberg(self) -> None:
        assert domainutils.get_proj_url("page.codeberg.user.repo") == "codeberg.org/user/repo"

    def test_sourceforge(self) -> None:
        assert (
            domainutils.get_proj_url("io.sourceforge.myproject.app")
            == "sourceforge.net/projects/myproject/"
        )

    def test_gnome_gitlab(self) -> None:
        assert (
            domainutils.get_proj_url("org.gnome.gitlab.user.repo") == "gitlab.gnome.org/user/repo"
        )

    def test_freedesktop_gitlab(self) -> None:
        assert (
            domainutils.get_proj_url("org.freedesktop.gitlab.user.repo")
            == "gitlab.freedesktop.org/user/repo"
        )

    def test_frama(self) -> None:
        assert domainutils.get_proj_url("io.frama.user.repo") == "framagit.org/user/repo"

    def test_invalid_raises(self) -> None:
        with pytest.raises(Exception):
            domainutils.get_proj_url("com.example")


class TestGetDomain:
    def test_gnome(self) -> None:
        assert domainutils.get_domain("org.gnome.Foo") == "gnome.org"

    def test_kde(self) -> None:
        assert domainutils.get_domain("org.kde.Foo") == "kde.org"

    def test_freedesktop(self) -> None:
        assert domainutils.get_domain("org.freedesktop.Foo") == "freedesktop.org"

    def test_gnome_gitlab(self) -> None:
        assert domainutils.get_domain("org.gnome.gitlab.user.repo") == "gnome.org"

    def test_freedesktop_gitlab(self) -> None:
        assert (
            domainutils.get_domain("org.freedesktop.gitlab.user.repo") == "gitlab.freedesktop.org"
        )

    def test_generic_reverse(self) -> None:
        assert domainutils.get_domain("com.example.App") == "example.com"

    def test_hyphenated(self) -> None:
        assert domainutils.get_domain("com.example_example.App") == "example-example.com"

    def test_leading_digit(self) -> None:
        assert domainutils.get_domain("com._1example.App") == "1example.com"

    def test_invalid_raises(self) -> None:
        with pytest.raises(Exception):
            domainutils.get_domain("com")


class TestIgnoreRef:
    def test_valid_ref_not_ignored(self) -> None:
        assert domainutils.ignore_ref("app/org.example.App/x86_64/stable") is False

    def test_locale_ref_ignored(self) -> None:
        assert domainutils.ignore_ref("app/org.example.App.Locale/x86_64/stable") is True

    def test_debug_ref_ignored(self) -> None:
        assert domainutils.ignore_ref("app/org.example.App.Debug/x86_64/stable") is True

    def test_unsupported_arch_ignored(self) -> None:
        assert domainutils.ignore_ref("app/org.example.App/i386/stable") is True

    def test_wrong_part_count_ignored(self) -> None:
        assert domainutils.ignore_ref("app/org.example.App/x86_64") is True
