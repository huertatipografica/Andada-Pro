from __future__ import annotations

import logging

from vfbLib.parsers.base import BaseParser, read_encoded_value


logger = logging.getLogger(__name__)


class NameRecordsParser(BaseParser):
    def _parse(self):
        stream = self.stream
        num = read_encoded_value(stream)
        result = []
        for _ in range(num):
            nameID = read_encoded_value(stream)
            platID = read_encoded_value(stream)
            encID = read_encoded_value(stream)
            langID = read_encoded_value(stream)
            name_length = read_encoded_value(stream)
            name_codes = [read_encoded_value(stream) for _ in range(name_length)]
            name = ""
            for c in name_codes:
                try:
                    char = chr(c)
                    # Fix platform-specific encodings for Mac
                    if platID == 1 and encID == 0:
                        # TODO: Remove default arguments when Python < 3.11 is dropped
                        char = c.to_bytes(length=1, byteorder="big").decode("macroman")
                except ValueError:
                    char = "\ufeff"
                name += char
            result.append([nameID, platID, encID, langID, name])

        assert stream.read() == b""
        return result


class OpenTypeClassParser(BaseParser):
    """
    A parser that reads data as strings and returns it formatted to represent an
    OpenType class
    """

    def _parse(self) -> dict[str, list[str] | str]:
        s = self.stream.read().decode(self.encoding).strip("\u0000 ")
        if ":" not in s:
            logger.warning(f"Malformed OpenType class: {s}")
            return {"str": s, "err": "PARSE_ERROR"}
            # raise ValueError

        name, contents = s.split(":")

        glyphs = []
        for glyph in contents.split(" "):
            glyph = glyph.strip()
            if glyph:
                glyphs.append(glyph)
        return {"name": name, "glyphs": glyphs}


class OpenTypeStringParser(BaseParser):
    """
    A parser that reads data as a strings and returns it as a list.
    """

    def _parse(self) -> list[str]:
        s = self.stream.read().decode(self.encoding).strip("\u0000 ")
        # Filter more than 2 consecutive empty lines
        lines = []
        c = 0
        for line in s.splitlines():
            if line.strip():
                c = 0
                lines.append(line)
            else:
                if c < 2:
                    lines.append(line)
                c += 1

        # Remove empty lines at the end, except one
        while not lines[-1]:
            lines.pop()
        lines.append("")
        return lines


class StringParser(BaseParser):
    """
    A parser that reads data as strings.
    """

    def _parse(self):
        return self.stream.read().decode(self.encoding).strip("\u0000 ")
