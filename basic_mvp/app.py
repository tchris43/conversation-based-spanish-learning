import json
import time

import gradio as gr

from config import (
    DEFAULT_USER_ID,
    DEBUG_AGENT_STATE,
    DEBUG_SKIP_ONBOARDING,
    DEBUG_DISABLE_STREAMING,
    DEFAULT_DEBUG_BEST_GUESS_LEVEL,
    DEFAULT_DEBUG_GOAL_SUMMARY,
    DEFAULT_DEBUG_SCENARIO,
    DEFAULT_DEBUG_TIME_CONSTRAINT,
    MAX_TURN_PAIRS,
    OPENAI_API_KEY,
    UI_THROTTLE_CHARS,
    UI_THROTTLE_SECONDS,
)
from data_paths import normalize_user_id
from model_calls import call_onboarding_model, generate_tts_audio, stream_model
from normalize import (
    coerce_text,
    extract_first_json_object,
    find_latest_assistant_message,
    normalize_gradio_history,
    parse_truthy,
    wrap_input_text,
    wrap_output_text,
)
from prompts import load_conversation_prompt, load_onboarding_prompt
from tools import (
    CONCLUDE_TOOL_DEF,
    CORRECTION_TOOL_DEF,
    RECORD_STRENGTH_GAP_TOOL_DEF,
    apply_record_strength_gap_calls,
    collect_tool_calls,
    normalize_adjustment_state,
    normalize_profile_state,
    run_generate_gameplan,
    run_conclude_assessment,
    run_conclude_tool,
    run_correction_tool,
    run_planning_prompt,
)
from profile_store import build_state_summary, load_profile
from plan_store import load_gameplan, load_module_progress, save_gameplan, save_module_progress
from spaced_review_store import build_spaced_review_state, merge_seed_words
from user_store import create_user, get_last_active_user, initialize_user_store, list_users, set_last_active_user


# ============================================================================
# Runtime Flow Map
# ============================================================================
#
# 1. `router` chooses the active phase.
# 2. `run_onboarding_phase` gathers goals and produces `onboarding_result`.
# 3. `run_conversation_phase` builds `conversation_request` and streams a reply.
# 4. `run_planning_phase` collects missing schedule constraints before planning.
# 5. `collect_tool_calls` turns the completed response into `tool_calls`.
# 6. Tool handlers perform the explicit handoffs:
#    - model -> correction tool -> model followup
#    - model -> conclude tool -> terminal chat summary or planning handoff
#    - model -> record_strength_gap tool -> session state + persistent profile
# 7. `generate_latest_assistant_audio` optionally turns the final assistant text into post-turn TTS.


# ============================================================================
# Message Builders
# ============================================================================


def refresh_spaced_review_state(existing_state=None, seed_words=None, user_id=DEFAULT_USER_ID):
    existing_state = existing_state if isinstance(existing_state, dict) else {}
    normalized_seed_words = []
    if isinstance(seed_words, list):
        normalized_seed_words = [coerce_text(word).strip() for word in seed_words if coerce_text(word).strip()]
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


def load_user_scoped_state(user_id):
    user_id = normalize_user_id(user_id)
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


def get_user_dropdown_choices():
    users = list_users()
    return [(item["display_name"], item["user_id"]) for item in users]


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
    # Load the system prompt on each request so prompt iteration doesn't require an app restart.
    # AUDIT: Editing `conversation.md` mid-conversation can change behavior between turns; this is desirable
    # for prompt testing but may be surprising for "real" use.
    system_prompt = load_conversation_prompt()
    if scenario:
        # AUDIT: Scenario is generated content. If it is too long, it will increase latency and cost.
        system_prompt = system_prompt.rstrip() + "\n\nPRACTICE SCENARIO:\n" + scenario.strip()
    if best_guess_level:
        # AUDIT: Onboarding produces only a rough baseline; if this estimate is noisy, the conversation
        # agent may start too high or too low unless the prompt treats it as a guess to test, not ground truth.
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nONBOARDING BASELINE:\n"
            + "The onboarding agent's current best guess of the learner's level is: "
            + best_guess_level.strip()
        )
    if state_summary:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nLEARNER STATE SUMMARY:\n"
            + state_summary.strip()
        )
    if adjustment_state:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nCURRENT ADJUSTMENT STATE:\n"
            + adjustment_state.strip()
        )

    normalized = normalize_gradio_history(history)
    recent_messages = normalized[-(MAX_TURN_PAIRS * 2) :]
    conversation_history = list(recent_messages)
    conversation_history.append({"role": "user", "content": user_message})
    return build_role_messages(system_prompt, conversation_history)


# ============================================================================
# Streaming / Tool Handoffs
# ============================================================================


def stream_assistant_reply(updated_history, stream_gen):
    if DEBUG_DISABLE_STREAMING:
        try:
            answer_text = next(stream_gen)
        except StopIteration as stop:
            return stop.value

        completed_response = None
        while True:
            try:
                answer_text = next(stream_gen)
            except StopIteration as stop:
                completed_response = stop.value
                break

        streamed_history = list(updated_history)
        streamed_history[-1] = {"role": "assistant", "content": answer_text}
        yield streamed_history, ""
        return completed_response

    last_yield_time = time.monotonic()
    last_yield_len = 0
    latest_answer_text = ""
    completed_response = None

    while True:
        try:
            answer_text = next(stream_gen)
        except StopIteration as stop:
            completed_response = stop.value
            break

        latest_answer_text = answer_text
        now = time.monotonic()
        if (len(answer_text) - last_yield_len) < UI_THROTTLE_CHARS and (
            now - last_yield_time
        ) < UI_THROTTLE_SECONDS:
            continue

        streamed_history = list(updated_history)
        streamed_history[-1] = {"role": "assistant", "content": answer_text}
        yield streamed_history, ""
        last_yield_time = now
        last_yield_len = len(answer_text)

    if latest_answer_text and last_yield_len != len(latest_answer_text):
        streamed_history = list(updated_history)
        streamed_history[-1] = {"role": "assistant", "content": latest_answer_text}
        yield streamed_history, ""

    return completed_response


def generate_latest_assistant_audio(display_history, tts_enabled):
    if not tts_enabled:
        return None

    latest_assistant_text = find_latest_assistant_message(display_history)
    if not latest_assistant_text:
        return None

    # AUDIT: Re-synthesizing the whole latest assistant message on every turn adds another API call
    # and can noticeably increase perceived latency when audio playback is enabled.
    return generate_tts_audio(latest_assistant_text)


def handle_conclude_calls(
    conclude_calls,
    profile_state,
    conversation_history,
    goal_summary,
    best_guess_level,
    state_summary,
    time_constraint,
    spaced_review_state,
    user_id=DEFAULT_USER_ID,
):
    if not conclude_calls:
        return None

    # HANDOFF: model -> conclude tool
    # AUDIT: The `conclude` tool is treated as terminal. We do not send tool outputs back to the model
    # because that would require another model call; instead we display the conclusion result directly.
    call = conclude_calls[0]
    try:
        arguments = json.loads(getattr(call, "arguments", "") or "{}")
    except json.JSONDecodeError:
        arguments = {}

    result = run_conclude_tool(
        arguments.get("review_seed_words", []),
        arguments.get("next_focus", ""),
        profile_state,
    )
    assessment = run_conclude_assessment(
        conversation_history=conversation_history,
        goal_summary=goal_summary,
        best_guess_level=best_guess_level,
        state_summary=state_summary,
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
    if state_summary:
        summary += "Known learner state:\n" + state_summary + "\n\n"
    summary += f"Strengths: {strengths_text}\n\n"
    summary += f"Gaps: {gaps_text}\n\n"
    if assessment["next_focus"]:
        summary += "\n\nNext focus: " + assessment["next_focus"]

    if not coerce_text(time_constraint).strip():
        planning_message = run_planning_prompt(
            goal_summary=goal_summary,
            assessment=assessment,
            best_guess_level=best_guess_level,
            state_summary=state_summary,
        )
        summary += "\n\nBefore I build your roadmap, I need one more thing.\n\n"
        summary += planning_message or "How soon do you want to reach this goal, and how often would you like to work?"
        return {
            "summary_text": summary,
            "needs_planning": True,
            "assessment_state": assessment,
            "gameplan_state": {},
            "spaced_review_state": refresh_spaced_review_state(
                # AUDIT: Keep existing per-user module progress when seeding review words during conclude.
                # Resetting to {} here would silently erase progress state across the planning handoff.
                existing_state=spaced_review_state,
                seed_words=assessment["review_seed_words"],
                user_id=user_id,
            ),
        }

    gameplan = run_generate_gameplan(
        goal_summary=goal_summary,
        time_constraint=time_constraint,
        assessment=assessment,
        state_summary=state_summary,
    )
    # AUDIT: `gameplan_state` and `spaced_review_state` are session-local Gradio state right now.
    # If the server restarts or the user opens a new session, the generated roadmap is lost unless persisted.
    words = gameplan["spaced_review_seed"] or assessment["review_seed_words"]
    spaced_review_state = refresh_spaced_review_state(
        # AUDIT: Preserve prior progress state while updating due words from new roadmap seeds.
        existing_state=spaced_review_state,
        seed_words=words,
        user_id=user_id,
    )
    gameplan = save_gameplan(user_id, gameplan)
    save_module_progress(user_id, spaced_review_state.get("progress", {}))
    todays_words = spaced_review_state.get("todays_words", [])
    words_text = ", ".join(words) if words else "(none)"
    todays_words_text = ", ".join(todays_words) if todays_words else "(none)"
    module_titles = []
    for module in gameplan["modules"]:
        if not isinstance(module, dict):
            continue
        title = coerce_text(module.get("title", "")).strip()
        if title:
            module_titles.append(title)

    summary += f"Spaced review seed: {words_text}"
    summary += f"\nToday's words: {todays_words_text}"
    if gameplan["roadmap_summary"]:
        summary += "\n\nGameplan:\n" + gameplan["roadmap_summary"]
    if module_titles:
        summary += "\n\nModules:\n" + "\n".join(f"- {title}" for title in module_titles)

    return {
        "summary_text": summary,
        "needs_planning": False,
        "assessment_state": assessment,
        "gameplan_state": gameplan,
        "spaced_review_state": spaced_review_state,
    }


def handle_correction_calls(
    updated_history,
    normalized_history,
    completed_response,
    correction_calls,
    extra_tool_outputs=None,
):
    if not correction_calls:
        return

    # HANDOFF: model -> correction tool
    # AUDIT: Tool calls add latency because they trigger at least one additional LLM call for correction.
    for call in correction_calls:
        try:
            arguments = json.loads(getattr(call, "arguments", "") or "{}")
        except json.JSONDecodeError:
            arguments = {}

        correction_request = {
            "user_utterance": coerce_text(arguments.get("user_utterance", "")),
            "previous_assistant_message": coerce_text(
                arguments.get("previous_assistant_message", "")
            ),
        }
        if not correction_request["previous_assistant_message"]:
            correction_request["previous_assistant_message"] = find_latest_assistant_message(
                normalized_history
            )
        if not correction_request["user_utterance"]:
            # AUDIT: If the model calls the tool without a valid user_utterance, skip rather than generating junk.
            continue

        corrected = run_correction_tool(
            correction_request["user_utterance"],
            correction_request["previous_assistant_message"],
        )
        call_id = getattr(call, "call_id", None)
        response_id = getattr(completed_response, "id", None)
        if not call_id or not response_id:
            continue

        # HANDOFF: correction tool -> model followup
        tool_outputs = list(extra_tool_outputs or [])
        tool_outputs.append(
            {"type": "function_call_output", "call_id": call_id, "output": corrected}
        )
        followup_stream = stream_model(
            previous_response_id=response_id,
            # AUDIT: Do not offer tools in the followup; we want the model to produce the final message,
            # not make recursive tool calls that this handler does not process.
            input_override=tool_outputs,
        )

        completed_followup = yield from stream_assistant_reply(updated_history, followup_stream)
        if completed_followup is not None:
            return

        # AUDIT: This app currently supports a single correction tool call per turn.
        return


# ============================================================================
# Phase Handlers
# ============================================================================


def run_onboarding_phase(
    user_message,
    display_history,
    scenario,
    goal_summary,
    best_guess_level,
    time_constraint,
    state_summary,
    adjustment_state,
    profile_state,
    gameplan_state,
    spaced_review_state,
    assessment_state,
    user_id,
):
    history_with_user = display_history + [{"role": "user", "content": user_message}]
    assistant_text = call_onboarding_model(build_onboarding_messages(history_with_user))
    parsed = extract_first_json_object(assistant_text)
    onboarding_result = {
        "assistant_text": assistant_text,
        "ready_for_scenario": isinstance(parsed, dict)
        and parse_truthy(parsed.get("ready_for_scenario")),
        "scenario": coerce_text(parsed.get("scenario", "")).strip() if isinstance(parsed, dict) else "",
        "goal_summary": coerce_text(parsed.get("goal_summary", "")).strip() if isinstance(parsed, dict) else "",
        "best_guess_level": coerce_text(parsed.get("best_guess_level", "")).strip()
        if isinstance(parsed, dict)
        else "",
        "time_constraint": coerce_text(parsed.get("time_constraint", "")).strip()
        if isinstance(parsed, dict)
        else "",
    }

    # HANDOFF: onboarding -> conversation
    if onboarding_result["ready_for_scenario"]:
        scenario = onboarding_result["scenario"]
        goal_summary = onboarding_result["goal_summary"]
        best_guess_level = onboarding_result["best_guess_level"]
        time_constraint = onboarding_result["time_constraint"]

        # AUDIT: If onboarding returns an empty scenario, the main conversation becomes generic.
        scenario_intro = (
            "Great. Here is your practice scenario:\n\n"
            + (scenario or "(no scenario provided)")
            + "\n\nWhen you're ready, reply with what you would say first in Spanish."
        )
        updated_history = history_with_user + [
            {"role": "assistant", "content": scenario_intro}
        ]
        conv_start_index = len(updated_history)
        yield (
            updated_history,
            "",
            updated_history,
            "conversation",
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            time_constraint,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )
        return

    updated_history = history_with_user + [
        {"role": "assistant", "content": onboarding_result["assistant_text"]}
    ]
    yield (
        updated_history,
        "",
        updated_history,
        "onboarding",
        0,
        scenario,
        goal_summary,
        best_guess_level,
        time_constraint,
        state_summary,
        adjustment_state,
        profile_state,
        gameplan_state,
        spaced_review_state,
        assessment_state,
        user_id,
    )


def run_planning_phase(
    user_message,
    display_history,
    conv_start_index,
    scenario,
    goal_summary,
    best_guess_level,
    state_summary,
    adjustment_state,
    profile_state,
    gameplan_state,
    spaced_review_state,
    assessment_state,
    user_id,
):
    time_constraint = coerce_text(user_message).strip()
    # AUDIT: The current planning phase assumes the user's reply contains enough schedule detail.
    # If the answer is vague ("soon"), the roadmap quality will be poor until planning becomes multi-turn.
    assessment_state = assessment_state if isinstance(assessment_state, dict) else {}
    gameplan = run_generate_gameplan(
        goal_summary=goal_summary,
        time_constraint=time_constraint,
        assessment=assessment_state,
        state_summary=state_summary,
    )
    words = gameplan["spaced_review_seed"] or assessment_state.get("review_seed_words", [])
    spaced_review_state = refresh_spaced_review_state(
        existing_state=spaced_review_state,
        seed_words=words,
        user_id=user_id,
    )
    gameplan = save_gameplan(user_id, gameplan)
    save_module_progress(user_id, spaced_review_state.get("progress", {}))
    todays_words = spaced_review_state.get("todays_words", [])
    words_text = ", ".join(words) if words else "(none)"
    todays_words_text = ", ".join(todays_words) if todays_words else "(none)"
    module_titles = []
    for module in gameplan["modules"]:
        if not isinstance(module, dict):
            continue
        title = coerce_text(module.get("title", "")).strip()
        if title:
            module_titles.append(title)

    summary = "Thanks. I will plan around this schedule:\n"
    summary += time_constraint or "(no schedule provided)"
    if gameplan["roadmap_summary"]:
        summary += "\n\nGameplan:\n" + gameplan["roadmap_summary"]
    if module_titles:
        summary += "\n\nModules:\n" + "\n".join(f"- {title}" for title in module_titles)
    summary += "\n\nSpaced review seed: " + words_text
    summary += "\nToday's words: " + todays_words_text

    updated_history = normalize_gradio_history(display_history) + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": summary},
    ]
    next_conv_start_index = len(updated_history)
    yield (
        updated_history,
        "",
        updated_history,
        "conversation",
        next_conv_start_index,
        scenario,
        goal_summary,
        best_guess_level,
        time_constraint,
        state_summary,
        adjustment_state,
        profile_state,
        gameplan,
        spaced_review_state,
        {},
        user_id,
    )


def run_conversation_phase(
    user_message,
    display_history,
    conv_start_index,
    scenario,
    goal_summary,
    best_guess_level,
    time_constraint,
    state_summary,
    adjustment_state,
    profile_state,
    gameplan_state,
    spaced_review_state,
    assessment_state,
    user_id,
):
    spaced_review_state = refresh_spaced_review_state(
        existing_state=spaced_review_state,
        user_id=user_id,
    )
    prefix = display_history[: int(conv_start_index or 0)]
    conversation_history = display_history[int(conv_start_index or 0) :]
    normalized_history = normalize_gradio_history(conversation_history)
    adjustment_state = normalize_adjustment_state(adjustment_state)
    conversation_request = {
        "history": conversation_history,
        "normalized_history": normalized_history,
        "user_message": user_message,
        "scenario": scenario,
        "best_guess_level": best_guess_level,
        "state_summary": state_summary,
        "adjustment_state": adjustment_state,
        "messages": build_conversation_messages(
            conversation_history,
            user_message,
            scenario=scenario,
            best_guess_level=best_guess_level,
            state_summary=state_summary,
            adjustment_state=adjustment_state,
        ),
    }
    updated_history = normalized_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": ""},
    ]

    yield (
        prefix + updated_history,
        "",
        prefix + updated_history,
        "conversation",
        conv_start_index,
        scenario,
        goal_summary,
        best_guess_level,
        time_constraint,
        state_summary,
        adjustment_state,
        profile_state,
        gameplan_state,
        spaced_review_state,
        assessment_state,
        user_id,
    )

    initial_stream = stream_model(
        input_messages=conversation_request["messages"],
        tools=[
            CORRECTION_TOOL_DEF,
            CONCLUDE_TOOL_DEF,
            RECORD_STRENGTH_GAP_TOOL_DEF,
        ],
    )
    # AUDIT: `run_conversation_phase` must always yield the full output tuple for Gradio.
    # Helpers like `stream_assistant_reply` yield only (convo_history, cleared), so we must wrap them here.
    gen = stream_assistant_reply(updated_history, initial_stream)
    final_assistant_text = ""
    last_convo_history = list(updated_history)
    while True:
        try:
            convo_history, cleared = next(gen)
        except StopIteration as stop:
            completed_response = stop.value
            break
        last_convo_history = convo_history
        if convo_history and isinstance(convo_history, list):
            last = convo_history[-1]
            if isinstance(last, dict) and last.get("role") == "assistant":
                final_assistant_text = last.get("content", "") or ""
        full_history = prefix + convo_history
        yield (
            full_history,
            cleared,
            full_history,
            "conversation",
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            time_constraint,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )

    tool_calls = collect_tool_calls(completed_response)
    profile_state, state_summary, new_adjustment_state, record_tool_outputs = apply_record_strength_gap_calls(
        profile_state,
        completed_response,
        tool_calls["record_strength_gap_calls"],
        user_id=user_id,
    )
    if new_adjustment_state:
        adjustment_state = new_adjustment_state
    recorded_any = bool(tool_calls["record_strength_gap_calls"])

    if DEBUG_AGENT_STATE:
        called_tool_names = []
        if tool_calls["record_strength_gap_calls"]:
            called_tool_names.append("record_strength_gap")
        if tool_calls["correction_calls"]:
            called_tool_names.append("correction")
        if tool_calls["conclude_calls"]:
            called_tool_names.append("conclude")
        print("=== AGENT STATE DEBUG ===")
        print("tool_calls:", ", ".join(called_tool_names) if called_tool_names else "(none)")
        print("state_summary:")
        print(state_summary or "(empty)")
        print("adjustment_state:")
        print(adjustment_state or "(empty)")
        print("=========================")

    if tool_calls["conclude_calls"]:
        conclude_result = handle_conclude_calls(
            tool_calls["conclude_calls"],
            profile_state,
            conversation_history=conversation_history + [{"role": "user", "content": user_message}],
            goal_summary=goal_summary,
            best_guess_level=best_guess_level,
            state_summary=state_summary,
            time_constraint=time_constraint,
            spaced_review_state=spaced_review_state,
            user_id=user_id,
        )
        if conclude_result is not None:
            assessment_state = conclude_result["assessment_state"]
            # HANDOFF: conclude assessment -> session roadmap state
            gameplan_state = conclude_result["gameplan_state"]
            spaced_review_state = conclude_result["spaced_review_state"]
            concluded_history = list(last_convo_history)
            if concluded_history and concluded_history[-1].get("role") == "assistant":
                concluded_history[-1] = {
                    "role": "assistant",
                    "content": conclude_result["summary_text"],
                }
            else:
                concluded_history.append(
                    {"role": "assistant", "content": conclude_result["summary_text"]}
                )
            full_history = prefix + concluded_history
            yield (
                full_history,
                "",
                full_history,
                "planning" if conclude_result["needs_planning"] else "conversation",
                conv_start_index,
                scenario,
                goal_summary,
                best_guess_level,
                time_constraint,
                state_summary,
                adjustment_state,
                profile_state,
                gameplan_state,
                spaced_review_state,
                assessment_state,
                user_id,
            )
        return

    if tool_calls["correction_calls"]:
        correction_gen = handle_correction_calls(
            updated_history,
            conversation_request["normalized_history"],
            completed_response,
            tool_calls["correction_calls"],
            extra_tool_outputs=record_tool_outputs,
        )
        if correction_gen is not None:
            while True:
                try:
                    convo_history, cleared = next(correction_gen)
                except StopIteration:
                    break
                full_history = prefix + convo_history
                yield (
                    full_history,
                    cleared,
                    full_history,
                    "conversation",
                    conv_start_index,
                    scenario,
                    goal_summary,
                    best_guess_level,
                    time_constraint,
                    state_summary,
                    adjustment_state,
                    profile_state,
                    gameplan_state,
                    spaced_review_state,
                    assessment_state,
                    user_id,
                )
        return

    if record_tool_outputs and not final_assistant_text:
        # HANDOFF: model -> record_strength_gap tool -> model followup
        # If the model produced only tool calls (no assistant text), we must send tool outputs back
        # and request a followup assistant message.
        response_id = getattr(completed_response, "id", None) if completed_response else None
        if response_id:
            followup_stream = stream_model(
                previous_response_id=response_id,
                input_override=record_tool_outputs,
            )
            gen2 = stream_assistant_reply(updated_history, followup_stream)
            while True:
                try:
                    convo_history, cleared = next(gen2)
                except StopIteration:
                    break
                full_history = prefix + convo_history
                yield (
                    full_history,
                    cleared,
                    full_history,
                    "conversation",
                    conv_start_index,
                    scenario,
                    goal_summary,
                    best_guess_level,
                    time_constraint,
                    state_summary,
                    adjustment_state,
                    profile_state,
                    gameplan_state,
                    spaced_review_state,
                    assessment_state,
                    user_id,
                )
        return

    if recorded_any:
        # Persist the updated profile_state even if there is no followup tool call that yields again.
        full_history = prefix + last_convo_history
        yield (
            full_history,
            "",
            full_history,
            "conversation",
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            time_constraint,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )


# ============================================================================
# Top-Level Router
# ============================================================================


def router(
    user_message,
    display_history,
    phase,
    conv_start_index,
    scenario,
    goal_summary,
    best_guess_level,
    time_constraint,
    state_summary,
    adjustment_state,
    profile_state,
    gameplan_state,
    spaced_review_state,
    assessment_state,
    user_id,
):
    user_id = normalize_user_id(user_id)
    # AUDIT: We persist last-active on each routed message for simplicity; this causes frequent writes
    # during long chats and may need throttling if storage backend moves from local files to network IO.
    set_last_active_user(user_id)
    display_history = normalize_gradio_history(display_history)
    profile_state = normalize_profile_state(profile_state)
    adjustment_state = normalize_adjustment_state(adjustment_state)

    if not OPENAI_API_KEY:
        # AUDIT: Missing API key prevents all usage; this error is the only hint.
        raise gr.Error("Set OPENAI_API_KEY in the environment to call OpenAI.")

    if not user_message:
        # AUDIT: `router` is a generator, so all early-exit paths should yield at least once.
        yield (
            display_history,
            "",
            display_history,
            phase,
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            time_constraint,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )
        return

    if phase == "conversation":
        yield from run_conversation_phase(
            user_message,
            display_history,
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            time_constraint,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )
        return

    if phase == "planning":
        yield from run_planning_phase(
            user_message,
            display_history,
            conv_start_index,
            scenario,
            goal_summary,
            best_guess_level,
            state_summary,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id,
        )
        return

    yield from run_onboarding_phase(
        user_message,
        display_history,
        scenario,
        goal_summary,
        best_guess_level,
        time_constraint,
        state_summary,
        adjustment_state,
        profile_state,
        gameplan_state,
        spaced_review_state,
        assessment_state,
        user_id,
    )


# ============================================================================
# User Switching
# ============================================================================


def build_user_session_payload(user_id):
    user_id = normalize_user_id(user_id)
    set_last_active_user(user_id)
    scoped = load_user_scoped_state(user_id)
    phase = "conversation" if DEBUG_SKIP_ONBOARDING else "onboarding"
    scenario = DEFAULT_DEBUG_SCENARIO if DEBUG_SKIP_ONBOARDING else ""
    goal_summary = DEFAULT_DEBUG_GOAL_SUMMARY if DEBUG_SKIP_ONBOARDING else ""
    best_guess_level = DEFAULT_DEBUG_BEST_GUESS_LEVEL if DEBUG_SKIP_ONBOARDING else ""
    time_constraint = DEFAULT_DEBUG_TIME_CONSTRAINT if DEBUG_SKIP_ONBOARDING else ""
    display_history = (
        [{"role": "assistant", "content": get_debug_intro_message()}]
        if DEBUG_SKIP_ONBOARDING
        else []
    )
    conv_start_index = 1 if DEBUG_SKIP_ONBOARDING else 0
    return {
        "chat_history": display_history,
        "phase": phase,
        "conv_start_index": conv_start_index,
        "scenario": scenario,
        "goal_summary": goal_summary,
        "best_guess_level": best_guess_level,
        "time_constraint": time_constraint,
        "state_summary": scoped["state_summary"],
        "adjustment_state": "",
        "profile_state": scoped["profile_state"],
        "gameplan_state": scoped["gameplan_state"],
        "spaced_review_state": scoped["spaced_review_state"],
        "assessment_state": {},
        "user_id": user_id,
    }


def switch_user_profile(selected_user_id):
    payload = build_user_session_payload(selected_user_id)
    choices = get_user_dropdown_choices()
    dropdown_update = gr.update(choices=choices, value=payload["user_id"])
    return (
        dropdown_update,
        "",
        payload["chat_history"],
        payload["chat_history"],
        payload["phase"],
        payload["conv_start_index"],
        payload["scenario"],
        payload["goal_summary"],
        payload["best_guess_level"],
        payload["time_constraint"],
        payload["state_summary"],
        payload["adjustment_state"],
        payload["profile_state"],
        payload["gameplan_state"],
        payload["spaced_review_state"],
        payload["assessment_state"],
        payload["user_id"],
    )


def create_user_profile(new_profile_name):
    user = create_user(new_profile_name)
    selected = user["user_id"] if user else (get_last_active_user() or DEFAULT_USER_ID)
    return switch_user_profile(selected)


# ============================================================================
# UI
# ============================================================================


with gr.Blocks() as demo:
    initial_user_id = initialize_user_store()
    initial_payload = build_user_session_payload(initial_user_id)
    user_choices = get_user_dropdown_choices()

    with gr.Row():
        user_picker = gr.Dropdown(
            label="Profile",
            choices=user_choices,
            value=initial_payload["user_id"],
        )
        new_profile_name = gr.Textbox(
            label="Create Profile",
            placeholder="Type a profile name (e.g., Taylor)",
        )
        create_profile_btn = gr.Button("Create / Switch")

    # AUDIT: Some Gradio versions don't accept `label=None`; use empty string for max compatibility.
    chatbot = gr.Chatbot(label="")
    tts_enabled = gr.Checkbox(label="Read replies aloud", value=False)
    assistant_audio = gr.Audio(label="", autoplay=True)
    user_message = gr.Textbox(
        label="",
        placeholder=(
            "Start the conversation in Spanish..."
            if DEBUG_SKIP_ONBOARDING
            else "Tell me why you want to learn Spanish..."
        ),
    )
    chat_history = gr.State(initial_payload["chat_history"])
    phase_state = gr.State(initial_payload["phase"])
    conv_start_index_state = gr.State(initial_payload["conv_start_index"])
    scenario_state = gr.State(initial_payload["scenario"])
    goal_summary_state = gr.State(initial_payload["goal_summary"])
    best_guess_level_state = gr.State(initial_payload["best_guess_level"])
    time_constraint_state = gr.State(initial_payload["time_constraint"])
    state_summary_state = gr.State(initial_payload["state_summary"])
    adjustment_state = gr.State(initial_payload["adjustment_state"])
    profile_state = gr.State(initial_payload["profile_state"])
    gameplan_state = gr.State(initial_payload["gameplan_state"])
    spaced_review_state = gr.State(initial_payload["spaced_review_state"])
    assessment_state = gr.State(initial_payload["assessment_state"])
    user_id_state = gr.State(initial_payload["user_id"])

    # AUDIT: Switching users clears in-memory chat/session state to avoid cross-user context leakage.
    user_picker.change(
        switch_user_profile,
        inputs=[user_picker],
        outputs=[
            user_picker,
            user_message,
            chatbot,
            chat_history,
            phase_state,
            conv_start_index_state,
            scenario_state,
            goal_summary_state,
            best_guess_level_state,
            time_constraint_state,
            state_summary_state,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id_state,
        ],
    )

    create_profile_btn.click(
        create_user_profile,
        inputs=[new_profile_name],
        outputs=[
            user_picker,
            user_message,
            chatbot,
            chat_history,
            phase_state,
            conv_start_index_state,
            scenario_state,
            goal_summary_state,
            best_guess_level_state,
            time_constraint_state,
            state_summary_state,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id_state,
        ],
    )

    submit_event = user_message.submit(
        router,
        inputs=[
            user_message,
            chat_history,
            phase_state,
            conv_start_index_state,
            scenario_state,
            goal_summary_state,
            best_guess_level_state,
            time_constraint_state,
            state_summary_state,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id_state,
        ],
        outputs=[
            chatbot,
            user_message,
            chat_history,
            phase_state,
            conv_start_index_state,
            scenario_state,
            goal_summary_state,
            best_guess_level_state,
            time_constraint_state,
            state_summary_state,
            adjustment_state,
            profile_state,
            gameplan_state,
            spaced_review_state,
            assessment_state,
            user_id_state,
        ],
    )
    submit_event.then(
        generate_latest_assistant_audio,
        inputs=[chat_history, tts_enabled],
        outputs=[assistant_audio],
    )

try:
    demo.queue()
except (AttributeError, TypeError):
    pass

demo.launch()
