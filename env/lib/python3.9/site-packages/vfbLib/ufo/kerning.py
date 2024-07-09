from __future__ import annotations

import logging

from typing import TYPE_CHECKING
from vfbLib.ufo.groups import build_glyph_to_group_maps

if TYPE_CHECKING:
    from vfbLib.ufo.typing import UfoGroups, UfoMasterKerning, UfoMMKerning


logger = logging.getLogger(__name__)


class UfoKerning:
    def __init__(
        self,
        glyph_order: list[str],
        groups: UfoGroups,
        mm_kerning: UfoMMKerning,
        key_glyphs: dict[str, str],
    ):
        self.glyph_order = glyph_order
        group_info = build_glyph_to_group_maps(groups)
        self.groups, self.glyph_group_1, self.glyph_group_2 = group_info
        self.mm_kerning = mm_kerning
        self.key_glyphs = self._reverse_key_glyph_dict(key_glyphs)
        self._make_name_based_kerning()

    def _is_exception(self, L: str, R: str):
        L_is_key = (1, L) in self.key_glyphs or L not in self.glyph_group_1

        R_is_key = (2, R) in self.key_glyphs or R not in self.glyph_group_2

        if L_is_key and R_is_key:
            return False

        return True

    def _make_name_based_kerning(self) -> None:
        """
        Convert the glyph indices to glyph names. Also solves group kerning
        references.
        """
        self.mm_kerning_names: dict[tuple[str, str], list[int]] = {}
        for pair, values in self.mm_kerning.items():
            L, Rid = pair
            # Make right GID into glyph name
            R = self.glyph_order[int(Rid)]

            # Is the left glyph a keyglyph? In that case, use the group name instead of
            # the glyph name.
            left_group = self.key_glyphs.get((1, L))
            left = left_group if left_group in self.groups else L

            # Is the right glyph a keyglyph?
            right_group = self.key_glyphs.get((2, R))
            right = right_group if right_group in self.groups else R

            self.mm_kerning_names[left, right] = values

    def _reverse_key_glyph_dict(
        self, key_glyphs: dict[str, str]
    ) -> dict[tuple[int, str], str]:
        """
        Rebuild the key glyphs dict (group_name: key_ glyph_name) into a reverse dict by
        kerning group side and key glyph to group name.
        """
        rev = {}
        for name, key_glyph in key_glyphs.items():
            if name.startswith("public.kern1"):
                key = (1, key_glyph)
            elif name.startswith("public.kern2"):
                key = (2, key_glyph)
            else:
                key = None
                logger.warning(
                    f"Can't determine kerning group side from name: '{name}'"
                )
            if key in rev:
                logger.warning(
                    f"Glyph is key glyph for more than one kerning group: {key}"
                )
                continue

            rev[key] = name
        return rev

    def get_master_kerning(self, master_index: int) -> UfoMasterKerning:
        """
        Extract the kerning values for master_index and return the kerning as
        Dict[Tuple[str, str], int].
        """
        master_kerning: UfoMasterKerning = {}
        for pair, values in self.mm_kerning_names.items():
            value = values[master_index]
            if value != 0 or self._is_exception(*pair):
                master_kerning[pair] = value
        return master_kerning
