import re

# Must stay identical to Parts-Backend/data/util/qplink.py's FILENAME_RE - this is the
# client-side mirror so QPLink can skip non-conforming files locally instead of wasting
# a round-trip to the server just to get rejected.
FILENAME_RE = re.compile(r"^(\d{3}-\d{2})-(P)?(\d+)\.(pdf|stl)$", re.IGNORECASE)


def is_valid_part_filename(filename: str) -> bool:
    """Checks a filename against the team's part naming convention: PPP-YY-[P]NNNN.ext"""
    return FILENAME_RE.match(filename) is not None
