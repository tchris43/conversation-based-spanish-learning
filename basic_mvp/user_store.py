import json
import re

from config import DEFAULT_USER_ID
from data_paths import (
    get_last_active_user_path,
    get_user_dir,
    get_users_index_path,
    get_users_root_dir,
    normalize_user_id,
)


_SAFE_DISPLAY = re.compile(r"\s+")


def normalize_profile_name(profile_name):
    text = str(profile_name or "").strip()
    text = _SAFE_DISPLAY.sub(" ", text)
    return text


def _default_users_index():
    default_name = DEFAULT_USER_ID.replace("-", " ").strip() or "Local User"
    return {
        "users": [
            {
                "user_id": normalize_user_id(DEFAULT_USER_ID),
                "display_name": default_name.title(),
            }
        ]
    }


def _load_users_index():
    path = get_users_index_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raw = _default_users_index()
    users = raw.get("users", []) if isinstance(raw, dict) else []
    normalized = []
    seen = set()
    for user in users:
        if not isinstance(user, dict):
            continue
        user_id = normalize_user_id(user.get("user_id"))
        display_name = normalize_profile_name(user.get("display_name"))
        if not display_name:
            display_name = user_id
        if user_id in seen:
            continue
        seen.add(user_id)
        normalized.append({"user_id": user_id, "display_name": display_name})
    if not normalized:
        normalized = _default_users_index()["users"]
    return {"users": normalized}


def _save_users_index(index_data):
    path = get_users_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index_data


def list_users():
    index_data = _load_users_index()
    users = index_data.get("users", [])
    users = sorted(users, key=lambda item: item.get("display_name", "").lower())
    return users


def create_user(profile_name):
    display_name = normalize_profile_name(profile_name)
    if not display_name:
        return None
    index_data = _load_users_index()
    users = index_data["users"]
    existing_names = {item["display_name"].lower(): item for item in users}
    if display_name.lower() in existing_names:
        user = existing_names[display_name.lower()]
        set_last_active_user(user["user_id"])
        return user

    base = normalize_user_id(display_name)
    if not base:
        base = normalize_user_id(DEFAULT_USER_ID)
    existing_ids = {item["user_id"] for item in users}
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}-{counter}"
        counter += 1

    user = {"user_id": candidate, "display_name": display_name}
    users.append(user)
    _save_users_index(index_data)
    get_user_dir(candidate).mkdir(parents=True, exist_ok=True)
    # AUDIT: We set last active on create so a refresh lands on the new profile;
    # if a create flow is canceled later, this may feel surprising to the user.
    set_last_active_user(candidate)
    return user


def set_last_active_user(user_id):
    path = get_last_active_user_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalize_user_id(user_id), encoding="utf-8")


def get_last_active_user():
    path = get_last_active_user_path()
    try:
        user_id = normalize_user_id(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    users = list_users()
    user_ids = {item["user_id"] for item in users}
    if user_id in user_ids:
        return user_id
    return None


def ensure_user_exists(user_id):
    normalized_id = normalize_user_id(user_id)
    users = list_users()
    for item in users:
        if item["user_id"] == normalized_id:
            return item
    fallback_name = normalized_id.replace("-", " ").title()
    index_data = _load_users_index()
    user = {"user_id": normalized_id, "display_name": fallback_name}
    index_data["users"].append(user)
    _save_users_index(index_data)
    get_user_dir(normalized_id).mkdir(parents=True, exist_ok=True)
    return user


def initialize_user_store():
    index_data = _load_users_index()
    _save_users_index(index_data)
    users_root = get_users_root_dir()
    users_root.mkdir(parents=True, exist_ok=True)
    last_active = get_last_active_user()
    if last_active:
        return last_active
    default_user = ensure_user_exists(DEFAULT_USER_ID)
    set_last_active_user(default_user["user_id"])
    return default_user["user_id"]
