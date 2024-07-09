from __future__ import annotations

import logging

from fontTools.pens.pointPen import (
    AbstractPointPen,
    PointToSegmentPen,
    SegmentToPointPen,
)
from functools import cached_property
from typing import TYPE_CHECKING
from vfbLib.ufo.glyph import VfbToUfoGlyph
from vfbLib.ufo.paths import UfoMasterGlyph
from vfbLib.templates.glyph import get_empty_glyph
from vfbLib.vfb.pens import VfbGlyphPointPen

if TYPE_CHECKING:
    from fontTools.pens.basePen import AbstractPen
    from vfbLib.vfb.vfb import Vfb, VfbMaster
    from vfbLib.vfb.entry import VfbEntry


logger = logging.getLogger(__name__)


class VfbGlyph:
    def __init__(self, entry: VfbEntry, parent: Vfb | VfbMaster) -> None:
        self.entry = entry
        self._parent = parent
        self._glyph: UfoMasterGlyph | None = None
        self.master_index = 0

    # UFO/cu2qu compatibility

    @cached_property
    def name(self) -> str:
        return self._glyph.name

    def clearContours(self):
        try:
            del self.entry.decompiled["hints"]
        except KeyError:
            pass
        self.entry.decompiled["nodes"] = []
        self.entry.modified = True

    # Native methods

    def decompile(self) -> str:
        """
        Decompile the Glyph entry and return the glyph name.
        """
        self.entry.decompile()
        if self.entry.decompiled is None:
            raise ValueError

        return self.entry.decompiled["name"]

    def empty(self):
        self.entry.decompiled = get_empty_glyph(self._parent.num_masters)

    def _copy_to_ufo_glyph(self):
        """
        Copy minimal data to the VfbToUfoGlyph. Only data that is necessary for the pen
        methods is copied.
        """
        if self.entry.decompiled is None:
            raise ValueError

        _mm_glyph = VfbToUfoGlyph()
        _mm_glyph.name = self.entry.decompiled["name"]

        if "components" in self.entry.decompiled:
            _mm_glyph.mm_components = self.entry.decompiled["components"]

        if "metrics" in self.entry.decompiled:
            _mm_glyph.mm_metrics = self.entry.decompiled["metrics"]

        if "nodes" in self.entry.decompiled:
            _mm_glyph.mm_nodes = self.entry.decompiled["nodes"]

        # TODO: Support point names used by TT hinting
        # if "tth" in self.entry.decompiled:
        #     _mm_glyph.tth_commands = self.entry.decompiled["tth"]

        self._glyph = UfoMasterGlyph(
            mm_glyph=_mm_glyph,
            glyph_order=self._parent.glyph_order,
            master_index=self._parent.master_index,
        )
        self._glyph.build()

    def draw(self, pen) -> None:
        """
        Draw the VFB glyph onto a segment pen.
        """
        sp = PointToSegmentPen(pen, outputImpliedClosingLine=False)
        self.drawPoints(sp)

    def drawPoints(self, pen: AbstractPointPen) -> None:
        """
        Draw the VFB glyph onto a point pen.
        """
        if self.entry.decompiled is None:
            raise ValueError

        if self._glyph is None:
            self._copy_to_ufo_glyph()

        if self._glyph is None:
            raise ValueError

        return self._glyph.drawPoints(pen)

    def getPen(self) -> AbstractPen:
        """
        Return a segment pen to draw into the VFB glyph.
        """
        # TODO: Test
        return SegmentToPointPen(self.getPointPen(), guessSmooth=True)

    def getPointPen(self) -> VfbGlyphPointPen:
        """
        Return a point pen to draw into the VFB glyph.
        """
        if self.entry.decompiled is None:
            if self.entry.data is None:
                # Make an empty glyph
                self.empty(self._parent.num_masters)
            else:
                self.decompile()
        return VfbGlyphPointPen(self, self._parent)


class VfbGlyphMaster:
    def __init__(self, glyph: VfbGlyph, master_index: int = 0):
        self.glyph = glyph
        self.entry = glyph.entry
        self.master_index = master_index
        self._glyph = None

    @cached_property
    def name(self) -> str:
        return self._glyph.name

    def _copy_to_ufo_glyph(self, master_index):
        """
        Copy minimal data to the VfbToUfoGlyph. Only data that is necessary for the pen
        methods is copied.
        """
        if self.entry.decompiled is None:
            raise ValueError

        _mm_glyph = VfbToUfoGlyph()
        _mm_glyph.name = self.entry.decompiled["name"]

        if "components" in self.entry.decompiled:
            _mm_glyph.mm_components = self.entry.decompiled["components"]

        if "metrics" in self.entry.decompiled:
            _mm_glyph.mm_metrics = self.entry.decompiled["metrics"]

        if "nodes" in self.entry.decompiled:
            _mm_glyph.mm_nodes = self.entry.decompiled["nodes"]

        # TODO: Support point names used by TT hinting
        # if "tth" in self.entry.decompiled:
        #     _mm_glyph.tth_commands = self.entry.decompiled["tth"]

        self._glyph = UfoMasterGlyph(
            mm_glyph=_mm_glyph,
            glyph_order=self.glyph._parent.glyph_order,
            master_index=master_index,
        )
        self._glyph.build()

    def clearContours(self):
        if self.master_index == 0:
            target = self.entry.decompiled
        else:
            if self.entry.temp_masters is None:
                self.entry.temp_masters = [
                    {} for _ in range(self.glyph._parent.num_masters)
                ]
            target = self.entry.temp_masters[self.master_index]
        try:
            del target["hints"]
        except KeyError:
            pass
        target["nodes"] = []
        self.entry.modified = True

    def drawPoints(self, pen: AbstractPointPen) -> None:
        """
        Draw the VFB glyph onto a point pen.
        """
        if self.entry.decompiled is None:
            raise ValueError

        if self._glyph is None:
            self._copy_to_ufo_glyph(self.master_index)

        if self._glyph is None:
            raise ValueError

        return self._glyph.drawPoints(pen)

    def getPen(self) -> AbstractPen:
        """
        Return a segment pen to draw into the VFB glyph.
        """
        # TODO: Test
        return SegmentToPointPen(self.getPointPen(), guessSmooth=True)

    def getPointPen(self) -> VfbGlyphPointPen:
        """
        Return a point pen to draw into the VFB glyph.
        """
        if self.entry.decompiled is None:
            if self.entry.data is None:
                # Make an empty glyph
                self.empty(self.glyph._parent.num_masters)
            else:
                self.decompile()
        return VfbGlyphPointPen(self, self.glyph._parent)
