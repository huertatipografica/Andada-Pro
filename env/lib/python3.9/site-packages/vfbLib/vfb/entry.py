from __future__ import annotations

import logging

from fontTools.misc.textTools import hexStr
from functools import cached_property
from io import BytesIO
from struct import pack
from typing import TYPE_CHECKING, Any

# from vfbLib.reader import FALLBACK_PARSER
from vfbLib.compilers import BaseCompiler
from vfbLib.constants import parser_classes
from vfbLib.parsers.base import BaseParser

if TYPE_CHECKING:
    from io import BufferedReader
    from vfbLib.vfb.vfb import Vfb


logger = logging.getLogger(__name__)


FALLBACK_PARSER = BaseParser


class VfbEntry(BaseParser):
    def __init__(
        self,
        parent: Vfb,
        parser: type[BaseParser] | None = None,
        compiler: type[BaseCompiler] | None = None,
    ) -> None:
        # The original or compiled binary data
        self.data: bytes | None = None
        # The decompiled data
        self.decompiled: dict[str, Any] | int | list[Any] | str | None = None
        # Temporary data for additional master, must be merged when compiling
        self.temp_masters: list[list] | None = None
        # The numeric and human-readable key of the entry
        self.id = None
        self.key = None
        # Has the data been modified, i.e. it needs recompilation
        self._modified = False
        # The parser which can convert data to decompiled
        self.parser = parser
        # The compiler which can convert the decompiled to compiled data
        self.compiler = compiler
        # The parent object, Vfb
        self.vfb = parent

    @cached_property
    def header(self) -> bytes:
        """The entry header.

        Returns:
            bytes: The data of the current entry header.
        """
        header = BytesIO()
        if self.size > 0xFFFF:
            entry_id = self.id | 0x8000
        else:
            entry_id = self.id
        header.write(pack("<H", entry_id))
        if self.size > 0xFFFF:
            header.write(pack("<I", self.size))
        else:
            header.write(pack("<H", self.size))
        return header.getvalue()

    @cached_property
    def size(self) -> int:
        """The size of the compiled data.

        Returns:
            int: The size of the current compiled data.
        """
        return len(self.data)

    @property
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, value) -> None:
        self._modified = value
        if self._modified:
            try:
                delattr(self, "size")
            except AttributeError:
                pass
        else:
            self.size
        # Optimized version?
        # if value:
        #     if self._modified:
        #         # Value has not changed from True
        #         return

        #     # Value has changed from False to True, invalidate caches
        #     try:
        #         delattr(self, "size")
        #     except AttributeError:
        #         pass
        #     return

        # if self._modified:
        #     # Value changes from True to False
        #     self._modified = False
        #     return

        # # Value is False, no change

    def _read_entry(
        self,
    ) -> tuple[str, type[BaseParser], type[BaseCompiler] | None, int]:
        """
        Read an entry from the stream and return its key, specialized parser
        class, and data size.
        """
        self.id = self.read_uint16()
        entry_info = parser_classes.get(
            self.id & ~0x8000, (str(self.id), FALLBACK_PARSER, None)
        )
        key, parser_class, compiler_class = entry_info

        parser_class.encoding = self.vfb.encoding

        if self.id == 5:
            # File end marker?
            self.read_uint16()
            two = self.read_uint16()
            if two == 2:
                self.read_uint16()
                raise EOFError

        if self.id & 0x8000:
            # Uses uint32 for data length
            num_bytes = self.read_uint32()
        else:
            # Uses uint16 for data length
            num_bytes = self.read_uint16()

        return key, parser_class, compiler_class, num_bytes

    def as_dict(self, minimize=True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": str(self.key),
        }
        if minimize:
            if self.decompiled is None:
                d["size"] = self.size
                d["data"] = hexStr(self.data)
                if self.parser is not None:
                    d["parser"] = self.parser.__name__
            else:
                d["decompiled"] = self.decompiled
                if self.compiler is not None:
                    d["compiler"] = self.compiler.__name__
                if self.modified:
                    d["modified"] = True
        else:
            d["size"] = self.size
            d["data"] = hexStr(self.data)
            if self.parser is not None:
                d["parser"] = self.parser.__name__
            d["decompiled"] = self.decompiled
            if self.compiler is not None:
                d["compiler"] = self.compiler.__name__
            if self.modified:
                d["modified"] = True
        return d

    def clear_decompiled(self) -> None:
        self.decompiled = None

    def compile(self) -> None:
        """
        Compile the entry. The result is stored in VfbEntry.data.
        """
        if self.compiler is None:
            logger.error(f"Compiling '{self.key}' is not supported yet.")
            return

        self.merge_masters_data()

        self.data = self.compiler().compile(
            self.decompiled, master_count=self.vfb.num_masters
        )
        self.modified = False

    def decompile(self) -> None:
        """
        Decompile the entry. The result is stored in VfbEntry.decompiled.
        """
        if self.decompiled is not None:
            # Already decompiled
            logger.error(
                f"Entry is already decompiled: {self.key}. If you really want to "
                "decompile again, clear the decompiled data beforehand using "
                "`clear_decompiled()`."
            )
            raise ValueError

        if self.parser is None:
            raise ValueError

        if self.data is None:
            raise ValueError

        try:
            self.decompiled = self.parser().parse(
                BytesIO(self.data),
                size=self.size,
                master_count=self.vfb.num_masters,
                ttStemsV_count=self.vfb.ttStemsV_count,
                ttStemsH_count=self.vfb.ttStemsH_count,
            )
        except:  # noqa: E722
            logger.error(f"Parse error for data: {self.key}; {hexStr(self.data)}")
            logger.error(f"Parser class: {self.parser.__name__}")
            self.decompiled = None
            raise

    def merge_masters_data(self) -> None:
        """
        Merge any temporary masters data into the main decompiled structure. Such data
        can be added as the result of drawing with a PointPen into a multiple master
        Vfb.
        """
        if self.temp_masters is None:
            return

        if self.vfb.num_masters == 1:
            return

        if self.compiler is None:
            return

        self.compiler.merge(self.temp_masters, self.decompiled)

    def read(self, stream: BufferedReader) -> None:
        """
        Read the entry from the stream without decompiling the data.
        """
        self.stream = stream
        self.key, self.parser, self.compiler, size = self._read_entry()
        if self.key == "1410":
            # FIXME: Special FL3 stuff?
            if size != 4:
                print(f"Entry 1410 with size {size}")
            self.data = self.stream.read(10)
        else:
            self.data = self.stream.read(size)
