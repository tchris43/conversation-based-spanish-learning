import json

from config import DEFAULT_USER_ID, OPENAI_MODEL, client
from model_calls import debug_log_model_input
from normalize import coerce_text, extract_first_json_object, normalize_gradio_history, wrap_input_text
from profile_store import build_state_summary, record_profile_signal
from prompts import (
    load_conclude_assessment_prompt,
    load_conclude_session_prompt,
    load_correction_prompt,
    load_gameplan_prompt,
    load_module_generator_prompt,
    load_planning_prompt,
    load_session_prompt,
)
from spaced_review_store import build_spaced_review_state, record_word_outcome as store_record_word_outcome

CORRECTION_TOOL_DEF = {
    "type": "function",
    "name": "correction",
    "description": "Rewrite a learner's Spanish utterance into corrected, natural conversational Spanish.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_utterance": {"type": "string"},
            "previous_assistant_message": {"type": "string"},
        },
        "required": ["user_utterance", "previous_assistant_message"],
        "additionalProperties": False,
    },
    # AUDIT: Strict schemas reduce argument-shape drift but can fail on older SDKs.
    "strict": True,
}

CONCLUDE_TOOL_DEF = {
    "type": "function",
    "name": "conclude",
    "description": "Conclude the assessment by outputting a seed list of spaced-review words and a suggested next focus area.",
    "parameters": {
        "type": "object",
        "properties": {
            "review_seed_words": {"type": "array", "items": {"type": "string"}},
            "next_focus": {"type": "string"},
        },
        # AUDIT: The Responses API requires `required` to include every property key, even if you
        # conceptually want an optional arg. Use an empty string or empty list when values are unknown.
        "required": ["review_seed_words", "next_focus"],
        "additionalProperties": False,
    },
    # AUDIT: Strict schemas reduce argument-shape drift but can fail on older SDKs.
    "strict": True,
}

RECORD_STRENGTH_GAP_TOOL_DEF = {
    "type": "function",
    "name": "record_strength_gap",
    "description": "Record a meaningful learner strength or gap during the conversation for later summarization.",
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string"},
            "label": {"type": "string"},
            "evidence": {"type": "string"},
        },
        # AUDIT: The Responses API requires `required` to include every property key in `properties`.
        # If something is unknown, pass an empty string.
        "required": ["kind", "label", "evidence"],
        "additionalProperties": False,
    },
    # AUDIT: Strict schemas reduce argument-shape drift but can fail on older SDKs.
    "strict": True,
}


RECORD_WORD_OUTCOME_TOOL_DEF = {
    "type": "function",
    "name": "record_word_outcome",
    "description": "Record whether a todays_words item was used accurately during the module session.",
    "parameters": {
        "type": "object",
        "properties": {
            "word": {"type": "string"},
            "outcome": {"type": "string", "enum": ["correct", "incorrect"]},
            "reason": {"type": "string"},
        },
        # AUDIT: The Responses API requires `required` to include every property key in `properties`.
        # Use an empty string when a field is not available.
        "required": ["word", "outcome", "reason"],
        "additionalProperties": False,
    },
    "strict": True,
}


CONCLUDE_SESSION_TOOL_DEF = {
    "type": "function",
    "name": "conclude_session",
    "description": "Wrap up the active module session and produce new strengths, gaps, and review words.",
    "parameters": {
        "type": "object",
        "properties": {
            "module_summary": {"type": "string"},
        },
        "required": ["module_summary"],
        "additionalProperties": False,
    },
    "strict": True,
}


def normalize_profile_state(profile_state):
    if not isinstance(profile_state, dict):
        return {"strengths": [], "gaps": []}
    strengths = profile_state.get("strengths")
    gaps = profile_state.get("gaps")
    if not isinstance(strengths, list):
        strengths = []
    if not isinstance(gaps, list):
        gaps = []
    return {"strengths": strengths, "gaps": gaps}


def normalize_adjustment_state(summary):
    if isinstance(summary, str):
        return summary.strip()
    if summary is None:
        return ""
    return coerce_text(summary).strip()


def run_correction_tool(user_utterance, previous_assistant_message=""):
    correction_prompt = load_correction_prompt()
    context_prefix = ""
    if previous_assistant_message:
        context_prefix = (
            "Previous assistant message (for context):\n"
            + previous_assistant_message.strip()
            + "\n\n"
        )

    input_messages = [
        {"role": "system", "content": wrap_input_text(correction_prompt)},
        {
            "role": "user",
            "content": wrap_input_text(
                context_prefix + "Learner message:\n" + user_utterance
            ),
        },
    ]
    debug_log_model_input(label="run_correction_tool", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    corrected = (getattr(response, "output_text", "") or "").strip()
    # AUDIT: If correction.md is too permissive, this may return extra text; tighten correction.md if needed.
    return corrected


def run_conclude_tool(review_seed_words, next_focus, profile_state):
    profile_state = normalize_profile_state(profile_state)
    next_focus_text = coerce_text(next_focus).strip()
    words = []

    if isinstance(review_seed_words, list):
        for value in review_seed_words:
            word = coerce_text(value).strip()
            if word:
                words.append(word)
    elif review_seed_words:
        word = coerce_text(review_seed_words).strip()
        if word:
            words.append(word)

    # AUDIT: Large word lists will create a huge chat message; keep the demo output readable.
    words = words[:12]

    return {
        "review_seed_words": words,
        "next_focus": next_focus_text,
        "strengths": profile_state.get("strengths", []),
        "gaps": profile_state.get("gaps", []),
    }


def format_conversation_transcript(conversation_history):
    lines = []
    for message in normalize_gradio_history(conversation_history):
        role = message.get("role", "")
        content = coerce_text(message.get("content", "")).strip()
        if not role or not content:
            continue
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def run_conclude_assessment(
    *,
    conversation_history,
    goal_summary,
    best_guess_level,
    state_summary,
    fallback_review_seed_words,
    fallback_next_focus,
):
    assessment_prompt = load_conclude_assessment_prompt()
    transcript = format_conversation_transcript(conversation_history)
    user_payload = (
        "Goal summary:\n"
        + (goal_summary.strip() or "(none)")
        + "\n\nBest guess level:\n"
        + (best_guess_level.strip() or "(none)")
        + "\n\nPersistent learner state summary:\n"
        + (state_summary.strip() or "(none)")
        + "\n\nConversation transcript:\n"
        + (transcript or "(empty)")
    )

    input_messages = [
        {"role": "system", "content": wrap_input_text(assessment_prompt)},
        {"role": "user", "content": wrap_input_text(user_payload)},
    ]
    debug_log_model_input(label="run_conclude_assessment", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    parsed = extract_first_json_object((getattr(response, "output_text", "") or "").strip()) or {}

    strengths = parsed.get("strengths")
    if not isinstance(strengths, list):
        strengths = []
    strengths = [coerce_text(item).strip() for item in strengths if coerce_text(item).strip()][:8]

    gaps = parsed.get("gaps")
    if not isinstance(gaps, list):
        gaps = []
    gaps = [coerce_text(item).strip() for item in gaps if coerce_text(item).strip()][:8]

    review_seed_words = parsed.get("review_seed_words")
    if not isinstance(review_seed_words, list):
        review_seed_words = fallback_review_seed_words
    review_seed_words = [
        coerce_text(item).strip() for item in review_seed_words if coerce_text(item).strip()
    ][:12]

    next_focus = coerce_text(parsed.get("next_focus", "")).strip() or fallback_next_focus
    where_they_stand = coerce_text(parsed.get("where_they_stand", "")).strip()
    session_summary = coerce_text(parsed.get("session_summary", "")).strip()

    return {
        "strengths": strengths,
        "gaps": gaps,
        "where_they_stand": where_they_stand,
        "next_focus": next_focus,
        "review_seed_words": review_seed_words,
        "session_summary": session_summary,
    }


def run_record_word_outcome(*, word, outcome, reason, user_id=DEFAULT_USER_ID):
    word = coerce_text(word).strip()
    reason_text = coerce_text(reason).strip()
    normalized_outcome = "correct" if outcome == "correct" else "incorrect"
    store, entry = store_record_word_outcome(user_id=user_id, word=word, was_correct=(normalized_outcome == "correct"))
    next_due = entry.get("next_due_on") if entry else ""
    # AUDIT: This tool assumes the same spaced review store handles the live practice state.
    # If the store becomes distributed or remote, the tool needs to synchronize via an explicit service call.
    return {
        "word": word,
        "outcome": normalized_outcome,
        "reason": reason_text,
        "next_due_on": next_due,
        "spaced_review_state": build_spaced_review_state(user_id=user_id),
    }


def format_module_transcript(conversation_history):
    return format_conversation_transcript(conversation_history)


def run_conclude_session(
    *,
    conversation_history,
    module_context,
    state_summary,
    todays_words,
    learned_words,
):
    prompt = load_conclude_session_prompt()
    transcript = format_module_transcript(conversation_history)
    user_payload = (
        "Module context:\n"
        + json.dumps(module_context or {}, ensure_ascii=False, indent=2)
        + "\n\nLearner state summary:\n"
        + (state_summary.strip() or "(none)")
        + "\n\nToday's words:\n"
        + json.dumps(todays_words or [], ensure_ascii=False)
        + "\n\nLearned words:\n"
        + json.dumps(learned_words or [], ensure_ascii=False)
        + "\n\nConversation transcript:\n"
        + (transcript or "(empty)")
    )

    input_messages = [
        {"role": "system", "content": wrap_input_text(prompt)},
        {"role": "user", "content": wrap_input_text(user_payload)},
    ]
    debug_log_model_input(label="run_conclude_session", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    parsed = extract_first_json_object((getattr(response, "output_text", "") or "").strip()) or {}

    strengths = parsed.get("strengths")
    if not isinstance(strengths, list):
        strengths = []
    strengths = [coerce_text(item).strip() for item in strengths if coerce_text(item).strip()][:8]

    gaps = parsed.get("gaps")
    if not isinstance(gaps, list):
        gaps = []
    gaps = [coerce_text(item).strip() for item in gaps if coerce_text(item).strip()][:8]

    session_summary = coerce_text(parsed.get("session_summary", "")).strip()
    new_review_words = parsed.get("new_review_words")
    if not isinstance(new_review_words, list):
        new_review_words = []
    new_review_words = [
        coerce_text(item).strip() for item in new_review_words if coerce_text(item).strip()
    ][:20]

    return {
        "strengths": strengths,
        "gaps": gaps,
        "session_summary": session_summary,
        "new_review_words": new_review_words,
    }


def run_generate_gameplan(
    *,
    goal_summary,
    time_constraint,
    assessment,
    state_summary,
):
    gameplan_prompt = load_gameplan_prompt()
    assessment_payload = {
        "session_summary": assessment.get("session_summary", ""),
        "where_they_stand": assessment.get("where_they_stand", ""),
        "strengths": assessment.get("strengths", []),
        "gaps": assessment.get("gaps", []),
        "next_focus": assessment.get("next_focus", ""),
        "review_seed_words": assessment.get("review_seed_words", []),
    }
    user_payload = (
        "Goal summary:\n"
        + (goal_summary.strip() or "(none)")
        + "\n\nTime constraint:\n"
        + (time_constraint.strip() or "(none)")
        + "\n\nAssessment:\n"
        + json.dumps(assessment_payload, ensure_ascii=False, indent=2)
        + "\n\nPersistent learner state summary:\n"
        + (state_summary.strip() or "(none)")
    )

    input_messages = [
        {"role": "system", "content": wrap_input_text(gameplan_prompt)},
        {"role": "user", "content": wrap_input_text(user_payload)},
    ]
    debug_log_model_input(label="run_generate_gameplan", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    parsed = extract_first_json_object((getattr(response, "output_text", "") or "").strip()) or {}

    roadmap_summary = coerce_text(parsed.get("roadmap_summary", "")).strip()
    modules = parsed.get("modules")
    if not isinstance(modules, list):
        modules = []
    normalized_modules = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        title = coerce_text(module.get("title", "")).strip()
        goal = coerce_text(module.get("goal", "")).strip()
        if not title:
            continue
        normalized_modules.append({"title": title, "goal": goal})
    normalized_modules = normalized_modules[:12]

    if not normalized_modules:
        goal_text = coerce_text(goal_summary).strip()
        next_focus_text = coerce_text(assessment.get("next_focus", "")).strip()
        gaps = assessment.get("gaps", [])
        if not isinstance(gaps, list):
            gaps = []
        normalized_gaps = [coerce_text(item).strip() for item in gaps if coerce_text(item).strip()]

        fallback_modules = []
        fallback_modules.append(
            {
                "title": "Build comfort in everyday conversation",
                "goal": goal_text or "Practice short, natural Spanish exchanges in everyday situations.",
            }
        )
        if next_focus_text:
            fallback_modules.append(
                {
                    "title": "Strengthen the next focus area",
                    "goal": next_focus_text,
                }
            )
        if normalized_gaps:
            fallback_modules.append(
                {
                    "title": "Work on the biggest communication gap",
                    "goal": normalized_gaps[0],
                }
            )

        # AUDIT: Empty module lists leave the learner stranded in the assessment UI with no way to advance.
        # This fallback guarantees a minimally usable roadmap even when `gameplan.md` returns weak or invalid JSON.
        normalized_modules = fallback_modules[:3]

    if not roadmap_summary and normalized_modules:
        roadmap_summary = (
            "Start with practical everyday conversation, then strengthen the next focus area, "
            "and finally target the biggest communication gap that emerged in assessment."
        )

    spaced_review_seed = parsed.get("spaced_review_seed")
    if not isinstance(spaced_review_seed, list):
        spaced_review_seed = assessment.get("review_seed_words", [])
    spaced_review_seed = [
        coerce_text(item).strip()
        for item in spaced_review_seed
        if coerce_text(item).strip()
    ][:20]

    return {
        "roadmap_summary": roadmap_summary,
        "modules": normalized_modules,
        "spaced_review_seed": spaced_review_seed,
    }


def run_planning_prompt(
    *,
    goal_summary,
    assessment,
    best_guess_level,
    state_summary,
):
    planning_prompt = load_planning_prompt()
    user_payload = (
        "Learner goal:\n"
        + (coerce_text(goal_summary).strip() or "(none)")
        + "\n\nCurrent standing:\n"
        + (coerce_text(assessment.get("where_they_stand", "")).strip() or "(none)")
        + "\n\nBest guess level:\n"
        + (coerce_text(best_guess_level).strip() or "(none)")
        + "\n\nState summary:\n"
        + (coerce_text(state_summary).strip() or "(none)")
    )

    input_messages = [
        {"role": "system", "content": wrap_input_text(planning_prompt)},
        {"role": "user", "content": wrap_input_text(user_payload)},
    ]
    debug_log_model_input(label="run_planning_prompt", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    return (getattr(response, "output_text", "") or "").strip()


def run_module_generator(
    *,
    module_title,
    module_goal,
    goal_summary,
    where_they_stand,
    best_guess_level,
    state_summary,
    spaced_review_state,
    todays_words,
    time_constraint,
):
    module_prompt = load_module_generator_prompt()
    # AUDIT: If `module_generator.md` is empty, the fallback prompt is generic and may produce weak scenarios.
    # Keep the real prompt file populated before relying on module generation quality.
    user_payload = (
        "Module title:\n"
        + (coerce_text(module_title).strip() or "(none)")
        + "\n\nModule goal:\n"
        + (coerce_text(module_goal).strip() or "(none)")
        + "\n\nLearner goal:\n"
        + (coerce_text(goal_summary).strip() or "(none)")
        + "\n\nWhere the learner stands:\n"
        + (coerce_text(where_they_stand).strip() or "(none)")
        + "\n\nBest guess level:\n"
        + (coerce_text(best_guess_level).strip() or "(none)")
        + "\n\nState summary:\n"
        + (coerce_text(state_summary).strip() or "(none)")
        + "\n\nTime constraint:\n"
        + (coerce_text(time_constraint).strip() or "(none)")
        + "\n\nSpaced review state:\n"
        + json.dumps(spaced_review_state or {}, ensure_ascii=False, indent=2)
        + "\n\nToday's words:\n"
        + json.dumps(todays_words or [], ensure_ascii=False)
    )

    input_messages = [
        {"role": "system", "content": wrap_input_text(module_prompt)},
        {"role": "user", "content": wrap_input_text(user_payload)},
    ]
    debug_log_model_input(label="run_module_generator", input_messages=input_messages)
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    parsed = extract_first_json_object((getattr(response, "output_text", "") or "").strip()) or {}

    spaced_review_focus = parsed.get("spaced_review_focus")
    if not isinstance(spaced_review_focus, list):
        spaced_review_focus = []
    spaced_review_focus = [
        coerce_text(item).strip() for item in spaced_review_focus if coerce_text(item).strip()
    ][:12]

    return {
        "title": coerce_text(parsed.get("title", module_title)).strip() or coerce_text(module_title).strip(),
        "goal": coerce_text(parsed.get("goal", module_goal)).strip() or coerce_text(module_goal).strip(),
        "scenario": coerce_text(parsed.get("scenario", "")).strip(),
        "session_prompt_seed": coerce_text(parsed.get("session_prompt_seed", "")).strip(),
        "spaced_review_focus": spaced_review_focus,
        "completion_signal": coerce_text(parsed.get("completion_signal", "")).strip(),
    }


def collect_tool_calls(completed_response):
    correction_calls = []
    conclude_calls = []
    record_strength_gap_calls = []
    record_word_outcome_calls = []
    conclude_session_calls = []
    if completed_response is None:
        return {
            "correction_calls": correction_calls,
            "conclude_calls": conclude_calls,
            "record_strength_gap_calls": record_strength_gap_calls,
            "record_word_outcome_calls": record_word_outcome_calls,
            "conclude_session_calls": conclude_session_calls,
        }

    for item in getattr(completed_response, "output", []) or []:
        if getattr(item, "type", None) != "function_call":
            continue
        name = getattr(item, "name", None)
        if name == "correction":
            correction_calls.append(item)
        elif name == "conclude":
            conclude_calls.append(item)
        elif name == "record_strength_gap":
            record_strength_gap_calls.append(item)
        elif name == "record_word_outcome":
            record_word_outcome_calls.append(item)
        elif name == "conclude_session":
            conclude_session_calls.append(item)

    return {
        "correction_calls": correction_calls,
        "conclude_calls": conclude_calls,
        "record_strength_gap_calls": record_strength_gap_calls,
        "record_word_outcome_calls": record_word_outcome_calls,
        "conclude_session_calls": conclude_session_calls,
    }


def record_strength_gap(profile_state, kind, label, evidence):
    profile_state = normalize_profile_state(profile_state)
    kind = (kind or "").strip().lower()
    label = (label or "").strip()
    evidence = (evidence or "").strip()
    if kind not in {"strength", "gap"} or not label:
        return profile_state

    bucket = "strengths" if kind == "strength" else "gaps"

    # AUDIT: Without dedupe, the model can spam repeated records and grow state unbounded.
    # We dedupe by (kind, label) and keep the most recent evidence string.
    for item in profile_state[bucket]:
        if isinstance(item, dict) and item.get("label") == label:
            item["evidence"] = evidence
            return profile_state

    profile_state[bucket].append({"label": label, "evidence": evidence})
    return profile_state


def apply_record_strength_gap_calls(
    profile_state, completed_response, record_calls, user_id=DEFAULT_USER_ID
):
    profile_state = normalize_profile_state(profile_state)
    tool_outputs = []
    adjustment_state = ""
    state_summary = build_state_summary(profile_state)
    response_id = getattr(completed_response, "id", None) if completed_response else None

    for call in record_calls or []:
        try:
            arguments = json.loads(getattr(call, "arguments", "") or "{}")
        except json.JSONDecodeError:
            arguments = {}

        kind = coerce_text(arguments.get("kind", ""))
        label = coerce_text(arguments.get("label", ""))
        evidence = coerce_text(arguments.get("evidence", ""))
        profile_state = record_strength_gap(profile_state, kind, label, evidence)
        if kind.strip().lower() in {"strength", "gap"} and label.strip():
            persistent_profile = record_profile_signal(
                user_id,
                kind.strip().lower(),
                label.strip(),
                evidence.strip(),
            )
            state_summary = build_state_summary(persistent_profile)
            if kind.strip().lower() == "gap":
                adjustment_state = (
                    f"Recent evidence suggests the learner is struggling with: {label.strip()}. "
                    "Keep the next responses simpler, shorter, and easier to answer until they recover."
                )
            else:
                adjustment_state = (
                    f"Recent evidence suggests the learner handled this strength well: {label.strip()}. "
                    "You can gradually make the next responses a bit more challenging while staying natural."
                )

        call_id = getattr(call, "call_id", None)
        if call_id and response_id:
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": "recorded",
                }
            )

    return profile_state, state_summary, adjustment_state, tool_outputs
