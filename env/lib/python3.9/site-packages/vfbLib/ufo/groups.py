from __future__ import annotations

import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vfbLib.typing import ClassFlagDict
    from vfbLib.ufo.typing import UfoGroups


logger = logging.getLogger(__name__)


def transform_groups(
    orig_groups: UfoGroups,
    kerning_class_flags: ClassFlagDict,
    glyphOrder: list[str],
    skip_missing_group_glyphs: bool = False,
) -> tuple[UfoGroups, list[str], dict[str, str]]:
    # Rename kerning groups by applying the side flags and using the public.kern prefix.
    # Remove missing glyphs from groups if requested.
    FIRST = 2**10
    SECOND = 2**11
    groups: UfoGroups = {}
    group_order = []
    key_glyphs: dict[str, str] = {}
    for name, glyphs in orig_groups.items():
        # Check for missing glyphs
        missing = [n for n in glyphs if n not in glyphOrder]
        num_missing = len(missing)
        num_glyphs = len(glyphs)
        if missing:
            if num_missing == num_glyphs:
                logger.warning(
                    f"All glyphs in group '{name}' are missing from "
                    f"the font: {', '.join(missing)}"
                )
            else:
                logger.warning(
                    f"{num_missing} of {num_glyphs} glyphs in group "
                    f"'{name}' are missing from the font: {', '.join(missing)}"
                )
            if skip_missing_group_glyphs:
                glyphs = list(set(glyphs) - set(missing))
                if not glyphs:
                    logger.warning(f"Not adding empty group '{name}' to the UFO.")
                    continue

        if name.startswith("_"):
            # Kerning group
            key_glyph = None
            if glyphs:
                key_glyph = glyphs[0]  # Groups have been reordered so keyglyph is 1st
                if key_glyph in missing:
                    if num_missing != num_glyphs:
                        # Only warn if not all group glyphs are missing from the font
                        logger.warning(
                            f"Key glyph '{key_glyph}' for group '{name}' is missing "
                            "from the font."
                        )

            if name in kerning_class_flags:
                flags = kerning_class_flags[name][0]
            else:
                # Don't add kerning groups without a side flag, as FLS ignores them when
                # compiling the kern feature
                logger.warning(f"Skipping kerning group without side flag: '{name}'")
                continue

            for side, sidename in ((FIRST, 1), (SECOND, 2)):
                if flags & side:
                    ufoname = f"public.kern{sidename}.{name}"
                    if ufoname in groups:
                        logger.warning(f"Duplicate kern{sidename} group: {ufoname}")
                    else:
                        groups[ufoname] = glyphs
                    group_order.append(ufoname)
                    if ufoname in key_glyphs:
                        if key_glyphs[ufoname] != key_glyph:
                            logger.warning(
                                f"Ignoring duplicate group '{ufoname}' with different "
                                f"key glyphs: {key_glyphs[ufoname]} vs. {key_glyph}."
                            )
                    elif key_glyph is not None:
                        key_glyphs[ufoname] = key_glyph

        else:
            # Pass non-kerning groups verbatim
            groups[name] = glyphs
            group_order.append(name)
    return groups, group_order, key_glyphs


def build_glyph_to_group_maps(
    groups: UfoGroups,
) -> tuple[UfoGroups, dict[str, str], dict[str, str]]:
    glyph_group_1: dict[str, str] = {}
    glyph_group_2: dict[str, str] = {}
    for group in groups.items():
        name, glyphs = group
        if name.startswith("public.kern1"):
            for g in glyphs:
                if g in glyph_group_1:
                    logger.error(
                        f"Multiple kerning groups (kern1) for glyph {g}: "
                        f"{glyph_group_1[g]}, {name}. New group ignored."
                    )
                    continue
                glyph_group_1[g] = name
        elif name.startswith("public.kern2"):
            for g in glyphs:
                if g in glyph_group_2:
                    logger.error(
                        f"Multiple kerning groups (kern2) for glyph {g}: "
                        f"{glyph_group_2[g]}, {name}. New group ignored."
                    )
                    continue
                glyph_group_2[g] = name
    # Rebuild groups to get rid of duplicate kerning groups per glyph and side.
    groups = rebuild_kerning_groups(groups, glyph_group_1, glyph_group_2)
    return groups, glyph_group_1, glyph_group_2


def _build_groups(glyph_to_group_mapping: dict[str, str]) -> UfoGroups:
    groups: UfoGroups = {}
    for name, group in glyph_to_group_mapping.items():
        if group in groups:
            groups[group].append(name)
        else:
            groups[group] = [name]
    return groups


def rebuild_kerning_groups(
    groups: UfoGroups, glyph_group_1: dict[str, str], glyph_group_2: dict[str, str]
) -> UfoGroups:
    """
    Rebuild the kerning groups from the left and right side glyph to group mappings.
    This should get rid of any duplicate groups per glyph.
    """
    # Filter groups so only non-kerning groups are kept
    new_groups: UfoGroups = {
        n: g for n, g in groups.items() if not n.startswith("public.kern")
    }
    new_groups.update(_build_groups(glyph_group_1))
    new_groups.update(_build_groups(glyph_group_2))
    return new_groups
