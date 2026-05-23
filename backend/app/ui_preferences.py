import json
import os
import threading
from pathlib import Path


_LOCK = threading.Lock()


def _prefs_path() -> Path:
    configured = os.environ.get("APP_UI_PREFERENCES_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("/app_data/ui_preferences.json")


def _default_payload() -> dict:
    return {
        "cu_selection": {
            "contents_analyzer_id": "",
            "contents_api_version": "",
            "header_analyzer_id": "",
            "header_api_version": "",
        },
        "analyzer_cache": {
            "api_version": "",
            "fetched_at": None,
            "analyzers": [],
        },
    }


def load_preferences() -> dict:
    path = _prefs_path()
    with _LOCK:
        if not path.exists():
            return _default_payload()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _default_payload()
    if not isinstance(data, dict):
        return _default_payload()
    payload = _default_payload()
    payload.update(data)
    return payload


def save_preferences(payload: dict) -> dict:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
