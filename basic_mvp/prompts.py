from config import (
    CONCLUDE_ASSESSMENT_PROMPT_PATH,
    CONVERSATION_PROMPT_PATH,
    CORRECTION_PROMPT_PATH,
    GAMEPLAN_PROMPT_PATH,
    MODULE_GENERATOR_PROMPT_PATH,
    ONBOARDING_PROMPT_PATH,
    PLANNING_PROMPT_PATH,
    SESSION_PROMPT_PATH,
    CONCLUDE_SESSION_PROMPT_PATH,
)

CONVERSATION_PROMPT_FALLBACK = (
    "You are a friendly Spanish tutor. Start with a simple question."
)

CORRECTION_PROMPT_FALLBACK = (
    "You are a Spanish correction tool.\n"
    "Rewrite the learner's message into natural, correct conversational Spanish.\n"
    "Preserve intended meaning.\n"
    "Return ONLY the corrected Spanish rewrite text with no extra commentary."
)

ONBOARDING_PROMPT_FALLBACK = (
    "You are an onboarding agent for a Spanish learning app.\n"
    "Ask a couple questions about the learner's goals.\n"
    "When you have enough info, output ONLY JSON with keys:\n"
    '- ready_for_scenario (boolean)\n'
    '- scenario (string)\n'
    '- goal_summary (string)\n'
    '- best_guess_level (string)\n'
    '- time_constraint (string)\n'
)

CONCLUDE_ASSESSMENT_PROMPT_FALLBACK = (
    "You are concluding a Spanish conversation assessment.\n"
    "Given the learner goal, baseline guess, persistent learner summary, and the conversation transcript,\n"
    "return ONLY valid JSON with these keys:\n"
    '- strengths (array of strings)\n'
    '- gaps (array of strings)\n'
    '- where_they_stand (string)\n'
    '- next_focus (string)\n'
    '- review_seed_words (array of strings)\n'
    '- session_summary (string)\n'
)

GAMEPLAN_PROMPT_FALLBACK = (
    "You are generating a Spanish learning gameplan.\n"
    "Given the learner goal, time constraint, current standing, strengths, gaps, and state summary,\n"
    "return ONLY valid JSON with these keys:\n"
    '- roadmap_summary (string)\n'
    '- modules (array of objects with keys title and goal)\n'
    '- spaced_review_seed (array of strings)\n'
)

MODULE_GENERATOR_PROMPT_FALLBACK = (
    "You are generating the next Spanish learning roleplay module.\n"
    "Given the module title, module goal, learner goal, learner standing, baseline level, state summary,\n"
    "time constraint, spaced review state, and today's due review words, return ONLY valid JSON with these keys:\n"
    '- title (string)\n'
    '- goal (string)\n'
    '- scenario (string)\n'
    '- session_prompt_seed (string)\n'
    '- spaced_review_focus (array of strings)\n'
    '- completion_signal (string)\n'
)

PLANNING_PROMPT_FALLBACK = (
    "Ask the user how soon they want to meet their goal and how often they would like to work. "
    "Tell them the time you would recommend as ideal."
)

SESSION_PROMPT_FALLBACK = (
    "You are roleplaying as a native Spanish speaker in the provided scenario.\n"
    "Keep responses short and natural, use the learner's `todays_words` when it fits naturally,\n"
    "avoid words already listed in `used_words`, and prefer `learned_words` or basic vocabulary otherwise.\n"
    "If the learner makes a meaningful conversational mistake, call `correction`.\n"
    "If a `todays_words` item was used or understood correctly/incorrectly, call `record_word_outcome`.\n"
    "When the module session should end, call `conclude_session`."
)

CONCLUDE_SESSION_PROMPT_FALLBACK = (
    "You are concluding one Spanish learning module session.\n"
    "Given the module transcript, todays words, learned words, learner state summary, and module context,\n"
    "return ONLY valid JSON with these keys:\n"
    '- strengths (array of strings)\n'
    '- gaps (array of strings)\n'
    '- session_summary (string)\n'
    '- new_review_words (array of strings)\n'
)


def load_text_prompt(path, fallback_text):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
            if not text:
                return fallback_text
            return text
    except FileNotFoundError:
        return fallback_text


def load_conversation_prompt():
    prompt = load_text_prompt(CONVERSATION_PROMPT_PATH, CONVERSATION_PROMPT_FALLBACK)
    if prompt == CONVERSATION_PROMPT_FALLBACK:
        # AUDIT: Missing or empty conversation prompt silently changes behavior to a generic tutor mode.
        return prompt
    return prompt


def load_correction_prompt():
    prompt = load_text_prompt(CORRECTION_PROMPT_PATH, CORRECTION_PROMPT_FALLBACK)
    if prompt == CORRECTION_PROMPT_FALLBACK:
        # AUDIT: Missing or empty correction prompt silently falls back to a generic rewrite prompt.
        return prompt
    return prompt


def load_onboarding_prompt():
    prompt = load_text_prompt(ONBOARDING_PROMPT_PATH, ONBOARDING_PROMPT_FALLBACK)
    if prompt == ONBOARDING_PROMPT_FALLBACK:
        # AUDIT: Missing or empty onboarding prompt silently falls back to generic goal intake behavior.
        return prompt
    return prompt


def load_conclude_assessment_prompt():
    prompt = load_text_prompt(
        CONCLUDE_ASSESSMENT_PROMPT_PATH,
        CONCLUDE_ASSESSMENT_PROMPT_FALLBACK,
    )
    if prompt == CONCLUDE_ASSESSMENT_PROMPT_FALLBACK:
        # AUDIT: Missing or empty conclude assessment prompt silently falls back to a generic end-of-session summary.
        return prompt
    return prompt


def load_gameplan_prompt():
    prompt = load_text_prompt(GAMEPLAN_PROMPT_PATH, GAMEPLAN_PROMPT_FALLBACK)
    if prompt == GAMEPLAN_PROMPT_FALLBACK:
        # AUDIT: Missing or empty gameplan prompt silently falls back to a generic roadmap generator.
        return prompt
    return prompt


def load_module_generator_prompt():
    prompt = load_text_prompt(MODULE_GENERATOR_PROMPT_PATH, MODULE_GENERATOR_PROMPT_FALLBACK)
    if prompt == MODULE_GENERATOR_PROMPT_FALLBACK:
        # AUDIT: Missing or empty module generator prompt silently falls back to a generic scenario generator.
        return prompt
    return prompt


def load_planning_prompt():
    prompt = load_text_prompt(PLANNING_PROMPT_PATH, PLANNING_PROMPT_FALLBACK)
    if prompt == PLANNING_PROMPT_FALLBACK:
        # AUDIT: Missing or empty planning prompt silently falls back to a generic scheduling question.
        return prompt
    return prompt


def load_session_prompt():
    prompt = load_text_prompt(SESSION_PROMPT_PATH, SESSION_PROMPT_FALLBACK)
    if prompt == SESSION_PROMPT_FALLBACK:
        # AUDIT: Missing or empty session prompt silently falls back to a generic module roleplay.
        return prompt
    return prompt


def load_conclude_session_prompt():
    prompt = load_text_prompt(CONCLUDE_SESSION_PROMPT_PATH, CONCLUDE_SESSION_PROMPT_FALLBACK)
    if prompt == CONCLUDE_SESSION_PROMPT_FALLBACK:
        # AUDIT: Missing or empty conclude-session prompt silently falls back to a generic module review.
        return prompt
    return prompt
