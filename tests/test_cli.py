import io
import json
import os
import sys
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

import pytest

from flatpak_builder_lint import checks
from flatpak_builder_lint.cli import (
    _filter,
    main,
    print_gh_annotations,
    run_checks,
)


def _write_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def _make_manifest_payload(appid: str = "com.example.App") -> MappingProxyType[str, Any]:
    return MappingProxyType({"id": appid, "x-manifest-filename": ""})


class TestFilter:
    def test_removes_matching_prefix(self) -> None:
        info = {"appid-url-not-reachable: Tried https://example.com", "other-error"}
        excepts = {"appid-url-not-reachable"}
        result = _filter(info, excepts)
        assert "other-error" in result
        assert not any(i.startswith("appid-url-not-reachable") for i in result)

    def test_keeps_non_matching(self) -> None:
        info = {"finish-args-x11-without-ipc", "appstream-missing-categories"}
        excepts = {"appid-url-not-reachable"}
        result = _filter(info, excepts)
        assert set(result) == info

    def test_empty_inputs(self) -> None:
        assert _filter(set(), set()) == []
        assert _filter({"foo"}, set()) == ["foo"]
        assert _filter(set(), {"foo"}) == []

    def test_prefix_match_does_not_bleed_across_keys(self) -> None:
        info = {"module-foo-bar", "modular-build-something"}
        excepts = {"module-"}
        result = _filter(info, excepts)
        assert "modular-build-something" in result
        assert "module-foo-bar" not in result


class TestPrintGhAnnotations:
    def _capture(self, results: dict[str, Any], artifact_type: str = "manifest") -> str:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            print_gh_annotations(results, artifact_type)
        return buf.getvalue()

    def test_empty_results_produces_no_output(self) -> None:
        assert self._capture({}) == ""

    def test_error_without_detail(self) -> None:
        out = self._capture({"errors": ["finish-args-not-defined"]})
        assert "::error::" in out
        assert "finish-args-not-defined" in out

    def test_error_with_detail_from_info(self) -> None:
        results = {
            "errors": ["finish-args-not-defined"],
            "info": ["finish-args-not-defined: finish-args has no finish-args key"],
        }
        out = self._capture(results)
        assert "finish-args has no finish-args key" in out

    def test_warning_annotation(self) -> None:
        out = self._capture({"warnings": ["appstream-screenshot-missing-caption"]})
        assert "::warning::" in out
        assert "appstream-screenshot-missing-caption" in out

    def test_appstream_lines(self) -> None:
        out = self._capture({"appstream": ["E:file.xml:tag:10 explanation"]})
        assert "::error::Appstream:" in out
        assert "E:file.xml:tag:10 explanation" in out

    def test_notice_message(self) -> None:
        out = self._capture({"message": "See https://docs.flathub.org/linter"})
        assert "::notice::" in out
        assert "https://docs.flathub.org/linter" in out

    def test_omitted_annotation_is_skipped(self) -> None:
        out = self._capture({"errors": ["appstream-failed-validation"]})
        assert "appstream-failed-validation" not in out

    def test_multiple_errors(self) -> None:
        results = {"errors": ["err-one", "err-two"]}
        out = self._capture(results)
        assert out.count("::error::") == 2


class TestRunChecksDispatch:
    def test_unknown_kind_raises(self, tmp_path: Any) -> None:
        with pytest.raises(ValueError, match="Unknown kind"):
            run_checks("invalid", str(tmp_path))

    def test_manifest_kind_calls_check_manifest(self) -> None:
        called: list[bool] = []

        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                called.append(True)
                self.errors.add("fake-error")

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(),
                ),
                patch("flatpak_builder_lint.cli.manifest.infer_appid", return_value=None),
            ):
                result = run_checks("manifest", "/fake/path")
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)

        assert called
        assert "fake-error" in result.get("errors", [])

    def test_errors_produce_message_key(self) -> None:
        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                self.errors.add("some-error")

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(),
                ),
                patch("flatpak_builder_lint.cli.manifest.infer_appid", return_value=None),
            ):
                result = run_checks("manifest", "/fake")
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)

        assert "message" in result

    def test_no_errors_no_message_key(self) -> None:
        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                pass

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(),
                ),
                patch("flatpak_builder_lint.cli.manifest.infer_appid", return_value=None),
            ):
                result = run_checks("manifest", "/fake")
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)

        assert "message" not in result
        assert "errors" not in result


class TestRunChecksExceptions:
    def _run_with_error(
        self, error: str, exceptions: set[str], appid: str = "com.example.App"
    ) -> dict[str, Any]:
        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                self.errors.add(error)

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(appid),
                ),
                patch("flatpak_builder_lint.cli.manifest.infer_appid", return_value=appid),
                patch(
                    "flatpak_builder_lint.cli.domainutils.get_remote_exceptions_github",
                    return_value=set(),
                ),
                patch("flatpak_builder_lint.cli.get_local_exceptions", return_value=exceptions),
            ):
                result = run_checks("manifest", "/fake", enable_exceptions=True, appid=appid)
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)
        return result

    def test_exception_removes_error(self) -> None:
        result = self._run_with_error("finish-args-not-defined", {"finish-args-not-defined"})
        assert "finish-args-not-defined" not in result.get("errors", [])

    def test_wildcard_exception_clears_all(self) -> None:
        result = self._run_with_error("finish-args-not-defined", {"*"})
        assert result == {}

    def test_non_matching_exception_keeps_error(self) -> None:
        result = self._run_with_error("finish-args-not-defined", {"appid-url-not-reachable"})
        assert "finish-args-not-defined" in result.get("errors", [])

    def test_user_exceptions_take_priority(self) -> None:
        error = "finish-args-not-defined"

        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                self.errors.add(error)

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(),
                ),
                patch(
                    "flatpak_builder_lint.cli.manifest.infer_appid",
                    return_value="com.example.App",
                ),
                patch(
                    "flatpak_builder_lint.cli.get_user_exceptions",
                    return_value={error},
                ),
            ):
                result = run_checks(
                    "manifest",
                    "/fake",
                    enable_exceptions=True,
                    appid="com.example.App",
                    user_exceptions_path="dummy.json",
                )
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)

        assert error not in result.get("errors", [])

    def test_appstream_exception_removes_appstream_block(self) -> None:
        class FakeCheck(checks.Check):
            def check_manifest(self, _manifest: Any) -> None:
                self.errors.add("appstream-failed-validation")
                self.appstream.add("E:file.xml:tag:1 bad")

        orig_all = checks.ALL[:]
        checks.ALL.clear()
        checks.ALL.append(FakeCheck)
        try:
            with (
                patch(
                    "flatpak_builder_lint.cli.manifest.show_manifest",
                    return_value=_make_manifest_payload(),
                ),
                patch(
                    "flatpak_builder_lint.cli.manifest.infer_appid",
                    return_value="com.example.App",
                ),
                patch(
                    "flatpak_builder_lint.cli.domainutils.get_remote_exceptions_github",
                    return_value=set(),
                ),
                patch(
                    "flatpak_builder_lint.cli.get_local_exceptions",
                    return_value={"appstream-failed-validation"},
                ),
            ):
                result = run_checks(
                    "manifest",
                    "/fake",
                    enable_exceptions=True,
                    appid="com.example.App",
                )
        finally:
            checks.ALL.clear()
            checks.ALL.extend(orig_all)

        assert "appstream" not in result


class TestMainArgParsing:
    def _run_main(self, argv: list[str]) -> int | None:
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
            main()
        code = exc.value.code
        assert code is None or isinstance(code, int)
        return code

    def test_help_exits_zero(self) -> None:
        assert self._run_main(["flatpak-builder-lint", "--help"]) == 0

    def test_version_exits_zero(self) -> None:
        assert self._run_main(["flatpak-builder-lint", "--version"]) == 0

    def test_invalid_type_exits_nonzero(self, tmp_path: Any) -> None:
        assert self._run_main(["flatpak-builder-lint", "badtype", str(tmp_path)]) != 0

    def test_missing_path_exits_nonzero(self) -> None:
        assert self._run_main(["flatpak-builder-lint", "manifest"]) != 0

    def test_manifest_no_errors_exits_zero(self, tmp_path: Any) -> None:
        p = tmp_path / "com.example.App.json"
        p.write_text("{}")
        with patch("flatpak_builder_lint.cli.run_checks", return_value={}):
            assert self._run_main(["flatpak-builder-lint", "manifest", str(p)]) == 0

    def test_manifest_with_errors_exits_one(self, tmp_path: Any) -> None:
        p = tmp_path / "com.example.App.json"
        p.write_text("{}")
        with patch(
            "flatpak_builder_lint.cli.run_checks",
            return_value={"errors": ["finish-args-not-defined"]},
        ):
            assert self._run_main(["flatpak-builder-lint", "manifest", str(p)]) == 1

    def test_warnings_only_exits_zero(self, tmp_path: Any) -> None:
        p = tmp_path / "com.example.App.json"
        p.write_text("{}")
        with patch(
            "flatpak_builder_lint.cli.run_checks",
            return_value={"warnings": ["appstream-screenshot-missing-caption"]},
        ):
            assert self._run_main(["flatpak-builder-lint", "manifest", str(p)]) == 0

    def test_gha_format_flag_triggers_annotations(self, tmp_path: Any) -> None:
        p = tmp_path / "com.example.App.json"
        p.write_text("{}")
        with (
            patch(
                "flatpak_builder_lint.cli.run_checks",
                return_value={"errors": ["finish-args-not-defined"]},
            ),
            patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
            patch("flatpak_builder_lint.cli.print_gh_annotations") as mock_ann,
        ):
            self._run_main(["flatpak-builder-lint", "--gha-format", "manifest", str(p)])
            mock_ann.assert_called_once()

    def test_cwd_flag_uses_getcwd(self, tmp_path: Any) -> None:
        with (
            patch("flatpak_builder_lint.cli.run_checks", return_value={}) as mock_rc,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            self._run_main(["flatpak-builder-lint", "--cwd", "manifest", "/ignored"])
        mock_rc.assert_called_once()
        assert mock_rc.call_args[0][1] == str(tmp_path)

    def test_appid_override_passed_to_run_checks(self, tmp_path: Any) -> None:
        p = tmp_path / "x.json"
        p.write_text("{}")
        with patch("flatpak_builder_lint.cli.run_checks", return_value={}) as mock_rc:
            self._run_main(
                [
                    "flatpak-builder-lint",
                    "--appid",
                    "com.override.App",
                    "manifest",
                    str(p),
                ]
            )
        assert mock_rc.call_args[0][3] == ["com.override.App"]

    def test_ref_override_sets_repo_primary_refs(self, tmp_path: Any) -> None:
        with patch("flatpak_builder_lint.cli.run_checks", return_value={}):
            self._run_main(
                [
                    "flatpak-builder-lint",
                    "--ref",
                    "app/com.example.App/x86_64/stable",
                    "manifest",
                    str(tmp_path / "x.json"),
                ]
            )
        assert "app/com.example.App/x86_64/stable" in checks.Check.repo_primary_refs
