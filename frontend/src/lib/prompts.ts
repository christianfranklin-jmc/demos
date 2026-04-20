import type { StepNumber } from "./types";

/**
 * Load the system prompt for a given step.
 * Prompts are markdown files imported as raw strings via Vite.
 */

const promptModules: Record<StepNumber, () => Promise<{ default: string }>> = {
  0: () => import("../data/prompts/step1-requirements.md?raw"),
  1: () => import("../data/prompts/step1-requirements.md?raw"),
  2: () => import("../data/prompts/step2-conceptual.md?raw"),
  3: () => import("../data/prompts/step3-logical.md?raw"),
  4: () => import("../data/prompts/step4-detailed.md?raw"),
};

export async function loadSystemPrompt(step: StepNumber): Promise<string> {
  const mod = await promptModules[step]();
  return mod.default;
}

/**
 * Inject artifact context into a system prompt for resume scenarios.
 * The agent needs to know the current state to generate a contextual resume message.
 */
export function enrichPromptWithContext(
  basePrompt: string,
  artifactJson: string
): string {
  return `${basePrompt}\n\n## Current Artifact State (Resume Context)\n\`\`\`json\n${artifactJson}\n\`\`\`\n\nThe user is returning to an in-progress session. Generate a resume message that demonstrates you know exactly where they left off. Do NOT ask "where were we?" — state the current artifact state and ask the next question directly.`;
}
