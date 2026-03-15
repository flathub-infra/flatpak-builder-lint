import gzip
import textwrap
from typing import Any

import pytest

from flatpak_builder_lint import appstream


def _write_appstream(tmp_path: Any, xml: str, gz: bool = False) -> str:
    content = textwrap.dedent(xml).strip().encode()
    if gz:
        p = tmp_path / "app.xml.gz"
        with gzip.open(str(p), "wb") as f:
            f.write(content)
    else:
        p = tmp_path / "app.xml"
        p.write_bytes(content)
    return str(p)


MINIMAL_METAINFO = """
    <component type="desktop-application">
      <id>org.example.App</id>
      <developer id="org.example">
        <name>Example Dev</name>
      </developer>
      <project_license>GPL-2.0</project_license>
      <categories><category>Utility</category></categories>
      <icon type="cached">org.example.App.png</icon>
      <launchable type="desktop-id">org.example.App.desktop</launchable>
      <releases>
        <release version="1.0" timestamp="1700000000"/>
      </releases>
      <screenshots>
        <screenshot type="default">
          <image>https://example.org/screen.png</image>
          <caption>A screenshot</caption>
        </screenshot>
      </screenshots>
      <url type="vcs-browser">https://github.com/example/app</url>
    </component>
"""


class TestAppstreamXml:
    def test_component_type(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.component_type(p) == "desktop-application"

    def test_component_type_generic_when_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component><id>org.example.App</id></component>")
        assert appstream.component_type(p) == "generic"

    def test_appstream_id(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.appstream_id(p) == ["org.example.App"]

    def test_is_developer_name_present_with_developer_tag(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_developer_name_present(p) is True

    def test_is_developer_name_present_with_developer_name_tag(self, tmp_path: Any) -> None:
        xml = "<component><id>org.example.App</id><developer_name>Dev</developer_name></component>"
        p = _write_appstream(tmp_path, xml)
        assert appstream.is_developer_name_present(p) is True

    def test_is_developer_name_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component><id>org.example.App</id></component>")
        assert appstream.is_developer_name_present(p) is False

    def test_is_project_license_present(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_project_license_present(p) is True

    def test_is_project_license_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component><id>org.example.App</id></component>")
        assert appstream.is_project_license_present(p) is False

    def test_get_project_license(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.get_project_license(p) == "GPL-2.0"

    def test_is_categories_present(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_categories_present(p) is True

    def test_is_categories_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component><id>org.example.App</id></component>")
        assert appstream.is_categories_present(p) is False

    def test_has_icon_key(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.has_icon_key(p) is True

    def test_icon_no_type_false(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.icon_no_type(p) is False

    def test_icon_no_type_true(self, tmp_path: Any) -> None:
        xml = "<component><icon>foo.png</icon></component>"
        p = _write_appstream(tmp_path, xml)
        assert appstream.icon_no_type(p) is True

    def test_get_icon_filename(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.get_icon_filename(p) == "org.example.App.png"

    def test_get_launchable(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.get_launchable(p) == ["org.example.App.desktop"]

    def test_check_caption_all_have_captions(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.check_caption(p) is True

    def test_check_caption_missing(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <screenshots>
                <screenshot><image>https://example.org/s.png</image></screenshot>
              </screenshots>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.check_caption(p) is False

    def test_all_release_has_timestamp_true(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.all_release_has_timestamp(p) is True

    def test_all_release_has_timestamp_false(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <releases><release version="1.0"/></releases>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.all_release_has_timestamp(p) is False

    def test_get_latest_release_version(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <releases>
                <release version="1.0" timestamp="1600000000"/>
                <release version="2.0" timestamp="1700000000"/>
              </releases>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.get_latest_release_version(p) == "2.0"

    def test_get_latest_release_version_none_when_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component/>")
        assert appstream.get_latest_release_version(p) is None

    def test_is_latest_release_prerelease_true(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <releases><release version="1.0-alpha" timestamp="1700000000"/></releases>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.is_latest_release_prerelease(p) is True

    def test_is_latest_release_prerelease_false(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_latest_release_prerelease(p) is False

    def test_is_vcs_browser_url_present(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_vcs_browser_url_present(p) is True

    def test_is_vcs_browser_url_absent(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, "<component><id>org.example.App</id></component>")
        assert appstream.is_vcs_browser_url_present(p) is False

    def test_get_manifest_key(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <custom>
                <value key="flathub::manifest">https://github.com/flathub/org.example.App/blob/master/org.example.App.json</value>
              </custom>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        result = appstream.get_manifest_key(p)
        assert len(result) == 1
        assert "flathub" in result[0]

    def test_is_valid_component_type_true(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.is_valid_component_type(p) is True

    def test_is_valid_component_type_false(self, tmp_path: Any) -> None:
        xml = '<component type="bogus"><id>org.example.App</id></component>'
        p = _write_appstream(tmp_path, xml)
        assert appstream.is_valid_component_type(p) is False

    def test_parse_xml_raises_on_missing_file(self, tmp_path: Any) -> None:
        with pytest.raises(FileNotFoundError):
            appstream.parse_xml(str(tmp_path / "nonexistent.xml"))

    def test_parse_xml_raises_on_invalid_xml(self, tmp_path: Any) -> None:
        p = tmp_path / "bad.xml"
        p.write_text("<unclosed>")
        with pytest.raises(RuntimeError):
            appstream.parse_xml(str(p))

    def test_validate_raises_on_missing_file(self, tmp_path: Any) -> None:
        with pytest.raises(FileNotFoundError):
            appstream.validate(str(tmp_path / "nonexistent.xml"))

    def test_is_remote_icon_mirrored_true(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <icon type="remote">https://dl.flathub.org/media/foo.png</icon>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.is_remote_icon_mirrored(p) is True

    def test_is_remote_icon_mirrored_false(self, tmp_path: Any) -> None:
        xml = """
            <component>
              <icon type="remote">https://example.org/foo.png</icon>
            </component>
        """
        p = _write_appstream(tmp_path, xml)
        assert appstream.is_remote_icon_mirrored(p) is False

    def test_metainfo_components_present(self, tmp_path: Any) -> None:
        p = _write_appstream(tmp_path, MINIMAL_METAINFO)
        assert appstream.metainfo_components(p) != []

    def test_metainfo_components_absent(self, tmp_path: Any) -> None:
        xml = "<components><component/></components>"
        p = _write_appstream(tmp_path, xml)
        assert appstream.metainfo_components(p) == []
