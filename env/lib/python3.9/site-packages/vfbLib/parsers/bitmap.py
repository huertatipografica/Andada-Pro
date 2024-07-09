from __future__ import annotations

import logging

from fontTools.misc.textTools import num2binary

# from math import log2
# from struct import unpack
from typing import Any
from vfbLib.parsers.base import BaseParser, read_encoded_value


logger = logging.getLogger(__name__)


def pprint_bitmap(bitmap, invert=False) -> list[str]:
    print(bitmap)
    w, h = bitmap["size_pixels"]
    data = bitmap["data"]
    col_bytes = w // 8
    rest = w % 8
    if rest > 0:
        col_bytes += 1
    col_bytes = max(col_bytes, 2)
    # print(f"Cols: {w}, bytes per line: {col_bytes}")
    if "bytes" not in data:
        b = []
    else:
        b = data["bytes"]
    gfx = []
    for y in range(0, h * col_bytes, col_bytes):
        col = ""
        for x in range(col_bytes):
            i = y + x
            if i < len(b):
                byte = b[i]
            else:
                byte = 0

            # print(f"Index: {i}, value: {byte}")
            col += num2binary(byte, bits=8).replace("0", "  ").replace("1", "██")
        gfx.append(col[: w * 2])
    if invert:
        gfx.reverse()
    print("\n".join(gfx))
    print(gfx)
    return gfx


class BaseBitmapParser(BaseParser):
    def parse_bitmap_data(self, datalen) -> dict[str, Any]:
        bitmap: dict[str, Any] = {}
        if datalen < 2:
            logger.error("parse_bitmap_data: Got datalen", datalen)
            raise ValueError

        rest = 2

        if datalen > 2:
            num_bytes = self.read_uint8()
            bitmap["num_bytes"] = num_bytes
            data = []
            for _ in range(num_bytes):
                data.append(self.read_uint8())
            bitmap["bytes"] = data
            rest = datalen - num_bytes - 1

        extra = []
        for _ in range(rest):
            extra.append(self.read_uint8())

        if extra:
            bitmap["extra"] = extra

        return bitmap


class BackgroundBitmapParser(BaseBitmapParser):
    def _parse(self) -> dict[str, Any]:
        s = self.stream
        bitmap: dict[str, Any] = {}
        bitmap["origin"] = (read_encoded_value(s), read_encoded_value(s))
        bitmap["size_units"] = (read_encoded_value(s), read_encoded_value(s))
        bitmap["size_pixels"] = (read_encoded_value(s), read_encoded_value(s))
        datalen = read_encoded_value(s)
        bitmap["len"] = datalen
        bitmap["data"] = self.parse_bitmap_data(datalen)
        # bitmap["preview"] = pprint_bitmap(bitmap)
        assert s.read() == b""
        return bitmap


class GlyphBitmapParser(BaseBitmapParser):
    def _parse(self) -> list[dict[str, Any]]:
        s = self.stream
        bitmaps: list[dict[str, Any]] = []
        num_bitmaps = read_encoded_value(s)
        for _ in range(num_bitmaps):
            bitmap: dict[str, Any] = {}
            bitmap["ppm"] = read_encoded_value(s)
            bitmap["origin"] = (read_encoded_value(s), read_encoded_value(s))
            bitmap["adv"] = (read_encoded_value(s), read_encoded_value(s))
            bitmap["size_pixels"] = (read_encoded_value(s), read_encoded_value(s))
            datalen = read_encoded_value(s)
            bitmap["len"] = datalen
            bitmap["data"] = self.parse_bitmap_data(datalen)
            # bitmap["preview"] = pprint_bitmap(bitmap, invert=True)
            bitmaps.append(bitmap)
        assert s.read() == b""
        return bitmaps
