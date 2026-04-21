# Critique

## Learner Modeling
- The old `increase_difficulty` / `decrease_difficulty` tools were decent for conversation steering, but they were a weak fit for the actual product goal. They made difficulty adjustments traceable, but they did not create a durable learner model.
- The main downside of those tools was latency and fragmentation. Each difficulty change required an extra tool-followup round, and the system still lacked a persistent record of why the learner was placed where they were.
- The stronger direction is to treat `strengths` and `gaps` as the real learner artifact. Those are what matter for roadmap planning, future sessions, and explaining the learner's starting line.
- `best_guess_level` is still useful, but only as an onboarding baseline. It should not be treated as the true learner state by itself.
- The improved architecture is:
  - `best_guess_level` = initial baseline from onboarding
  - `state_summary` = persistent learner record built from stored strengths/gaps
  - `adjustment_state` = session-only guidance for how hard/easy the conversation should currently be
- This is a better fit because it gives the conversation agent:
  - a starting point
  - durable cross-session evidence
  - current session adaptation guidance
- The current persistent storage approach is now per-user local JSON (`basic_mvp/data/users/<user_id>/...`), which is a strong step for local multi-profile workflows. The remaining limitation is identity trust and hosting readiness: there is no auth boundary, so this should move to server-side user context before internet deployment.

## Roadmap State
- The new roadmap/gameplan flow is a better fit than trying to force long-term planning into the live conversation prompt. Assessment and planning are different jobs and should stay split.
- The extra `planning` phase is the right compromise when `time_constraint` is missing. Hiding that question inside `generate_gameplan(...)` would make the flow harder to trace and debug, while the explicit phase keeps the user interaction visible in `app.py`.
- The current compromise is that `gameplan_state` and `spaced_review_state` live only in Gradio session state. That is enough to debug the flow and later drive a mountain-path UI, but it is not durable. A refresh or server restart loses the generated roadmap.
- The `run_module_generator(...)` helper is now the right boundary for turning a module title into a concrete roleplay scenario. The weak point is prompt quality: if `basic_mvp/prompts/module_generator.md` is empty or vague, the generated modules will look generic even if the planning layer is good.

## Spaced Review
- Moving spaced review into `basic_mvp/spaced_review_store.py` is the right separation: the schedule engine is deterministic and does not depend on model behavior.
- Using permanent disk state (`basic_mvp/data/spaced_review.json`) fixes the earlier session-only limitation, but it is still single-user local storage and will conflict once multiple users exist.
- The current retry rule (incorrect -> half of remaining time to normal due date) is pragmatic and easy to reason about, but it creates a tradeoff: heavily overdue words can still be due immediately unless clamped. The current implementation clamps to at least 1 day for stability.
- Mastery-by-streak (`consecutive_correct >= 4`) is simple and demo-friendly, but it may overfit short sessions. If retention quality matters later, mastery should also consider elapsed time and not only streak count.

## Per-User Local Storage
- Moving persistence into `basic_mvp/data/users/<user_id>/...` is the right interim architecture. It allows user-scoped profile, spaced review, gameplan, and module progress without introducing DB complexity too early.
- The new profile picker is adequate for local multi-user testing (no auth), but it is still trust-based client selection. For a hosted app, user identity must move to authenticated server-side context.
- Legacy migration fallback from `basic_mvp/data/profile.json` and `basic_mvp/data/spaced_review.json` is practical, but it is one-way and file-based. Once web auth exists, migration should be explicit and auditable.
- `gameplan_state` persistence is now local and durable, but module progress capture is still minimal. We still need explicit module/session outcome writes to make roadmap progression trustworthy.
- ## Module Sessions
- Adding a dedicated `module_session` phase is the right evolution: it isolates module roleplay from the assessment, injects `todays_words`/`used_words`/`learned_words`, and makes tooling decisions recoverable.
- The new `record_word_outcome` tool keeps spaced review deterministic, but it also means prompts must explicitly call the tool each time a review word is used or missed; otherwise the spaced-review store will drift. This is the new failure surface we need to monitor.
- The `conclude_session` tool must summarize the module transcript and persist new strengths/gaps + new review words. If the prompt or JSON schema drifts, the module conclusion may stop updating the learner profile, so we need to keep `basic_mvp/prompts/conclude_session.md` under active iteration the same way we already do for `conclude_assessment.md`.

## Web Integration
- Splitting the product into a lightweight Python API plus a separate Next.js frontend is the right boundary. It preserves the existing prompt/tool/state logic while giving the UI the control it needs for the mountain roadmap and session views.
- The first live-chat web integration should stay full-turn and non-streaming. That is the correct tradeoff right now because session persistence, tool handoffs, and user-scoped state are still stabilizing; adding SSE/websocket chat immediately would multiply failure modes.
- `basic_mvp/chat_backend.py` is the right kind of compromise, but it does duplicate some orchestration logic from `basic_mvp/app.py`. That duplication is acceptable short-term to avoid Gradio coupling, but it will become a maintenance risk if the two paths drift.
- The backend import model is still too local-script-oriented. Requiring the API server to run from inside `basic_mvp` is acceptable for a prototype, but it is a packaging smell that should be fixed before deployment or CI hardening.
- The Next.js integration is currently stronger on roadmap/session rendering than on feature parity. Full-turn chat is wired, but web audio playback and richer module progress are still missing. That is a good sequencing choice, but it should be treated as an explicit gap rather than assumed complete.
