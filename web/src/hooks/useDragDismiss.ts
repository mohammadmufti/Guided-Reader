import { useEffect, useRef, useState } from "react";

/**
 * Pull-down-to-dismiss for the mobile word sheet.
 *
 * On a phone the panel is a bottom sheet (see the `<aside>` in Reader). The X
 * in its header was the only way out; this adds the gesture readers expect from
 * every other sheet on their phone — drag it down and let go.
 *
 * The sheet scrolls, and a tall Lane entry can be much taller than the sheet,
 * so the gesture must not steal every downward drag. It engages only when a
 * drag BEGINS at the top of the scroll (scrollTop 0) and its first move is
 * downward; anything else — an upward drag, or a downward one that starts
 * mid-content — is handed straight back to the browser to scroll as normal.
 * This is the same rule iOS and Android sheets use, and it is why the decision
 * is made once, on the first move, and then latched for the rest of the touch.
 *
 * Only armed below `lg`, where the panel is actually a sheet. On desktop it is
 * a static side column and there is nothing to drag, so the listeners are never
 * attached and `offset` stays 0.
 */

interface Options {
  /** Fired when the drag is released past the dismiss threshold. */
  onDismiss: () => void;
  /** Arm the gesture only while the sheet is open. */
  active: boolean;
}

// Pull further than this and release, and the sheet closes. Below it, the
// sheet springs back — the drag is read as a change of mind.
const DISMISS_PX = 120;

// Below Tailwind's `lg`, matching the `max-lg:` sheet styling in Reader.
const SHEET_QUERY = "(max-width: 1023px)";

export function useDragDismiss({ onDismiss, active }: Options) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [drag, setDrag] = useState({ offset: 0, dragging: false });

  // onDismiss is often an inline arrow (`() => onSelect(null, null)`), a fresh
  // function each render. Reading it through a ref keeps the effect's only
  // dependency `active`, so the listeners attach once per open rather than once
  // per render.
  const dismiss = useRef(onDismiss);
  dismiss.current = onDismiss;

  useEffect(() => {
    const el = ref.current;
    if (!el || !active) return;
    if (!window.matchMedia(SHEET_QUERY).matches) return;

    // Per-touch bookkeeping. Kept in a ref, not state: it changes many times a
    // frame and none of it should trigger a render — only the transform does.
    const g = { startY: 0, offset: 0, claimed: false, tracking: false };

    function onStart(e: TouchEvent) {
      const touch = e.touches[0];
      if (!touch || e.touches.length !== 1) return; // ignore pinch / multi-touch
      g.startY = touch.clientY;
      g.offset = 0;
      g.claimed = false;
      g.tracking = true;
    }

    function onMove(e: TouchEvent) {
      const touch = e.touches[0];
      if (!g.tracking || !touch) return;
      const dy = touch.clientY - g.startY;

      if (!g.claimed) {
        // First meaningful move decides who owns this touch. A dismiss-drag is
        // downward AND starts at the top of the scroll; otherwise yield.
        if (dy <= 0 || el!.scrollTop > 0) {
          g.tracking = false;
          return;
        }
        g.claimed = true;
        setDrag({ offset: 0, dragging: true });
      }

      // Ours now: follow the finger and stop the sheet from also scrolling.
      // (touchmove is registered non-passive so this preventDefault holds.)
      e.preventDefault();
      g.offset = Math.max(0, dy);
      setDrag({ offset: g.offset, dragging: true });
    }

    function onEnd() {
      if (g.claimed) {
        const shouldDismiss = g.offset >= DISMISS_PX;
        // Drop `dragging` so the spring-back (or the reset) animates.
        setDrag({ offset: 0, dragging: false });
        if (shouldDismiss) dismiss.current();
      }
      g.tracking = false;
      g.claimed = false;
      g.offset = 0;
    }

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", onEnd);
    el.addEventListener("touchcancel", onEnd);
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
  }, [active]);

  return { ref, offset: drag.offset, dragging: drag.dragging };
}
