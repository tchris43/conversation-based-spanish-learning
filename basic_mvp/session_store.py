import json

from data_paths import get_user_file_path


def _default_session():
    return {}


def load_session(user_id):
    path = get_user_file_path(user_id, "session.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_session()
    return raw if isinstance(raw, dict) else _default_session()


def save_session(user_id, session_state):
    normalized = session_state if isinstance(session_state, dict) else _default_session()
    path = get_user_file_path(user_id, "session.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def clear_session(user_id):
    return save_session(user_id, _default_session())
