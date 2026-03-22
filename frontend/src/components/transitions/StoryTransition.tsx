// ─── Story Transition ─────────────────────────────────────────────
// Enter-animation wrapper for story panel content.
// DS-1 §12: Directional transitions communicate spatial meaning.
//
// - push (drill-in)    → content slides in from right  (~200ms)
// - bounce_back (ascent) → content slides in from left  (~200ms)
// - null / lateral     → content fades in              (~150ms)
//
// Uses `key` prop to trigger React re-mount on navigation,
// which replays the CSS animation. No animation library needed.

import type { ReactNode } from "react";
import type { NavigationState } from "@/types/navigation";

interface StoryTransitionProps {
  /** Changes to this key trigger re-mount → animation replay. */
  itemKey: string | null;
  /** Last navigation action — determines animation direction. */
  lastAction: NavigationState["lastAction"];
  children: ReactNode;
}

function animationClass(
  lastAction: NavigationState["lastAction"],
): string {
  switch (lastAction) {
    case "push":
      return "animate-slide-in-right";
    case "bounce_back":
      return "animate-slide-in-left";
    default:
      return "animate-fade-in";
  }
}

export function StoryTransition({
  itemKey,
  lastAction,
  children,
}: StoryTransitionProps) {
  return (
    <div key={itemKey ?? "empty"} className={animationClass(lastAction)}>
      {children}
    </div>
  );
}
