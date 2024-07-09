from __future__ import annotations

# try:
#     # NotRequired is only available in Python 3.11+
#     from typing import NotRequired, TypedDict
# except ImportError:
from typing_extensions import NotRequired, TypedDict

from typing import Any, Literal, Tuple


Point = Tuple[int, int]


class Anchor(TypedDict):
    name: NotRequired[str]
    x: int
    x1: NotRequired[int]
    y: int
    y1: NotRequired[int]


ClassFlagDict = dict[str, Tuple[int, int]]


class Component(TypedDict):
    gid: int
    offsetX: list[int]
    offsetY: list[int]
    scaleX: list[float]
    scaleY: list[float]


GaspList = list[dict[str, int]]


class GdefDict(TypedDict):
    anchors: NotRequired[list[Anchor]]
    carets: NotRequired[list[tuple[int, int]]]
    glyph_class: NotRequired[str]
    unknown: NotRequired[list[int]]


class GlyphData(TypedDict):
    components: NotRequired[list[Component]]
    # constants: NotRequired[Tuple[Any, ...]]
    guides: NotRequired[GuideDict]
    hints: NotRequired[HintDict]
    imported: NotRequired[Any]  # FIXME
    kerning: NotRequired[dict[int, list[int]]]
    metrics: NotRequired[list[Point]]
    name: NotRequired[str]
    nodes: NotRequired[list[MMNode]]
    num_masters: NotRequired[int]
    # num_node_values: NotRequired[int]
    tth: NotRequired[list[Instruction]]


class Guide(TypedDict):
    angle: float | int
    pos: int


GuideList = list[Guide]


class GuideDict(TypedDict):
    h: list[GuideList]
    v: list[GuideList]


class GuideProperty(TypedDict):
    color: NotRequired[str]
    index: int
    name: NotRequired[str]


GuidePropertyList = list[GuideProperty]


class Hint(TypedDict):
    pos: int
    width: int


class HintDict(TypedDict):
    h: list[list[Hint]]
    v: list[list[Hint]]
    hintmasks: NotRequired[list[dict[str, int]]]


HintTuple = Tuple[str, int, int]


class Instruction(TypedDict):
    cmd: str
    params: dict[str, int]


class LinkDict(TypedDict):
    x: NotRequired[list[tuple[int, int]]]
    y: NotRequired[list[tuple[int, int]]]


class MaskData(GlyphData):
    num: int
    reserved0: NotRequired[int]


class MMAnchor(TypedDict):
    x: list[int]
    y: list[int]


class MMHintsDict(TypedDict):
    h: list[list[Hint]]
    v: list[list[Hint]]


class MMNode(TypedDict):
    flags: int
    points: list[list[Point]]
    type: Literal["move", "line", "curve", "qcurve"]


class TTCommandDict(TypedDict):
    name: str
    params: list[str]
