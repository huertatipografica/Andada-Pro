from __future__ import annotations

from argparse import ArgumentParser
from fontTools.cu2qu.ufo import font_to_quadratic, fonts_to_quadratic
from pathlib import Path
from vfbLib.version import build_date
from vfbLib.vfb.vfb import Vfb


def vfbcu2qu():
    parser = ArgumentParser(
        description=(
            "VFB Cubic to Quadratic Converter\nCopyright (c) 2023 by LucasFonts\n"
            f"Build {build_date}"
        )
    )
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        nargs=1,
        help="output folder",
    )
    parser.add_argument(
        "-fo",
        "--force-overwrite",
        action="store_true",
        default=False,
        help="force overwrite",
    )
    parser.add_argument(
        "inputpath",
        type=str,
        nargs=1,
        help="input file path (.vfb)",
    )
    parser.add_argument(
        "outputpath",
        type=str,
        nargs="?",
        help="output file path (.vfb)",
    )
    parser.add_argument(
        "-m",
        "--max-err-em",
        type=float,
        nargs=1,
        help="Maximum allowed error, relative to the font's units per em.",
    )
    args = parser.parse_args()
    if args:
        vfb_path = Path(args.inputpath[0])
        print(parser.description)
        print(f"Reading file {vfb_path} ...")
        vfb = Vfb(vfb_path, drop_keys={"Links"})
        kwargs = {
            "max_err_em": None,
            "max_err": None,
            "reverse_direction": True,
            "stats": None,
            "dump_stats": False,
            "remember_curve_type": False,  # Prevent write access to the lib
            "all_quadratic": True,
        }
        if args.max_err_em:
            kwargs["max_err_em"] = args.max_err_em[0]
        if vfb.num_masters == 1:
            modified = font_to_quadratic(vfb, **kwargs)
        elif vfb.num_masters > 1:
            vfbs = vfb.get_masters()
            modified = fonts_to_quadratic(vfbs, **kwargs)
        else:
            print(f"Unsupported number of masters: {vfb.num_masters}")
            return

        if not modified:
            print("File was not modified.")
            return

        suffix = ".qu.vfb"
        if args.path:
            suffix = ".vfb"
            out_path = (Path(args.path[0]) / vfb_path.name).with_suffix(suffix)
        else:
            out_path = vfb_path.with_suffix(suffix)
        if out_path.exists():
            if not args.force_overwrite:
                print(
                    "Output file exists, new file was not saved. "
                    "Use -fo to force overwriting."
                )
                raise FileExistsError

        print(f"Saving converted file to {out_path}.")
        vfb.write(out_path)
    else:
        parser.print_help()
