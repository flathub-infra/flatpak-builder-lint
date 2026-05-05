from datetime import date

from flatpak_builder_lint.policy import TimedSeverityPolicy


class DummyCheck:
    def __init__(self) -> None:
        self.errors: set[str] = set()
        self.warnings: set[str] = set()
        self.info: set[str] = set()


class TestTimedSeverityPolicy:
    def test_is_enforced_before_cutoff(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))
        assert not policy.is_enforced(date(2026, 12, 30))

    def test_is_enforced_on_cutoff(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))
        assert policy.is_enforced(date(2026, 12, 31))

    def test_severity(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))

        assert policy.severity(date(2026, 12, 30)) == "warning"
        assert policy.severity(date(2026, 12, 31)) == "error"

    def test_promotion_date_str(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))
        assert policy.promotion_date_str() == "31 December 2026 UTC"

    def test_format_message(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))

        msg = policy.format_message("base message", today=date(2026, 12, 30))

        assert msg == (
            "base message (will become an error after '31 December 2026 UTC': '1' day remaining)."
        )

    def test_apply_before_cutoff(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))
        check = DummyCheck()

        policy.apply(check, "message", today=date(2026, 12, 30))

        assert "test-code" in check.warnings
        assert "test-code" not in check.errors
        assert any("'1' day remaining" in m for m in check.info)

    def test_apply_after_cutoff(self) -> None:
        policy = TimedSeverityPolicy("test-code", date(2026, 12, 31))
        check = DummyCheck()

        policy.apply(check, "message", today=date(2026, 12, 31))

        assert "test-code" in check.errors
        assert "test-code" not in check.warnings
        assert any("message" in m for m in check.info)

    def test_format_message_with_extra_info(self) -> None:
        policy = TimedSeverityPolicy(
            "test-code",
            date(2026, 12, 31),
            extra_info_msg="Additional context here.",
        )

        msg = policy.format_message("base message", today=date(2026, 12, 30))
        assert msg == (
            "base message (will become an error after '31 December 2026 UTC': '1' day remaining)."
            " Additional context here."
        )

    def test_apply_includes_extra_info(self) -> None:
        policy = TimedSeverityPolicy(
            "test-code",
            date(2026, 12, 31),
            extra_info_msg="Extra info.",
        )
        check = DummyCheck()

        policy.apply(check, "message", today=date(2026, 12, 30))

        assert any("Extra info." in m for m in check.info)
