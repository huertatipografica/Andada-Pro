from __future__ import annotations

import logging

from vfbLib.parsers.base import BaseParser
from struct import unpack


logger = logging.getLogger(__name__)


class DoubleParser(BaseParser):
    """
    A parser that reads data as a double-size float.
    """

    def _parse(self):
        return unpack("d", self.stream.read(8))[0]


class FloatListParser(BaseParser):
    """
    A parser that reads data as a list of floats.
    """

    __size__ = 4
    __fmt__ = "f"

    def _parse(self):
        values = []
        for _ in range(self.stream.getbuffer().nbytes // self.__size__):
            values.extend(unpack(self.__fmt__, self.stream.read(self.__size__)))

        return values


class DoubleListParser(FloatListParser):
    """
    A parser that reads data as a list of doubles.
    """

    __size__ = 8
    __fmt__ = "d"


class IntParser(BaseParser):
    """
    A parser that reads data as UInt16.
    """

    def _parse(self):
        return int.from_bytes(self.stream.read(), byteorder="little", signed=False)


class IntListParser(BaseParser):
    """
    A parser that reads data as a list of UInt16.
    """

    __size__ = 4

    def _parse(self):
        values = []
        for _ in range(self.stream.getbuffer().nbytes // self.__size__):
            values.append(
                int.from_bytes(
                    self.stream.read(self.__size__),
                    byteorder="little",
                    signed=False,
                )
            )
        return values


class PanoseParser(BaseParser):
    """
    A parser that reads data as an array representing PANOSE values.
    """

    def _parse(self):
        return unpack("<10b", self.stream.read())


class SignedIntParser(BaseParser):
    """
    A parser that reads data as signed Int16.
    """

    def _parse(self):
        return int.from_bytes(self.stream.read(), byteorder="little", signed=True)
