# Architecture

## Decision Workflow
- The `/decision` skill integrates ThinkDeep with the open question backlog. It auto-detects references to `design/open_questions.md` (by number or text) and forces the ThinkDeep phases before issuing an answer, ensuring every design choice is explored with clarifying questions and challenge prompts.
- Once a decision is reached, the skill appends a concise log to `design/decisions.md`, noting the question number/text, the highlighted choice, any considered options, and a short rationale. This keeps the log scannable and auditable.
- The manual `/decision` trigger mirrors the same flow so we can revisit questions deliberately. Any architecture or process updates we derive during the flow should be recorded in this file so the reasoning trail is centralized.
