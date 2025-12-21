---
agent: 'agent'
name: 'ImplementPlanAndResearch'
model: Gemini 3 Pro (Preview)
description: 'Implement research.md and implementation_plan.md if exists.'
---
Implement the requested feature or bug fix using the research documented in `research.md` and the step-by-step instructions in `implementation_plan.md` if it exists. Both files are located in the root of the repository, implementation plan being optional.

**Instructions:**

1.  **Analyze Context:**
    *   Read `research.md` in the root of the repository to understand the task, relevant files, and constraints.
    *   Check for the existence of `implementation_plan.md` in the root.

2.  **Implementation Strategy:**
    *   **If `implementation_plan.md` exists:** Strictly follow the step-by-step plan outlined in that file. Use `research.md` for additional context.
    *   **If `implementation_plan.md` does NOT exist:** Use the findings in `research.md` to determine the necessary changes and implement them directly.

4.  **Cleanup:**
    *   Upon successful implementation and verification, delete `research.md`.
    *   Upon successful implementation and verification, delete `implementation_plan.md` if it exists.
