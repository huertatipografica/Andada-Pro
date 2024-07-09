from __future__ import annotations

from io import BufferedWriter, BytesIO
from struct import pack


def write_encoded_value(
    value: int, stream: BufferedWriter | BytesIO, signed=True
) -> None:
    # Encode an integer value and write it to the stream. The "signed" param
    # only applies to the longest representation form.
    if -107 <= value <= 107:
        # 1-byte representation
        encoded = pack(">B", (value + 0x8B))
    elif 107 < value <= 1131:
        # 2-byte representation
        encoded = pack(">H", (value + 0xF694))
    elif -1131 <= value < -107:
        # 2-byte representation, negative values
        encoded = pack(">H", (-value + 0xFA94))
    else:
        # 5-byte representation
        write_value_5(value, stream, signed)
        return

    stream.write(encoded)


def write_value_5(value: int, stream: BufferedWriter | BytesIO, signed=True) -> None:
    # Write an integer value to the stream using the longest encoding (4 bytes plus
    # marker byte).
    fmt = "i" if signed else "I"
    encoded = pack(f">B{fmt}", 0xFF, value)
    stream.write(encoded)
