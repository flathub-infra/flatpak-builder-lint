from typing import Any

from ruamel.yaml.error import YAMLError

from flatpak_builder_lint import manifest


class TestFormatYamlError:
    def test_strips_suppression_hints(self) -> None:
        err = YAMLError(
            "bad yaml\n  To suppress this check see https://yaml.dev/\n  https://yaml.dev/"
        )

        result = manifest.format_yaml_error(err)

        assert "To suppress" not in result
        assert "https://yaml.dev" not in result
        assert "bad yaml" in result


class TestGetKeyLineno:
    def test_json_finds_key(self, tmp_path: Any) -> None:
        p = tmp_path / "app.json"
        p.write_text('{\n  "id": "org.example.App",\n  "finish-args": []\n}')

        assert manifest.get_key_lineno(str(p), "finish-args") == 3

    def test_json_key_not_found_returns_none(self, tmp_path: Any) -> None:
        p = tmp_path / "app.json"
        p.write_text('{"id": "org.example.App"}')

        assert manifest.get_key_lineno(str(p), "nonexistent-key") is None

    def test_yaml_finds_key(self, tmp_path: Any) -> None:
        p = tmp_path / "app.yaml"
        p.write_text("id: org.example.App\nfinish-args:\n  - --share=network\n")

        result = manifest.get_key_lineno(str(p), "finish-args")

        assert result is not None
        assert result >= 1

    def test_missing_file_returns_none(self, tmp_path: Any) -> None:
        assert manifest.get_key_lineno(str(tmp_path / "nonexistent.json"), "id") is None

    def test_unsupported_extension_returns_none(self, tmp_path: Any) -> None:
        p = tmp_path / "app.toml"
        p.write_text('id = "org.example.App"\n')

        assert manifest.get_key_lineno(str(p), "id") is None
