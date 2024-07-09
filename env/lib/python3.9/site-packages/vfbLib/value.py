from __future__ import annotations

from argparse import ArgumentParser
from fontTools.misc.textTools import deHexStr, hexStr
from io import BytesIO
from vfbLib.compilers.value import write_encoded_value
from vfbLib.parsers.value import read_encoded_value
from vfbLib.version import build_date


def yuri():
    parser = ArgumentParser(
        description=(f"vfbtool\nCopyright (c) 2023 by LucasFonts\nBuild {build_date}")
    )
    parser.add_argument(
        "-e",
        "--encode",
        action="store_true",
        default=False,
        help="Encode value instead of decoding",
    )
    parser.add_argument(
        "-l",
        "--long",
        action="store_true",
        default=False,
        help="Output longest notation when encoding",
    )
    parser.add_argument(
        "-s",
        "--signed",
        action="store_true",
        default=False,
        help="Treat value as signed",
    )
    parser.add_argument(
        "hexstring",
        type=str,
        nargs="+",
        help="Input hex string",
    )
    args = parser.parse_args()
    if args:
        if args.encode:
            stream = BytesIO()
            for value in args.hexstring:
                write_encoded_value(int(value), stream, args.signed)
            print(hexStr(stream.getvalue()))
        else:
            data = deHexStr("".join(args.hexstring))
            stream = BytesIO(data)
            while True:
                try:
                    print(read_encoded_value(stream, args.signed))
                except EOFError:
                    break

    else:
        parser.print_help()
