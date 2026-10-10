

VALID_SPECIALIZATIONS = [
    "General Physician",
    "Cardiologist",
    "Nephrologist",
    "Endocrinologist",
    "Gastroenterologist",
    "Dermatologist",
    "Neurologist",
    "Orthopedic",
    "Ophthalmologist",
    "Psychiatrist",
    "Pulmonologist",
    "Emergency Medicine",
]


def snap_specialization(value: str) -> str:
    """Map free-text like "Nephrology" or "kidney doctor" to a real column value."""
    spec = (value or "").strip()
    if not spec:
        return "General Physician"

    for valid in VALID_SPECIALIZATIONS:
        if valid.lower() == spec.lower():
            return valid

    low = spec.lower()
    for valid in VALID_SPECIALIZATIONS:
        root = valid.lower().replace("ist", "").replace("ian", "")
        if root and root in low:
            return valid

    return "General Physician"
