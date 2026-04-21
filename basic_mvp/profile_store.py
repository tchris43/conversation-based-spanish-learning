import json

from config import DEFAULT_USER_ID
from data_paths import get_legacy_file_path, get_user_file_path


def normalize_profile(profile):
    if not isinstance(profile, dict):
        return {"strengths": [], "gaps": []}
    strengths = profile.get("strengths")
    gaps = profile.get("gaps")
    if not isinstance(strengths, list):
        strengths = []
    if not isinstance(gaps, list):
        gaps = []
    normalized_strengths = []
    for item in strengths:
        normalized_item = normalize_profile_entry(item)
        if normalized_item:
            normalized_strengths.append(normalized_item)
    normalized_gaps = []
    for item in gaps:
        normalized_item = normalize_profile_entry(item)
        if normalized_item:
            normalized_gaps.append(normalized_item)
    return {
        "strengths": normalized_strengths,
        "gaps": normalized_gaps,
    }


def normalize_profile_entry(item):
    if not isinstance(item, dict):
        return None
    label = str(item.get("label", "")).strip()
    if not label:
        return None

    evidence_history = item.get("evidence_history")
    if not isinstance(evidence_history, list):
        evidence_history = []
    normalized_history = []
    for evidence in evidence_history:
        evidence_text = str(evidence).strip()
        if evidence_text:
            normalized_history.append(evidence_text)

    legacy_evidence = str(item.get("evidence", "")).strip()
    last_evidence = str(item.get("last_evidence", "")).strip()
    if not last_evidence and legacy_evidence:
        last_evidence = legacy_evidence
    if last_evidence and last_evidence not in normalized_history:
        normalized_history.append(last_evidence)

    count = item.get("count")
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = len(normalized_history) or (1 if last_evidence else 0)
    if count < 0:
        count = len(normalized_history) or (1 if last_evidence else 0)

    return {
        "label": label,
        "count": max(count, len(normalized_history)),
        "last_evidence": last_evidence,
        # AUDIT: Cap stored evidence history so the local profile file does not grow without bound
        # during long testing sessions; if richer analytics are needed later, store timestamps separately.
        "evidence_history": normalized_history[-12:],
    }


def load_profile(user_id=DEFAULT_USER_ID):
    profile_path = get_user_file_path(user_id, "profile.json")
    legacy_path = get_legacy_file_path("profile.json")
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"strengths": [], "gaps": []}
        normalized = normalize_profile(data)
        save_profile(user_id, normalized)
        return normalized
    except json.JSONDecodeError:
        # AUDIT: A manually edited or corrupted profile file should not crash the app; falling back
        # to an empty profile preserves availability but hides data loss unless DEBUGGING.md is checked.
        return {"strengths": [], "gaps": []}
    return normalize_profile(data)


def save_profile(user_id=DEFAULT_USER_ID, profile=None):
    if profile is None:
        profile = {"strengths": [], "gaps": []}
    normalized = normalize_profile(profile)
    profile_path = get_user_file_path(user_id, "profile.json")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_profile_signal(user_id=DEFAULT_USER_ID, kind="", label="", evidence=""):
    profile = load_profile(user_id)
    bucket = "strengths" if kind == "strength" else "gaps"
    evidence_text = str(evidence).strip()

    for item in profile[bucket]:
        if isinstance(item, dict) and item.get("label") == label:
            history = item.get("evidence_history")
            if not isinstance(history, list):
                history = []
            if evidence_text:
                history.append(evidence_text)
            item["evidence_history"] = history[-12:]
            item["last_evidence"] = evidence_text
            item["count"] = max(int(item.get("count", 0) or 0) + 1, len(item["evidence_history"]))
            save_profile(user_id, profile)
            return profile

    profile[bucket].append(
        {
            "label": label,
            "count": 1 if evidence_text else 0,
            "last_evidence": evidence_text,
            "evidence_history": [evidence_text] if evidence_text else [],
        }
    )
    save_profile(user_id, profile)
    return profile


def build_state_summary(profile):
    profile = normalize_profile(profile)
    strengths = profile.get("strengths", [])[-6:]
    gaps = profile.get("gaps", [])[-6:]

    strength_lines = []
    for item in strengths:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        evidence = str(item.get("last_evidence", "")).strip()
        count = item.get("count", 0)
        if not label:
            continue
        if evidence:
            strength_lines.append(f"- {label} ({count}): {evidence}")
        else:
            strength_lines.append(f"- {label} ({count})")

    gap_lines = []
    for item in gaps:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        evidence = str(item.get("last_evidence", "")).strip()
        count = item.get("count", 0)
        if not label:
            continue
        if evidence:
            gap_lines.append(f"- {label} ({count}): {evidence}")
        else:
            gap_lines.append(f"- {label} ({count})")

    summary_parts = []
    if strength_lines:
        summary_parts.append("Known strengths:\n" + "\n".join(strength_lines))
    if gap_lines:
        summary_parts.append("Known gaps:\n" + "\n".join(gap_lines))
    return "\n\n".join(summary_parts)
