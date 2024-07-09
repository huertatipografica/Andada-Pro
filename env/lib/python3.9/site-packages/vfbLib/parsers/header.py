from __future__ import annotations

import logging

from io import BufferedReader
from typing import Any
from vfbLib.parsers.base import read_encoded_value, uint8, uint16


logger = logging.getLogger(__name__)


class VfbHeaderParser:
    stream: BufferedReader | None = None

    def parse(self, stream: BufferedReader) -> tuple[dict[str, Any], int]:
        self.stream = stream
        header: dict[str, Any] = {}
        header["header0"] = self.read_uint8()
        header["filetype"] = self.stream.read(5).decode("cp1252")
        header["header1"] = self.read_uint16()
        header["header2"] = self.read_uint16()
        header["reserved"] = str(self.stream.read(34))
        header["header3"] = self.read_uint16()
        header["header4"] = self.read_uint16()
        header["header5"] = self.read_uint16()
        header["header6"] = self.read_uint16()
        header["header7"] = self.read_uint16()
        if header["header7"] == 10:
            # FL5 additions over FL3
            header["header8"] = self.read_uint16()
            for i in range(9, 12):
                key = self.read_uint8()
                val = read_encoded_value(stream)
                header[f"header{i}"] = {key: val}
            header["header12"] = self.read_uint8()
            header["header13"] = self.read_uint16()
        else:
            header["header13"] = header["header7"]
            del header["header7"]
        header["header14"] = self.read_uint16()

        # Get the size of the original binary data
        datasize = self.stream.tell()

        return header, datasize

    def read_uint8(self) -> int:
        assert self.stream is not None
        return int.from_bytes(self.stream.read(uint8), byteorder="little", signed=False)

    def read_uint16(self) -> int:
        assert self.stream is not None
        return int.from_bytes(
            self.stream.read(uint16), byteorder="little", signed=False
        )
