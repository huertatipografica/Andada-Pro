from __future__ import annotations

import logging

from colorsys import hls_to_rgb
from typing import TYPE_CHECKING, Any
from vfbLib.ufo.vfb2ufo import vfb2ufo_label_codes

if TYPE_CHECKING:
    from vfbLib.typing import (
        Anchor,
        GuidePropertyList,
        GuideDict,
        HintDict,
        LinkDict,
        MMNode,
    )
    from vfbLib.ufo.builder import VfbToUfoBuilder
    from vfbLib.ufo.tth import TTGlyphHints


logger = logging.getLogger(__name__)


class VfbToUfoGlyph:
    def __init__(self, builder: VfbToUfoBuilder | None = None) -> None:
        self.builder = builder
        self.anchors: list[Anchor] = []
        self.guide_properties: GuidePropertyList = []
        self.hintmasks: list[dict[str, int]] = []
        self.labels: dict[str, int] = {}
        self.lib: dict[str, Any] = {}
        self.links: LinkDict = {}
        self.mm_anchors: list[Any] | None = None
        self.mm_components: list[Any] = []
        self.mm_guides: GuideDict | None = None
        self.mm_hints: HintDict = {"h": [], "v": []}
        self.mm_metrics: list[tuple[int, int]] = []
        self.mm_nodes: list[MMNode] = []
        self.name: str | None = None
        self.note: str | None = None
        self.point_labels: dict[int, str] = {}
        self.rename_points: dict[str, str]
        self.tt_glyph_hints: TTGlyphHints | None = None
        self.tth_commands: list[dict[str, str | bool]] = []
        self.unicodes: list[int] = []

    def get_point_label(self, index: int, code: str, start_count: int = 1) -> str:
        if self.mm_components:
            # Composite: We must add the label to the referenced glyph
            if self.builder is None:
                logger.error(
                    "To compile composite TrueType hinting, you must supply the"
                    "VfbToUfoBuilder to VfbToUfoGlyph.__init__()"
                )
                raise ValueError

            # Find the right component the point index belongs to
            orig_index = index
            total_num_nodes = 0
            for i, mm_component in enumerate(self.mm_components):
                component_name = self.builder.glyphOrder[mm_component["gid"]]
                component = self.builder.glyph_masters[component_name]
                num_nodes = len(component.mm_nodes)
                if index < num_nodes:
                    # Add the component index to the label to make it unique enough.
                    return f"{component.get_point_label(index, code)}-{i}"

                index -= num_nodes
                total_num_nodes += num_nodes

            # Side bearings may be hinted
            if orig_index == total_num_nodes:
                return "lsb"
            elif orig_index == total_num_nodes + 1:
                return "rsb"
            logger.error(
                f"Could not find point {orig_index} for hinted composite '{self.name}'."
                " TrueType hinting will be broken in UFO glyph."
            )
            return "invalid"

        if index in self.point_labels:
            # We already have a label for this point index
            return self.point_labels[index]

        # Special points
        num_nodes = len(self.mm_nodes)
        if index == num_nodes:
            return "lsb"
        elif index == num_nodes + 1:
            return "rsb"

        # Make a new label
        label_short = vfb2ufo_label_codes[code]
        i = start_count
        label = "%s%02d" % (label_short, i)
        while label in self.labels:
            i += 1
            label = "%s%02d" % (label_short, i)
        self.labels[label] = index
        self.point_labels[index] = label
        return label

    def set_mark(self, hue):
        self.lib["public.markColor"] = "%0.4f,%0.4f,%0.4f,1" % hls_to_rgb(
            h=hue / 255, l=0.8, s=0.76
        )

    def __eq__(self, other) -> bool:
        if len(self.mm_components) == len(other.mm_components):
            if self.name == other.name:
                return True

        return False

    def __gt__(self, other) -> bool:
        ns = len(self.mm_components)
        no = len(other.mm_components)
        if ns > no:
            return True
        if ns == no:
            if self.name > other.name:
                return True

        return False

    def __lt__(self, other) -> bool:
        ns = len(self.mm_components)
        no = len(other.mm_components)
        if ns < no:
            return True
        if ns == no:
            if self.name < other.name:
                return True

        return False
