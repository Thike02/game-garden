import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  /** Built only while open, so hundreds of grid cells stay cheap. */
  content: () => ReactNode;
  children: ReactNode;
  className?: string;
  width?: number;
  /** Let a tap open the card on touch screens. Off when the tap already does something else. */
  tapToOpen?: boolean;
}

const GAP = 6;
const MARGIN = 8;

/**
 * Shows a small card next to its children on hover or keyboard focus.
 * Touch screens have no hover, so a tap toggles it instead.
 */
export function HoverCard({ content, children, className, width = 320, tapToOpen = true }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const show = () => ref.current && setRect(ref.current.getBoundingClientRect());
  const hide = () => setRect(null);

  useEffect(() => {
    if (!rect) return;
    // The card is fixed-positioned, so close it instead of letting it drift on scroll.
    window.addEventListener("scroll", hide, { passive: true, capture: true });
    // On touch screens, tapping anywhere else closes it.
    const outside = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) hide();
    };
    document.addEventListener("pointerdown", outside);
    return () => {
      window.removeEventListener("scroll", hide, { capture: true });
      document.removeEventListener("pointerdown", outside);
    };
  }, [rect]);

  let style: CSSProperties | undefined;
  if (rect) {
    const left = Math.min(Math.max(rect.left + rect.width / 2 - width / 2, MARGIN), window.innerWidth - width - MARGIN);
    const below = rect.bottom + GAP;
    const placeAbove = below > window.innerHeight * 0.6;
    style = placeAbove
      ? { left, width, bottom: window.innerHeight - rect.top + GAP }
      : { left, width, top: below };
  }

  return (
    <span
      ref={ref}
      className={className}
      tabIndex={0}
      // Pointer events say whether it was a mouse or a finger; mouse events don't on every browser.
      onPointerEnter={(e) => e.pointerType === "mouse" && show()}
      onPointerLeave={(e) => e.pointerType === "mouse" && hide()}
      onPointerUp={(e) => {
        if (e.pointerType === "mouse" || !tapToOpen) return;
        if (rect) hide();
        else show();
      }}
      // Keyboard only: taps also focus the element, and those are handled above.
      onFocus={(e) => e.currentTarget.matches(":focus-visible") && show()}
      onBlur={hide}
    >
      {children}
      {/* Rendered on <body> so it doesn't inherit the anchor's styles (e.g. dimmed locked rows). */}
      {rect &&
        createPortal(
          <div className="hover-card" role="tooltip" style={style}>
            {content()}
          </div>,
          document.body,
        )}
    </span>
  );
}
