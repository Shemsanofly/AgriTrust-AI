"""Regional soil defaults for Tanzania (used when a farm has no lab test or sensor).

USSD cannot read the handset's GPS, so the farmer's chosen region is the location.
Values are indicative topsoil figures per region (dominant soil texture, pH in water,
salinity as EC of saturated paste in dS/m) and should be replaced with TARI / iSDAsoil
data for the farm's exact coordinates when available.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionSoil:
    name: str
    lat: float
    lon: float
    soil_type: str  # loam | sandy loam | sandy | clay (keys of planting.SOIL_CROP_FIT)
    ph: float
    salinity_ec: float


REGIONS: tuple[RegionSoil, ...] = (
    RegionSoil("Arusha", -3.37, 36.68, "loam", 6.5, 0.6),
    RegionSoil("Dar es Salaam", -6.82, 39.27, "sandy", 6.0, 0.8),
    RegionSoil("Dodoma", -6.17, 35.74, "sandy loam", 6.4, 1.2),
    RegionSoil("Geita", -2.87, 32.23, "sandy loam", 5.8, 0.3),
    RegionSoil("Iringa", -7.77, 35.69, "loam", 5.6, 0.3),
    RegionSoil("Kagera", -1.33, 31.81, "loam", 5.2, 0.2),
    RegionSoil("Katavi", -6.35, 31.07, "loam", 5.8, 0.3),
    RegionSoil("Kigoma", -4.88, 29.63, "loam", 5.4, 0.2),
    RegionSoil("Kilimanjaro", -3.35, 37.34, "loam", 6.3, 0.5),
    RegionSoil("Lindi", -10.00, 39.71, "sandy loam", 6.0, 0.4),
    RegionSoil("Manyara", -4.32, 35.90, "sandy loam", 7.6, 2.5),
    RegionSoil("Mara", -1.77, 34.00, "clay", 6.8, 0.8),
    RegionSoil("Mbeya", -8.90, 33.46, "loam", 5.4, 0.2),
    RegionSoil("Morogoro", -6.82, 37.66, "clay", 6.0, 0.4),
    RegionSoil("Mtwara", -10.27, 40.18, "sandy", 5.9, 0.4),
    RegionSoil("Mwanza", -2.52, 32.90, "sandy loam", 6.5, 0.7),
    RegionSoil("Njombe", -9.33, 34.77, "loam", 5.0, 0.1),
    RegionSoil("Pwani", -7.00, 38.90, "sandy loam", 6.2, 0.9),
    RegionSoil("Rukwa", -7.95, 31.60, "loam", 5.7, 0.3),
    RegionSoil("Ruvuma", -10.68, 35.65, "loam", 5.5, 0.2),
    RegionSoil("Shinyanga", -3.66, 33.42, "clay", 7.4, 1.8),
    RegionSoil("Simiyu", -2.83, 34.15, "clay", 7.2, 1.5),
    RegionSoil("Singida", -4.82, 34.74, "sandy loam", 7.0, 1.6),
    RegionSoil("Songwe", -9.10, 32.93, "loam", 5.6, 0.3),
    RegionSoil("Tabora", -5.02, 32.80, "sandy", 5.8, 0.4),
    RegionSoil("Tanga", -5.07, 39.10, "loam", 6.3, 0.6),
)

_BY_NAME = {r.name.lower(): r for r in REGIONS}


def lookup(region: str) -> RegionSoil | None:
    return _BY_NAME.get((region or "").strip().lower())


def salinity_band(ec: float) -> str:
    """FAO classes on EC (dS/m): <2 non-saline, 2-4 slightly saline, >4 saline."""
    if ec < 2:
        return "low"
    if ec <= 4:
        return "moderate"
    return "high"
