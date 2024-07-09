from __future__ import annotations

TT_LIB_KEY = "com.fontlab.v2.tth"
TT_GLYPH_LIB_KEY = "com.fontlab.ttprogram"
PS_GLYPH_LIB_KEY_ADOBE = "com.adobe.type.autohint"
PS_GLYPH_LIB_KEY = "com.adobe.type.autohint.v2"
# TODO: What tool uses the official UFO key?
# PS_GLYPH_LIB_KEY = "public.postscript.hints"


# alignment

ALIGN_CLOSEST_PIXEL = 0
ALIGN_LEFT_BOTTOM = 1
ALIGN_RIGHT_TOP = 2
ALIGN_CENTER = 3
ALIGN_DOUBLE = 4

vfb2ufo_alignment = {
    "default": -1,
    "none": -1,  # Alias
    "round": ALIGN_CLOSEST_PIXEL,
    "bottom": ALIGN_LEFT_BOTTOM,  # Alias
    "left": ALIGN_LEFT_BOTTOM,
    "top": ALIGN_RIGHT_TOP,  # Alias
    "right": ALIGN_RIGHT_TOP,
    "center": ALIGN_CENTER,
    "double": ALIGN_DOUBLE,
}

# There may be other values in the wild, which should be mapped to "round".
# TODO: Use defaultdict?
vfb2ufo_alignment_rev = {
    -1: "default",
    ALIGN_CLOSEST_PIXEL: "round",
    ALIGN_LEFT_BOTTOM: "left",
    ALIGN_RIGHT_TOP: "right",
    ALIGN_CENTER: "center",
    ALIGN_DOUBLE: "double",
}

vfb2ufo_command_codes = {
    "AlignBottom": "alignb",
    "AlignTop": "alignt",
    "SingleLinkH": "singleh",
    "SingleLinkV": "singlev",
    "DoubleLinkH": "doubleh",
    "DoubleLinkV": "doublev",
    "AlignH": "alignh",
    "AlignV": "alignv",
    "InterpolateH": "interpolateh",
    "InterpolateV": "interpolatev",
    "MDeltaH": "mdeltah",
    "MDeltaV": "mdeltav",
    "FDeltaH": "fdeltah",
    "FDeltaV": "fdeltav",
}

vfb2ufo_label_codes = {
    "AlignBottom": "ab",
    "AlignTop": "at",
    "SingleLinkH": "sh",
    "SingleLinkV": "sv",
    "DoubleLinkH": "dh",
    "DoubleLinkV": "dv",
    "AlignH": "ah",
    "AlignV": "av",
    "InterpolateH": "ih",
    "InterpolateV": "iv",
    "MDeltaH": "mh",
    "MDeltaV": "mv",
    "FDeltaH": "fh",
    "FDeltaV": "fv",
    "PSHintReplacement": "hr",
}
