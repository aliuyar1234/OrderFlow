"""UoM (Unit of Measure) normalization utilities."""

from typing import Dict

# Canonical UoM codes per SSOT §7.5.3
CANONICAL_UOMS = {
    "ST", "M", "CM", "MM", "KG", "G", "L", "ML", "KAR", "PAL", "SET"
}

# Mapping from common variations to canonical codes
UOM_MAPPING: Dict[str, str] = {
    # Pieces / Each
    "ST": "ST",
    "STK": "ST",
    "STÜCK": "ST",
    "STUECK": "ST",
    "PCE": "ST",
    "PCS": "ST",
    "PC": "ST",
    "EA": "ST",
    "EACH": "ST",
    "PIECE": "ST",
    "PIECES": "ST",

    # Meters
    "M": "M",
    "MTR": "M",
    "METER": "M",
    "METRE": "M",
    "METRES": "M",

    # Centimeters
    "CM": "CM",
    "ZENTIMETER": "CM",

    # Millimeters
    "MM": "MM",
    "MILLIMETER": "MM",

    # Kilograms
    "KG": "KG",
    "KILO": "KG",
    "KILOGRAM": "KG",
    "KILOGRAMM": "KG",

    # Grams
    "G": "G",
    "GR": "G",
    "GRAM": "G",
    "GRAMM": "G",

    # Liters
    "L": "L",
    "LTR": "L",
    "LITER": "L",
    "LITRE": "L",

    # Milliliters
    "ML": "ML",
    "MILLILITER": "ML",
    "MILLILITRE": "ML",

    # Carton
    "KAR": "KAR",
    "KARTON": "KAR",
    "CTN": "KAR",
    "CARTON": "KAR",

    # Pallet
    "PAL": "PAL",
    "PALETTE": "PAL",
    "PALLET": "PAL",
    "PLT": "PAL",

    # Set
    "SET": "SET",
    "KIT": "SET",
}


def normalize_uom(uom: str | None) -> str | None:
    """Normalize UoM string to canonical code.

    Args:
        uom: Raw UoM string from extraction

    Returns:
        Canonical UoM code or None if unmappable
    """
    if not uom:
        return None

    # Normalize: uppercase, strip whitespace
    uom_normalized = uom.strip().upper()

    # Direct match to canonical
    if uom_normalized in CANONICAL_UOMS:
        return uom_normalized

    # Try mapping
    if uom_normalized in UOM_MAPPING:
        return UOM_MAPPING[uom_normalized]

    # No match
    return None


def is_uom_compatible(uom1: str | None, uom2: str | None) -> bool:
    """Check if two UoMs are compatible (same base unit).

    Args:
        uom1: First UoM
        uom2: Second UoM

    Returns:
        True if compatible or if either is None
    """
    if uom1 is None or uom2 is None:
        return True  # Unknown is compatible with anything

    norm1 = normalize_uom(uom1)
    norm2 = normalize_uom(uom2)

    if norm1 is None or norm2 is None:
        return True  # Unknown is compatible

    # Same UoM
    if norm1 == norm2:
        return True

    # Length units are compatible (M, CM, MM)
    length_units = {"M", "CM", "MM"}
    if norm1 in length_units and norm2 in length_units:
        return True

    # Weight units are compatible (KG, G)
    weight_units = {"KG", "G"}
    if norm1 in weight_units and norm2 in weight_units:
        return True

    # Volume units are compatible (L, ML)
    volume_units = {"L", "ML"}
    if norm1 in volume_units and norm2 in volume_units:
        return True

    return False
