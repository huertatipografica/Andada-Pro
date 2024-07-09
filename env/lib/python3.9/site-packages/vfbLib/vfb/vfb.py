from __future__ import annotations

import logging

from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, Iterable
from vfbLib.vfb.glyph import VfbGlyph, VfbGlyphMaster
from vfbLib.vfb.entry import VfbEntry
from vfbLib.vfb.header import VfbHeader
from vfbLib.vfb.info import VfbInfo

if TYPE_CHECKING:
    from io import BufferedReader


logger = logging.getLogger(__name__)


# Convenience objects for vfb access


class Vfb:
    """
    Object to represent the vfb data, with the ability to read and write. You can use
    the Vfb object to access glyphs through dict methods, where the glyph name is the
    key and the glyph object is the value.
    """

    def __init__(
        self,
        vfb_path: Path,
        timing=True,
        minimal=False,
        drop_keys: set[str] | None = None,
        only_header=False,
        unicode_strings=False,
    ) -> None:
        self.vfb_path = vfb_path
        self.timing = timing
        self.minimal = minimal
        if drop_keys is None:
            self.drop_keys = set()
        else:
            self.drop_keys = set(drop_keys)
        self.only_header = only_header
        # String encoding for nametable entries
        self.encoding = "utf-8" if unicode_strings else "cp1252"

        # We need some minimal API to make pen access work ...
        self._glyphs: dict[str, VfbGlyph] = {}
        self.glyph_order: list[str] = []

        # cu2qu accesses the info and lib ...
        self.info = VfbInfo(vfb=self)
        self.lib = {}

        self.master_index = 0
        self.num_masters: int = 0
        self.ttStemsV_count: int = 0
        self.ttStemsH_count: int = 0
        self.read()

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """
        Return the Vfb structure as Dict, e.g. for saving as JSON. The dict has the keys
        "header" and "entries".
        """
        d = {}
        if self.header is not None:
            d["header"] = self.header.as_dict()
        if self.entries:
            d["entries"] = [e.as_dict() for e in self.entries]
        return d

    def clear(self):
        """
        Clear any data that may have been read before.
        """
        self.header: VfbHeader | None = None
        self.entries: list[VfbEntry] = []

    def _decompile_glyphs(self):
        for entry in self.entries:
            if entry.key == "Glyph":
                glyph = VfbGlyph(entry, self)
                name = glyph.decompile()
                i = 0
                while name in self._glyphs:
                    logger.error(f"VFB contains duplicate glyph name: {name}")
                    # Disambiguate duplicate names
                    i += 1
                    name = f"{name}#{i}"
                self._glyphs[name] = glyph
                self.glyph_order.append(name)

    def __contains__(self, key: str) -> bool:
        if not self._glyphs:
            self._decompile_glyphs()
        return key in self._glyphs

    def __getitem__(self, key: str) -> VfbGlyph:
        if not self._glyphs:
            self._decompile_glyphs()
        return self._glyphs[key]

    def getGlyphMaster(self, key: str, master_index: int) -> VfbGlyphMaster:
        return VfbGlyphMaster(self[key], master_index)

    def get_masters(self) -> list[VfbMaster]:
        return [VfbMaster(self, i) for i in range(self.num_masters)]

    def decompile(self) -> None:
        """
        Decompile all entries, except for the ones listed in `drop_keys`.
        """
        start = time()
        for entry in self.entries:
            if entry.key in self.drop_keys:
                continue

            entry.decompile()

        end = time()
        if self.timing:
            print(f"Interpreting binary data took {round((end - start) * 1000)} ms.")

    def items(self) -> Iterable[tuple[str, VfbGlyph]]:
        if not self._glyphs:
            self._decompile_glyphs()
        return self._glyphs.items()

    def keys(self) -> Iterable[str]:
        if not self._glyphs:
            self._decompile_glyphs()
        return self._glyphs.keys()

    def read_stream(self, stream: BufferedReader):
        """
        Lazily read and parse the vfb stream, i.e. parse the header, but only read the
        binary data of other entries.
        """
        start = time()
        self.header = VfbHeader()
        self.header.read(stream)
        if self.only_header:
            return

        entry: VfbEntry | None = None
        while True:
            try:
                entry = VfbEntry(self)
                entry.read(stream)
            except EOFError:
                break

            # Some info needs to be stored for later access, so we decompile a selection
            # of entries right here.

            if entry is not None:
                if entry.key == "Master Count":
                    entry.decompile()
                    if entry.decompiled is not None:
                        self.num_masters = entry.decompiled
                        entry.decompiled = None

                elif entry.key == "TrueType Stems":
                    entry.decompile()
                    if entry.decompiled is not None:
                        self.ttStemsV_count = len(entry.decompiled.get("ttStemsV", []))
                        self.ttStemsH_count = len(entry.decompiled.get("ttStemsH", []))
                        entry.decompiled = None

                if entry.key not in self.drop_keys:
                    self.entries.append(entry)

        end = time()
        if self.timing:
            print(
                "Source file was successfully read in "
                f"{round((end - start) * 1000)} ms."
            )

    def read(self):
        """
        Read data from the file at vfb_path, without decompiling
        """
        self.clear()
        with open(self.vfb_path, "rb") as vfb:
            self.read_stream(vfb)

    def write(self, out_path: Path) -> None:
        """
        Compile any entries with changes, and write the VFB to out_path.
        """
        if self.header is None:
            raise ValueError

        with open(out_path, "wb") as vfb:
            if self.header.modified:
                self.header.compile()
            assert self.header.data
            vfb.write(self.header.data)

            for entry in self.entries:
                if entry.modified:
                    entry.compile()
                vfb.write(entry.header)
                vfb.write(entry.data)
            # File end marker
            vfb.write(b"\05\00\00\00\02\00\00\00")


class VfbMaster:
    """
    Minimal UFO interface for a single master of a multiple master VFB.
    """

    def __init__(self, vfb: Vfb, master_index: int = 0):
        self.vfb = vfb
        self.master_index = master_index

    def __contains__(self, key: str) -> bool:
        return key in self.vfb

    def __getitem__(self, key: str) -> VfbGlyphMaster:
        return self.vfb.getGlyphMaster(key, self.master_index)

    @property
    def info(self) -> VfbInfo:
        return self.vfb.info

    def items(self) -> Iterable[tuple[str, VfbGlyph]]:
        return self.vfb.items()

    def keys(self) -> Iterable[str]:
        return self.vfb.keys()

    def num_masters(self) -> int:
        return self.vfb.num_masters
