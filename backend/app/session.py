import uuid
from pathlib import Path
from app.engines import DEFAULT_ENGINE
from app.header_position import DEFAULT_HEADER_POSITION, HeaderPosition
from app.models import DetectionRun, EngineName
from app.title_position import DEFAULT_TITLE_POSITION, TitlePosition

_sessions: dict[str, dict] = {}

TMP_DIR = Path("/tmp/blueprint_extractor")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def create_session() -> str:
    session_id = str(uuid.uuid4())
    session_dir = TMP_DIR / session_id
    session_dir.mkdir()
    _sessions[session_id] = {
        "dir": session_dir,
        "page_count": 0,
        "active_engine": DEFAULT_ENGINE,
        "title_position": DEFAULT_TITLE_POSITION,
        "header_position": DEFAULT_HEADER_POSITION,
        "cu_contents_analyzer_id": None,
        "cu_contents_api_version": None,
        "cu_header_analyzer_id": None,
        "cu_header_api_version": None,
        "runs": {},
    }
    return session_id


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def set_page_count(session_id: str, page_count: int) -> None:
    _sessions[session_id]["page_count"] = page_count


def set_active_engine(session_id: str, engine: EngineName) -> None:
    _sessions[session_id]["active_engine"] = engine


def set_title_position(session_id: str, title_position: TitlePosition) -> None:
    _sessions[session_id]["title_position"] = title_position


def get_title_position(session_id: str) -> TitlePosition:
    return _sessions[session_id]["title_position"]


def set_header_position(session_id: str, header_position: HeaderPosition) -> None:
    _sessions[session_id]["header_position"] = header_position


def get_header_position(session_id: str) -> HeaderPosition:
    return _sessions[session_id]["header_position"]


def set_cu_selection(
    session_id: str,
    contents_analyzer_id: str | None,
    contents_api_version: str | None,
    header_analyzer_id: str | None,
    header_api_version: str | None,
) -> None:
    _sessions[session_id]["cu_contents_analyzer_id"] = contents_analyzer_id
    _sessions[session_id]["cu_contents_api_version"] = contents_api_version
    _sessions[session_id]["cu_header_analyzer_id"] = header_analyzer_id
    _sessions[session_id]["cu_header_api_version"] = header_api_version


def get_cu_selection(session_id: str) -> tuple[str | None, str | None, str | None, str | None]:
    sess = _sessions[session_id]
    return (
        sess.get("cu_contents_analyzer_id"),
        sess.get("cu_contents_api_version"),
        sess.get("cu_header_analyzer_id"),
        sess.get("cu_header_api_version"),
    )


def set_session_run(session_id: str, run: DetectionRun) -> None:
    _sessions[session_id]["runs"][run.engine] = run


def get_session_run(session_id: str, engine: EngineName) -> DetectionRun | None:
    return _sessions.get(session_id, {}).get("runs", {}).get(engine)


def get_active_engine(session_id: str) -> EngineName:
    return _sessions[session_id]["active_engine"]


def get_active_run(session_id: str) -> DetectionRun | None:
    engine = get_active_engine(session_id)
    return get_session_run(session_id, engine)


def list_runs(session_id: str) -> dict[EngineName, DetectionRun]:
    return _sessions[session_id]["runs"]


def session_dir(session_id: str) -> Path:
    return _sessions[session_id]["dir"]
