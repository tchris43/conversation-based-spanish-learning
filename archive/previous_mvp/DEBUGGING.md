## Decision Skill
- If referencing an open question (e.g., "Question 4") fails to trigger the dedicated flow: check `.agents/skills/decision/SKILL.md` under the Activation section — the auto-detection rules may need to be rephrased or the message didn’t match the expected pattern.
- If the log entry never appears in `design/decisions.md` after a decision: check the skill instructions for the precise append logic and confirm the file is writable (design/decisions.md) and the skill actually writes there.
- If the decision summary doesn’t highlight the chosen answer or mentions too many unrelated options: check the Logging section in `.agents/skills/decision/SKILL.md` to make sure the bolded decision is inserted and the rationale stays concise.

## Chat UI
- If the inline hint never appears even though corrections are generated: check `app.js` around `callModel`/`logNeedsWork` — the response may have an empty `Correction` or the hint block isn’t being toggled visible.
- If the collapsible logs sidebar stays empty after a session: check `app.js` in `renderLogs` — the `state.logs` array might only contain prompt entries and no `needs_work` items, so ensure `logNeedsWork` pushes entries when corrections happen.

## Onboarding Flow
- If the onboarding form reappears on refresh: check `app.js` at the `onboardingForm` handler — the profile meta may not be persisted, so `state.profile.meta` stays empty and the panel is not removed.
- If `sessionSummary` never updates after onboarding submission: check the same handler to ensure `sessionSummary.textContent` is set after the profile is saved and the form is removed.

## Practice Loop
- If pressing Enter doesn’t send the message: check `app.js` around `messageInput`’s `keydown` listener to ensure it calls `handleMessageSubmit` and doesn’t require Shift.
- If scheduled reviews aren’t appearing: inspect `computeScheduler`/`registerNewConcepts` to confirm `profile.meta.dailyPlan` is updated with today’s date before `reviewSet` is built.
- If the inline hint shows but the correction doesn’t reset spacing: verify `callModel` returns `focusConcept` and `resetConceptSpacing` is invoked with that text.
- If the real LLM never fires or returns invalid JSON: check `callModel` — ensure `OPENAI_API_KEY` is defined on `window`, the response is parsed by `parseStructuredOutput`, and the backend falls back to the stub.
