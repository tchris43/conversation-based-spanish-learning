# Multi-Agent Conversational Spanish Platform
*An immersive language learning system built on a modular, multi-agent architecture.*

## Overview
This platform moves beyond simple chatbot interactions by utilizing a coordinated multi-agent system to facilitate natural Spanish acquisition. The system prioritizes **"productive struggle"** by tracking user vocabulary and dynamically injecting specific target words into the conversation context via a custom **Spaced Repetition System (SRS)** algorithm.

## Key Technical Features
* **Dynamic Context Injection:** Automates vocabulary review by prioritizing words due for reinforcement (`todays_words`, `used_words`, `learned_words`) and surfacing them within the LLM's system prompt to ensure contextual usage.
* **Separation of Concerns:** Distinct agents handle onboarding, assessment, gameplan generation, module generation, and session management to ensure high reliability and specific persona maintenance.
* **Agent-as-Tool Pattern:** A dedicated correction sub-agent is invoked as a tool for real-time grammar and syntax feedback, allowing the primary conversation agent to maintain the flow of dialogue without losing focus on pedagogical goals.
* **Custom SRS Algorithm:** A hand-rolled spacing schedule (0 → 1 → 4 → 8 days, mastery at 4 consecutive correct answers) rather than an off-the-shelf library, so review cadence can be tuned against real usage.

## System Architecture
The platform operates as a staged pipeline with branching logic for real-time feedback.

### Pipeline Orchestration
1.  **Onboarding:** Captures user goals and initial proficiency.
2.  **Assessment:** Initiates a diagnostic conversation to establish a baseline.
3.  **Conclude Assessment:** Produces a structured summary with `strengths`, `gaps`, `where_they_stand`, `next_focus`, `review_seed_words`, and `session_summary`.
4.  **Gameplan:** Produces a customized list of `modules`.
5.  **Module Generator:** Designs a specific `scenario` (with `title`, `goal`, `completion_signal`, and `spaced_review_focus`).
6.  **Session:** Immersive conversation utilizing the SRS-injected context.
7.  **Conclude Session:** Updates vocabulary tracking and retention metrics (strengths, gaps, new review words).

## Development Methodology
This project was developed using an **AI-Augmented workflow**.

* **Adversarial Spec Refinement:** Using LLMs to stress-test the architectural flow before implementation.
* **Engineering Harness:** Detailed logging in `DEBUGGING.md` to track agent state transitions and resolve orchestration logic errors.
