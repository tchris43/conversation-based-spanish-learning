---
name: decision
description: >
  Coordinates ThinkDeep with every response tied to design/open_questions.md.
  Auto-detects when we are addressing one of those questions (by number or text) and
  ensures a guided exploration before finalizing an answer; also fires when the user
  explicitly types `/decision`.
---

# Decision Skill

## Activation
- Run this skill whenever the latest user message references `design/open_questions.md` by question number (e.g., "Question 4" or "Q4") or by repeating the question text. If `/decision` is used manually, start the same flow.
- Do not proceed to answer until you confirm which open question is in scope.

## ThinkDeep Flow
1. Use the ThinkDeep phases: listen, challenge (surface blind spots), and contribute (offer ideas) while keeping the open question in focus.
2. Keep the conversation concise—ask 2-4 thoughtful follow-ups to tease out assumptions or constraints before moving on.
3. When you have enough clarity, summarize the question, the context, and the options discussed so both you and Taylor share alignment.

## Logging
- After agreeing on a decision, append an entry to `design/decisions.md` that follows this structure:
  ```
  ### Question 4 – What does success look like for the complete-beginner persona?
  - **Decision:** Use conversational goals of greetings, past narratives, and help-seeking with automated prompts.
  - Options considered: Quick grammar drills, open-ended storytelling, template-based feedback.
  - Rationale: Balances immediate confidence-building with narrative practice.
  ```
  Keep entries short, highlight the chosen decision in bold, and mention the question number plus text.
- If multiple options were on the table, briefly mention them (list or comma-separated) so the rationale makes sense.

## Hand-offs
- After logging, continue with whatever follow-up Taylor needs—provide code, docs, or next steps.
- If any new architecture conclusions arise, note them in `ARCHITECTURE.md` and explain why.

## Reminder
- This skill never skips ThinkDeep when handling an open question; treat `/decision` as both a trigger and a guardrail.
