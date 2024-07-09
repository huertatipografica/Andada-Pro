from __future__ import annotations

import logging

from fontTools.pens.pointPen import AbstractPointPen
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vfbLib.vfb.glyph import VfbGlyph, VfbGlyphMaster
    from vfbLib.vfb.vfb import Vfb


logger = logging.getLogger(__name__)


class VfbGlyphPointPen(AbstractPointPen):
    # FIXME: Only supports TrueType curves
    def __init__(self, glyph: VfbGlyph | VfbGlyphMaster, glyphSet: Vfb) -> None:
        """A PointPen to draw into the VFB glyph.

        Args:
            glyph (VfbGlyph): The glyph to draw into.
        """
        self.glyph = glyph
        self.glyphSet = glyphSet
        self.currentPath = None
        self.in_qcurve = False
        if self.glyph.master_index == 0:
            self.target = self.glyph.entry.decompiled
        else:
            if self.glyph.entry.temp_masters is None:
                self.glyph.entry.temp_masters = [[] * self.glyphSet.num_masters]
            self.target = self.glyph.entry.temp_masters[self.glyph.master_index]

    def beginPath(self) -> None:
        self.currentPath = []

    def endPath(self) -> None:
        if not isinstance(self.target, dict):
            raise TypeError

        if "nodes" not in self.target:
            self.target["nodes"] = []

        if self.currentPath is None:
            raise TypeError

        self.target["nodes"].extend(self.currentPath)
        self.currentPath = None

    def addPoint(
        self,
        pt: tuple[int, int],
        segmentType: str | None = None,
        smooth: bool = False,
        name: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        assert self.currentPath is not None

        flags = 0
        x, y = pt
        node = {
            "type": None,
            "flags": flags,
            "points": [
                [(round(x), round(y))] for _ in range(self.glyphSet.num_masters)
            ],
        }

        if segmentType == "qcurve":
            self.in_qcurve = True

        if not self.currentPath:
            # Begin a new path

            if segmentType == "move":  # Open path
                flags += 8

            # VFB first node always has type "move"
            node["type"] = "move"

        else:
            # During path
            if segmentType is None:
                node["type"] = "qcurve"
            elif segmentType == "qcurve":
                if self.in_qcurve:
                    node["type"] = "line"
                    self.in_qcurve = False
            elif segmentType == "line":
                node["type"] = "line"
            else:
                print(f"Unsupported segment type: {segmentType}")
                raise ValueError

        node["flags"] = flags
        self.currentPath.append(node)

    def addComponent(
        self,
        baseGlyphName: str,
        transformation: tuple[float, float, float, float, float, float],
        identifier: str | None = None,
        **kwargs: Any,
    ) -> None:
        assert self.currentPath is None
        base_index = self.glyphSet.glyph_order.index(baseGlyphName)
        if base_index == -1:
            raise KeyError(f"Base glyph not found: '{baseGlyphName}'")

        xx, xy, yx, yy, dx, dy = transformation

        if not isinstance(self.target, dict):
            raise TypeError

        if "components" not in self.target:
            self.target["components"] = []
        self.target["components"].append(
            {
                "gid": base_index,
                "offsetX": [dx] * self.glyphSet.num_masters,
                "offsetY": [dy] * self.glyphSet.num_masters,
                "scaleX": [xx] * self.glyphSet.num_masters,
                "scaleY": [yy] * self.glyphSet.num_masters,
            }
        )
