from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from flatpak_builder_lint import config


class CheckLike(Protocol):
    errors: set[str]
    warnings: set[str]
    info: set[str]


@dataclass(frozen=True)
class TimedSeverityPolicy:
    code: str
    promotion_date: date

    def is_enforced(self, today: date | None = None) -> bool:
        if config.SKIP_POLICY_ENFORCEMENT:
            return False

        if today is None:
            today = datetime.now(timezone.utc).date()
        return today >= self.promotion_date

    def severity(self, today: date | None = None) -> str:
        return "error" if self.is_enforced(today) else "warning"

    def promotion_date_str(self) -> str:
        d = self.promotion_date
        return f"{d.day} {d.strftime('%B %Y')} UTC"

    def format_message(self, base: str) -> str:
        return f"{base} (will become an error after '{self.promotion_date_str()}')."

    def apply(self, check: Any, base_message: str, today: date | None = None) -> None:
        msg = self.format_message(base_message)

        if self.is_enforced(today):
            check.errors.add(self.code)
        else:
            check.warnings.add(self.code)

        check.info.add(msg)


JSON_INVALID = TimedSeverityPolicy(
    code="manifest-invalid-json",
    promotion_date=date(2026, 12, 31),
)
