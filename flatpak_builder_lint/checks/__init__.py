from typing import ClassVar

from .. import ostree

ALL = []


class CheckMeta(type):
    def __init__(cls, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        if object in cls.__bases__:
            # Don't register base class
            return
        ALL.append(cls)


class Check(metaclass=CheckMeta):
    warnings: ClassVar[set[str]] = set()
    errors: ClassVar[set[str]] = set()
    jsonschema: ClassVar[set[str]] = set()
    appstream: ClassVar[set[str]] = set()
    desktopfile: ClassVar[set[str]] = set()
    info: ClassVar[set[str]] = set()
    repo_primary_ref: str | None = None

    def _populate_ref(self, repo: str) -> None:
        if self.repo_primary_ref is None:
            self.repo_primary_ref = ostree.get_primary_ref(repo)
