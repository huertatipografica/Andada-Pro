from __future__ import annotations

from vfbLib.compilers.glyph import GlyphCompiler

from vfbLib.parsers.base import (
    BaseParser,
    # EncodedValueParser,
    EncodedValueListParser,
    EncodedValueListWithCountParser,
    EncodedKeyValuesParser,
    EncodedKeyValuesParser1742,
    GaspParser,
    GlyphEncodingParser,
    OpenTypeClassFlagsParser,
)
from vfbLib.parsers.bitmap import BackgroundBitmapParser, GlyphBitmapParser
from vfbLib.parsers.cmap import CustomCmapParser
from vfbLib.parsers.glyph import (
    GlyphAnchorsParser,
    GlyphAnchorsSuppParser,
    GlyphGDEFParser,
    GlyphOriginParser,
    GlyphParser,
    GlyphUnicodeParser,
    GlyphUnicodeSuppParser,
    LinkParser,
    MaskParser,
)
from vfbLib.parsers.guides import (
    GlobalGuidesParser,
    GuidePropertiesParser,
)
from vfbLib.parsers.mm import (
    AnisotropicInterpolationsParser,
    AxisMappingsCountParser,
    AxisMappingsParser,
    MasterLocationParser,
    PrimaryInstancesParser,
)
from vfbLib.parsers.numeric import (
    DoubleListParser,
    DoubleParser,
    # FloatListParser,
    IntParser,
    IntListParser,
    PanoseParser,
    SignedIntParser,
)
from vfbLib.parsers.options import ExportOptionsParser
from vfbLib.parsers.ps import PostScriptInfoParser
from vfbLib.parsers.text import (
    NameRecordsParser,
    OpenTypeClassParser,
    OpenTypeStringParser,
    StringParser,
)
from vfbLib.parsers.truetype import (
    TrueTypeInfoParser,
    TrueTypeStemPpemsParser,
    TrueTypeStemPpems1Parser,
    TrueTypeStemsParser,
    TrueTypeZoneDeltasParser,
    TrueTypeZonesParser,
)


# fmt: off
parser_classes = {
    513: ("513", BaseParser, None),
    527: ("527", BaseParser, None),
    1024: ("sgn", StringParser, None),
    1025: ("ffn", StringParser, None),
    1026: ("psn", StringParser, None),
    1027: ("tfn", StringParser, None),
    1028: ("weight_name", StringParser, None),
    1029: ("Italic Angle", DoubleParser, None),
    1030: ("underlinePosition", SignedIntParser, None),
    1031: ("underlineThickness", IntParser, None),
    1034: ("Monospaced", IntParser, None),
    1037: ("copyright", StringParser, None),
    1038: ("description", StringParser, None),
    1039: ("manufacturer", StringParser, None),
    1044: ("Type 1 Unique ID", SignedIntParser, None),
    1046: ("version full", StringParser, None),
    1047: ("Slant Angle", DoubleParser, None),
    1048: ("weight", SignedIntParser, None),  # Weight Class
    1054: ("MS Character Set", IntParser, None),
    1056: ("Menu Name", StringParser, None),
    1057: ("PCL ID", IntParser, None),
    1058: ("VP ID", IntParser, None),
    1059: ("1059", BaseParser, None),
    1060: ("MS ID", IntParser, None),
    1061: ("trademark", StringParser, None),
    1062: ("designer", StringParser, None),
    1063: ("designerURL", StringParser, None),
    1064: ("manufacturerURL", StringParser, None),
    1065: ("width_name", StringParser, None),
    1066: ("Default Glyph", StringParser, None),
    1068: ("1068", EncodedValueListWithCountParser, None),
    1069: ("License", StringParser, None),
    1070: ("License URL", StringParser, None),
    1090: ("FOND Family ID", IntParser, None),
    1092: ("FOND Name", StringParser, None),
    1093: ("1093", BaseParser, None),
    1118: ("panose", PanoseParser, None),
    1121: ("vendorID", StringParser, None),
    1127: ("Style Name", StringParser, None),
    1128: ("version", StringParser, None),
    1129: ("UniqueID", StringParser, None),
    1130: ("versionMajor", IntParser, None),
    1131: ("versionMinor", IntParser, None),
    1132: ("year", IntParser, None),
    1133: ("Type 1 XUIDs", IntListParser, None),
    1134: ("Type 1 XUIDs Count", IntParser, None),
    1135: ("upm", IntParser, None),
    1136: ("PCLT Table", EncodedValueListParser, None),
    1137: ("tsn", StringParser, None),
    1138: ("Name Records", NameRecordsParser, None),
    1139: ("OT Mac Name", StringParser, None),
    1140: ("1140", BaseParser, None),
    1141: ("Custom CMAPs", CustomCmapParser, None),
    1247: ("Primary Instance Locations", DoubleListParser, None),
    1250: ("Glyph Unicode", GlyphUnicodeParser, None),
    1253: ("Glyph Unicode Non-BMP", GlyphUnicodeSuppParser, None),
    1254: ("Primary Instances", PrimaryInstancesParser, None),
    1255: ("TrueType Zones", TrueTypeZonesParser, None),
    1264: ("TrueType Info", TrueTypeInfoParser, None),
    1265: ("Gasp Ranges", GaspParser, None),
    1267: ("Selection", IntParser, None),
    1268: ("TrueType Stem PPEMs", TrueTypeStemPpemsParser, None),
    1269: ("TrueType Stems", TrueTypeStemsParser, None),
    1270: ("hhea_line_gap", IntParser, None),
    1271: ("1271", EncodedValueListParser, None),
    1272: ("Pixel Snap", IntParser, None),
    1273: ("TrueType Zone Deltas", TrueTypeZoneDeltasParser, None),
    1274: ("Zone Stop PPEM", IntParser, None),
    1275: ("Code Stop PPEM", IntParser, None),
    1276: ("openTypeFeatures", OpenTypeStringParser, None),
    1277: ("OpenType Class", OpenTypeClassParser, None),
    1278: ("hhea_ascender", SignedIntParser, None),
    1279: ("hhea_descender", SignedIntParser, None),
    1294: ("Global Guides", GlobalGuidesParser, None),
    1296: ("Global Guide Properties", GuidePropertiesParser, None),
    1410: ("1410", BaseParser, None),
    1500: ("Encoding", GlyphEncodingParser, None),
    1501: ("Encoding Mac", GlyphEncodingParser, None),
    1502: ("1502", IntParser, None),
    1503: ("Master Count", IntParser, None),
    1504: ("Master Name", StringParser, None),
    1505: ("Master Location", MasterLocationParser, None),
    1513: ("Axis Count", IntParser, None),
    1514: ("Axis Name", StringParser, None),
    1515: ("Axis Mappings Count", AxisMappingsCountParser, None),
    1516: ("Axis Mappings", AxisMappingsParser, None),
    1517: ("Default Weight Vector", DoubleListParser, None),  # Interp. coeffs for all masters  # noqa: E501
    1523: ("Anisotropic Interpolation Mappings", AnisotropicInterpolationsParser, None),
    1524: ("TrueType Stem PPEMs 1", TrueTypeStemPpems1Parser, None),
    1530: ("Blue Values Count", IntParser, None),
    1531: ("Other Blues Count", IntParser, None),
    1532: ("Family Blues Count", IntParser, None),
    1533: ("Family Other Blues Count", IntParser, None),
    1534: ("StemSnapH Count", IntParser, None),
    1535: ("StemSnapV Count", IntParser, None),
    1536: ("PostScript Info", PostScriptInfoParser, None),
    1604: ("1604", IntParser, None),
    1742: ("1742", EncodedKeyValuesParser1742, None),
    1743: ("OpenType Export Options", EncodedKeyValuesParser, None),
    1744: ("Export Options", ExportOptionsParser, None),
    2001: ("Glyph", GlyphParser, GlyphCompiler),
    2007: ("Background Bitmap", BackgroundBitmapParser, None),
    2008: ("Links", LinkParser, None),
    2009: ("Mask", MaskParser, None),
    2010: ("2010", BaseParser, None),
    2011: ("2011", BaseParser, None),
    2012: ("Mark Color", IntParser, None),
    2013: ("Glyph Bitmaps", GlyphBitmapParser, None),
    2014: ("Binary Tables", BaseParser, None),
    2015: ("Glyph User Data", StringParser, None),
    2016: ("Font User Data", StringParser, None),
    2017: ("Glyph Note", StringParser, None),
    2018: ("Glyph GDEF Data", GlyphGDEFParser, None),
    2020: ("Glyph Anchors Supplemental", GlyphAnchorsSuppParser, None),
    2021: ("Unicode Ranges", IntParser, None),
    2022: ("Export PCLT Table", IntParser, None),
    2023: ("2023", EncodedValueListParser, None),  # Glyph
    2024: ("OpenType Metrics Class Flags", OpenTypeClassFlagsParser, None),
    2025: ("fontNote", StringParser, None),
    2026: ("OpenType Kerning Class Flags", OpenTypeClassFlagsParser, None),
    2027: ("Glyph Origin", GlyphOriginParser, None),
    2028: ("2028", EncodedValueListParser, None),  # MM, proportional to num of masters
    2029: ("Glyph Anchors MM", GlyphAnchorsParser, None),  # MM-compatible
    2031: ("Glyph Guide Properties", GuidePropertiesParser, None),
    2032: ("2032", IntParser, None),
}
# fmt: on

# Make sure the human-readable keys are unique
all_classes = [key for key, _, _ in parser_classes.values()]
assert len(set(all_classes)) == len(all_classes)

entry_ids = {v[0]: k for k, v in parser_classes.items()}

ignore_minimal = [
    "Background Bitmap",
    "fontNote",
    "Global Guides",
    "Glyph Bitmaps",
    "Glyph Guide Properties",
    "Mark Color",
    "Mask",
]
