# Multi-Agent Conversational Spanish Platform
*An immersive language learning system built on a modular, multi-agent architecture.*

## Overview
This platform moves beyond simple chatbot interactions by utilizing a coordinated multi-agent system to facilitate natural Spanish acquisition. The system prioritizes **"productive struggle"** by tracking user vocabulary and dynamically injecting specific target words into the conversation context via a custom **Spaced Repetition System (SRS)** algorithm.

## Key Technical Features
* **Dynamic Context Injection:** Automates vocabulary review by prioritizing words due for reinforcement and surfacing them within the LLM's system prompt to ensure contextual usage.
* **Separation of Concerns:** Distinct agents handle onboarding, assessment, and session management to ensure high reliability and specific persona maintenance.
* **Agent-as-Tool Pattern:** Utilizes sub-agents for real-time grammar and syntax corrections, allowing the primary conversation agent to maintain the flow of dialogue without losing focus on pedagogical goals.

## System Architecture
The platform operates as a linear pipeline with branching logic for real-time feedback.

### Pipeline Orchestration
1.  **Onboarding:** Captures user goals and initial proficiency.
2.  **Assessment:** Initiates a diagnostic conversation to establish a baseline.
3.  **Conclude Assessment:** Generates a `user_feedback_summary`.
4.  **Gameplan:** Produces a customized `module_list`.
5.  **Module Generator:** Designs a specific `session_scenario`.
6.  **Session:** Immersive conversation utilizing the SRS-injected context.
7.  **Conclude Session:** Updates vocabulary tracking and retention metrics.

## Development Methodology
This project was developed using an **AI-Augmented workflow**.

* **Adversarial Spec Refinement:** Using LLMs to stress-test the architectural flow before implementation.
* **Engineering Harness:** Detailed logging in `DEBUGGING.md` to track agent state transitions and resolve orchestration logic errors.
