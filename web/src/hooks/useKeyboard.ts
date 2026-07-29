import { useEffect } from "react";

/**
 * Keyboard shortcuts.
 *
 * The arrow mapping mirrors NavControls: Arabic runs right to left, so
 * ArrowLeft advances and ArrowRight goes back. If one of these is ever
 * changed, change the other.
 *
 * Nothing fires while the user is typing in a field, otherwise `/` would be
 * unusable inside the jump-to input it is supposed to focus.
 */
export function useKeyboard(handlers: {
  onNext?: () => void;
  onPrev?: () => void;
  onFocusJump?: () => void;
  onSearch?: () => void;
  onEscape?: () => void;
}) {
  useEffect(() => {
    function isTyping(target: EventTarget | null): boolean {
      const el = target as HTMLElement | null;
      if (!el) return false;
      return (
        el.tagName === "INPUT" ||
        el.tagName === "TEXTAREA" ||
        el.tagName === "SELECT" ||
        el.isContentEditable
      );
    }

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        handlers.onEscape?.();
        return;
      }
      if (isTyping(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;

      // While a word is focused the arrows belong to the reading pane, which
      // traverses word by word. The pane also stops propagation, so this is a
      // second line of defence rather than the only one — if the two ever
      // disagree, hadith navigation must be the one that yields.
      const active = document.activeElement as HTMLElement | null;
      if (active?.hasAttribute("data-token")) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        handlers.onNext?.();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handlers.onPrev?.();
      } else if (e.key === "/") {
        e.preventDefault();
        handlers.onFocusJump?.();
      } else if (e.key === "s") {
        e.preventDefault();
        handlers.onSearch?.();
      }
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlers]);
}
