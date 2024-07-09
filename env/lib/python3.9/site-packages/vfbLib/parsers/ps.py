from __future__ import annotations

import logging

from vfbLib.parsers.base import BaseParser


logger = logging.getLogger(__name__)


class PostScriptInfoParser(BaseParser):
    """
    A parser that reads data as a double-size float.
    """

    def _parse(self):
        values = {}
        values["font_matrix"] = self.read_doubles(6)
        values["force_bold"] = self.read_int32()
        values["blue_values"] = [self.read_int32() for _ in range(14)]
        values["other_blues"] = [self.read_int32() for _ in range(10)]
        values["family_blues"] = [self.read_int32() for _ in range(14)]
        values["family_other_blues"] = [self.read_int32() for _ in range(10)]
        values["blue_scale"] = self.read_double()
        values["blue_shift"] = self.read_uint32()
        values["blue_fuzz"] = self.read_uint32()
        values["std_hw"] = self.read_uint32()
        values["std_vw"] = self.read_uint32()
        values["stem_snap_h"] = [self.read_uint32() for _ in range(12)]
        values["stem_snap_v"] = [self.read_uint32() for _ in range(12)]
        # The bounding box values only get updated during some actions, e.g.
        # going into PS hinting mode
        values["bounding_box"] = dict(
            zip(
                ["xMin", "yMin", "xMax", "yMax"],
                [self.read_int16() for _ in range(4)],
            )
        )
        values["adv_width_min"] = self.read_int32()
        values["adv_width_max"] = self.read_int32()
        values["adv_width_avg"] = self.read_int32()
        values["ascender"] = self.read_int32()
        values["descender"] = self.read_int32()
        values["x_height"] = self.read_int32()
        values["cap_height"] = self.read_int32()
        assert self.stream.read() == b""
        return values
