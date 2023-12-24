from typing import Optional, Set

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
    warnings: Set[Optional[str]] = set()
    errors: Set[Optional[str]] = set()
    jsonschema: Set[Optional[str]] = set()
    appstream: Set[Optional[str]] = set()
    repo_primary_ref: Optional[str] = None

    def _populate_ref(self, repo: str) -> None:
        if self.repo_primary_ref is None:
            self.repo_primary_ref = ostree.get_primary_ref(repo)
