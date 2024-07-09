from __future__ import annotations

import logging

from io import BytesIO
from vfbLib.helpers import binaryToIntList
from vfbLib.parsers.base import BaseParser, read_encoded_value


logger = logging.getLogger(__name__)


class TrueTypeInfoParser(BaseParser):
    """
    A parser that reads data as "TrueType Info" values.
    """

    def read_key_value_pairs_encoded(
        self,
        stream: BytesIO,
        num: int,
        target: list,
        key_names: dict[int, str] | None = None,
    ):
        if key_names is None:
            key_names = {}
        for _ in range(num):
            k = self.read_uint8(stream)
            v = read_encoded_value(stream)
            target.append({key_names.get(k, str(k)): v})

    def _parse(self):
        info_names = {
            0x33: "0x33",
            0x34: "0x34",
            0x35: "0x35",
            0x36: "0x36",
            0x37: "0x37",
            0x38: "0x38",
            0x39: "tt_font_info_settings",  # 0 = false, 65536 = true
            0x3A: "units_per_em",  # duplicate
            0x3B: "0x3b",
            0x3C: "lowest_rec_ppem",
            0x3D: "font_direction_hint",
            0x3E: "weight_class",  # duplicate
            0x3F: "width_class",  # duplicate
            0x40: "embedding",
            0x41: "subscript_x_size",
            0x42: "subscript_y_size",
            0x43: "subscript_x_offset",
            0x44: "subscript_y_offset",
            0x45: "superscript_x_size",
            0x46: "superscript_y_size",
            0x47: "superscript_x_offset",
            0x48: "superscript_y_offset",
            0x49: "strikeout_size",
            0x4A: "strikeout_position",
            0x4B: "ibm_classification",  # ibm_classification + subclass
            0x4C: "OpenTypeOS2Panose",
            0x4D: "OpenTypeOS2TypoAscender",
            0x4E: "OpenTypeOS2TypoDescender",
            0x4F: "OpenTypeOS2TypoLineGap",
            0x50: "0x50",
            0x51: "OpenTypeOS2WinAscent",
            0x52: "OpenTypeOS2WinDescent",
            0x53: "Hdmx PPMs 1",
            0x54: "Codepages",
            0x56: "timestamp",
            0x57: "0x57",
            0x58: "Hdmx PPMs 2",
            0x5C: "Average Width",
        }
        s = self.stream
        info = []

        while True:
            k = self.read_uint8(s)

            if k == 0x32:
                return info

            elif k in (0x33, 0x34, 0x35, 0x36, 0x37, 0x38):
                info.append([info_names.get(k, str(k)), read_encoded_value(s)])

            elif k == 0x39:
                bits = binaryToIntList(read_encoded_value(s))
                settings = {
                    16: "use_custom_tt_values",
                    17: "create_vdmx",
                    18: "add_null_cr_space",
                }
                options = [settings.get(i, str(i)) for i in bits]
                info.append([info_names.get(k, str(k)), options])

            elif k in (0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F):
                info.append([info_names.get(k, f"bit{k}"), read_encoded_value(s)])

            elif k in (
                0x40,
                0x41,
                0x42,
                0x43,
                0x44,
                0x45,
                0x46,
                0x47,
                0x48,
                0x49,
                0x4A,
                0x4B,
            ):
                info.append([info_names.get(k, str(k)), read_encoded_value(s)])

            elif k == 0x4C:  # PANOSE?
                v = [self.read_uint8(s) for _ in range(10)]
                info.append([info_names.get(k, str(k)), v])

            elif k in (0x4D, 0x4E, 0x4F, 0x50, 0x51, 0x52):
                info.append([info_names.get(k, str(k)), read_encoded_value(s)])

            elif k == 0x53:
                num_values = read_encoded_value(s)
                v = [self.read_uint8(s) for _ in range(num_values)]
                info.append([info_names.get(k, str(k)), v])

            elif k == 0x54:
                # Codepages
                info.append(
                    [
                        info_names.get(k, str(k)),
                        [
                            read_encoded_value(s, signed=False),
                            read_encoded_value(s, signed=False),
                        ],
                    ]
                )

            elif k == 0x56:
                # Timestamp, unsigned
                info.append(
                    [info_names.get(k, str(k)), read_encoded_value(s, signed=False)]
                )

            elif k in (0x57, 0x5C):
                info.append([info_names.get(k, str(k)), read_encoded_value(s)])

            elif k == 0x58:
                num_values = read_encoded_value(s)
                v = [self.read_uint8(s) for _ in range(num_values)]
                info.append([info_names.get(k, hex(k)), v])

            else:
                logger.info(f"Unknown key in TrueType info: {hex(k)}")


class TrueTypeStemsParser(BaseParser):
    def _parse(self):
        stream = self.stream
        names = ("ttStemsV", "ttStemsH")
        result = {}
        for i in range(2):
            direction = []
            num_stems = read_encoded_value(stream)
            for _ in range(num_stems):
                width = read_encoded_value(stream)
                stem_name_length = self.read_uint8(stream)
                stem_name = stream.read(stem_name_length).decode("cp1252")
                ppm6 = read_encoded_value(stream)

                direction.append(
                    {
                        "value": width,
                        "name": stem_name,
                        "round": {"6": ppm6},
                    }
                )
            result[names[i]] = direction

        assert stream.read() == b""
        return result


class TrueTypeStemPpemsParser(BaseParser):
    def _parse(self):
        stream = self.stream
        names = ("ttStemsV", "ttStemsH")
        result = {}
        for i in range(2):
            direction = []
            num_stems = read_encoded_value(stream)
            d = {}
            for j in range(num_stems):
                for k in range(2, 6):
                    ppm = read_encoded_value(stream)
                    d[str(k)] = ppm

                direction.append(
                    {
                        "stem": j,
                        "round": d.copy(),
                    }
                )
            result[names[i]] = direction

        assert stream.read() == b""
        return result


class TrueTypeStemPpems1Parser(BaseParser):
    # PPEM 1 for each stem is stored in a separate entry ...
    def _parse(self):
        stream = self.stream
        names = ("ttStemsV", "ttStemsH")
        result = {}
        for i in range(2):
            direction = []
            num_stems = (self.ttStemsV_count, self.ttStemsH_count)[i]
            if num_stems is None:
                raise ValueError

            for j in range(num_stems):
                ppm = read_encoded_value(stream)
                direction.append(
                    {
                        "stem": j,
                        "round": {"1": ppm},
                    }
                )
            result[names[i]] = direction

        assert stream.read() == b""
        return result


class TrueTypeZoneDeltasParser(BaseParser):
    def _parse(self):
        stream = self.stream
        num_deltas = read_encoded_value(stream)
        result = {}
        for _ in range(num_deltas):
            # Index into Bottom + Top Zones
            index = read_encoded_value(stream)
            ppm = read_encoded_value(stream)
            shift = read_encoded_value(stream)
            if index in result:
                result[index][ppm] = shift
            else:
                result[index] = {ppm: shift}

        assert stream.read() == b""
        return result


class TrueTypeZonesParser(BaseParser):
    def _parse(self):
        stream = self.stream
        names = ("ttZonesT", "ttZonesB")
        result = {}
        for i in range(2):
            side = []
            num_zones = read_encoded_value(stream)
            logger.debug(f"Zones: {num_zones}")
            for _ in range(num_zones):
                position = read_encoded_value(stream)
                width = read_encoded_value(stream)
                logger.debug(f"    pos: {position}, width: {width}")
                name_length = read_encoded_value(stream)
                logger.debug(f"Name of length {name_length} follows")
                zone_name = stream.read(name_length).decode("cp1252")
                side.append(
                    {
                        "position": position,
                        "value": width,
                        "name": zone_name,
                    }
                )
            result[names[i]] = side

        assert stream.read() == b""
        return result
