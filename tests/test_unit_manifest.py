from pathlib import Path
from typing import Any

from flatpak_builder_lint import manifest


class TestValidateManifestFiles:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("key: value\n")

        yaml_errors, json_errors = manifest.validate_manifest_files(str(tmp_path / "a.yaml"))

        assert yaml_errors == []
        assert json_errors == []

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [1, 2\n")

        yaml_errors, json_errors = manifest.validate_manifest_files(str(bad_yaml))

        assert len(yaml_errors) == 1
        assert "bad.yaml" in yaml_errors[0]
        assert json_errors == []

    def test_valid_json(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text('{"key": "value"}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(tmp_path / "a.json"))

        assert yaml_errors == []
        assert json_errors == []

    def test_invalid_json(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{"key": value}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(bad_json))

        assert yaml_errors == []
        assert len(json_errors) == 1
        assert "bad.json" in json_errors[0]

    def test_multiple_errors(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("a: [1, 2\n")
        (tmp_path / "b.yaml").write_text("b: [3, 4\n")
        (tmp_path / "a.json").write_text("{bad}")
        (tmp_path / "b.json").write_text("{also bad}")

        yaml_errors, json_errors = manifest.validate_manifest_files(str(tmp_path / "a.yaml"))

        assert len(yaml_errors) == 2
        assert len(json_errors) == 2


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
