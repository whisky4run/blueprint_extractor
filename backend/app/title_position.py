from typing import Final, Literal

TitlePosition = Literal["top", "bottom", "left", "right"]

DEFAULT_TITLE_POSITION: Final[TitlePosition] = "top"
TITLE_POSITIONS: Final[tuple[TitlePosition, ...]] = ("top", "bottom", "left", "right")


def normalize_title_position(value: str | None) -> TitlePosition:
    if not value:
        return DEFAULT_TITLE_POSITION
    normalized = value.strip().lower()
    if normalized not in TITLE_POSITIONS:
        raise ValueError(f"unknown title position: {value}")
    return normalized  # type: ignore[return-value]
