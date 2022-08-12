from typing import List, Optional

ALL = []


class CheckMeta(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if object in cls.__bases__:
            # Don't register base class
            return
        ALL.append(cls)


class Check(metaclass=CheckMeta):
    warnings: List[Optional[str]] = []
    errors: List[Optional[str]] = []
