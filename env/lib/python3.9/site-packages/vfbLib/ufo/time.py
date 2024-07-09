from __future__ import annotations

from datetime import datetime
from sys import version_info

if version_info[0] == 3 and version_info[1] > 10:
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc


TIME_ZERO = 2082841200


def convert_timestamp(t: int) -> datetime:
    """
    Convert the FontLab timestamp to a datetime object.
    """
    # 1970-01-01 is the earliest timestamp in FL notation, enforce it
    if t < TIME_ZERO:
        t = TIME_ZERO

    if version_info[0] == 3 and version_info[1] > 10:
        return datetime.fromtimestamp(t - TIME_ZERO, UTC)
    return datetime.utcfromtimestamp(t - TIME_ZERO)
