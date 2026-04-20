import { useState, useEffect, useRef } from "react";
import { useTheme } from "../../context/ThemeContext";
import { TIMING } from "../../lib/constants";

interface SuggestedRepliesProps {
  replies: string[];
  onSelect: (text: string) => void;
}

export default function SuggestedReplies({ replies, onSelect }: SuggestedRepliesProps) {
  const { theme } = useTheme();
  const [visibleCount, setVisibleCount] = useState(0);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const maxReplies = theme.agent.maxSuggestedReplies ?? 3;
  const displayReplies = replies.slice(0, maxReplies);

  useEffect(() => {
    setVisibleCount(0);
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];

    displayReplies.forEach((_, i) => {
      const timer = setTimeout(() => {
        setVisibleCount((prev) => prev + 1);
      }, TIMING.SUGGESTED_REPLY_APPEAR_DELAY + i * TIMING.SUGGESTED_REPLY_STAGGER);
      timersRef.current.push(timer);
    });

    return () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };
  }, [replies]);

  if (displayReplies.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2 pl-12">
      {displayReplies.map((reply, i) => (
        <button
          key={`${reply}-${i}`}
          onClick={() => onSelect(reply)}
          className="text-sm px-3 py-1.5 transition-colors"
          style={{
            backgroundColor: theme.colors.surfaceInput,
            borderRadius: "20px",
            color: theme.colors.textPrimary,
            opacity: i < visibleCount ? 1 : 0,
            transform: i < visibleCount ? "translateY(0)" : "translateY(4px)",
            transition: "opacity 200ms ease, transform 200ms ease, background-color 150ms ease",
          }}
          onMouseEnter={(e) => {
            (e.target as HTMLElement).style.backgroundColor = theme.colors.surfaceActiveNav;
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLElement).style.backgroundColor = theme.colors.surfaceInput;
          }}
        >
          {reply}
        </button>
      ))}
    </div>
  );
}
