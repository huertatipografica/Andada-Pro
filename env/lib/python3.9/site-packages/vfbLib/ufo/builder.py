from __future__ import annotations

import logging

from copy import deepcopy
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
)
from fontTools.ufoLib import UFOFileStructure
from pathlib import Path
from typing import TYPE_CHECKING, Any
from ufoLib2.objects.font import Font
from ufoLib2.objects.features import Features
from ufonormalizer import normalizeUFO
from vfbLib.constants import ignore_minimal
from vfbLib.ufo.designspace import get_ds_location
from vfbLib.ufo.features import rename_kern_classes_in_feature_code
from vfbLib.ufo.glyph import VfbToUfoGlyph
from vfbLib.ufo.groups import transform_groups
from vfbLib.ufo.guides import apply_guide_properties, get_master_guides
from vfbLib.ufo.info import VfbToUfoInfo
from vfbLib.ufo.kerning import UfoKerning
from vfbLib.ufo.paths import UfoMasterGlyph
from vfbLib.ufo.tth import TTGlyphHints, transform_stem_rounds
from vfbLib.ufo.typing import (
    TUfoRawStemsDict,
    TUfoStemDict,
    TUfoStemPPMDict,
    TUfoStemPPMsDict,
    TUfoStemsDict,
    TUfoTTZoneDict,
    TUfoTTZonesDict,
)
from vfbLib.ufo.vfb2ufo import TT_GLYPH_LIB_KEY, TT_LIB_KEY

if TYPE_CHECKING:
    from fontTools.designspaceLib import DiscreteAxisDescriptor
    from vfbLib.typing import Anchor, ClassFlagDict, GuidePropertyList
    from vfbLib.ufo.typing import UfoGroups, UfoMMKerning
    from vfbLib.vfb.vfb import Vfb


logger = logging.getLogger(__name__)


class VfbToUfoBuilder:
    def __init__(
        self,
        vfb: Vfb,
        minimal=False,
        base64=False,
        pshints=True,
        add_kerning_groups=False,
    ) -> None:
        """
        Serialize the JSON structure to UFO(s)
        """
        self.axes: list[AxisDescriptor | DiscreteAxisDescriptor] = []
        self.axis_count = 0
        self.vfb = vfb
        self.minimal = minimal
        self.encode_data_base64 = base64
        self.include_ps_hints = pshints
        self.add_kerning_groups = add_kerning_groups

        self.features_classes = ""
        self.features_code = ""
        self.groups: UfoGroups = {}
        self.guide_properties: GuidePropertyList = []
        self.info = VfbToUfoInfo()
        self.kerning_class_flags: ClassFlagDict = {}
        self.num_blue_values = 0
        self.num_other_blues = 0
        self.num_family_blues = 0
        self.num_family_other_blues = 0
        self.num_stem_snap_h = 0
        self.num_stem_snap_v = 0
        self.mm_guides = None
        self.mm_kerning: UfoMMKerning = {}
        self.kerning: dict[tuple[str, str], int] = {}
        self.lib: dict[str, Any] = {}
        self.masters: list[str] = []
        self.master_locations: dict[int, list[float]] = {}
        self.masters_ps_info: list[dict] = []
        self.primary_instances: list[dict[str, str | list[float]]] = []
        self.current_glyph: VfbToUfoGlyph | None = None
        self.glyph_masters: dict[str, VfbToUfoGlyph] = {}
        self.glyphOrder: list[str] = []
        # TT
        self.stem_ppms: TUfoStemPPMsDict = {"ttStemsH": [], "ttStemsV": []}
        self.stems: TUfoStemsDict = {"ttStemsH": [], "ttStemsV": []}
        self.tt_zones: TUfoTTZonesDict = {}
        self.tt_zone_names: list[str] = []
        self.zone_names: dict[str, list[str]] = {}
        self.build()

    def add_axis_mappings(self, data: list[tuple[float, float]]) -> None:
        if not self.axis_mappings_count:
            raise ValueError(
                "If axis mappings are present, axis mappings count must be set before "
                "parsing them."
            )
        for i in range(self.axis_count):
            # Get the number of mappings for the current axis
            n = self.axis_mappings_count[i]
            if n > 0:
                # Use only n mappings out of 10 for the current axis
                mappings = data[:n]
                axis = self.axes[i]
                axis.map = [(u, round(d * 1000)) for u, d in mappings]
                if isinstance(axis, AxisDescriptor):
                    # Derive min/max from the mappings
                    # FIXME: Is this info available elsewhere in the VFB?
                    user_coords = [c[0] for c in mappings]
                    axis.minimum = min(user_coords, default=0)
                    axis.default = axis.minimum
                    axis.maximum = max(user_coords, default=1000)
            # Jump to the next 10 axis mappings
            data = data[10:]

    def add_ot_class(self, data: dict[str, list[str] | str]) -> None:
        if "name" not in data:
            logger.warning(f"Malformed OT class definition, skipping: {data}")
            return

        name = data["name"]
        if not isinstance(name, str):
            raise TypeError(f"OT class name must be a string: {name} ({type(name)})")

        is_kerning = name.startswith("_")

        if name in self.groups:
            logger.warning(f"Duplicate OT class name, skipping: {name}")
            return

        glyphs_list = data["glyphs"]
        if is_kerning:
            # Reorganize glyphs so that the "keyglyph" is first
            glyphs: list[str] = [g.strip() for g in glyphs_list if not g.endswith("'")]
            keyglyphs = [g.strip() for g in glyphs_list if g.endswith("'")]
            keyglyphs = [k.strip("'") for k in keyglyphs]
            if len(keyglyphs) != 1:
                logger.warning(
                    f"Unexpected number of key glyphs in group {name}: {keyglyphs}"
                )
            else:
                glyphs.insert(0, *keyglyphs)

        else:
            glyphs = [g.strip() for g in glyphs_list]
        self.groups[name] = glyphs

    def assure_tt_lib(self) -> None:
        if TT_LIB_KEY not in self.lib:
            self.lib[TT_LIB_KEY] = {}

    def assure_tt_glyphlib(self) -> None:
        if TT_GLYPH_LIB_KEY not in self.lib:
            self.lib[TT_GLYPH_LIB_KEY] = {}

    def build_mm_glyph(self, data: dict[str, Any]) -> None:
        g = self.current_glyph = VfbToUfoGlyph(self)
        g.lib = {}
        g.name = data["name"]
        g.unicodes = []

        # MM Stuff, need to extract later
        if not self.minimal and "guides" in data:
            g.mm_guides = data["guides"]

        if self.include_ps_hints and "hints" in data:
            g.mm_hints = data["hints"]
            if "hintmasks" in data["hints"]:
                g.hintmasks = data["hints"]["hintmasks"]
                del data["hints"]["hintmasks"]

        if "kerning" in data:
            kerning: dict[int, list[int]] = data["kerning"]
            for Rid, values in kerning.items():
                assert g.name is not None
                self.mm_kerning[(g.name, Rid)] = values

        g.mm_metrics = data["metrics"]  # width and height
        g.mm_nodes = data["nodes"]

        if "components" in data:
            g.mm_components = data["components"]

        # TrueType hinting, stored here for later processing after all glyphs are there.
        if "tth" in data:
            g.tt_glyph_hints = TTGlyphHints(g, data["tth"], self.zone_names, self.stems)

    def set_feature_code(self, data: list[str]) -> None:
        # Make the kern feature compilable
        self.features_code = "\n".join(rename_kern_classes_in_feature_code(data))

    def set_glyph_background(self, data: dict[str, Any]) -> None:
        assert self.current_glyph is not None
        self.current_glyph.lib["com.fontlab.v5.background"] = data

    def set_tt_stem_ppms(self, data: TUfoStemPPMsDict) -> None:
        """Set the TT stem PPMs for stem widths of 2 to 5 pixels.

        Args:
            data (TUfoStemPPMsDict): The raw data.
        """
        for d in ("ttStemsH", "ttStemsV"):
            direction_stems = data[d]
            for ds in direction_stems:
                index = ds["stem"]
                # We can only show an index, self.stems is not filled yet
                name = f"{d[-1]}#{index}"
                rounds = transform_stem_rounds(ds["round"], name)
                stem: TUfoStemPPMDict = {"stem": index, "round": rounds}
                self.stem_ppms[d].append(stem)

    def set_tt_stem_ppms_1(self, data: TUfoStemPPMsDict) -> None:
        """Set the TT stem PPMs for stem width of 1 pixel.

        Args:
            data (TUfoStemPPMDict): The raw data.
        """
        for d in ("ttStemsH", "ttStemsV"):
            direction_stems = data[d]
            for ds in direction_stems:
                round_dict = self.stem_ppms[d][ds["stem"]]["round"]
                ppm = "1"
                ppm1 = str(ds["round"][ppm])
                if ppm1 in round_dict:
                    logger.warning(
                        f"Duplicate rounding ppm {ppm1} in TT stem {d[-1]}#{ds['stem']}"
                        f", keeping value {round_dict[ppm1]}px over {ppm}px, "
                        f"which may not be what you want. {round_dict}"
                    )
                else:
                    round_dict[ppm1] = 1

    def set_tt_stems(self, data: TUfoRawStemsDict) -> None:
        for d in ("ttStemsH", "ttStemsV"):
            direction_stems = data[d]
            for i, ds in enumerate(direction_stems):
                # The rounding ppm value for 6 pixels is stored right here. We must
                #  re-add it to the dict later
                r = ds["round"]
                rk = list(r.keys())[0]
                rv = str(r[rk])

                # Take the other rounding ppm values (2-5) from self.stem_ppms
                stem_ppms = self.stem_ppms[d][i]
                assert i == stem_ppms["stem"]

                # Build the final stem dict
                stem: TUfoStemDict = {
                    "horizontal": d == "ttStemsV",
                    "width": ds["value"],
                    "name": ds["name"],
                    "round": stem_ppms["round"],
                }

                # Re-add the rounding ppm value for 6 pixels
                if rv in stem["round"]:
                    logger.warning(
                        f"Duplicate rounding ppm {rv} in TT stem {d[-1]}#{i}, "
                        f"choosing bigger value {rk}px over {stem['round'][rv]}px."
                    )
                stem["round"][rv] = int(rk)

                self.stems[d].append(stem)

    def set_tt_zones(self, data: dict[str, list]) -> None:
        self.zone_names = {
            "ttZonesT": [],
            "ttZonesB": [],
        }
        for d in ("ttZonesB", "ttZonesT"):
            direction_zones = data[d]
            for dz in direction_zones:
                zone = TUfoTTZoneDict(
                    position=dz["position"],
                    top=d == "ttZonesT",
                    width=dz["value"],
                )
                name = dz["name"]
                if name in self.tt_zones:
                    logger.warning(f"Duplicate zone name: {name}, overwriting.")
                self.tt_zones[name] = zone
                self.tt_zone_names.append(name)  # for deltas
                self.zone_names[d].append(name)  # for AlignTop/AlignBottom

    def set_tt_pixel_snap(self, data) -> None:
        self.assure_tt_lib()
        if data != 68:
            # Omit default value
            self.lib[TT_LIB_KEY]["stemsnaplimit"] = data

    def set_tt_zone_stop(self, data) -> None:
        self.assure_tt_lib()
        if data != 48:
            # Omit default value
            self.lib[TT_LIB_KEY]["zoneppm"] = data

    def set_tt_code_stop(self, data) -> None:
        self.assure_tt_lib()
        self.lib[TT_LIB_KEY]["codeppm"] = data

    def set_tt_zone_deltas(self, data) -> None:
        for zone_index, deltas in data.items():
            zone_name = self.tt_zone_names[int(zone_index)]
            self.tt_zones[zone_name]["delta"] = {str(k): v for k, v in deltas.items()}

    def build_tt_stems_lib(self) -> None:
        lib = {}
        for d in ("ttStemsH", "ttStemsV"):
            i = 0
            direction_stems = self.stems[d]
            for stem in direction_stems:
                name = stem["name"]
                del stem["name"]
                if name == "":
                    dname = "v" if d == "ttStemsH" else "h"
                    name = "%s%02i" % (dname, i)
                    i += 1
                if name in lib:
                    oldname = name
                    name = "%s#%02i" % (oldname, i)
                    logger.warning(
                        f"Duplicate TrueType stem name '{oldname}', renamed to '{name}'"
                        ". Preferably make stem names unique in VFB."
                    )
                lib[name] = stem
        if lib:
            self.lib[TT_LIB_KEY]["stems"] = lib

    def build_tt_zones_lib(self) -> None:
        self.assure_tt_lib()
        if self.tt_zones:
            self.lib[TT_LIB_KEY]["zones"] = self.tt_zones

    def build_tt_glyph_lib(self) -> None:
        for glyph in sorted(self.glyph_masters.values()):
            if glyph.tt_glyph_hints is None:
                continue

            glyph.tth_commands = glyph.tt_glyph_hints.get_tt_glyph_hints()

    def build(self) -> None:  # noqa: C901
        # Non-MM data
        minimal_build = self.vfb.minimal
        for e in self.vfb.entries:
            name = e.key
            if name is None:
                raise TypeError
            if minimal_build and name in ignore_minimal:
                continue
            data = e.decompiled
            if data is None:
                continue

            # Font Info
            attr = self.info.mapping.get(name, None)
            if attr is not None:
                self.info.set_attr(attr, data)
                continue

            if name == "header":
                pass
            elif name == "sgn":  # 1024
                self.info.familyName = data
                self.info.openTypeNamePreferredFamilyName = data
            elif name == "Monospaced":  # 1034
                self.info.set_fixed_pitch(data)
            elif name == "version full":
                pass
            elif name == "weight":  # 1048
                self.info.set_weight_class(data)
            elif name == "Style Name":  # 1127
                self.info.postscriptWeightName = data  # FIXME: Does not contain Italic
            elif name == "Type 1 XUIDs":  # 1133
                pass
            elif name == "tsn":  # 1137
                self.info.set_style_name(data)
            elif name == "Name Records":  # 1138
                self.info.set_name_records(data)
            elif name == "Glyph Unicode":  # 1250
                assert self.current_glyph is not None
                self.current_glyph.unicodes.extend(data)
            elif name == "Glyph Unicode Non-BMP":  # 1253
                assert self.current_glyph is not None
                self.current_glyph.unicodes.extend(data)
            elif name == "Primary Instances":  # 1254
                self.primary_instances = data
            elif name == "TrueType Zones":  # 1255
                self.set_tt_zones(data)
            elif name == "TrueType Info":  # 1264
                self.info.set_tt_info(data)
            elif name == "Gasp Ranges":  # 1265
                self.info.set_tt_gasp(data)
            elif name == "Selection":  # 1267
                self.info.set_selection(data)
            elif name == "TrueType Stem PPEMs":  # 1268
                self.set_tt_stem_ppms(data)
            elif name == "TrueType Stems":  # 1269
                self.set_tt_stems(data)
            elif name == "Pixel Snap":  # 1272
                self.set_tt_pixel_snap(data)
            elif name == "TrueType Zone Deltas":  # 1273
                self.set_tt_zone_deltas(data)
            elif name == "Zone Stop PPEM":  # 1274
                self.set_tt_zone_stop(data)
            elif name == "Code Stop PPEM":  # 1275
                self.set_tt_code_stop(data)
            elif name == "openTypeFeatures":  # 1276
                self.set_feature_code(data)
            elif name == "OpenType Class":  # 1277
                self.add_ot_class(data)
            elif name == "Global Guides":  # 1294
                self.mm_guides = data
            elif name == "Global Guide Properties":  # 1296
                self.guide_properties = data
            elif name == "Encoding":  # 1500
                pass
            elif name == "Master Count":  # 1503
                self.master_count = data
            elif name == "Master Name":  # 1504
                self.masters.append(data)
            elif name == "Master Location":  # 1505
                index, locations = data
                self.master_locations[index] = locations
            elif name == "Axis Count":  # 1513
                self.axis_count = data
            elif name == "Axis Name":  # 1514
                tags = {
                    "Weight": "wght",
                    "Width": "wdth",
                    "Optical Size": "opsz",
                    "Serif": "SERF",
                }
                self.axes.append(
                    AxisDescriptor(tag=tags.get(data, data.upper()[:4]), name=data)
                )
            elif name == "Axis Mappings Count":  # 1515
                self.axis_mappings_count: list[int] = data
            elif name == "Axis Mappings":  # 1516
                self.add_axis_mappings(data)
            elif name == "Anisotropic Interpolation Mappings":  # 1523
                # TODO: Can we properly output this to designspace?
                for axis in data:
                    for a, b in axis:
                        if a != b:
                            maps = {
                                self.axes[i].name: data[i]
                                for i in range(self.axis_count)
                            }
                            logger.warning(
                                "WARNING: Designspace output of anisotropic "
                                "interpolation settings is not yet supported. You must "
                                "set it up manually."
                            )
                            logger.warning(f"         Mappings: {maps}")
                            break
            elif name == "TrueType Stem PPEMs 1":  # 1524
                self.set_tt_stem_ppms_1(data)
            elif name == "Blue Values Count":  # 1530
                self.num_blue_values = data
            elif name == "Other Blues Count":  # 1531
                self.num_other_blues = data
            elif name == "Family Blues Count":  # 1532
                self.num_family_blues = data
            elif name == "Family Other Blues Count":  # 1533
                self.num_family_other_blues = data
            elif name == "StemSnapH Count":  # 1534
                self.num_stem_snap_h = data
            elif name == "StemSnapV Count":  # 1535
                self.num_stem_snap_v = data
            elif name == "PostScript Info":  # 1536
                self.masters_ps_info.append(data)
            elif name == "Glyph":  # 2001
                if self.current_glyph is not None:
                    name = self.current_glyph.name
                    if name in self.glyph_masters:
                        for i in range(255):
                            n = f"{name}#{i}"
                            if n not in self.glyph_masters:
                                self.glyph_masters[n] = self.current_glyph
                                self.glyphOrder.append(n)
                                logger.warning(
                                    f"Duplicate glyph, renamed from {name} to {n}."
                                )
                                break
                    else:
                        if name is None:
                            logger.error("Glyph without name.")
                        else:
                            self.glyph_masters[name] = self.current_glyph
                            self.glyphOrder.append(name)
                self.build_mm_glyph(data)
            elif name == "Background Bitmap":  # 2007
                self.set_glyph_background(data)
            elif name == "Links":  # 2008
                assert self.current_glyph is not None
                self.current_glyph.links = data
            elif name == "Mask":  # 2009
                pass
            elif name == "2010":
                pass
            elif name == "2011":
                pass
            elif name == "Mark Color":  # 2012
                assert self.current_glyph is not None
                self.current_glyph.set_mark(data)
            elif name == "Glyph User Data":  # 2015
                assert self.current_glyph is not None
                self.current_glyph.lib["com.fontlab.v5.userData"] = data
            elif name == "Font User Data":  # 2016
                self.lib["com.fontlab.v5.userData"] = data
            elif name == "Glyph Note":  # 2017
                assert self.current_glyph is not None
                self.current_glyph.note = data
            elif name == "Glyph GDEF Data":  # 2018
                if "anchors" in data:
                    assert self.current_glyph is not None
                    self.current_glyph.anchors = []
                    for anchor in data["anchors"]:
                        a: Anchor = {
                            "x": anchor["x"],
                            "y": anchor["y"],
                        }
                        if "name" in anchor:
                            a["name"] = anchor["name"]
                        self.current_glyph.anchors.append(a)
            elif name == "Glyph Anchors Supplemental":  # 2020
                pass
            elif name == "Unicode Ranges":  # 2021
                self.info.set_unicode_ranges(data)
            elif name == "2023":
                pass
            elif name == "OpenType Metrics Class Flags":  # 2024
                self.lib["com.fontlab.v5.metricsClassFlags"] = data
            elif name == "fontNote":  # 2025
                self.info.note = data
            elif name == "OpenType Kerning Class Flags":  # 2026
                self.kerning_class_flags = data
            elif name == "Glyph Origin":  # 2027
                pass
            elif name == "Glyph Anchors MM":  # 2029
                assert self.current_glyph is not None
                self.current_glyph.mm_anchors = data
            elif name == "Glyph Guide Properties":  # 2031
                assert self.current_glyph is not None
                self.current_glyph.guide_properties = data
            else:
                logger.info(f"Unhandled key: {name}")

        if self.current_glyph is not None:
            assert self.current_glyph.name is not None
            self.glyph_masters[self.current_glyph.name] = self.current_glyph
            self.glyphOrder.append(self.current_glyph.name)
        self.lib["public.glyphOrder"] = self.glyphOrder
        self.build_tt_glyph_lib()
        self.assure_tt_lib()
        self.build_tt_stems_lib()
        self.build_tt_zones_lib()
        if not self.lib[TT_LIB_KEY]:
            del self.lib[TT_LIB_KEY]
        self.info.fix_underline_position()

    def get_master_info(self, master_index: int = 0) -> VfbToUfoInfo:
        master_info = deepcopy(self.info)
        # Update the info with master-specific values
        properties = [
            ("ascender", "ascender"),
            ("descender", "descender"),
            ("x_height", "xHeight"),
            ("cap_height", "capHeight"),
        ]
        if self.include_ps_hints:
            properties.extend(
                [
                    # ("force_bold", "postscriptForceBold"),
                    ("blue_scale", "postscriptBlueScale"),
                    ("blue_shift", "postscriptBlueShift"),
                    ("blue_fuzz", "postscriptBlueFuzz"),
                ]
            )

        for key, attr in properties:
            value = self.masters_ps_info[master_index].get(key, None)
            if value is not None:
                setattr(master_info, attr, value)

        if self.include_ps_hints:
            # Set "force bold"
            value = self.masters_ps_info[master_index].get("force_bold", None)
            if value is not None:
                master_info.postscriptForceBold = bool(value)

            # Set attributes that must be clipped at a certain index
            for key, attr in (
                ("blue_values", "postscriptBlueValues"),
                ("other_blues", "postscriptOtherBlues"),
                ("family_blues", "postscriptFamilyBlues"),
                ("family_other_blues", "postscriptFamilyOtherBlues"),
                ("stem_snap_h", "postscriptStemSnapH"),
                ("stem_snap_v", "postscriptStemSnapV"),
            ):
                # Get the number of values from the corresponding attribute
                num_values = getattr(self, f"num_{key}")
                if num_values == 0:
                    continue

                value = self.masters_ps_info[master_index].get(key, None)
                if value is not None:
                    setattr(master_info, attr, value[:num_values])

        # Guides
        if not self.minimal and self.mm_guides is not None:
            guides = get_master_guides(self.mm_guides, master_index)
            apply_guide_properties(guides, self.guide_properties)

            if guides:
                master_info.guidelines = guides

        return master_info

    def get_ufo_master(self, index: int, silent=False) -> Font:
        if not silent:
            print(f"Processing font: {self.info.ui_name.strip()}, master {index}")

        # Build the master-specific data that can be passed when instantiating the UFO
        master_kerning = self.ufo_kerning.get_master_kerning(master_index=index)
        master_info = self.get_master_info(master_index=index)

        # Pass as much data right to the UFO
        ufo = Font(
            features=self.ufo_features.text,
            groups=deepcopy(self.ufo_groups),
            info=master_info,
            kerning=master_kerning,
            lib=self.lib,
        )

        # Add the glyphs
        for name, mm_glyph in self.glyph_masters.items():
            logger.debug(f"    {name}, {type(name)}, {mm_glyph}")
            # TODO: Any way to use the ufoLib2 Glyph directly?
            master_glyph = UfoMasterGlyph(mm_glyph, self.glyphOrder, index)
            master_glyph.build(
                self.minimal, self.include_ps_hints, self.encode_data_base64
            )
            ufo_glyph = ufo.newGlyph(name)
            pen = ufo_glyph.getPointPen()
            master_glyph.drawPoints(pen)
            # FIXME: Anchors work, but typing wrong
            ufo_glyph.anchors = master_glyph.anchors
            ufo_glyph.guidelines = master_glyph.guidelines
            ufo_glyph.height = master_glyph.height
            ufo_glyph.lib = master_glyph.lib
            ufo_glyph.width = master_glyph.width
            ufo_glyph.unicodes = master_glyph.unicodes

        return ufo

    def get_ufo_masters(self, silent=False) -> list[Font]:
        # Prepare data shared by the master UFOs
        ufo_groups, group_order, key_glyphs = transform_groups(
            self.groups,
            self.kerning_class_flags,
            self.glyphOrder,
            self.minimal,
        )
        self.ufo_kerning = UfoKerning(
            self.glyphOrder, ufo_groups, self.mm_kerning, key_glyphs
        )
        self.ufo_groups = self.ufo_kerning.groups

        if group_order:
            self.lib["public.groupOrder"] = group_order
        if key_glyphs:
            self.lib["com.lucasfonts.vfblib.groupKeyGlyphs"] = key_glyphs

        self.ufo_features = Features()
        # Also add non-kerning classes to the feature code
        for name, glyphs in ufo_groups.items():
            if (
                name.startswith(".")
                or not self.add_kerning_groups
                and name.startswith("public.kern")
            ):
                continue

            self.ufo_features.text += f"@{name} = [{' '.join(glyphs)}];\n"

        if self.features_code:
            self.ufo_features.text += f"\n\n{self.features_code}"

        ufo_masters = []
        for i in range(len(self.masters)):
            ufo_masters.append(self.get_ufo_master(i, silent))
        return ufo_masters

    def get_ufos_designspace(
        self, out_path: Path, silent=False
    ) -> tuple[list[Font], DesignSpaceDocument | None]:
        """
        Build UFOs and a DesignSpaceDocument from the VFB contents in memory and return
        them. The DesignSpaceDocument is only returned for VFBs containing more than one
        master. In other cases, the second element of the returned tuple is None.
        """
        ufo_masters = self.get_ufo_masters(silent)
        ds: DesignSpaceDocument | None = None
        if self.axes:
            ds = self.get_designspace(out_path)
        return ufo_masters, ds

    def write(self, out_path: Path, overwrite=False, silent=False, ufoz=False) -> None:
        """
        Write a the VFB contents to master UFOs and a designspace file. The designspace
        file is only written if the VFB contains more than one master.
        """
        # Build UFOs and DesignSpace
        ufos, ds = self.get_ufos_designspace(out_path, silent)

        # Write the master UFOs
        strct = UFOFileStructure.ZIP if ufoz else None
        for index, ufo in enumerate(ufos):
            master_path = self.get_master_path(out_path, index)
            ufo.save(master_path, structure=strct, overwrite=overwrite)
            if not ufoz:
                normalizeUFO(
                    ufoPath=master_path, onlyModified=False, writeModTimes=False
                )

        # Write the Designspace
        if ds:
            ds_path = out_path.with_suffix(".designspace")
            if ds_path.exists():
                if not overwrite:
                    raise FileExistsError(str(ds_path))
            if not silent:
                print(f"Writing designspace: {ds_path}")
            ds.write(str(ds_path))

    def get_designspace(self, out_path: Path) -> DesignSpaceDocument:
        """
        Build and return a DesignSpaceDocument. The out_path argument will be used to
        construct the UFO paths assigned to the source descriptors.
        """
        ds = DesignSpaceDocument()
        ds.axes = self.axes

        # Add labels
        if self.axis_count == 1:
            # Only support the simple case here
            for p in self.primary_instances:
                self.axes[0].axisLabels.append(
                    AxisLabelDescriptor(name=p["name"], userValue=p["values"][0])
                )
        else:
            logger.warning(
                "WARNING: Designspace output of AxisLabelDescriptors is only supported "
                "for VFBs with 1 axis. Please add labels manually."
            )

        # Add sources
        for i in range(self.master_count):
            ds.addSourceDescriptor(
                # designLocation=,
                familyName=self.info.ds_family_name,
                filename=f"{self.get_master_path(out_path.with_suffix('.ufo'), i)}",
                location=get_ds_location(self.axes, self.master_locations[i + 1]),
                name=self.masters[i],
                styleName=f"Master {i}",
            )

        # Add instances
        for i in range(len(self.primary_instances)):
            p = self.primary_instances[i]
            loc = p["values"]
            if not isinstance(loc, list):
                raise TypeError

            style_name = p["name"]
            # FIXME: Support anisotropic interpolation
            ds.addInstanceDescriptor(
                # designLocation=get_ds_design_location(self.axes, loc),
                familyName=self.info.ds_family_name,
                filename=f"instance_ufo/{self.info.ds_family_name}-{style_name}.ufo",
                # lib=,
                # locationLabel="",
                name=f"instance_{i}",
                # postScriptFontName="",
                # FIXME:
                styleMapFamilyName=f"{self.info.ds_family_name} {style_name}".strip(),
                styleMapStyleName=self.info.styleMapStyleName,
                styleName=style_name,
                userLocation=get_ds_location(self.axes, loc, 1),
            )

        return ds

    @classmethod
    def get_master_path(cls, out_path: Path, master_index: int) -> Path:
        if master_index > 0:
            try:
                return out_path.with_stem(f"{out_path.stem}-{master_index}")
            except AttributeError:
                # Python 3.8 doesn't have `Path.with_stem`
                return out_path.with_name(
                    f"{out_path.stem}-{master_index}{out_path.suffix}"
                )
        return out_path
