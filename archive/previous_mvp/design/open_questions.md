# Open Questions
These are the open questions we want to log before we let the AI make decisions on architecture, flows, or prompts. Questions marked with **[Before MVP]** should be resolved prior to locking down the MVP; the rest can land after the MVP is working.

## Pre-MVP
1. **[Before MVP]** What does success look like for the complete-beginner persona—what conversational abilities must they demonstrate after the MVP (e.g., greetings, narrating past events, asking for help)?  
2. **[Before MVP]** What should the onboarding flow collect (goals, time availability, self-assessment, preferred topics) so we can seed each session with a personalized starting point?  
3. **[Before MVP]** Where does the progress profile live (client memory, backend database, or hybrid) and how do we keep it in sync between sessions?  
4. **[Before MVP]** Which LLM/models and tool providers are we targeting, and how do we keep prompt + context sizes under their token limits while still providing the learner’s profile in every interaction?  
5. **[Before MVP]** How do we detect that a learner “needs work” on a concept (definitions of exposures, correct usages, streak rules) and what evidence (turn logs) do we persist with each decision?  
6. **[Before MVP]** How do we store rationale for each “needs work” tag so it is auditable and explainable (LLM-supplied reason + pointer to the conversation turn that triggered it)?  
7. **[Before MVP]** What authentication/session mechanisms are required (anonymous, email, social, etc.) and how do they affect storing progress data?  
8. **[Before MVP]** What instrumentation/logging do we need from day one to debug prompts, conversation failures, and “needs work” misclassifications?  
9. **[Before MVP]** What infrastructure/hosting constraints exist for the web UI, LLM proxy, and data store (e.g., cost limits, latency requirements)?
10. **[Before MVP]** Are there regulatory/privacy requirements for storing conversation history or learner performance data that we need to address before launching the MVP?
11. **[Before MVP]** How do we handle prompt reliability—what fallback path or verification do we use when the model’s explanation is low-confidence or missing?
12. **[Before MVP]** Do we need an initial content library (starter prompts, topics, grammar jokes) or can the LLM improvise entirely from our instructions?

## Post-MVP / Later
13. What does content authoring look like (who curates prompts, how do we version them, how do we collect feedback) once the core flow is stable?
14. When and how do we expand beyond Spanish and beginner level—do we need modular content or architecture to support other languages/levels from the start?
15. How do we visualize progress for learners and for Taylor (dashboards, charts, streaks) without overwhelming the MVP?
16. Do we need a review/approval flow for the “needs work” tags (e.g., can Taylor review and edit them before pushing to a learner)?
17. How should we price or monetize the product (subscription, freemium, one-time) once we validate demand?
18. What offline or degraded-network behavior is acceptable, and which aspects can wait until after the MVP proves the core loop?
19. How do we keep the conversation context manageable across long sessions (scrollback pruning, summary, caching) once usage scales up?
20. What instrumentation and alerting do we need for production monitoring (e.g., prompt failure rates, LLM latency spikes)?
21. How do we gather qualitative user feedback (surveys, interviews, prompts) without interrupting the conversational flow?
22. What accessibility considerations (screen readers, high contrast, keyboard) should we prioritize in the future?
23. How do we generalize the “needs work” insights for curriculum planning (e.g., clustering common mistakes to update prompts)?
