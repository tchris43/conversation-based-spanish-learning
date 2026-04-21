# Spanish Learning App — Development Guidelines

## Development Process

### Taylor Makes the Decisions
- **Explain before writing.** Before writing any major component, explain what it does, why it's structured that way, and what decisions need to be made. Do NOT write code until Taylor understands the approach and gives the green light.
- **Stop and ask on decisions.** If a design decision comes up mid-build (architecture choices, how to handle edge cases, tradeoffs), stop and present the options to Taylor rather than making the call silently.
- **No surprise complexity.** If a component is going to be more complex than expected, flag it and explain why before proceeding.

### Understanding Checks
- After completing a major component, ask Taylor if he wants a /thinkDeep session to verify he understands the code before moving on. Don't skip ahead — Taylor needs to understand each piece to maintain and debug it later.
- After an understanding check, save what Taylor learned to `notes/<filename>_taylor_notes.md`. These capture Taylor's understanding of each component in his own terms — what it does, why it's built that way, and key details he needs to remember.

### Architecture Documentation
- When architecture decisions are discussed or made, update `ARCHITECTURE.md` with what was decided and why. This file should explain how things work in plain language so Taylor or a new developer can understand the system without reading every line of code.
- When a meaningful critique or tradeoff is identified (for example, a design that works technically but is weak product architecture, too latent, too brittle, or hard to scale), update `CRITIQUE.md` with that critique and the recommended direction.

### Project Structure
- Do NOT move node_modules, package.json, or package-lock.json from their default locations. Every Node.js tool and hosting platform expects them at the project root. Moving them breaks tooling.
- Keep the file structure standard and conventional so other developers (or future Taylor) can navigate it immediately.

## Code Quality Rules

### AUDIT Comments
When writing or modifying code, add `// AUDIT:` comments at any point where something could break, behave unexpectedly, or become a maintenance issue. These should explain WHAT could go wrong and WHY, not just flag the line. Examples:

```js
// AUDIT: If the vocab database grows large, injecting the full list into context will blow the token limit — need pagination or summarization
// AUDIT: Spaced repetition intervals are hardcoded — may need tuning after real usage data
// AUDIT: Tool call for dictionary lookup assumes the API is available — no offline fallback
```

### DEBUGGING.md
After writing or modifying a component, update `DEBUGGING.md` with symptom → cause mappings:

Format:

```
## [Component Name]
- If [symptom]: check [file:location] — [likely cause]
```

This file is the FIRST thing to read when diagnosing a bug. Keep entries short and specific. Each component should have 2-3 entries covering the most likely failure modes.

### General
- Keep code simple. Prefer clarity over cleverness.
- Use descriptive variable and function names — the code should read like documentation.
- Abstract the LLM API call behind a single function (`callModel`) so the model can be swapped easily.

### Prompt Iteration
- Taylor will design and tweak the prompt templates, so describe the candidate prompt before coding and keep an easily editable place to update it during testing.
- Make the prompt structure as parseable as possible (corrections, rationale, next question) so Taylor can observe agent responses, adjust wording, and understand how the AI behaves.

### Model Recommendations
- If a particular model would be recommended for a task, explicitly tell Taylor to change to that model before continuing.

## AI Policy Reminder
- AI tools are strictly prohibited on exams and for prompt engineering practice for this course; use them only for writing or supporting code.
- Quiz answers and reports must be entirely your own content—do not rely on AI-generated text for those submissions.
- Document any AI-assisted UI or tooling changes so Taylor can see how tools were used, and double-check this section before editing anything the student expects to handle personally.

## Final Project Scope
- Final project must include at least three of the following: prompt engineering, hallucination/jailbreak protection, context management (e.g., RAG), tool calling (including MCP/code-as-tool), multiple agents (agent-at-tool), multimodal inputs.
- The semester finale includes a small-group demo with a handful of nominations presenting to the whole class, so plan iterations accordingly.
- Treat the final project as a portfolio highlight—document agent engineering decisions you can discuss in interviews or demos later.
