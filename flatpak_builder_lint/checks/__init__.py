from typing import Optional, Set

ALL = []

ARCHES = {"x86_64", "aarch64"}


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
