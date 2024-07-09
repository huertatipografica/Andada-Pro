from __future__ import annotations

from io import BytesIO
from math import radians, tan
from struct import pack
from typing import Any
from vfbLib import GLYPH_CONSTANT
from vfbLib.compilers import BaseCompiler
from vfbLib.parsers.glyph import PathCommand
from vfbLib.truetype import TT_COMMAND_CONSTANTS, TT_COMMANDS

import logging


logger = logging.getLogger(__name__)


class GlyphCompiler(BaseCompiler):
    @classmethod
    def merge(cls, masters_data: list[Any], data: Any) -> None:
        num_masters = len(masters_data)
        if num_masters < 2:
            return

        for m in range(1, num_masters):
            master_data = masters_data[m]
            # See if there is any data to merge
            if "nodes" in master_data:
                assert "nodes" in data
                for i, tgt in enumerate(data["nodes"]):
                    src = master_data["nodes"][i]
                    for key in ("type", "flags"):
                        assert src[key] == tgt[key]
                    tgt["points"][m] = src["points"][m]

            if "components" in master_data:
                assert "components" in data
                for i, tgt in enumerate(data["components"]):
                    src = master_data["components"][i]
                    for key in ("gid",):
                        assert src[key] == tgt[key]
                    tgt["offsetX"][m] = src["offsetX"][m]
                    tgt["offsetY"][m] = src["offsetY"][m]
                    tgt["scaleX"][m] = src["scaleX"][m]
                    tgt["scaleY"][m] = src["scaleY"][m]

    def _compile_binary(self, data):
        # Imported binary data 8-)
        if not (imported := data.get("imported")):  # noqa: F841
            return

        logger.warning("Compiling imported binary data is not supported.")
        return

        self.write_uint1(9)

    def _compile_components(self, data):
        # Components
        if not (components := data.get("components")):
            return

        self.write_uint1(5)
        self.write_encoded_value(len(components))
        for component in components:
            self.write_encoded_value(component["gid"])
            for i in range(self.num_masters):
                self.write_encoded_value(component["offsetX"][i])
                self.write_encoded_value(component["offsetY"][i])
                self.write_float(component["scaleX"][i])
                self.write_float(component["scaleY"][i])

    def _compile_glyph_name(self, data):
        # Glyph name
        if not (name := data.get("name")):
            return

        glyph_name = name.encode("cp1252")
        glyph_name_length = len(glyph_name)
        self.write_uint1(1)
        self.write_encoded_value(glyph_name_length)
        self.write_bytes(glyph_name)
        logger.debug(f"Compiling glyph '{name}'")

    def _compile_guides(self, data):
        # Guidelines
        # TODO: Reuse for global guides
        if not (guides := data.get("guides")):
            return

        self.write_uint1(4)
        for direction in ("h", "v"):
            direction_guides = guides.get(direction)
            if direction_guides is None:
                self.write_encoded_value(0)
                continue

            self.write_encoded_value(len(direction_guides[0]))  # first master
            for m in range(self.num_masters):
                for guide in direction_guides[m]:
                    pos = guide["pos"]
                    angle = round(tan(radians(guide["angle"])) * 10000)
                    self.write_encoded_value(pos)
                    self.write_encoded_value(angle)

    def _compile_hints(self, data):
        # PostScript hints
        if not (hints := data.get("hints")):
            return

        self.write_uint1(3)
        for direction in ("h", "v"):
            if direction_hints := hints.get(direction):
                self.write_encoded_value(len(direction_hints))
                for mm_hint in direction_hints:
                    for i in range(self.num_masters):
                        hint = mm_hint[i]
                        self.write_encoded_value(hint["pos"])
                        self.write_encoded_value(hint["width"])
            else:
                self.write_encoded_value(0)

        if not (hintmasks := hints.get("hintmasks")):  # noqa: F841
            self.write_encoded_value(0)
            return

        # FIXME: Implement writing of hintmasks
        # self.write_encoded_value(len(hintmasks))
        self.write_encoded_value(0)
        logger.warning("Compilation of hint masks is not supported.")

    def _compile_instructions(self, data):
        # TrueType instructions
        if not (tth := data.get("tth")):
            return

        self.write_uint1(0x0A)
        instructions = InstructionsCompiler().compile(tth)
        self.write_encoded_value(len(instructions))
        self.stream.write(instructions)

    def _compile_kerning(self, data):
        # Kerning
        if not (kerning := data.get("kerning")):
            return

        self.write_uint1(6)
        self.write_encoded_value(len(kerning))
        for gid, values in kerning.items():
            self.write_encoded_value(gid)
            for value in values:
                self.write_encoded_value(value)

    def _compile_metrics(self, data):
        # Metrics
        if not (metrics := data.get("metrics")):
            return

        self.write_uint1(2)
        for i in range(self.num_masters):
            x, y = metrics[i]
            self.write_encoded_value(x)
            self.write_encoded_value(y)

    def _compile_outlines(self, data):
        # Outlines
        # A minimal outlines structure is always written:
        self.write_uint1(8)
        self.write_encoded_value(self.num_masters)  # Number of masters

        if not (nodes := data.get("nodes")):
            # 0 nodes with 0 values
            self.write_encoded_value(0)
            self.write_encoded_value(0)
            return

        outlines, num_values = OutlinesCompiler().compile(nodes, self.num_masters)
        self.write_encoded_value(num_values)
        self.stream.write(outlines)

    def _compile(self, data: Any) -> None:
        # Constants?
        self.write_bytes(pack("<4B", *GLYPH_CONSTANT))
        self.num_masters = data["num_masters"]

        self._compile_glyph_name(data)
        self._compile_outlines(data)
        self._compile_metrics(data)
        self._compile_hints(data)
        self._compile_guides(data)
        self._compile_components(data)
        self._compile_kerning(data)
        self._compile_binary(data)
        self._compile_instructions(data)
        self.write_uint1(15)  # End of glyph


class InstructionsCompiler(BaseCompiler):
    def _compile(self, data: Any) -> None:
        self.write_encoded_value(len(data))
        for cmd in data:
            command_id = TT_COMMAND_CONSTANTS[cmd["cmd"]]
            self.write_uint1(command_id)
            params = cmd["params"]
            for param_name in TT_COMMANDS[command_id]["params"]:
                self.write_encoded_value(params[param_name])
        for _ in range(3):
            self.write_encoded_value(0)


class OutlinesCompiler(BaseCompiler):
    def compile(self, data: Any, num_masters: int) -> tuple[bytes, int]:
        self.num_masters = num_masters
        assert not hasattr(self, "stream")
        self.stream = BytesIO()
        num_values = self._compile(data)
        return self.stream.getvalue(), num_values

    def _compile(self, data: Any) -> int:
        self.write_encoded_value(len(data))  # Number of nodes, may be 0
        num_values = 0
        ref_coords = [[0, 0] for _ in range(self.num_masters)]
        for node in data:
            type_flags = node.get("flags", 0) * 16 + PathCommand[node["type"]].value
            self.write_uint1(type_flags)
            num_values += 1
            for j in range(len(node["points"][0])):
                for i in range(self.num_masters):
                    x, y = node["points"][i][j]
                    refx, refy = ref_coords[i]
                    # Coordinates are written relatively to the previous coords
                    self.write_encoded_value(x - refx)
                    self.write_encoded_value(y - refy)
                    num_values += 2
                    ref_coords[i] = [x, y]
        return 2 * num_values
