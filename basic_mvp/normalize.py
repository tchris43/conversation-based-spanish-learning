import json


def wrap_input_text(text):
    return [{"type": "input_text", "text": text}]


def wrap_output_text(text):
    return [{"type": "output_text", "text": text}]


def normalize_message_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            block_text = block.get("text")
            if isinstance(block_text, str):
                text_parts.append(block_text)
                continue
            nested_value = block.get("content")
            if isinstance(nested_value, str):
                text_parts.append(nested_value)
        # AUDIT: Structured Gradio blocks can include non-text data; those are dropped here.
        return "\n".join(part for part in text_parts if part)
    if isinstance(content, dict):
        block_text = content.get("text")
        if isinstance(block_text, str):
            return block_text
        nested_value = content.get("content")
        if isinstance(nested_value, str):
            return nested_value
    return ""


def coerce_text(value):
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    text = normalize_message_content(value)
    if text:
        return text
    # AUDIT: If the model sends unexpected tool-argument types, falling back to `str(...)` avoids 400s
    # but may produce confusing corrections; tighten the tool schema/prompt if this happens.
    return str(value)


def normalize_gradio_history(history):
    normalized = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = normalize_message_content(item.get("content"))
            if role and content:
                normalized.append({"role": role, "content": content})
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            user_text, assistant_text = item
            user_text = normalize_message_content(user_text)
            assistant_text = normalize_message_content(assistant_text)
            if user_text:
                normalized.append({"role": "user", "content": user_text})
            if assistant_text:
                normalized.append({"role": "assistant", "content": assistant_text})
            continue
        # AUDIT: Unknown history item shapes are ignored, which may drop data if Gradio changes formats.
    return normalized


def extract_first_json_object(text):
    if not isinstance(text, str):
        return None

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    if start == -1:
        return None

    in_string = False
    escape = False
    depth = 0
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : idx + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def parse_truthy(value):
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False


def find_latest_assistant_message(history):
    for message in reversed(history or []):
        if message.get("role") == "assistant":
            return message.get("content", "")
    return ""
