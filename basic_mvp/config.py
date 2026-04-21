import math
import os
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
DATA_DIR = BASE_DIR / "data"
USER_DATA_DIR = DATA_DIR / "users"

CONVERSATION_PROMPT_PATH = PROMPTS_DIR / "conversation.md"
ONBOARDING_PROMPT_PATH = PROMPTS_DIR / "onboarding.md"
CORRECTION_PROMPT_PATH = PROMPTS_DIR / "correction.md"
CONCLUDE_ASSESSMENT_PROMPT_PATH = PROMPTS_DIR / "conclude_assessment.md"
GAMEPLAN_PROMPT_PATH = PROMPTS_DIR / "gameplan.md"
MODULE_GENERATOR_PROMPT_PATH = PROMPTS_DIR / "module_generator.md"
PLANNING_PROMPT_PATH = PROMPTS_DIR / "planning.md"
SESSION_PROMPT_PATH = PROMPTS_DIR / "session.md"
CONCLUDE_SESSION_PROMPT_PATH = PROMPTS_DIR / "conclude_session.md"
SPACED_REVIEW_PATH = DATA_DIR / "spaced_review.json"

OPENAI_MODEL = "gpt-4o-mini"
TTS_MODEL = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "marin")
TTS_SAMPLE_RATE = 24000
DEBUG_SSE = os.environ.get("DEBUG_SSE", "").lower() in {"1", "true", "yes"}
DEBUG_AGENT_STATE = os.environ.get("DEBUG_AGENT_STATE", "").lower() in {"1", "true", "yes"}
DEBUG_MODEL_INPUT = os.environ.get("DEBUG_MODEL_INPUT", "").lower() in {"1", "true", "yes"}
DEBUG_SKIP_ONBOARDING = os.environ.get("DEBUG_SKIP_ONBOARDING", "").lower() in {"1", "true", "yes"}
DEBUG_DISABLE_STREAMING = os.environ.get("DEBUG_DISABLE_STREAMING", "").lower() in {"1", "true", "yes"}
MAX_TURN_PAIRS = 4

DEFAULT_DEBUG_GOAL_SUMMARY = os.environ.get(
    "DEBUG_GOAL_SUMMARY",
    "Beginner learner who wants to be able to talk to Spanish-speaking neighbors.",
)
DEFAULT_DEBUG_BEST_GUESS_LEVEL = os.environ.get(
    "DEBUG_BEST_GUESS_LEVEL",
    "beginner",
)
DEFAULT_DEBUG_TIME_CONSTRAINT = os.environ.get(
    "DEBUG_TIME_CONSTRAINT",
    "No fixed deadline yet.",
)
DEFAULT_DEBUG_SCENARIO = os.environ.get(
    "DEBUG_SCENARIO",
    (
        "You are a Spanish-speaking neighbor meeting the learner outside your homes for the first time. "
        "Have a short, natural conversation about introductions, where each of you is from, and small "
        "neighborly topics like family, work, or the neighborhood."
    ),
)

DEFAULT_USER_ID = os.environ.get("DEFAULT_USER_ID", "local-dev-user")


def env_float(name, default_value):
    raw = os.environ.get(name)
    if raw is None:
        return default_value
    try:
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            # AUDIT: Weird throttle values (NaN/inf/negative) can make streaming appear broken or too chatty.
            return default_value
        return value
    except ValueError:
        # AUDIT: Bad env var values should not prevent the app from starting.
        return default_value


def env_int(name, default_value):
    raw = os.environ.get(name)
    if raw is None:
        return default_value
    try:
        value = int(raw)
        if value <= 0:
            # AUDIT: Non-positive throttling values can make streaming rerender too frequently.
            return default_value
        return value
    except ValueError:
        # AUDIT: Bad env var values should not prevent the app from starting.
        return default_value


# How often we update the UI while streaming.
# AUDIT: If these are too aggressive (too frequent), Gradio can appear to "not stream"
# due to buffering/rerender overhead; too conservative makes streaming feel laggy.
UI_THROTTLE_SECONDS = env_float("UI_THROTTLE_SECONDS", 0.08)
UI_THROTTLE_CHARS = env_int("UI_THROTTLE_CHARS", 24)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# AUDIT: Creating the client at import time can be surprising if OPENAI_API_KEY is missing.
# We still guard in `router`, but if the SDK ever validates keys at init, this could fail early.
client = OpenAI(api_key=OPENAI_API_KEY)
