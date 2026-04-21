# Final Project Brainstorm Summary

## Decision: Spanish Conversation Learning App

### What it is
An AI-powered Spanish learning app focused on conversational fluency. It tracks what the user knows (words, phrases, confidence levels) and generates conversations that weave in review vocabulary alongside new words using spaced repetition — embedded in natural conversation, not flashcards.

### Why this over other options
- **Coding harness idea** was considered but only naturally hits 1 of the 3 required agentic patterns (prompt engineering). It would also mostly be packaging workflow Taylor has already built, not learning something new.
- **Spanish app** naturally uses 3+ patterns without forcing them, solves a real daily pain point, and is something Taylor would keep using after the class ends.
- Taylor has domain expertise from learning Japanese — knows Duolingo doesn't cut it for real conversational fluency.

### Core agentic patterns (must hit 3+)
1. **Prompt engineering** — driving the AI to converse at the user's level, correcting mistakes inline without breaking conversational flow
2. **Context management** — injecting the user's learning graph (known vocab, confidence scores, last reviewed) into each session so the AI naturally uses known words while introducing new ones at the right rate
3. **Tool calling** — dictionary lookups, updating the vocabulary database, pulling example sentences

### Stretch goals (if time allows)
- **Multimodal (audio)** — browser speech-to-text + TTS for spoken conversation. Big demo wow-factor. Could be added in ~2 hours on top of a working text version.
- **Multi-agent** — conversation agent + review agent that analyzes sessions and plans the next one. Only if it emerges naturally, not forced.
- **RAG** — upload files describing conversation types you want fluency in (e.g., ordering food, job interviews)

### Key insight from brainstorm
The core feature isn't "chat in Spanish" — it's the **learning graph**. The system tracking what you know, your weak spots, and generating conversations that naturally review old words while introducing new ones. That's what makes it better than just prompting ChatGPT.

### Open design question
How to represent "what the user knows" — individual words with confidence scores? Phrases? Grammar patterns? This data model shapes everything.

### Time budget
10-15 hours total.
