from pathlib import Path
import re

from config import DATA_DIR, DEFAULT_USER_ID


_SAFE_USER_ID = re.compile(r"[^a-zA-Z0-9._-]+")


def normalize_user_id(user_id):
    text = str(user_id or "").strip()
    if not text:
        text = DEFAULT_USER_ID
    text = _SAFE_USER_ID.sub("_", text)
    text = text.strip("._-")
    if not text:
        text = DEFAULT_USER_ID
    return text


def get_user_dir(user_id):
    user_key = normalize_user_id(user_id)
    return DATA_DIR / "users" / user_key


def get_user_file_path(user_id, filename):
    return get_user_dir(user_id) / filename


def get_legacy_file_path(filename):
    return DATA_DIR / filename


def get_users_root_dir():
    return DATA_DIR / "users"


def get_users_index_path():
    return get_users_root_dir() / "users_index.json"


def get_last_active_user_path():
    return DATA_DIR / "last_active_user.txt"
