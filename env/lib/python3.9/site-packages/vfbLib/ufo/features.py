from __future__ import annotations

from re import search


def rename_kern_classes_in_feature_code(data: list[str]) -> list[str]:
    """
    Convert references to kerning classes in the feature code to current UFO naming
    standards (public.kern1, public.kern2).
    """
    features = []
    for line in data:
        if "#" in line:
            code, comment = line.split("#", 1)
        else:
            code = line
            comment = None

        if m := search(r"^([\t\s]*)(enum )?(pos) +([\S]+) ([\S]+) +([\S]+.*)$", code):
            indent, enum, pos, L, R, value = m.groups()
            if L.startswith("@_"):
                L = f"@public.kern1.{L[1:]}"
            if R.startswith("@_"):
                R = f"@public.kern2.{R[1:]}"
            if enum is None:
                enum = ""
            code = f"{indent}{enum}{pos} {L} {R} {value}"
            if comment:
                code += f"#{comment}"
            features.append(code)
        else:
            features.append(line)

    return features
