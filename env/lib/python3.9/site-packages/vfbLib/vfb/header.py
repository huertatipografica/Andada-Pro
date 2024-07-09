from __future__ import annotations

import logging

from fontTools.misc.textTools import hexStr
from typing import TYPE_CHECKING, Any
from vfbLib.parsers.header import VfbHeaderParser

if TYPE_CHECKING:
    from io import BufferedReader


logger = logging.getLogger(__name__)


class VfbHeader:
    def __init__(self) -> None:
        # The original or compiled binary data
        self.data: bytes | None = None
        # The decompiled data
        self.decompiled = None
        # Has the data been modified, i.e. it needs recompilation
        self.modified = False
        # The parser which can convert data to decompiled
        self.parser = VfbHeaderParser
        # The size of the compiled data
        self.size = 0

    def as_dict(self) -> dict[str, Any]:
        d = {
            "size": self.size,
            "decompiled": self.decompiled,
            "modified": self.modified,
            "parser": self.parser.__name__,
        }
        if self.data:
            d["data"] = hexStr(self.data)
        return d

    def compile(self) -> bytes:
        logger.error("Compiling the VFB header is not supported yet.")

        if self.data:
            self.size = len(self.data)
        else:
            self.size = 0

        self.modified = False

        if self.data is None:
            return b""

        return self.data

    def read(self, stream: BufferedReader) -> None:
        self.decompiled, self.size = self.parser().parse(stream)
        stream.seek(0)
        self.data = stream.read(self.size)
