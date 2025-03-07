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
    repo_primary_refs: ClassVar[set[str]] = set()

    def _populate_refs(self, repo: str) -> None:
        if not Check.repo_primary_refs:
            Check.repo_primary_refs.update(ostree.get_primary_refs(repo))
