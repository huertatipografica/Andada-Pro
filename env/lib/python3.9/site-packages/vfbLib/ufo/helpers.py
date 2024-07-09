from __future__ import annotations

import codecs
import logging

from defcon.objects.font import Font
from ufonormalizer import normalizeUFO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from vfbLib.ufo.pshints import update_adobe_hinting
from vfbLib.ufo.vfb2ufo import (
    PS_GLYPH_LIB_KEY_ADOBE,
    PS_GLYPH_LIB_KEY,
    TT_GLYPH_LIB_KEY,
)


logger = logging.getLogger(__name__)

RF_GUIDES_KEY = "com.typemytype.robofont.guides"

delete_lib_keys: list[str] = []


def fix_vfb2ufo_feature_encoding(ufo_path: Path) -> None:
    # Read vfb2ufo's Windows-1252-encoded feature file and convert to UTF-8
    fea_path = ufo_path / "features.fea"
    if not fea_path.exists():
        # UFOs may omit the fea file
        return

    with codecs.open(str(fea_path), "rb", "cp1252") as f:
        fea = f.read()
    with codecs.open(str(fea_path), "wb", "utf-8") as f:
        f.write(fea)


def update_global_guides(f: Font):
    # Update Global Guides to UFO standard
    if RF_GUIDES_KEY in f.lib:
        guides = []
        for guide in f.lib[RF_GUIDES_KEY]:
            isGlobal = guide["isGlobal"]
            del guide["isGlobal"]
            del guide["magnetic"]
            assert isGlobal
            guides.append(guide)
        if guides:
            f.guidelines = guides
        del f.lib[RF_GUIDES_KEY]


def update_glyph_guides(glyph):
    # Update Guides to UFO standard
    if RF_GUIDES_KEY in glyph.lib:
        guides = []
        for guide in glyph.lib[RF_GUIDES_KEY]:
            isGlobal = guide["isGlobal"]
            del guide["isGlobal"]
            del guide["magnetic"]
            assert not isGlobal
            guides.append(guide)
        if guides:
            glyph.guidelines = guides
        del glyph.lib[RF_GUIDES_KEY]


def normalize_ufo(
    filepath: Path, structure: Literal["package", "zip"] = "package"
) -> None:
    logger.info(f"Processing {filepath.name}...")

    normalized_file = filepath / ".normalized"

    if structure == "package":
        if normalized_file.exists():
            logger.info(f"    Skipping already normalized UFO: {filepath.name}")
            return

        fix_vfb2ufo_feature_encoding(filepath)  # FIXME: Support ufoz

    try:
        f = Font(str(filepath))
    except:  # noqa: E722
        logger.error(f"Skipping UFO with errors: {filepath}")
        raise

    with NamedTemporaryFile(suffix="ufoz") as tf:
        f.save(path=tf.name, formatVersion=3, structure="zip")
        f = Font(tf.name)
        for glyph in f:
            for key in delete_lib_keys:
                try:
                    del glyph.lib[key]
                except KeyError:
                    pass

            # Make TT glyph program readable
            if TT_GLYPH_LIB_KEY in glyph.lib:
                data = glyph.lib[TT_GLYPH_LIB_KEY]
                try:
                    data = data.decode()
                except AttributeError:
                    pass
                glyph.lib[TT_GLYPH_LIB_KEY] = data

            # Update PS Hinting to V2
            if PS_GLYPH_LIB_KEY_ADOBE in glyph.lib:
                v2 = update_adobe_hinting(glyph.lib[PS_GLYPH_LIB_KEY_ADOBE])
                if v2:
                    glyph.lib[PS_GLYPH_LIB_KEY] = v2
                del glyph.lib[PS_GLYPH_LIB_KEY_ADOBE]

            update_glyph_guides(glyph)

        update_global_guides(f)

        if structure == "zip":
            if not filepath.suffix == ".ufoz":
                filepath = filepath.with_suffix(".ufoz")
        else:
            if filepath.suffix == ".ufoz":
                filepath = filepath.with_suffix(".ufo")
        f.save(path=str(filepath), formatVersion=3, structure=structure)
        normalizeUFO(ufoPath=str(filepath), onlyModified=False, writeModTimes=False)
        if structure == "package":
            normalized_file.touch()


def normalize_ufoz(filepath):
    """
    Normalize the ufo, but save as .ufoz
    """
    normalize_ufo(filepath, structure="zip")


def normalize():
    from sys import argv

    for ufo_path in argv[1:]:
        normalize_ufo(Path(ufo_path))
