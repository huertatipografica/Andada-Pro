from __future__ import annotations

from io import BytesIO
from struct import pack
from typing import Any
from vfbLib.compilers.value import write_encoded_value, write_value_5


# Compilers for VFB entries


class BaseCompiler:
    """
    Base class to compile vfb data.
    """

    def compile(self, data: Any, master_count: int = 0) -> bytes:
        """
        Compile the JSON-like main data structure and return the compiled binary data.

        Args:
            data (Any): The main data structure.
            master_count (int, optional): The number of masters. Defaults to 0.

        Returns:
            bytes: The compiled binary data.
        """
        self.master_count = master_count
        self.stream = BytesIO()
        self._compile(data)
        return self.stream.getvalue()

    def _compile(self, data: Any) -> None:
        raise NotImplementedError

    @classmethod
    def merge(cls, masters_data: list[Any], data: Any) -> None:
        """
        Merge the data of additional masters into the main data structure. This operates
        on the uncompiled JSON-like data structure.

        Args:
            masters_data (List[Any]): The additional masters data as a list with one
                entry per master.
            data (Any): The main data structure.
        """
        # Must be implemented for compilers that need it, e.g. the GlyphCompiler.
        pass

    def write_bytes(self, value: bytes) -> None:
        """
        Write binary data to the stream.

        Args:
            value (bytes): The data.
        """
        self.stream.write(value)

    def write_encoded_value(self, value: int, shortest=True) -> None:
        """
        Encode and write an int value to the stream. Optionally don't apply the length
        encoding optimization.

        Args:
            value (int): The value to write to the stream.
            shortest (bool, optional): Whether to write in the shortest possible
                notation. Defaults to True.
        """
        if shortest:
            write_encoded_value(value, self.stream)
        else:
            write_value_5(value, self.stream)

    def write_float(self, value: float, fmt: str = "d") -> None:
        """
        Write a float value to the stream.
        """
        encoded = pack(fmt, value)
        self.stream.write(encoded)

    def write_uint1(self, value: int) -> None:
        """
        Write a 1-byte unsigned value to the stream.
        """
        encoded = pack(">B", value)
        self.stream.write(encoded)

    def write_uint8(self, value: int) -> None:
        """
        Write a uint8 value to the stream.
        """
        encoded = pack(">H", value)
        self.stream.write(encoded)
