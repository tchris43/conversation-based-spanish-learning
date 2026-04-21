# Basic MVP Plan

This restart keeps things minimal and Python-native. The app reads `prompt.md` and uses it every turn to guide a short, adaptive chat that ends once the assistant can assign a baseline score. We host the UI with Gradio so you can focus entirely on editing `prompt.md` and testing prompt behaviour.

## Scope
1. **Prompt-driven chat**  
   - The system reads `prompt.md` (the only file you need to edit) and feeds that instruction to the conversational stub on each turn.  
   - Gradio displays the chat history, a text input, and a final score panel; no extra UI elements or snapshots.  
   - A minimal state machine (difficulty index + turn count) keeps track of when to escalate or simplify; once the stub sets `"final": true` the chat ends and a score is shown.

2. **Simple backend**  
   - All logic lives in `basic_mvp/app.py`: it loads `prompt.md`, fires `openai.ChatCompletion` (model `gpt-4o-mini`) with the prompt plus the chat history, and returns the assistant’s reply. The Gradio UI simply reflects that chat loop.
   - This stub is trivial to replace with your real LLM call once the prompt text is stabilized.

3. **Gradio hosting**  
   - Launch the UI via `python basic_mvp/app.py`; edit `prompt.md` at any time between runs to change the assistant’s behaviour.  
   - We keep the UX as minimal as possible so the prompt file is the only surface you iterate against.

## Infrastructure
- No Node or JS server—everything runs in Python. The only support file is `prompt.md`, which you edit manually.  
- Running `python basic_mvp/app.py` starts the Gradio chat where the prompt is loaded from disk and used to guide the evaluation.

## Next steps
1. Start the app with `python basic_mvp/app.py`, enter a few Spanish responses, and watch how the stub uses the prompt.  
2. Once the prompt flow feels right, replace the stub inside `app.py` with the real LLM call and refine the prompt text iteratively.  
3. We can add context tracking or a scheduler later if the prompt-first baseline proves valuable.
