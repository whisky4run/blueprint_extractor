from typing import Final

from app.models import EngineName

DEFAULT_ENGINE: Final[EngineName] = "azure_cu"
AVAILABLE_ENGINES: Final[tuple[EngineName, ...]] = ("opencv", "azure_cu")

ENGINE_LABELS: Final[dict[EngineName, str]] = {
    "opencv": "OpenCV切り出し",
    "azure_cu": "AzureCU切り出し",
}


def normalize_engine(engine: str | None) -> EngineName:
    if not engine:
        return DEFAULT_ENGINE
    value = engine.strip().lower()
    if value not in AVAILABLE_ENGINES:
        raise ValueError(f"unknown engine: {engine}")
    return value  # type: ignore[return-value]
