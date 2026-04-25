import { useRef, useEffect, useCallback } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getStepConfig } from "../../lib/constants";
import { useAgent } from "../../hooks/useAgent";
import { useSourceDiscovery } from "../../hooks/useSourceDiscovery";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import SuggestedReplies from "./SuggestedReplies";
import ChatInput from "./ChatInput";
import CancelButton from "./CancelButton";
import type { StepNumber } from "../../lib/types";

export default function ChatPanel() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);
  const currentStep = state.lifecycle.current_step;
  const stepConfig = getStepConfig(currentStep);

  // Activate the agent — handles opening message and responses
  useAgent();
  // Discover business processes/pills/product-name for the connected source.
  useSourceDiscovery();

  // Filter messages for current step
  const messages = state.conversation.filter(
    (m) => m.step === currentStep
  );

  // Last agent message's suggested replies, minus anything the user already
  // used in this step. Prevents the same pill showing up after it's been
  // clicked, which was causing users to re-click identical prompts and see
  // nearly-identical agent responses.
  const lastAgentMessage = [...messages].reverse().find((m) => m.message_role === "agent");
  const usedPrompts = new Set(
    messages
      .filter((m) => m.message_role === "user")
      .map((m) => m.message_text.trim().toLowerCase()),
  );
  const suggestedReplies = (lastAgentMessage?.suggested_replies ?? []).filter(
    (r) => !usedPrompts.has(r.trim().toLowerCase()),
  );

  // Scroll handling
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    userScrolledUpRef.current = distanceFromBottom > 50;
  }, []);

  const scrollToBottom = useCallback(() => {
    if (userScrolledUpRef.current) return;
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  // Auto-scroll on new messages or thinking state
  useEffect(() => {
    scrollToBottom();
  }, [messages.length, state.ui.isAgentThinking, scrollToBottom]);

  const handleSend = (text: string) => {
    dispatch({
      type: "ADD_MESSAGE",
      message: {
        data_product_id: state.lifecycle.data_product_id,
        step: currentStep as StepNumber,
        message_role: "user",
        message_text: text,
        timestamp: new Date().toISOString(),
      },
    });
  };

  const handleSuggestedReply = (text: string) => {
    handleSend(text);
  };

  const totalSteps = theme.features.showStep0 ? 5 : 4;

  return (
    <div
      className="flex flex-col h-full border-r"
      style={{
        width: `${theme.layout.chatPanelPercent}%`,
        borderColor: theme.colors.borderSubtle,
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-2 shrink-0"
        style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}
      >
        <p className="text-xs" style={{ color: theme.colors.textTertiary }}>
          {stepConfig.agent_persona} &middot; Step {currentStep} of {totalSteps}
        </p>
      </div>

      {/* Message list */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto py-3"
      >
        {messages.length === 0 && !state.ui.isAgentThinking && (
          <div className="flex-1 flex items-center justify-center h-full">
            <p className="text-sm italic" style={{ color: theme.colors.textTertiary }}>
              The agent will start the conversation...
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={`${msg.timestamp}-${i}`} message={msg} />
        ))}

        {state.ui.isAgentThinking && <TypingIndicator />}

        {!state.ui.isAgentThinking && suggestedReplies.length > 0 && (
          <SuggestedReplies replies={suggestedReplies} onSelect={handleSuggestedReply} />
        )}
      </div>

      {/* Cancel button — only visible while a backend run is in flight (T046). */}
      <div className="flex justify-end px-3">
        <CancelButton />
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={state.ui.isAgentThinking} />
    </div>
  );
}
