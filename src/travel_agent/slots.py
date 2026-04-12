"""Slot and service helpers used by the beginner-friendly travel demo."""

SERVICE_ORDER = ["weather", "hotel", "flight", "restaurant"]
ALL_SLOTS = list(SERVICE_ORDER)

REQUIRED_TRIP_FIELDS = ("destination", "start_date", "end_date")
SLOT_FIELDS: dict[str, list[str]] = {
    "weather": ["destination", "start_date", "end_date"],
    "hotel": ["destination", "start_date", "end_date"],
    "flight": ["origin", "destination", "start_date", "end_date"],
    "restaurant": ["destination", "start_date", "end_date"],
}


def missing_trip_fields(slot_values: dict[str, str]) -> list[str]:
    """Return required trip fields that are still missing."""

    return [field for field in REQUIRED_TRIP_FIELDS if not (slot_values.get(field) or "").strip()]


def format_trip_period(slot_values: dict[str, str]) -> str:
    """Format the selected trip period for user-facing output."""

    start = (slot_values.get("start_date") or "").strip()
    end = (slot_values.get("end_date") or "").strip()

    if start and end:
        return f"{start} ~ {end}"
    if start:
        return start
    return "일정 미정"


def get_departure_city(slot_values: dict[str, str], default: str = "서울") -> str:
    """Return the departure city or a simple default for the flight demo."""

    origin = (slot_values.get("origin") or "").strip()
    return origin or default
