from pathlib import Path
from typing import Any

from flatpak_builder_lint import manifest


class TestValidateManifestFiles:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("key: value\n")

        yaml_errors = manifest.validate_manifest_files(str(tmp_path / "a.yaml"))

        assert yaml_errors == []

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [1, 2\n")

        yaml_errors = manifest.validate_manifest_files(str(bad_yaml))

        assert len(yaml_errors) == 1
        assert "bad.yaml" in yaml_errors[0]


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
