from typing import Final, Literal

HeaderPosition = Literal["top", "bottom", "left", "right"]

DEFAULT_HEADER_POSITION: Final[HeaderPosition] = "right"
HEADER_POSITIONS: Final[tuple[HeaderPosition, ...]] = ("top", "bottom", "left", "right")


def normalize_header_position(value: str | None) -> HeaderPosition:
    if not value:
        return DEFAULT_HEADER_POSITION
    normalized = value.strip().lower()
    if normalized not in HEADER_POSITIONS:
        raise ValueError(f"unknown header position: {value}")
    return normalized  # type: ignore[return-value]
