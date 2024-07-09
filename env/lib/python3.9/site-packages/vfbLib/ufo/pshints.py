from __future__ import annotations

import logging

import xml.etree.ElementTree as elementTree

from vfbLib.ufo.typing import UfoHintingV2, UfoHintSet
from vfbLib.ufo.vfb2ufo import PS_GLYPH_LIB_KEY
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vfbLib.typing import Hint, HintTuple
    from vfbLib.ufo.glyph import VfbToUfoGlyph
    from vfbLib.ufo.paths import UfoMasterGlyph


logger = logging.getLogger(__name__)


def normalize_hint(hint: tuple[str, int, int]):
    direction, pos, width = hint
    if width < 0:
        if width not in (-21, -20):  # Skip ghost hints
            pos = pos + width
            width = abs(width)
    return (direction, pos, width)


def normalize_hint_dict(hint: Hint, name: str = "dummy"):
    return normalize_hint((name, hint["pos"], hint["width"]))


def build_ps_glyph_hints(
    mmglyph: VfbToUfoGlyph,
    glyph: UfoMasterGlyph,
    master_hints: dict[str, list[str | HintTuple]],
) -> None:
    # Set the master-specific hints from data to the glyph lib
    # Use the format defined in UFO3, not what FL does.
    # https://github.com/adobe-type-tools/psautohint/blob/master/python/psautohint/ufoFont.py
    # https://unifiedfontobject.org/versions/ufo3/glyphs/glif/#publicpostscripthints
    hint_sets = []
    stems: list[str | HintTuple] = []
    hint_set: UfoHintSet = UfoHintSet(pointTag="0", stems=stems)
    if mmglyph.hintmasks:
        for mask in mmglyph.hintmasks:
            for d in ("h", "v"):
                if d in mask:
                    master_direction_hints = master_hints[d]
                    hint_index = mask[d]
                    if hint_index < len(master_direction_hints):
                        hint: HintTuple | str = master_direction_hints[hint_index]
                        hint_set["stems"].append(hint)
                    else:
                        logger.debug(
                            f"Hint mask '{d}' with index {hint_index} found in glyph "
                            f"{glyph.name}, but hint list is empty."
                        )
            if "r" in mask:
                hint_set["pointTag"] = mmglyph.get_point_label(
                    index=int(hint_set["pointTag"]),
                    code="PSHintReplacement",
                    start_count=0,
                )
                hint_sets.append(hint_set)
                node_index = mask["r"]
                # FIXME: What do negative values mean?
                if node_index < 0:
                    node_index = abs(node_index) - 1
                stems = []
                hint_set = UfoHintSet(pointTag=str(node_index), stems=stems)

        if hint_set["stems"]:
            # Append the last hint set
            hint_set["pointTag"] = mmglyph.get_point_label(
                index=int(hint_set["pointTag"]),
                code="PSHintReplacement",
                start_count=0,
            )
            hint_sets.append(hint_set)
    else:
        # Only one hint set, always make a hint set with first point
        for d in ("h", "v"):
            for hint in master_hints[d]:
                hint_set["stems"].append(hint)
        if hint_set["stems"]:
            hint_set["pointTag"] = mmglyph.get_point_label(
                index=int(hint_set["pointTag"]),
                code="PSHintReplacement",
                start_count=0,
            )
            hint_sets = [hint_set]

    # Reformat stems from sortable tuples to str required by UFO spec
    for hint_set in hint_sets:
        hint_set["stems"] = [
            f"{h[0]} {h[1]} {h[2]}"
            for h in sorted(set(hint_set["stems"]))
            # if isinstance(h, tuple)
        ]

    if hint_sets:
        if not hasattr(glyph, "lib"):
            glyph.lib = {}
        glyph.lib[PS_GLYPH_LIB_KEY] = {
            # "id": "FIXME",
            "hintSetList": hint_sets,
            # "flexList": [],
        }


def get_master_hints(
    mmglyph: VfbToUfoGlyph, master_index=0
) -> dict[str, list[str | HintTuple]]:
    hints: dict[str, list[str | HintTuple]] = {"h": [], "v": []}

    # Hints
    for d in "hv":
        dh = mmglyph.mm_hints[d]
        for mm_hints in dh:
            hint = mm_hints[master_index]
            hint = normalize_hint_dict(hint, f"{d}stem")
            hints[d].append(hint)

    # Links
    if not mmglyph.links:
        return hints

    # Convert links to hints
    for i, axis in enumerate("xy"):
        direction_links = mmglyph.links[axis]
        for link in direction_links:
            isrc, itgt = link  # indices of source and target node
            src = mmglyph.mm_nodes[isrc]
            src_pos = src["points"][master_index][0][i]
            pos = src_pos
            if itgt == -1:  # Bottom ghost
                width = -21
                pos = src_pos - width
            elif itgt == -2:  # Top ghost
                width = -20
            else:
                tgt = mmglyph.mm_nodes[itgt]
                tgt_pos = tgt["points"][master_index][0][i]
                width = tgt_pos - src_pos
                # pos = min(src_pos, tgt_pos)

            d = "v" if axis == "x" else "h"
            # Don't normalize those values, the above code already did that
            hint = (f"{d}stem", pos, width)
            # hint = normalize_hint((f"{d}stem", pos, width))
            hints[d].append(hint)

    return hints


def update_adobe_hinting(data) -> UfoHintingV2:
    # Convert Adobe hinting data from v1 to v2.
    # https://github.com/adobe-type-tools/psautohint/blob/master/python/psautohint/ufoFont.py
    try:
        # Data may be base64-encoded
        data = data.decode()
    except AttributeError:
        pass
    if not isinstance(data, str):
        # V1 data is stored as str, so if it is not a str, we have nothing to do
        return data

    v2: UfoHintingV2 = {
        # "flexList": [],
        # "id": "",
    }
    root = elementTree.fromstring(data)
    hintset: UfoHintSet | None = None
    hintSetList: list[UfoHintSet] = []
    for el in root.iter():
        if el.tag == "hintSetList":
            hintSetList = []
        elif el.tag == "hintset":
            if hintset:
                hintSetList.append(hintset)
            hintset = {
                "pointTag": el.attrib["pointTag"],
                "stems": [],
            }
        elif el.tag in ("hstem", "vstem"):
            if hintset is not None:
                tag, pos, width = normalize_hint(
                    (el.tag, int(el.attrib["pos"]), int(el.attrib["width"]))
                )
                hintset["stems"].append(f"{tag} {pos} {width}")
    if hintset:
        hintSetList.append(hintset)
    if hintSetList:
        v2["hintSetList"] = hintSetList

    # Remove empty entries
    empty = [k for k in v2 if not v2[k]]
    for k in empty:
        del v2[k]
    return v2
