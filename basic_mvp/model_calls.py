import io
import json
import wave

import gradio as gr
import numpy as np

from config import (
    DEBUG_DISABLE_STREAMING,
    DEBUG_MODEL_INPUT,
    DEBUG_SSE,
    OPENAI_MODEL,
    TTS_MODEL,
    TTS_SAMPLE_RATE,
    TTS_VOICE,
    client,
)


def debug_log_model_input(*, label, input_messages=None, tools=None, previous_response_id=None, input_override=None):
    if not DEBUG_MODEL_INPUT:
        return
    payload = {
        "label": label,
        "model": OPENAI_MODEL,
        "previous_response_id": previous_response_id,
        "tools": [tool.get("name") for tool in (tools or []) if isinstance(tool, dict)],
        "input": input_override if previous_response_id is not None else input_messages,
    }
    print("=== MODEL INPUT DEBUG ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("=========================")


def call_model(input_messages):
    debug_log_model_input(label="call_model", input_messages=input_messages)
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=input_messages,
    )
    return response


def run_model_turn(*, input_messages=None, tools=None, previous_response_id=None, input_override=None):
    debug_log_model_input(
        label="run_model_turn",
        input_messages=input_messages,
        tools=tools,
        previous_response_id=previous_response_id,
        input_override=input_override,
    )
    create_kwargs = {"model": OPENAI_MODEL}
    if previous_response_id is not None:
        create_kwargs["previous_response_id"] = previous_response_id
        create_kwargs["input"] = input_override or []
    else:
        create_kwargs["input"] = input_messages or []
    if tools is not None:
        create_kwargs["tools"] = tools
    return client.responses.create(**create_kwargs)


def call_onboarding_model(input_messages):
    response = call_model(input_messages)
    return (getattr(response, "output_text", "") or "").strip()


def stream_model(*, input_messages=None, tools=None, previous_response_id=None, input_override=None):
    debug_log_model_input(
        label="stream_model",
        input_messages=input_messages,
        tools=tools,
        previous_response_id=previous_response_id,
        input_override=input_override,
    )
    if DEBUG_DISABLE_STREAMING:
        create_kwargs = {"model": OPENAI_MODEL}
        if previous_response_id is not None:
            create_kwargs["previous_response_id"] = previous_response_id
            create_kwargs["input"] = input_override or []
        else:
            create_kwargs["input"] = input_messages or []
        if tools is not None:
            create_kwargs["tools"] = tools

        response = client.responses.create(**create_kwargs)
        answer_text = (getattr(response, "output_text", "") or "")
        if answer_text:
            yield answer_text
        return response

    create_kwargs = {"model": OPENAI_MODEL, "stream": True}
    if previous_response_id is not None:
        create_kwargs["previous_response_id"] = previous_response_id
        create_kwargs["input"] = input_override or []
    else:
        create_kwargs["input"] = input_messages or []
    if tools is not None:
        create_kwargs["tools"] = tools

    stream = client.responses.create(**create_kwargs)
    answer_text = ""
    completed_response = None
    for event in stream:
        event_type = getattr(event, "type", "")
        if DEBUG_SSE:
            print(f"SSE event: {event_type}")
        if event_type == "response.output_text.delta":
            answer_text += getattr(event, "delta", "")
            yield answer_text
        elif event_type == "response.output_text.done":
            done_text = getattr(event, "text", "")
            if done_text:
                answer_text = done_text
                yield answer_text
        elif event_type == "response.completed":
            completed_response = getattr(event, "response", None)
        elif event_type == "error":
            raise gr.Error(getattr(event, "message", "Streaming response failed."))
    return completed_response


def generate_tts_audio(text):
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return None

    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=cleaned_text,
        response_format="pcm",
    )
    audio = np.frombuffer(response.read(), dtype=np.int16)
    if not audio.size:
        return None
    # AUDIT: This is post-turn playback, not true live TTS streaming. It is more reliable in Gradio
    # because it avoids the streamed-audio conversion path that depended on ffmpeg/ffprobe.
    return (TTS_SAMPLE_RATE, audio)


def generate_tts_wav_bytes(text):
    audio = generate_tts_audio(text)
    if audio is None:
        return None
    sample_rate, pcm = audio
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.astype(np.int16).tobytes())
    return buffer.getvalue()
