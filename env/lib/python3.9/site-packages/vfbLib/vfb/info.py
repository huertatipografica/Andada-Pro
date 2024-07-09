from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vfbLib.vfb.vfb import Vfb


class VfbInfo:
    def __init__(self, vfb: Vfb) -> None:
        self.parent = vfb

    @cached_property
    def unitsPerEm(self) -> int:
        for entry in self.parent.entries:
            if entry.key == "upm":
                entry.decompile()
                if entry.decompiled is None:
                    return 0
                return entry.decompiled
        return 0
