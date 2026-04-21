import json
import math
from datetime import date, datetime, timedelta

from config import DEFAULT_USER_ID
from data_paths import get_legacy_file_path, get_user_file_path


def _today():
    return date.today()


def _to_iso(day):
    return day.isoformat()


def _parse_iso_day(raw, fallback):
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return fallback
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def _normalize_word(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def _word_key(value):
    return _normalize_word(value).lower()


def _next_offset_days(current_offset_days):
    if current_offset_days <= 0:
        return 1
    if current_offset_days == 1:
        return 4
    return current_offset_days * 2


def _default_entry(word, today):
    return {
        "word": word,
        "introduced_on": _to_iso(today),
        "next_due_on": _to_iso(today),
        "next_offset_days": 0,
        "consecutive_correct": 0,
        "status": "learning",
    }


def _normalize_entry(raw_entry, today):
    word = _normalize_word(raw_entry.get("word")) if isinstance(raw_entry, dict) else ""
    if not word:
        return None

    introduced_day = _parse_iso_day(raw_entry.get("introduced_on"), today)
    next_due_day = _parse_iso_day(raw_entry.get("next_due_on"), introduced_day)
    next_offset_days = raw_entry.get("next_offset_days", 0)
    try:
        next_offset_days = int(next_offset_days)
    except (TypeError, ValueError):
        next_offset_days = 0
    if next_offset_days < 0:
        next_offset_days = 0

    consecutive_correct = raw_entry.get("consecutive_correct", 0)
    try:
        consecutive_correct = int(consecutive_correct)
    except (TypeError, ValueError):
        consecutive_correct = 0
    if consecutive_correct < 0:
        consecutive_correct = 0

    status = str(raw_entry.get("status", "learning")).strip().lower()
    if status not in {"learning", "mastered"}:
        status = "learning"

    return {
        "word": word,
        "introduced_on": _to_iso(introduced_day),
        "next_due_on": _to_iso(next_due_day),
        "next_offset_days": next_offset_days,
        "consecutive_correct": consecutive_correct,
        "status": status,
    }


def normalize_spaced_review_store(store, today=None):
    today = today or _today()
    if not isinstance(store, dict):
        store = {}

    words = store.get("words", [])
    if not isinstance(words, list):
        words = []

    normalized = []
    seen_keys = set()
    for raw_entry in words:
        entry = _normalize_entry(raw_entry, today)
        if entry is None:
            continue
        key = _word_key(entry["word"])
        if key in seen_keys:
            # AUDIT: Duplicate entries for the same word create conflicting schedules and non-deterministic
            # today selection; keep the first normalized instance.
            continue
        seen_keys.add(key)
        normalized.append(entry)

    return {"words": normalized}


def load_spaced_review_store(user_id=DEFAULT_USER_ID, today=None):
    today = today or _today()
    spaced_review_path = get_user_file_path(user_id, "spaced_review.json")
    legacy_path = get_legacy_file_path("spaced_review.json")
    try:
        with open(spaced_review_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        try:
            with open(legacy_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            normalized = normalize_spaced_review_store(raw, today=today)
            save_spaced_review_store(user_id, normalized)
            return normalized
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
    except json.JSONDecodeError:
        # AUDIT: Corrupt JSON should not crash the app; reset to an empty store and let the user
        # recover from backups if needed.
        raw = {}
    return normalize_spaced_review_store(raw, today=today)


def save_spaced_review_store(user_id=DEFAULT_USER_ID, store=None):
    if store is None:
        store = {"words": []}
    normalized = normalize_spaced_review_store(store)
    spaced_review_path = get_user_file_path(user_id, "spaced_review.json")
    spaced_review_path.parent.mkdir(parents=True, exist_ok=True)
    with open(spaced_review_path, "w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2)
    return normalized


def merge_seed_words(user_id=DEFAULT_USER_ID, seed_words=None, today=None):
    today = today or _today()
    store = load_spaced_review_store(user_id, today=today)
    seen = {_word_key(entry.get("word")): entry for entry in store["words"]}

    if not isinstance(seed_words, list):
        seed_words = [seed_words]

    for raw_word in seed_words:
        word = _normalize_word(raw_word)
        if not word:
            continue
        key = _word_key(word)
        if key in seen:
            continue
        entry = _default_entry(word, today)
        store["words"].append(entry)
        seen[key] = entry

    return save_spaced_review_store(user_id, store)


def get_todays_words(user_id=DEFAULT_USER_ID, today=None, include_mastered=False):
    today = today or _today()
    store = load_spaced_review_store(user_id, today=today)
    today_words = []
    for entry in store["words"]:
        status = entry.get("status", "learning")
        if status == "mastered" and not include_mastered:
            continue
        due_day = _parse_iso_day(entry.get("next_due_on"), today)
        if due_day <= today:
            today_words.append(entry.get("word", ""))
    # AUDIT: Keep output deterministic so repeated calls in the same turn produce stable prompts.
    today_words = sorted({w for w in today_words if w}, key=lambda w: w.lower())
    return today_words


def get_mastered_words(user_id=DEFAULT_USER_ID, today=None):
    today = today or _today()
    store = load_spaced_review_store(user_id, today=today)
    mastered = []
    for entry in store["words"]:
        if entry.get("status") == "mastered":
            word = entry.get("word", "")
            if word:
                mastered.append(word)
    return sorted({w for w in mastered if w}, key=lambda w: w.lower())


def record_word_outcome(user_id=DEFAULT_USER_ID, word="", was_correct=False, today=None):
    today = today or _today()
    key = _word_key(word)
    if not key:
        return load_spaced_review_store(user_id, today=today), None

    store = load_spaced_review_store(user_id, today=today)
    target = None
    for entry in store["words"]:
        if _word_key(entry.get("word")) == key:
            target = entry
            break

    if target is None:
        target = _default_entry(_normalize_word(word), today)
        store["words"].append(target)

    target["status"] = "learning"
    if was_correct:
        target["consecutive_correct"] = int(target.get("consecutive_correct", 0)) + 1
        if target["consecutive_correct"] >= 4:
            target["status"] = "mastered"
            target["next_due_on"] = ""
        else:
            introduced_day = _parse_iso_day(target.get("introduced_on"), today)
            current_offset = int(target.get("next_offset_days", 0))
            next_offset = _next_offset_days(current_offset)
            target["next_offset_days"] = next_offset
            next_due_day = introduced_day + timedelta(days=next_offset)
            if next_due_day < today:
                # AUDIT: If the learner practices late, keeping a past due date causes immediate re-queues.
                # Clamp to today so the next due date is always forward-looking.
                next_due_day = today
            target["next_due_on"] = _to_iso(next_due_day)
    else:
        target["consecutive_correct"] = 0
        current_due = _parse_iso_day(target.get("next_due_on"), today)
        days_until_normal = max(1, (current_due - today).days)
        retry_days = max(1, int(math.ceil(days_until_normal / 2)))
        target["next_due_on"] = _to_iso(today + timedelta(days=retry_days))
        # AUDIT: We intentionally keep `next_offset_days` unchanged on an incorrect result so the learner
        # retries sooner but does not permanently reset the long-term schedule progression.

    store = save_spaced_review_store(user_id, store)
    return store, target


def build_spaced_review_state(user_id=DEFAULT_USER_ID, today=None):
    today = today or _today()
    store = load_spaced_review_store(user_id, today=today)
    return {
        "todays_words": get_todays_words(user_id, today=today),
        "learned_words": get_mastered_words(user_id, today=today),
        "store_size": len(store.get("words", [])),
        "store": store,
    }
