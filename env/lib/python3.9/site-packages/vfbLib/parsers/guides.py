from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Literal, Sequence
from math import atan2, degrees
from vfbLib.parsers.base import BaseParser, read_encoded_value
from vfbLib.typing import Guide, GuideDict, GuideProperty

if TYPE_CHECKING:
    from io import BytesIO


logger = logging.getLogger(__name__)


DIRECTIONS: Sequence[Literal["h", "v"]] = ("h", "v")


def parse_guides(stream: BytesIO, num_masters: int) -> GuideDict:
    # Common parser for glyph and global guides
    guides: GuideDict = {
        "h": [[] for _ in range(num_masters)],
        "v": [[] for _ in range(num_masters)],
    }
    for d in DIRECTIONS:
        num_guides = read_encoded_value(stream)
        for _ in range(num_guides):
            for m in range(num_masters):
                pos = read_encoded_value(stream)
                angle = degrees(atan2(read_encoded_value(stream), 10000))
                guides[d][m].append(Guide(pos=pos, angle=angle))

    return guides


class GlobalGuidesParser(BaseParser):
    def _parse(self) -> GuideDict:
        assert self.master_count is not None
        guides = parse_guides(self.stream, self.master_count)
        assert self.stream.read() == b""
        return guides


class GuidePropertiesParser(BaseParser):
    def _parse(self) -> list:
        stream = self.stream
        guides = []
        for _ in range(2):
            while True:
                index = read_encoded_value(stream)
                if index == 0:
                    break

                g = GuideProperty(index=index)

                color = read_encoded_value(stream)
                if color > -1:
                    g["color"] = "#" + hex(color & ~0xFF00000000)[2:]

                name_length = read_encoded_value(stream)
                if name_length > 0:
                    name = self.stream.read(name_length).decode("cp1252")
                    g["name"] = name

                guides.append(g)

        assert stream.read() == b""
        return guides
