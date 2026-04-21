import json

from config import (
    DEBUG_SKIP_ONBOARDING,
    DEFAULT_DEBUG_BEST_GUESS_LEVEL,
    DEFAULT_DEBUG_GOAL_SUMMARY,
    DEFAULT_DEBUG_SCENARIO,
    DEFAULT_DEBUG_TIME_CONSTRAINT,
    MAX_TURN_PAIRS,
)
from model_calls import call_onboarding_model, generate_tts_wav_bytes, run_model_turn
from normalize import (
    coerce_text,
    extract_first_json_object,
    find_latest_assistant_message,
    normalize_gradio_history,
    parse_truthy,
    wrap_input_text,
    wrap_output_text,
)
from plan_store import load_gameplan, load_module_progress, save_gameplan, save_module_progress
from profile_store import build_state_summary, load_profile, record_profile_signal
from prompts import (
    load_conclude_session_prompt,
    load_conversation_prompt,
    load_onboarding_prompt,
    load_session_prompt,
)
from session_store import load_session, save_session
from spaced_review_store import (
    build_spaced_review_state,
    merge_seed_words,
)
from tools import (
    CONCLUDE_SESSION_TOOL_DEF,
    CONCLUDE_TOOL_DEF,
    CORRECTION_TOOL_DEF,
    RECORD_STRENGTH_GAP_TOOL_DEF,
    RECORD_WORD_OUTCOME_TOOL_DEF,
    apply_record_strength_gap_calls,
    collect_tool_calls,
    normalize_adjustment_state,
    normalize_profile_state,
    record_strength_gap,
    run_conclude_assessment,
    run_conclude_session,
    run_conclude_tool,
    run_correction_tool,
    run_generate_gameplan,
    run_module_generator,
    run_planning_prompt,
    run_record_word_outcome,
)


def refresh_spaced_review_state(existing_state=None, seed_words=None, user_id="local-dev-user"):
    existing_state = existing_state if isinstance(existing_state, dict) else {}
    normalized_seed_words = []
    if isinstance(seed_words, list):
        normalized_seed_words = [
            coerce_text(word).strip() for word in seed_words if coerce_text(word).strip()
        ]
    elif seed_words:
        value = coerce_text(seed_words).strip()
        if value:
            normalized_seed_words = [value]
    if normalized_seed_words:
        merge_seed_words(user_id=user_id, seed_words=normalized_seed_words)
    store_state = build_spaced_review_state(user_id=user_id)
    existing_seed_words = existing_state.get("seed_words", [])
    if not isinstance(existing_seed_words, list):
        existing_seed_words = []
    return {
        "seed_words": normalized_seed_words or existing_seed_words,
        "todays_words": store_state.get("todays_words", []),
        "progress": dict(existing_state.get("progress", {})),
        "store_size": int(store_state.get("store_size", 0)),
        "learned_words": store_state.get("learned_words", []),
    }


def get_debug_intro_message():
    return (
        "Debug mode: skipping onboarding.\n\n"
        f"Goal summary: {DEFAULT_DEBUG_GOAL_SUMMARY}\n"
        f"Best guess level: {DEFAULT_DEBUG_BEST_GUESS_LEVEL}\n"
        f"Time constraint: {DEFAULT_DEBUG_TIME_CONSTRAINT}\n\n"
        f"Practice scenario:\n{DEFAULT_DEBUG_SCENARIO}\n\n"
        "Reply with what you would say first in Spanish."
    )


def get_onboarding_intro_message():
    return (
        "Hola. Before we practice, tell me what you want to be able to do in Spanish and why it matters to you."
    )


def build_role_messages(system_prompt, history):
    messages = [{"role": "system", "content": wrap_input_text(system_prompt)}]
    for message in history or []:
        role = message.get("role")
        content = message.get("content")
        if not role or not content:
            continue
        if role == "assistant":
            messages.append({"role": "assistant", "content": wrap_output_text(content)})
        else:
            messages.append({"role": role, "content": wrap_input_text(content)})
    return messages


def build_onboarding_messages(history_with_user):
    return build_role_messages(load_onboarding_prompt(), history_with_user)


def build_conversation_messages(
    history,
    user_message,
    scenario="",
    best_guess_level="",
    state_summary="",
    adjustment_state="",
):
    system_prompt = load_conversation_prompt()
    if scenario:
        system_prompt = system_prompt.rstrip() + "\n\nPRACTICE SCENARIO:\n" + scenario.strip()
    if best_guess_level:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nONBOARDING BASELINE:\n"
            + "The onboarding agent's current best guess of the learner's level is: "
            + best_guess_level.strip()
        )
    if state_summary:
        system_prompt = system_prompt.rstrip() + "\n\nLEARNER STATE SUMMARY:\n" + state_summary.strip()
    if adjustment_state:
        system_prompt = system_prompt.rstrip() + "\n\nCURRENT ADJUSTMENT STATE:\n" + adjustment_state.strip()
    normalized = normalize_gradio_history(history)
    recent_messages = normalized[-(MAX_TURN_PAIRS * 2) :]
    conversation_history = list(recent_messages)
    conversation_history.append({"role": "user", "content": user_message})
    return build_role_messages(system_prompt, conversation_history)


def _ensure_module_session_state(state):
    module_state = state.get("module_session_state")
    if not isinstance(module_state, dict):
        module_state = {}
    module_state.setdefault("todays_words", [])
    module_state.setdefault("used_words", [])
    module_state.setdefault("learned_words", [])
    module_state.setdefault("module_id", "")
    module_state.setdefault("module_title", "")
    module_state.setdefault("module_goal", "")
    module_state.setdefault("completion_signal", "")
    state["module_session_state"] = module_state
    return module_state


def build_session_messages(state, user_message):
    module_state = _ensure_module_session_state(state)
    system_prompt = load_session_prompt()
    scenario = state.get("scenario", "").strip()
    module_title = module_state.get("module_title", "").strip()
    module_goal = module_state.get("module_goal", "").strip()
    if scenario:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nMODULE SCENARIO:\n"
            + scenario
        )
    if module_title:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nMODULE TITLE:\n"
            + module_title
        )
    if module_goal:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nMODULE GOAL:\n"
            + module_goal
        )
    todays_words = module_state.get("todays_words") or []
    if todays_words:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nTODAY'S WORDS:\n"
            + ", ".join(todays_words)
        )
    used_words = module_state.get("used_words") or []
    if used_words:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nUSED WORDS:\n"
            + ", ".join(used_words)
        )
    learned_words = module_state.get("learned_words") or []
    if learned_words:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nLEARNED WORDS:\n"
            + ", ".join(learned_words)
        )
    normalized = normalize_gradio_history(state.get("chat_history", []))
    recent_messages = normalized[-(MAX_TURN_PAIRS * 2) :]
    conversation_history = list(recent_messages)
    conversation_history.append({"role": "user", "content": user_message})
    return build_role_messages(system_prompt, conversation_history)


def reset_module_session_state(state):
    module_state = {
        "todays_words": [],
        "used_words": [],
        "learned_words": [],
        "module_id": "",
        "module_title": "",
        "module_goal": "",
        "completion_signal": "",
    }
    state["module_session_state"] = module_state
    return module_state


def _module_context_for_prompt(state):
    module_state = state.get("module_session_state", {}) or {}
    return {
        "module_id": module_state.get("module_id", ""),
        "title": module_state.get("module_title", ""),
        "goal": module_state.get("module_goal", ""),
        "completion_signal": module_state.get("completion_signal", ""),
        "scenario": state.get("scenario", ""),
    }


def load_user_scoped_state(user_id):
    profile = load_profile(user_id)
    gameplan = load_gameplan(user_id)
    module_progress = load_module_progress(user_id)
    spaced_review = refresh_spaced_review_state(
        existing_state={"progress": module_progress},
        user_id=user_id,
    )
    return {
        "profile_state": profile,
        "state_summary": build_state_summary(profile),
        "gameplan_state": gameplan,
        "spaced_review_state": spaced_review,
    }


def default_session_state(user_id):
    scoped = load_user_scoped_state(user_id)
    if DEBUG_SKIP_ONBOARDING:
        base = {
            "phase": "conversation",
            "conv_start_index": 1,
            "scenario": DEFAULT_DEBUG_SCENARIO,
            "goal_summary": DEFAULT_DEBUG_GOAL_SUMMARY,
            "best_guess_level": DEFAULT_DEBUG_BEST_GUESS_LEVEL,
            "time_constraint": DEFAULT_DEBUG_TIME_CONSTRAINT,
            "state_summary": scoped["state_summary"],
            "adjustment_state": "",
            "profile_state": scoped["profile_state"],
            "gameplan_state": scoped["gameplan_state"],
            "spaced_review_state": scoped["spaced_review_state"],
            "assessment_state": {},
            "chat_history": [{"role": "assistant", "content": get_debug_intro_message()}],
            "active_module_id": "",
        }
        reset_module_session_state(base)
        return base
    base = {
        "phase": "onboarding",
        "conv_start_index": 0,
        "scenario": "",
        "goal_summary": "",
        "best_guess_level": "",
        "time_constraint": "",
        "state_summary": scoped["state_summary"],
        "adjustment_state": "",
        "profile_state": scoped["profile_state"],
        "gameplan_state": scoped["gameplan_state"],
        "spaced_review_state": scoped["spaced_review_state"],
        "assessment_state": {},
        # AUDIT: This starter message is static rather than model-generated. If Taylor changes the onboarding
        # prompt to expect a very different opener, the first visible assistant turn here may drift from the
        # actual onboarding policy even though the backend logic still works.
        "chat_history": [{"role": "assistant", "content": get_onboarding_intro_message()}],
        "active_module_id": "",
    }
    reset_module_session_state(base)
    return base


def get_current_session(user_id):
    session = load_session(user_id)
    if not session:
        session = default_session_state(user_id)
        save_session(user_id, session)
    return session


def serialize_session(session_state):
    return {
        "phase": session_state.get("phase", "onboarding"),
        "chat_history": normalize_gradio_history(session_state.get("chat_history", [])),
        "scenario": session_state.get("scenario", ""),
        "goal_summary": session_state.get("goal_summary", ""),
        "best_guess_level": session_state.get("best_guess_level", ""),
        "time_constraint": session_state.get("time_constraint", ""),
        "state_summary": session_state.get("state_summary", ""),
        "adjustment_state": session_state.get("adjustment_state", ""),
        "gameplan_state": session_state.get("gameplan_state", {}),
        "spaced_review_state": session_state.get("spaced_review_state", {}),
        "active_module_id": session_state.get("active_module_id", ""),
        "module_session_state": session_state.get("module_session_state", {}),
    }


def get_latest_assistant_text(user_id):
    session = get_current_session(user_id)
    history = normalize_gradio_history(session.get("chat_history", []))
    for message in reversed(history):
        if message.get("role") == "assistant":
            return coerce_text(message.get("content", "")).strip()
    return ""


def get_latest_assistant_audio(user_id):
    text = get_latest_assistant_text(user_id)
    if not text:
        return None
    return generate_tts_wav_bytes(text)


def _handle_conclude(user_id, state):
    chat_history = normalize_gradio_history(state.get("chat_history", []))
    conversation_history = chat_history[int(state.get("conv_start_index", 0) or 0) :]
    result = run_conclude_tool([], "", state.get("profile_state", {}))
    assessment = run_conclude_assessment(
        conversation_history=conversation_history,
        goal_summary=state.get("goal_summary", ""),
        best_guess_level=state.get("best_guess_level", ""),
        state_summary=state.get("state_summary", ""),
        fallback_review_seed_words=result["review_seed_words"],
        fallback_next_focus=result["next_focus"],
    )

    strengths_text = ", ".join(assessment["strengths"]) if assessment["strengths"] else "(none identified)"
    gaps_text = ", ".join(assessment["gaps"]) if assessment["gaps"] else "(none identified)"
    summary = "Assessment complete.\n\n"
    if assessment["session_summary"]:
        summary += assessment["session_summary"] + "\n\n"
    if assessment["where_they_stand"]:
        summary += "Where they stand:\n" + assessment["where_they_stand"] + "\n\n"
    if state.get("state_summary", ""):
        summary += "Known learner state:\n" + state["state_summary"] + "\n\n"
    summary += f"Strengths: {strengths_text}\n\n"
    summary += f"Gaps: {gaps_text}\n\n"
    if assessment["next_focus"]:
        summary += "Next focus: " + assessment["next_focus"]

    if not coerce_text(state.get("time_constraint", "")).strip():
        planning_message = run_planning_prompt(
            goal_summary=state.get("goal_summary", ""),
            assessment=assessment,
            best_guess_level=state.get("best_guess_level", ""),
            state_summary=state.get("state_summary", ""),
        )
        summary += "\n\nBefore I build your roadmap, I need one more thing.\n\n"
        summary += planning_message or "How soon do you want to reach this goal, and how often would you like to work?"
        state["phase"] = "planning"
        state["assessment_state"] = assessment
        state["spaced_review_state"] = refresh_spaced_review_state(
            existing_state=state.get("spaced_review_state", {}),
            seed_words=assessment["review_seed_words"],
            user_id=user_id,
        )
        state["chat_history"] = chat_history + [{"role": "assistant", "content": summary}]
        return state

    gameplan = run_generate_gameplan(
        goal_summary=state.get("goal_summary", ""),
        time_constraint=state.get("time_constraint", ""),
        assessment=assessment,
        state_summary=state.get("state_summary", ""),
    )
    spaced_review_state = refresh_spaced_review_state(
        existing_state=state.get("spaced_review_state", {}),
        seed_words=gameplan["spaced_review_seed"] or assessment["review_seed_words"],
        user_id=user_id,
    )
    save_gameplan(user_id, gameplan)
    save_module_progress(user_id, spaced_review_state.get("progress", {}))
    words = spaced_review_state.get("seed_words", [])
    summary += "\n\nSpaced review seed: " + (", ".join(words) if words else "(none)")
    if gameplan.get("roadmap_summary"):
        summary += "\n\nGameplan:\n" + gameplan["roadmap_summary"]
    if gameplan.get("modules"):
        summary += "\n\nModules:\n" + "\n".join(f"- {m['title']}" for m in gameplan["modules"] if m.get("title"))
    state["phase"] = "conversation"
    state["assessment_state"] = assessment
    state["gameplan_state"] = gameplan
    state["spaced_review_state"] = spaced_review_state
    state["chat_history"] = chat_history + [{"role": "assistant", "content": summary}]
    return state


def _handle_conclude_session(user_id, state):
    chat_history = normalize_gradio_history(state.get("chat_history", []))
    conversation_history = chat_history[int(state.get("conv_start_index", 0) or 0) :]
    module_state = state.get("module_session_state", {}) or {}
    conclusion = run_conclude_session(
        conversation_history=conversation_history,
        module_context=_module_context_for_prompt(state),
        state_summary=state.get("state_summary", ""),
        todays_words=module_state.get("todays_words", []),
        learned_words=module_state.get("learned_words", []),
    )
    profile_state = state.get("profile_state", {})
    summary_text = conclusion.get("session_summary", "").strip() or "Module complete."
    for label in conclusion.get("strengths", []) or []:
        profile_state = record_strength_gap(profile_state, "strength", label, summary_text)
        profile_state = record_profile_signal(user_id, "strength", label, summary_text)
    for label in conclusion.get("gaps", []) or []:
        profile_state = record_strength_gap(profile_state, "gap", label, summary_text)
        profile_state = record_profile_signal(user_id, "gap", label, summary_text)
    state["profile_state"] = profile_state
    state["state_summary"] = build_state_summary(profile_state)
    spaced_review_state = refresh_spaced_review_state(
        existing_state=state.get("spaced_review_state", {}),
        seed_words=conclusion.get("new_review_words", []),
        user_id=user_id,
    )
    save_module_progress(user_id, spaced_review_state.get("progress", {}))
    reset_module_session_state(state)
    state["phase"] = "conversation"
    state["active_module_id"] = ""
    if conclusion.get("new_review_words"):
        summary_text += "\n\nNew review words: " + ", ".join(conclusion["new_review_words"])
    state["chat_history"] = chat_history + [{"role": "assistant", "content": summary_text}]
    state["spaced_review_state"] = spaced_review_state
    return state


def process_user_message(user_id, user_message):
    state = get_current_session(user_id)
    message = coerce_text(user_message).strip()
    if not message:
        return serialize_session(state)

    state["profile_state"] = normalize_profile_state(state.get("profile_state", {}))
    state["adjustment_state"] = normalize_adjustment_state(state.get("adjustment_state", ""))
    chat_history = normalize_gradio_history(state.get("chat_history", []))

    if state.get("phase") == "onboarding":
        history_with_user = chat_history + [{"role": "user", "content": message}]
        assistant_text = call_onboarding_model(build_onboarding_messages(history_with_user))
        parsed = extract_first_json_object(assistant_text)
        ready = isinstance(parsed, dict) and parse_truthy(parsed.get("ready_for_scenario"))
        if ready:
            state["scenario"] = coerce_text(parsed.get("scenario", "")).strip()
            state["goal_summary"] = coerce_text(parsed.get("goal_summary", "")).strip()
            state["best_guess_level"] = coerce_text(parsed.get("best_guess_level", "")).strip()
            state["time_constraint"] = coerce_text(parsed.get("time_constraint", "")).strip()
            scenario_intro = (
                "Great. Here is your practice scenario:\n\n"
                + (state["scenario"] or "(no scenario provided)")
                + "\n\nWhen you're ready, reply with what you would say first in Spanish."
            )
            state["chat_history"] = history_with_user + [{"role": "assistant", "content": scenario_intro}]
            state["phase"] = "conversation"
            state["conv_start_index"] = len(state["chat_history"])
        else:
            state["chat_history"] = history_with_user + [{"role": "assistant", "content": assistant_text}]
        save_session(user_id, state)
        return serialize_session(state)

    if state.get("phase") == "planning":
        state["time_constraint"] = message
        assessment = state.get("assessment_state", {}) if isinstance(state.get("assessment_state"), dict) else {}
        gameplan = run_generate_gameplan(
            goal_summary=state.get("goal_summary", ""),
            time_constraint=state["time_constraint"],
            assessment=assessment,
            state_summary=state.get("state_summary", ""),
        )
        words = gameplan["spaced_review_seed"] or assessment.get("review_seed_words", [])
        state["spaced_review_state"] = refresh_spaced_review_state(
            existing_state=state.get("spaced_review_state", {}),
            seed_words=words,
            user_id=user_id,
        )
        state["gameplan_state"] = save_gameplan(user_id, gameplan)
        save_module_progress(user_id, state["spaced_review_state"].get("progress", {}))
        summary = "Thanks. I will plan around this schedule:\n"
        summary += state["time_constraint"] or "(no schedule provided)"
        if state["gameplan_state"].get("roadmap_summary"):
            summary += "\n\nGameplan:\n" + state["gameplan_state"]["roadmap_summary"]
        if state["gameplan_state"].get("modules"):
            summary += "\n\nModules:\n" + "\n".join(
                f"- {m['title']}" for m in state["gameplan_state"]["modules"] if m.get("title")
            )
        state["chat_history"] = chat_history + [{"role": "user", "content": message}, {"role": "assistant", "content": summary}]
        state["phase"] = "conversation"
        state["conv_start_index"] = len(state["chat_history"])
        save_session(user_id, state)
        return serialize_session(state)

    if state.get("phase") == "module_session":
        return _handle_module_session_message(user_id, state, message)

    conversation_history = chat_history[int(state.get("conv_start_index", 0) or 0) :]
    messages = build_conversation_messages(
        conversation_history,
        message,
        scenario=state.get("scenario", ""),
        best_guess_level=state.get("best_guess_level", ""),
        state_summary=state.get("state_summary", ""),
        adjustment_state=state.get("adjustment_state", ""),
    )
    response = run_model_turn(
        input_messages=messages,
        tools=[CORRECTION_TOOL_DEF, CONCLUDE_TOOL_DEF, RECORD_STRENGTH_GAP_TOOL_DEF],
    )
    assistant_text = (getattr(response, "output_text", "") or "").strip()
    provisional_history = chat_history + [{"role": "user", "content": message}]
    if assistant_text:
        provisional_history.append({"role": "assistant", "content": assistant_text})
    state["chat_history"] = provisional_history
    tool_calls = collect_tool_calls(response)
    profile_state, state_summary, adjustment_state, record_tool_outputs = apply_record_strength_gap_calls(
        state.get("profile_state", {}),
        response,
        tool_calls["record_strength_gap_calls"],
        user_id=user_id,
    )
    state["profile_state"] = profile_state
    state["state_summary"] = state_summary
    if adjustment_state:
        state["adjustment_state"] = adjustment_state

    if tool_calls["conclude_calls"]:
        state = _handle_conclude(user_id, state)
        save_session(user_id, state)
        return serialize_session(state)

    if tool_calls["correction_calls"]:
        call = tool_calls["correction_calls"][0]
        try:
            arguments = json.loads(getattr(call, "arguments", "") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        correction_request = {
            "user_utterance": coerce_text(arguments.get("user_utterance", "")),
            "previous_assistant_message": coerce_text(arguments.get("previous_assistant_message", "")),
        }
        if not correction_request["previous_assistant_message"]:
            correction_request["previous_assistant_message"] = find_latest_assistant_message(conversation_history)
        if correction_request["user_utterance"]:
            corrected = run_correction_tool(
                correction_request["user_utterance"],
                correction_request["previous_assistant_message"],
            )
            call_id = getattr(call, "call_id", None)
            response_id = getattr(response, "id", None)
            if call_id and response_id:
                tool_outputs = list(record_tool_outputs or [])
                tool_outputs.append({"type": "function_call_output", "call_id": call_id, "output": corrected})
                followup = run_model_turn(previous_response_id=response_id, input_override=tool_outputs)
                followup_text = (getattr(followup, "output_text", "") or "").strip()
                state["chat_history"] = chat_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": followup_text or assistant_text},
                ]
                save_session(user_id, state)
        return serialize_session(state)

    if record_tool_outputs and not assistant_text:
        response_id = getattr(response, "id", None)
        if response_id:
            followup = run_model_turn(previous_response_id=response_id, input_override=record_tool_outputs)
            followup_text = (getattr(followup, "output_text", "") or "").strip()
            state["chat_history"] = chat_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": followup_text},
            ]

    save_session(user_id, state)
    return serialize_session(state)


def _apply_module_word_outcome(call, response_id, state, user_id):
    try:
        arguments = json.loads(getattr(call, "arguments", "") or "{}")
    except json.JSONDecodeError:
        arguments = {}
    word = coerce_text(arguments.get("word", "")).strip()
    outcome = coerce_text(arguments.get("outcome", "")).strip().lower()
    reason = coerce_text(arguments.get("reason", "")).strip()
    module_state = _ensure_module_session_state(state)
    if word and outcome in {"correct", "incorrect"}:
        result = run_record_word_outcome(word=word, outcome=outcome, reason=reason, user_id=user_id)
        state["spaced_review_state"] = result["spaced_review_state"]
        module_state["todays_words"] = result["spaced_review_state"].get("todays_words", module_state.get("todays_words", []))
        module_state["learned_words"] = result["spaced_review_state"].get("learned_words", module_state.get("learned_words", []))
        used_words = module_state.get("used_words", [])
        if word not in used_words:
            used_words.append(word)
        module_state["used_words"] = used_words
        tool_output = None
        call_id = getattr(call, "call_id", None)
        if call_id and response_id:
            tool_output = {"type": "function_call_output", "call_id": call_id, "output": "recorded"}
        return result, tool_output
    return None, None


def _handle_module_session_message(user_id, state, message):
    chat_history = normalize_gradio_history(state.get("chat_history", []))
    messages = build_session_messages(state, message)
    tools = [
        CORRECTION_TOOL_DEF,
        RECORD_STRENGTH_GAP_TOOL_DEF,
        RECORD_WORD_OUTCOME_TOOL_DEF,
        CONCLUDE_SESSION_TOOL_DEF,
    ]
    response = run_model_turn(
        input_messages=messages,
        tools=tools,
    )
    assistant_text = (getattr(response, "output_text", "") or "").strip()
    provisional_history = chat_history + [{"role": "user", "content": message}]
    if assistant_text:
        provisional_history.append({"role": "assistant", "content": assistant_text})
    state["chat_history"] = provisional_history
    tool_calls = collect_tool_calls(response)
    profile_state, state_summary, adjustment_state, record_tool_outputs = apply_record_strength_gap_calls(
        state.get("profile_state", {}),
        response,
        tool_calls["record_strength_gap_calls"],
        user_id=user_id,
    )
    state["profile_state"] = profile_state
    state["state_summary"] = state_summary
    if adjustment_state:
        state["adjustment_state"] = adjustment_state

    if tool_calls["record_word_outcome_calls"]:
        response_id = getattr(response, "id", None)
        for call in tool_calls["record_word_outcome_calls"]:
            _, tool_output = _apply_module_word_outcome(call, response_id, state, user_id)
            if tool_output:
                record_tool_outputs.append(tool_output)

    if tool_calls["conclude_session_calls"]:
        state = _handle_conclude_session(user_id, state)
        save_session(user_id, state)
        return serialize_session(state)

    if tool_calls["conclude_calls"]:
        state["phase"] = "conversation"
        state = _handle_conclude(user_id, state)
        save_session(user_id, state)
        return serialize_session(state)

    if tool_calls["correction_calls"]:
        call = tool_calls["correction_calls"][0]
        try:
            arguments = json.loads(getattr(call, "arguments", "") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        correction_request = {
            "user_utterance": coerce_text(arguments.get("user_utterance", "")),
            "previous_assistant_message": coerce_text(arguments.get("previous_assistant_message", "")),
        }
        if not correction_request["previous_assistant_message"]:
            correction_request["previous_assistant_message"] = find_latest_assistant_message(messages)
        if correction_request["user_utterance"]:
            corrected = run_correction_tool(
                correction_request["user_utterance"],
                correction_request["previous_assistant_message"],
            )
            call_id = getattr(call, "call_id", None)
            response_id = getattr(response, "id", None)
            if call_id and response_id:
                record_tool_outputs.append(
                    {"type": "function_call_output", "call_id": call_id, "output": corrected}
                )
            if corrected:
                state["chat_history"] = chat_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": corrected},
                ]
                save_session(user_id, state)
                return serialize_session(state)

    if record_tool_outputs and not assistant_text:
        response_id = getattr(response, "id", None)
        if response_id:
            followup = run_model_turn(previous_response_id=response_id, input_override=record_tool_outputs)
            followup_text = (getattr(followup, "output_text", "") or "").strip()
            state["chat_history"] = chat_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": followup_text},
            ]
            save_session(user_id, state)
            return serialize_session(state)

    save_session(user_id, state)
    return serialize_session(state)


def get_roadmap_payload(user_id):
    scoped = load_user_scoped_state(user_id)
    session = get_current_session(user_id)
    return {
        "user_id": user_id,
        "goal_summary": session.get("goal_summary", ""),
        "best_guess_level": session.get("best_guess_level", ""),
        "time_constraint": session.get("time_constraint", ""),
        "state_summary": scoped["state_summary"],
        "gameplan_state": scoped["gameplan_state"],
        "spaced_review_state": scoped["spaced_review_state"],
        "active_module_id": session.get("active_module_id", ""),
    }


def start_module_session(user_id, module_id):
    state = get_current_session(user_id)
    gameplan = load_gameplan(user_id)
    module = next((m for m in gameplan.get("modules", []) if m.get("title", "").lower().replace(" ", "-") == module_id or m.get("id") == module_id), None)
    if module is None:
        module = next((m for m in gameplan.get("modules", []) if m.get("title")), None)
    if module is None:
        # AUDIT: If the user opens a session route before a gameplan exists, we fall back to a generic
        # scenario derived from the current session state. This keeps the route alive but weakens personalization.
        module = {"title": "Practice", "goal": state.get("goal_summary", "General Spanish practice")}

    assessment = state.get("assessment_state", {}) if isinstance(state.get("assessment_state"), dict) else {}
    spaced_review_state = refresh_spaced_review_state(
        existing_state=state.get("spaced_review_state", {}),
        user_id=user_id,
    )
    module_context = run_module_generator(
        module_title=module.get("title", "Practice"),
        module_goal=module.get("goal", ""),
        goal_summary=state.get("goal_summary", "") or module.get("goal", ""),
        where_they_stand=assessment.get("where_they_stand", ""),
        best_guess_level=state.get("best_guess_level", ""),
        state_summary=state.get("state_summary", ""),
        spaced_review_state=spaced_review_state,
        todays_words=spaced_review_state.get("todays_words", []),
        time_constraint=state.get("time_constraint", ""),
    )
    intro = module_context.get("scenario", "").strip() or module_context.get("session_prompt_seed", "").strip()
    if not intro:
        intro = "Reply with what you would say first in Spanish."
    else:
        intro += "\n\nReply with what you would say first in Spanish."
    state.update(
        {
            "phase": "module_session",
            "scenario": module_context.get("scenario", ""),
            "chat_history": [{"role": "assistant", "content": intro}],
            "conv_start_index": 0,
            "active_module_id": module_id,
            "spaced_review_state": spaced_review_state,
        }
    )
    state["module_session_state"] = {
        "module_id": module_id,
        "module_title": module_context.get("title", module.get("title", "Practice")),
        "module_goal": module_context.get("goal", module.get("goal", "")),
        "completion_signal": module_context.get("completion_signal", ""),
        "todays_words": spaced_review_state.get("todays_words", []),
        "used_words": [],
        "learned_words": spaced_review_state.get("learned_words", []),
    }
    save_session(user_id, state)
    return {
        "module": {
            "id": module_id,
            "title": module_context.get("title", module.get("title", "Practice")),
            "goal": module_context.get("goal", module.get("goal", "")),
            "scenario": module_context.get("scenario", ""),
            "completion_signal": module_context.get("completion_signal", ""),
        },
        "session": serialize_session(state),
    }
