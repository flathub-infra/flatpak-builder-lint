from pathlib import Path
from typing import Any

from flatpak_builder_lint import manifest


class TestCollectSubManifests:
    def test_no_string_modules_returns_empty(self, tmp_path: Path) -> None:
        main = tmp_path / "main.json"
        main.write_text('{"modules": [{"name": "inline"}]}')

        result = manifest.collect_sub_manifests(str(main))

        assert result == []

    def test_string_module_collected(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub.json"
        sub.write_text('{"name": "mod"}')
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.json"]}')

        result = manifest.collect_sub_manifests(str(main))

        assert result is not None
        assert str(sub.resolve()) in result

    def test_missing_sub_manifest_skipped(self, tmp_path: Path) -> None:
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["nonexistent.json"]}')

        result = manifest.collect_sub_manifests(str(main))

        assert result == []

    def test_circular_reference_does_not_loop(self, tmp_path: Path) -> None:
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text('{"modules": ["b.json"]}')
        b.write_text('{"modules": ["a.json"]}')

        result = manifest.collect_sub_manifests(str(a))

        assert result is not None
        assert str(b.resolve()) in result

    def test_yaml_sub_manifest_collected(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub.yaml"
        sub.write_text("name: mod\n")
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.yaml"]}')

        result = manifest.collect_sub_manifests(str(main))

        assert result is not None
        assert str(sub.resolve()) in result

    def test_nested_sub_manifests(self, tmp_path: Path) -> None:
        sub_dir = tmp_path / "shared"
        sub_dir.mkdir()
        deep = sub_dir / "deep.json"
        deep.write_text('{"name": "deep"}')
        sub = tmp_path / "sub.json"
        sub.write_text('{"modules": [{"name": "outer", "modules": ["shared/deep.json"]}]}')
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.json"]}')

        result = manifest.collect_sub_manifests(str(main))

        assert result is not None
        assert str(sub.resolve()) in result
        assert str(deep.resolve()) in result


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

    def test_json_with_block_comments(self, tmp_path: Path) -> None:
        main = tmp_path / "main.json"
        sub = tmp_path / "sub.json"
        sub.write_text('/* a comment */\n{"name": "mod"}')
        main.write_text('{"modules": ["sub.json"]}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(main))

        assert yaml_errors == []
        assert len(json_errors) == 1
        assert "sub.json" in json_errors[0]

    def test_sub_manifest_collected_and_validated(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub.json"
        sub.write_text('{"name": "mod"}')
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.json"]}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(main))

        assert yaml_errors == []
        assert json_errors == []

    def test_invalid_sub_manifest_reported(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub.json"
        sub.write_text('{"name": bad}')
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.json"]}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(main))

        assert yaml_errors == []
        assert len(json_errors) == 1
        assert "sub.json" in json_errors[0]

    def test_nested_sub_manifests_collected(self, tmp_path: Path) -> None:
        sub_dir = tmp_path / "shared"
        sub_dir.mkdir()
        subsub = sub_dir / "deep.json"
        subsub.write_text('{"name": "deep-mod"}')
        sub = tmp_path / "sub.json"
        sub.write_text('{"modules": ["shared/deep.json"]}')
        main = tmp_path / "main.json"
        main.write_text('{"modules": ["sub.json"]}')

        yaml_errors, json_errors = manifest.validate_manifest_files(str(main))

        assert yaml_errors == []
        assert json_errors == []

    def test_fallback_to_glob_when_sub_manifest_collection_fails(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{bad}")

        main = tmp_path / "main.json"
        main.write_text("{invalid json}")

        _, json_errors = manifest.validate_manifest_files(str(main))

        assert any("bad.json" in e for e in json_errors)

    def test_no_fallback_when_main_manifest_has_no_submanifests(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{bad}")

        main = tmp_path / "main.json"
        main.write_text('{"modules": [{"name": "inline-mod"}]}')

        _, json_errors = manifest.validate_manifest_files(str(main))

        assert json_errors == []


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
