import uuid
from pathlib import Path
from app.models import DetectedPart

_sessions: dict[str, dict] = {}

TMP_DIR = Path("/tmp/blueprint_extractor")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def create_session() -> str:
    session_id = str(uuid.uuid4())
    session_dir = TMP_DIR / session_id
    session_dir.mkdir()
    _sessions[session_id] = {"dir": session_dir, "parts": [], "page_count": 0}
    return session_id


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def set_session_parts(session_id: str, parts: list[DetectedPart], page_count: int) -> None:
    _sessions[session_id]["parts"] = parts
    _sessions[session_id]["page_count"] = page_count


def session_dir(session_id: str) -> Path:
    return _sessions[session_id]["dir"]
