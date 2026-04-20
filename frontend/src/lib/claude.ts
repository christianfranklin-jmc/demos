import type { StepNumber, ConversationMessage } from "./types";

/**
 * Claude API client for DSA agent conversations.
 *
 * IMPORTANT: In production, this must go through a backend proxy to avoid
 * exposing the API key in the browser. For the demo, route through
 * Vite's proxy config or a simple /api/chat edge function.
 */

const API_URL = "/api/chat"; // Proxied to Claude API

interface ClaudeMessage {
  role: "user" | "assistant";
  content: string;
}

interface ClaudeRequest {
  model: string;
  max_tokens: number;
  system: string;
  messages: ClaudeMessage[];
}

interface ClaudeResponse {
  content: Array<{ type: string; text: string }>;
}

/**
 * Load the system prompt for a given step.
 * In the build, these are markdown files in src/data/prompts/.
 * At runtime, they are imported as strings.
 */
const SYSTEM_PROMPTS: Record<StepNumber, () => Promise<string>> = {
  0: () => import("../data/prompts/step1-requirements.md?raw").then((m) => m.default), // Step 0 reuses Step 1 for now
  1: () => import("../data/prompts/step1-requirements.md?raw").then((m) => m.default),
  2: () => import("../data/prompts/step2-conceptual.md?raw").then((m) => m.default),
  3: () => import("../data/prompts/step3-logical.md?raw").then((m) => m.default),
  4: () => import("../data/prompts/step4-detailed.md?raw").then((m) => m.default),
};

/**
 * Send a message to the Claude API and get a response.
 * Step-scoped: each step uses its own system prompt. No cross-step context.
 */
export async function sendMessage(
  step: StepNumber,
  conversationHistory: ConversationMessage[],
  userMessage: string,
  artifactContext?: string
): Promise<string> {
  const systemPrompt = await SYSTEM_PROMPTS[step]();

  // Build the message history for this step only
  const stepMessages = conversationHistory
    .filter((m) => m.step === step && m.message_role !== "system")
    .map(
      (m): ClaudeMessage => ({
        role: m.message_role === "agent" ? "assistant" : "user",
        content: m.message_text,
      })
    );

  // Add the new user message
  stepMessages.push({ role: "user", content: userMessage });

  // If there's artifact context (e.g., PRD state for resume), prepend to system
  const fullSystemPrompt = artifactContext
    ? `${systemPrompt}\n\n## Current Artifact State\n${artifactContext}`
    : systemPrompt;

  const request: ClaudeRequest = {
    model: "claude-sonnet-4-6-20250514",
    max_tokens: 1024,
    system: fullSystemPrompt,
    messages: stepMessages,
  };

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Claude API error: ${response.status}`);
    }

    const data: ClaudeResponse = await response.json();
    return data.content[0]?.text || "I'm having trouble responding. Could you try that again?";
  } catch (error) {
    console.error("Claude API call failed:", error);
    throw error;
  }
}

/**
 * Generate the opening message for a step (new session).
 * This is called when entering a step for the first time.
 */
export async function getOpeningMessage(step: StepNumber): Promise<string> {
  return sendMessage(step, [], "__SYSTEM_INIT__");
}

/**
 * Generate a resume message for a step (returning session).
 * Includes current artifact state so the agent knows where the user left off.
 */
export async function getResumeMessage(
  step: StepNumber,
  conversationHistory: ConversationMessage[],
  artifactState: string
): Promise<string> {
  return sendMessage(
    step,
    conversationHistory,
    "__SYSTEM_RESUME__",
    artifactState
  );
}
