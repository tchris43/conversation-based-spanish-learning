import json

from data_paths import get_legacy_file_path, get_user_file_path


def _normalize_gameplan(gameplan):
    if not isinstance(gameplan, dict):
        return {}
    roadmap_summary = str(gameplan.get("roadmap_summary", "")).strip()
    modules = gameplan.get("modules", [])
    if not isinstance(modules, list):
        modules = []
    normalized_modules = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        title = str(module.get("title", "")).strip()
        goal = str(module.get("goal", "")).strip()
        if not title:
            continue
        normalized_modules.append({"title": title, "goal": goal})
    spaced_review_seed = gameplan.get("spaced_review_seed", [])
    if not isinstance(spaced_review_seed, list):
        spaced_review_seed = []
    spaced_review_seed = [str(item).strip() for item in spaced_review_seed if str(item).strip()]
    return {
        "roadmap_summary": roadmap_summary,
        "modules": normalized_modules[:12],
        "spaced_review_seed": spaced_review_seed[:20],
    }


def load_gameplan(user_id):
    path = get_user_file_path(user_id, "gameplan.json")
    legacy_path = get_legacy_file_path("gameplan.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            raw = json.loads(legacy_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        # AUDIT: Legacy fallback is a one-time convenience migration path. The first user who reads here
        # receives the old global plan copy; if multiple profiles are created after upgrade, only that first
        # profile will inherit legacy gameplan content.
        normalized = _normalize_gameplan(raw)
        save_gameplan(user_id, normalized)
        return normalized
    except json.JSONDecodeError:
        return {}
    return _normalize_gameplan(raw)


def save_gameplan(user_id, gameplan):
    normalized = _normalize_gameplan(gameplan)
    path = get_user_file_path(user_id, "gameplan.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def load_module_progress(user_id):
    path = get_user_file_path(user_id, "module_progress.json")
    legacy_path = get_legacy_file_path("module_progress.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            raw = json.loads(legacy_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        # AUDIT: Same as gameplan migration: legacy module progress is copied into the first reading profile.
        # This is acceptable for local migration but should be replaced by explicit user-bound migration logic.
        normalized = raw if isinstance(raw, dict) else {}
        save_module_progress(user_id, normalized)
        return normalized
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items()}


def save_module_progress(user_id, progress):
    normalized = progress if isinstance(progress, dict) else {}
    path = get_user_file_path(user_id, "module_progress.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized
