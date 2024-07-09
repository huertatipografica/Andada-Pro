from __future__ import annotations

# try:
#     # NotRequired is only available in Python 3.11+
#     from typing import NotRequired, TypedDict
# except ImportError:
from typing_extensions import NotRequired, TypedDict

from typing import Optional, Tuple
from vfbLib.typing import HintTuple


class TUfoTTZoneDict(TypedDict):
    position: int
    top: bool
    width: int
    # Zone index, shift; index must be str to be saved in lib
    delta: NotRequired[dict[str, int]]


UfoPoint = Tuple[int, int]
UfoComponent = Tuple[str, Tuple[float, float, float, float, int, int]]
UfoGroups = dict[str, list[str]]  # name, glyphs
UfoMasterKerning = dict[Tuple[str, str], int]  # Lstr, Rstr, value
UfoMMKerning = dict[Tuple[str, int], list[int]]  # Lstr, Rid, master values
UfoSegment = Tuple[Optional[str], bool, Optional[str], UfoPoint]
UfoContour = list[UfoSegment]
TUfoTTZonesDict = dict[str, TUfoTTZoneDict]


class TUfoRawStemDict(TypedDict):
    name: str
    round: dict[str, int]
    value: int


class TUfoRawStemsDict(TypedDict):
    ttStemsH: list[TUfoRawStemDict]
    ttStemsV: list[TUfoRawStemDict]


class TUfoGaspRecDict(TypedDict):
    rangeMaxPPEM: int
    rangeGaspBehavior: list[int]


class TUfoStemDict(TypedDict):
    horizontal: bool
    name: str
    round: dict[str, int]
    width: int


class TUfoStemsDict(TypedDict):
    ttStemsH: list[TUfoStemDict]
    ttStemsV: list[TUfoStemDict]


class TUfoStemPPMDict(TypedDict):
    stem: int
    round: dict[str, int]


class TUfoStemPPMsDict(TypedDict):
    ttStemsH: list[TUfoStemPPMDict]
    ttStemsV: list[TUfoStemPPMDict]


class UfoGuide(TypedDict):
    angle: float | int
    color: NotRequired[str]
    name: NotRequired[str]
    x: int
    y: int


class UfoHintingV2(TypedDict):
    flexList: NotRequired[list]
    hintSetList: NotRequired[list[UfoHintSet]]
    id: NotRequired[str]


class UfoHintSet(TypedDict):
    pointTag: str
    stems: list[str | HintTuple]
