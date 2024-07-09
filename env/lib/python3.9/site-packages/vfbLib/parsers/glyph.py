from __future__ import annotations

import logging

from enum import Enum
from fontTools.misc.textTools import hexStr  # , num2binary
from fontTools.ttLib.tables.ttProgram import Program
from io import BytesIO
from struct import unpack
from typing import Any
from vfbLib.parsers.base import BaseParser, read_encoded_value
from vfbLib.parsers.guides import parse_guides
from vfbLib.truetype import TT_COMMANDS
from vfbLib.typing import (
    Anchor,
    Component,
    GdefDict,
    GlyphData,
    Hint,
    HintDict,
    Instruction,
    LinkDict,
    MaskData,
    MMAnchor,
    MMNode,
    Point,
)


logger = logging.getLogger(__name__)


class PathCommand(Enum):
    move = 0
    line = 1
    curve = 3
    qcurve = 4


def read_absolute_point(
    points: list[list[Any]],
    stream,
    num_masters: int,
    x_masters: list[int],
    y_masters: list[int],
):
    # Read coordinates for all masters from stream, add the points to a list
    # of points per master. Keep track of the relative coordinates reference
    # value in x_masters and y_masters.
    for m in range(num_masters):
        # End point
        xrel = read_encoded_value(stream)
        yrel = read_encoded_value(stream)
        x_masters[m] += xrel
        y_masters[m] += yrel
        points[m].append((x_masters[m], y_masters[m]))


class GlyphAnchorsParser(BaseParser):
    def _parse(self) -> list[MMAnchor]:
        stream = self.stream
        anchors = []
        num_anchors = read_encoded_value(stream)
        num_masters = read_encoded_value(stream)
        for _ in range(num_anchors):
            anchor = MMAnchor(x=[], y=[])
            for _ in range(num_masters):
                anchor["x"].append(read_encoded_value(stream))
                anchor["y"].append(read_encoded_value(stream))
            anchors.append(anchor)
        return anchors


class GlyphAnchorsSuppParser(BaseParser):
    def _parse(self) -> list:
        stream = self.stream
        anchors = []
        num_anchors = read_encoded_value(stream)
        for _ in range(num_anchors):
            a = read_encoded_value(stream)
            b = read_encoded_value(stream)
            anchors.append([a, b])
        return anchors


class GlyphGDEFParser(BaseParser):
    def _parse(self) -> GdefDict:
        stream = self.stream
        gdef: GdefDict = {}
        class_names = {
            0: "unassigned",
            1: "base",
            2: "ligature",
            3: "mark",
            4: "component",
        }
        glyph_class = read_encoded_value(stream)
        glyph_class_name = class_names.get(glyph_class, "unassigned")
        if glyph_class_name != "unassigned":
            gdef["glyph_class"] = glyph_class_name

        num_anchors = read_encoded_value(stream)
        anchors = []
        for _ in range(num_anchors):
            anchor_name_length = read_encoded_value(stream)
            name = None
            if anchor_name_length > 0:
                name = stream.read(anchor_name_length).decode(self.encoding)

            x = read_encoded_value(stream)
            x1 = read_encoded_value(stream)
            y = read_encoded_value(stream)
            y1 = read_encoded_value(stream)
            anchor = Anchor(x=x, x1=x1, y=y, y1=y1)
            if name:
                anchor["name"] = name
            anchors.append(anchor)
        if anchors:
            gdef["anchors"] = anchors

        num_carets = read_encoded_value(stream)
        carets = []
        for _ in range(num_carets):
            pos = read_encoded_value(stream)
            xxx = read_encoded_value(stream)
            carets.append((pos, xxx))
        if carets:
            gdef["carets"] = carets

        try:
            num_values = read_encoded_value(stream)
            values = [read_encoded_value(stream) for _ in range(num_values)]
            if values:
                gdef["unknown"] = values
        except EOFError:
            pass

        assert stream.read() == b""
        return gdef


class GlyphOriginParser(BaseParser):
    def _parse(self) -> dict[str, Any]:
        stream = self.stream
        x = int.from_bytes(stream.read(2), signed=True, byteorder="little")
        y = int.from_bytes(stream.read(2), signed=True, byteorder="little")
        return {"x": x, "y": y}


class GlyphParser(BaseParser):
    def parse_guides(
        self, stream: BytesIO, glyphdata: GlyphData, num_masters=1
    ) -> None:
        # Guidelines
        guides = parse_guides(stream, num_masters)
        if guides:
            glyphdata["guides"] = guides

    def parse_binary(self, stream: BytesIO, glyphdata: GlyphData) -> None:
        # Imported binary TrueType data
        imported: dict[str, Any] = {}
        while True:
            key = self.read_uint8()

            if key == 0x28:
                break

            elif key == 0x29:
                # Metrics
                imported["width"] = read_encoded_value(self.stream)
                imported["lsb"] = read_encoded_value(self.stream)
                imported["unknown1"] = read_encoded_value(self.stream)
                imported["unknown2"] = read_encoded_value(self.stream)
                imported["unknown3"] = read_encoded_value(self.stream)
                imported["bbox"] = [read_encoded_value(self.stream) for _ in range(4)]

            elif key == 0x2A:
                # Outlines
                num_contours = read_encoded_value(self.stream)
                imported["endpoints"] = [
                    read_encoded_value(self.stream) for _ in range(num_contours)
                ]
                num_nodes = read_encoded_value(self.stream)
                nodes = []
                # logger.debug(f"Parsing {num_nodes} nodes...")
                x = 0
                y = 0
                for i in range(num_nodes):
                    x += read_encoded_value(self.stream)
                    y += read_encoded_value(self.stream)
                    byte = self.read_uint8(stream)
                    flags = byte >> 4
                    cmd = byte & 0x0F
                    node = (hex(cmd), hex(flags), x, y)
                    # logger.debug(f"    {i}: {node}")
                    nodes.append(node)
                if nodes:
                    imported["nodes"] = nodes

            elif key == 0x2B:
                # Instructions
                num_instructions = read_encoded_value(self.stream)
                instructions = self.stream.read(num_instructions)
                p = Program()
                p.fromBytecode(instructions)
                imported["instructions"] = p.getAssembly()

            elif key == 0x2C:
                # Probably HDMX data
                num = read_encoded_value(self.stream)
                imported["hdmx"] = [self.read_uint8() for _ in range(num)]

            else:
                logger.error(imported)
                logger.error(f"Unknown key in imported binary glyph data: {hex(key)}")
                raise ValueError

        glyphdata["imported"] = imported

    def parse_components(
        self, stream: BytesIO, glyphdata: GlyphData, num_masters=1
    ) -> None:
        components = []
        num = read_encoded_value(stream)
        for i in range(num):
            gid = read_encoded_value(stream)
            c = Component(gid=gid, offsetX=[], offsetY=[], scaleX=[], scaleY=[])
            for _ in range(num_masters):
                x = read_encoded_value(stream)
                y = read_encoded_value(stream)
                scaleX, scaleY = unpack("dd", stream.read(16))
                c["offsetX"].append(x)
                c["offsetY"].append(y)
                c["scaleX"].append(scaleX)
                c["scaleY"].append(scaleY)
            components.append(c)
        glyphdata["components"] = components

    def parse_hints(self, stream: BytesIO, glyphdata: GlyphData, num_masters=1) -> None:
        hints = HintDict(v=[], h=[])
        for d in ("h", "v"):
            num_hints = read_encoded_value(stream)
            for _ in range(num_hints):
                master_hints = []
                for _ in range(num_masters):
                    pos = read_encoded_value(stream)
                    width = read_encoded_value(stream)
                    master_hints.append(Hint(pos=pos, width=width))
                hints[d].append(master_hints)

        num_hintmasks = read_encoded_value(stream)
        if num_hintmasks > 0:
            hintmasks: list[dict[str, int]] = []
            for i in range(num_hintmasks):
                k = self.read_uint8(stream)
                val = read_encoded_value(stream)
                mask = {}
                if k == 0x01:
                    # hintmask for hstem
                    if "h" in mask:
                        raise KeyError
                    mask["h"] = val  # num2binary(val, bits=8)
                elif k == 0x02:
                    # hintmask for vstem
                    if "v" in mask:
                        raise KeyError
                    mask["v"] = val  # num2binary(val, bits=8)
                elif k == 0xFF:
                    # Replacement point
                    # FIXME: This seems to be the node index of the replacement
                    # point. But sometimes it is negative, why?
                    mask["r"] = val
                hintmasks.append(mask)
            if hintmasks:
                hints["hintmasks"] = hintmasks

        if hints["v"] or hints["h"] or "hintmasks" in hints:
            glyphdata["hints"] = hints

    def parse_instructions(self, stream: BytesIO, glyphdata: GlyphData) -> None:
        # Number of bytes for instructions that follow;
        # we don't use it
        _ = read_encoded_value(stream)
        num_commands = read_encoded_value(stream)
        commands: list[Instruction] = []
        for i in range(num_commands):
            cmd = self.read_uint8(stream)
            params = [
                read_encoded_value(stream)
                for _ in range(len(TT_COMMANDS[cmd]["params"]))
            ]
            commands.append(
                Instruction(
                    cmd=TT_COMMANDS[cmd]["name"],
                    params=dict(zip(TT_COMMANDS[cmd]["params"], params)),
                )
            )
        # Instructions are ended by 3 * 0!?
        for _ in range(3):
            read_encoded_value(stream)

        if commands:
            glyphdata["tth"] = commands

    def parse_metrics(
        self, stream: BytesIO, glyphdata: GlyphData, num_masters=1
    ) -> None:
        metrics: list[Point] = []
        for _ in range(num_masters):
            master_metrics = (
                read_encoded_value(stream),
                read_encoded_value(stream),
            )
            metrics.append(master_metrics)
        glyphdata["metrics"] = metrics

    def parse_outlines(self, stream: BytesIO, glyphdata: GlyphData) -> int:
        # Nodes
        num_masters = read_encoded_value(stream)
        glyphdata["num_masters"] = num_masters

        # 2 x the number of values to be read after num_nodes, the reason is unclear.
        _ = read_encoded_value(stream)
        # glyphdata["num_node_values"] = num_node_values

        num_nodes = read_encoded_value(stream)
        segments: list[MMNode] = []
        x = [0 for _ in range(num_masters)]
        y = [0 for _ in range(num_masters)]

        for _ in range(num_nodes):
            byte = self.read_uint8(stream)
            flags = byte >> 4
            cmd = PathCommand(byte & 0x0F).name

            # End point
            points: list[list[Point]] = [[] for _ in range(num_masters)]
            read_absolute_point(points, stream, num_masters, x, y)

            if cmd == "curve":
                # First control point
                read_absolute_point(points, stream, num_masters, x, y)
                # Second control point
                read_absolute_point(points, stream, num_masters, x, y)

            segment = MMNode(type=cmd, flags=flags, points=points)
            segments.append(segment)
        glyphdata["nodes"] = segments
        return num_masters

    def parse_kerning(
        self, stream: BytesIO, glyphdata: GlyphData, num_masters=1
    ) -> None:
        num = read_encoded_value(stream)
        kerning = {}
        for _ in range(num):
            # Glyph index of right kerning partner
            gid = read_encoded_value(stream)
            values = []
            for _ in range(num_masters):
                # List of values, one value per master
                values.append(read_encoded_value(stream))
            kerning[gid] = values
        glyphdata["kerning"] = kerning

    def _parse(self) -> dict[str, Any]:
        """
        01090701
        01  92[7]2e 6e 6f 74 64 65 66 # Glyph name
        08  8c bb[48] 93[8]
            00 ab 8b    [  32,    0] move
            01 8b f9a0  [   0,  780] line 32,780
            01 f7fc 8b  [ 360,    0] line 392,780
            01 8b fda0  [   0, -780] line 392, 0
            00 fbcc bb  [-312,   48] move  80, 48
            01 f79c 8b  [ 264,    0] line
            01 8b f940  [   0,  684] line
            01 fb9c 8b  [-264,    0] line
        02  f83c 8b  [ 424,    0]
        03  8b 8b 8b
        04  8b 8b
        0a  a1[22] 8f[4] # TT hinting
            02 8b 8b
            04 8b 8c 89 8a
            04 8b 8f 89 8a
            04 8c 92 89 8a
            8b 8b 8b
        0f
        """
        s = self.stream
        glyphdata = GlyphData()
        start = unpack("<4B", s.read(4))
        if start != (1, 9, 7, 1):
            logger.warning(
                f"Unexpected glyph constant: {start}, please notify developer"
            )
        # glyphdata["constants"] = start
        num_masters = 1
        while True:
            # Read a value to decide what kind of information follows
            v = self.read_uint8(s)

            if v == 0x01:
                # Glyph name
                glyph_name_length = read_encoded_value(s)
                glyph_name = s.read(glyph_name_length)
                glyphdata["name"] = glyph_name.decode(self.encoding)
                logger.debug(f"Glyph: {glyphdata['name']}")

            elif v == 0x02:
                # Metrics
                self.parse_metrics(s, glyphdata, num_masters)

            elif v == 0x03:
                # PS Hints
                self.parse_hints(s, glyphdata, num_masters)

            elif v == 0x04:
                # Guides
                self.parse_guides(s, glyphdata, num_masters)

            elif v == 0x05:
                # Components
                self.parse_components(s, glyphdata, num_masters)

            elif v == 0x06:
                # Kerning
                self.parse_kerning(s, glyphdata, num_masters)

            elif v == 0x08:
                # Outlines
                num_masters = self.parse_outlines(s, glyphdata)

            elif v == 0x09:
                # Imported binary TrueType data
                self.parse_binary(s, glyphdata)

            elif v == 0x0A:
                # TrueType instructions
                self.parse_instructions(s, glyphdata)

            elif v == 0x0F:
                logger.debug("Glyph done.")
                break

            else:
                logger.error(f"Unhandled info field: {hex(v)}")
                logger.error(hexStr(s.read()))
                raise ValueError

        return dict(glyphdata)


class GlyphUnicodeParser(BaseParser):
    def _parse(self) -> list:
        unicodes = []
        for _ in range(self.stream.getbuffer().nbytes // 2):
            u = self.read_uint16(self.stream)
            unicodes.append(u)
        return unicodes


class GlyphUnicodeSuppParser(BaseParser):
    def _parse(self) -> list:
        unicodes = []
        for _ in range(self.stream.getbuffer().nbytes // 4):
            u = self.read_uint32(self.stream)
            unicodes.append(u)
        return unicodes


class LinkParser(BaseParser):
    def _parse(self) -> dict[str, Any]:
        s = self.stream
        links = LinkDict(x=[], y=[])
        for i in range(2):
            num = read_encoded_value(s)
            for _ in range(num):
                src = read_encoded_value(s)
                tgt = read_encoded_value(s)
                links["yx"[i]].append([src, tgt])
        return dict(links)


class MaskParser(GlyphParser):
    def _parse(self) -> dict[str, Any]:
        s = self.stream
        num = read_encoded_value(s)
        maskdata = MaskData(num=num)
        for i in range(num):
            maskdata[f"reserved{i}"] = read_encoded_value(s)

        # From here, the mask is equal to the outlines
        self.parse_outlines(s, maskdata)
        return dict(maskdata)
