from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePath
import re


_VHF_FULLCOLOR_NAME = re.compile(
    r"^avf(?P<index>\d{4})(?P<suffix>[abc])(?:\.(?:png|raw|raw\.Z|dcm))?$"
)
_SUFFIX_MM = {
    "a": Decimal("0"),
    "b": Decimal("0.3333333333"),
    "c": Decimal("0.6666666667"),
}


@dataclass(frozen=True)
class VisibleHumanFemaleFullcolorIndex:
    filename: str
    millimetre_index: int
    submillimetre_suffix: str
    nominal_source_z_mm: Decimal


def parse_visible_human_female_fullcolor_name(
    path: str | PurePath,
) -> VisibleHumanFemaleFullcolorIndex:
    """Parse source naming only; the result is not a patient-space transform."""
    filename = PurePath(path).name
    match = _VHF_FULLCOLOR_NAME.fullmatch(filename)
    if match is None:
        raise ValueError(
            f"not a Visible Human Female fullcolor filename: {filename}"
        )
    millimetre_index = int(match.group("index"))
    suffix = match.group("suffix")
    return VisibleHumanFemaleFullcolorIndex(
        filename=filename,
        millimetre_index=millimetre_index,
        submillimetre_suffix=suffix,
        nominal_source_z_mm=Decimal(millimetre_index) + _SUFFIX_MM[suffix],
    )
