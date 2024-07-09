from __future__ import annotations

import logging

from base64 import b64encode
from copy import deepcopy
from typing import Any, TYPE_CHECKING
from vfbLib.ufo.guides import apply_guide_properties, get_master_guides
from vfbLib.ufo.pshints import build_ps_glyph_hints, get_master_hints
from vfbLib.ufo.tth import set_tth_lib
from vfbLib.ufo.vfb2ufo import TT_GLYPH_LIB_KEY

if TYPE_CHECKING:
    from fontTools.pens.pointPen import AbstractPointPen
    from vfbLib.typing import Anchor
    from vfbLib.ufo.glyph import VfbToUfoGlyph
    from vfbLib.ufo.typing import UfoComponent, UfoContour


logger = logging.getLogger(__name__)


class UfoMasterGlyph:
    def __init__(
        self,
        mm_glyph: VfbToUfoGlyph,
        glyph_order: list[str],
        master_index: int,
    ) -> None:
        self.mm_glyph = mm_glyph
        self.glyph_order = glyph_order
        self.master_index = master_index

        self.lib: dict[str, Any] = {}
        self.anchors: list[Anchor] = []
        self.guidelines: list = []
        self.unicodes: list[int] = []
        self.width: int = 0
        self.height: int = 0

        self.components: list[UfoComponent] = []
        self.contours: list[UfoContour] = []
        self.rename_points: dict[str, str] = {}
        self.tth_commands: list[dict[str, str | bool]] = []

    @property
    def name(self) -> str | None:
        return self.mm_glyph.name

    def build(
        self,
        minimal: bool = False,
        include_ps_hints: bool = True,
        encode_data_base64: bool = False,
    ) -> None:
        # Extract the single master glyph from an mm glyph. The main method.
        # Copy glyph lib
        self.lib = deepcopy(self.mm_glyph.lib)
        self.tth_commands = deepcopy(self.mm_glyph.tth_commands)
        if include_ps_hints:
            self._extract_master_ps_hints()
        self._extract_master_tt_hints()
        self._extract_master_contours()
        self._finalize_point_labels(include_ps_hints)
        self._extract_master_anchors()
        if not minimal:
            self._extract_master_guides()
        self._finalize_lib(encode_data_base64)
        self.unicodes = self.mm_glyph.unicodes.copy()
        self.width, self.height = self.mm_glyph.mm_metrics[self.master_index]

    def drawPoints(self, pen: AbstractPointPen) -> None:
        """
        Draw the glyph onto the supplied point pen.
        """
        for contour in self.contours:
            pen.beginPath()
            for segment_type, smooth, name, pt in contour:
                pen.addPoint(pt, segment_type, name=name, smooth=smooth)
            pen.endPath()

        for gn, tr in self.components:
            pen.addComponent(gn, tr)

    def _extract_master_anchors(self) -> None:
        if self.mm_glyph.anchors is None:
            return

        # Copy anchors from the mm glyph
        self.anchors = deepcopy(self.mm_glyph.anchors)

        if self.mm_glyph.mm_anchors is None:
            return

        # Apply master anchor positions
        for j, anchor in enumerate(self.mm_glyph.mm_anchors):
            self.anchors[j]["x"] = anchor["x"][self.master_index]
            self.anchors[j]["y"] = anchor["y"][self.master_index]

    def _extract_master_contours(self) -> None:
        """
        Extract the contours and components from the mm contours.
        """
        self.contours = []
        self.rename_points = {}
        path_is_open = False
        in_qcurve = False
        if hasattr(self.mm_glyph, "mm_nodes"):
            contour: UfoContour = []
            for i, n in enumerate(self.mm_glyph.mm_nodes):
                name: str | None = self.mm_glyph.point_labels.get(i, None)
                nodes = n["points"][self.master_index]
                pt = nodes[0]
                segment_type = n["type"]
                flags = n["flags"]
                smooth = bool(flags & 1)

                if segment_type == "move":
                    self._append_contour(contour, path_is_open)
                    contour = [("move", smooth, name, pt)]
                    path_is_open = bool(flags & 8)
                    in_qcurve = False

                elif segment_type == "line":
                    if in_qcurve:
                        contour.append(("qcurve", smooth, name, pt))
                        in_qcurve = False
                    else:
                        contour.append(("line", smooth, name, pt))

                elif segment_type == "curve":
                    pt, c1, c2 = nodes
                    contour.append((None, False, None, c1))
                    contour.append((None, False, None, c2))
                    contour.append(("curve", smooth, name, pt))
                    in_qcurve = False

                elif segment_type == "qcurve":
                    contour.append((None, False, name, pt))
                    in_qcurve = True

                else:
                    logger.error(f"Unknown segment type: {segment_type}")
                    raise ValueError

            self._append_contour(contour, path_is_open)

        self.components = []
        if hasattr(self.mm_glyph, "mm_components"):
            for c in self.mm_glyph.mm_components:
                xx: float | int = c["scaleX"][self.master_index]
                # The xy and yx components of the matrix are always 0
                # xy = 0
                # yx = 0
                yy: float | int = c["scaleY"][self.master_index]
                dx: int = c["offsetX"][self.master_index]
                dy: int = c["offsetY"][self.master_index]
                # Convert to integer to avoid type differences in the UFO pre/post save
                if xx.is_integer():
                    xx = int(xx)
                if yy.is_integer():
                    yy = int(yy)
                self.components.append(
                    (self.glyph_order[c["gid"]], (xx, 0, 0, yy, dx, dy))
                )

    def _extract_master_guides(self) -> None:
        if self.mm_glyph.mm_guides is None:
            return

        master_guides = get_master_guides(self.mm_glyph.mm_guides, self.master_index)
        apply_guide_properties(master_guides, self.mm_glyph.guide_properties)
        if master_guides:
            self.guidelines = master_guides

    def _extract_master_ps_hints(self) -> None:
        """
        Apply master hint positions and widths.
        """
        master_hints = get_master_hints(
            mmglyph=self.mm_glyph, master_index=self.master_index
        )
        build_ps_glyph_hints(
            mmglyph=self.mm_glyph,
            glyph=self,
            master_hints=master_hints,
        )

    def _extract_master_tt_hints(self) -> None:
        if self.mm_glyph.tth_commands is None:
            return

        set_tth_lib(self, self.tth_commands)

    def _finalize_lib(self, encode_data_base64: bool = False) -> None:
        # If requested, apply base64 encoding to TT lib
        if encode_data_base64 and TT_GLYPH_LIB_KEY in self.lib:
            data = self.lib[TT_GLYPH_LIB_KEY]
            if not isinstance(data, bytes):
                self.lib[TT_GLYPH_LIB_KEY] = b64encode(data.encode("ascii"))

    def _finalize_point_labels(self, include_ps_hints: bool = True) -> None:
        self._finalize_tt_point_labels()
        if include_ps_hints:
            self._finalize_ps_point_labels()

    def _finalize_ps_point_labels(self) -> None:
        """
        Rename the ps-hinted point labels according to the supplied rename_dict.
        """
        if not self.rename_points:
            return

        # FIXME

    def _finalize_tt_point_labels(self) -> None:
        """
        Rename the tt-hinted point labels according to the supplied rename_dict.
        """
        if not self.rename_points:
            return

        for cmd in self.tth_commands:
            code = cmd["code"]
            if code in (
                "alignb",
                "alignt",
                "alignh",
                "alignv",
                "mdeltah",
                "mdeltav",
                "fdeltah",
                "fdeltav",
            ):
                self._rename_point_in_cmd(cmd, "point")
            elif code in ("singleh", "singlev", "doubleh", "doublev"):
                self._rename_point_in_cmd(cmd, "point1")
                self._rename_point_in_cmd(cmd, "point2")
            elif code in ("interpolateh", "interpolatev"):
                self._rename_point_in_cmd(cmd, "point")
                self._rename_point_in_cmd(cmd, "point1")
                self._rename_point_in_cmd(cmd, "point2")
            else:
                logger.error(f"Unknown TT command: {code}")
                raise ValueError

    def _rename_point_in_cmd(self, cmd, key: str) -> None:
        """
        Rename a point label in a TTH cmd according to the current rename_points dict.
        """
        pt_name = cmd[key]
        if pt_name in self.rename_points:
            cmd[key] = self.rename_points[pt_name]

    def _append_contour(self, contour: UfoContour, path_is_open: bool) -> None:
        """
        Append the contour to the glyph's contours, applying closepath optimizations.
        """
        if contour:
            ct = self._flush_contour(contour, path_is_open)
            self.contours.append(ct)

    def _apply_closepath(self, contour: UfoContour) -> None:
        """
        Apply closepath optimizations to the contour.
        """
        last_type = contour[-1][0]
        if contour[-1][3] == contour[0][3] and last_type not in ("line", "qcurve"):
            # Equal coords, use closepath to draw the last line, but not for explicit
            # lines
            name = contour[0][2]
            contour[0] = contour.pop()
            if name is not None:
                # Keep old point name
                if contour[0][2] is None:
                    t, smooth, _, pt = contour[0]
                    contour[0] = (t, smooth, name, pt)
                else:
                    logger.warning(f"Glyph '{self.name}':")
                    logger.warning(
                        f"Point name conflict in {contour[0]} vs. {name} while "
                        f"applying closepath. Not applying old name ({name})"
                    )
                    # Note the old and new name so the labels can be updated
                    self.rename_points[name] = contour[0][2]

        else:
            _, smooth, name, pt = contour[0]
            contour[0] = ("line", smooth, name, pt)

    def _flush_contour(self, contour: UfoContour, path_is_open: bool) -> UfoContour:
        """
        Post-process a contour before it is appended to the glyph's contours.
        """
        if not path_is_open:
            last_type = contour[-1][0]
            if last_type in ("line", "curve", "qcurve"):
                self._apply_closepath(contour)

            elif last_type is None:
                _, smooth, name, pt = contour[0]
                contour[0] = ("qcurve", smooth, name, pt)
        return contour
