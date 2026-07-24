/**
 * JillaSpotlight — dims everything except the target element.
 *
 * Uses clip-path polygon to cut a "window" in a dark overlay,
 * then positions a TeachingCard adjacent to the cutout with an SVG arrow.
 */
import { useEffect, useRef, useState } from "react";
import TeachingCard from "./TeachingCard";

interface SpotlightStep {
  target: string;           // CSS selector for the element to spotlight
  type: "concept" | "action" | "result" | "flow";
  title: string;
  body: string;
  code?: string;
  diagram?: React.ReactNode;
  waitFor?: string;         // sim event to wait for before auto-advancing
  deepenLabel?: string;
  onDeepen?: () => void;
}

interface Props {
  steps: SpotlightStep[];
  currentStep: number;
  onNext: () => void;
  onDismiss: () => void;
  total?: number;
}

export default function JillaSpotlight({ steps, currentStep, onNext, onDismiss, total }: Props) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const step = steps[currentStep];
  if (!step) return null;

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    const el = document.querySelector(step.target);
    if (el) {
      const r = el.getBoundingClientRect();
      setRect(r);
      // Observe resize
      const ro = new ResizeObserver(() => setRect(el.getBoundingClientRect()));
      ro.observe(el);
      return () => ro.disconnect();
    }
    setRect(null);
  }, [step.target, currentStep]);

  // Escape to dismiss
  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onDismiss(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onDismiss]);

  const pad = 8;
  const clipPath = rect
    ? `polygon(
        0% 0%, 0% 100%, 100% 100%, 100% 0%,
        ${rect.left - pad}px ${rect.top - pad}px,
        ${rect.right + pad}px ${rect.top - pad}px,
        ${rect.right + pad}px ${rect.bottom + pad}px,
        ${rect.left - pad}px ${rect.bottom + pad}px,
        ${rect.left - pad}px ${rect.top - pad}px,
        0% 0%
      )`
    : undefined;

  // Position card: to the right of cutout if space, else below
  const cardStyle: React.CSSProperties = rect ? {
    position: "fixed",
    zIndex: 9600,
    ...(rect.right + 400 < window.innerWidth
      ? { left: rect.right + pad + 16, top: Math.max(20, rect.top) }
      : { left: Math.max(20, rect.left), top: rect.bottom + pad + 16 }),
  } : { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 9600 };

  // Arrow from card edge to cutout edge
  const arrowSvg = rect ? (() => {
    const cardLeft = rect.right + pad + 16;
    const cardTop = Math.max(20, rect.top) + 30;
    const cutoutRight = rect.right + pad;
    const cutoutMidY = rect.top + rect.height / 2;

    if (cardLeft + 400 < window.innerWidth) {
      return (
        <svg style={{ position: "fixed", inset: 0, zIndex: 9550, pointerEvents: "none" }}
          width="100%" height="100%">
          <line x1={cutoutRight + 4} y1={cutoutMidY} x2={cardLeft - 4} y2={cardTop}
            stroke="var(--gc-primary)" strokeWidth="2" strokeDasharray="6 3"
            style={{ animation: "arrowDraw 0.6s ease forwards" }} />
          <circle cx={cutoutRight + 4} cy={cutoutMidY} r="4" fill="var(--gc-primary)" />
        </svg>
      );
    }
    return null;
  })() : null;

  return (
    <>
      {/* Overlay with cutout */}
      <div ref={overlayRef} onClick={e => { if (e.target === overlayRef.current) onDismiss(); }}
        style={{
          position: "fixed", inset: 0, zIndex: 9400,
          background: "rgba(0,0,0,0.55)", clipPath,
          transition: "clip-path 0.4s ease",
          cursor: "pointer",
        }} />

      {/* Highlight ring around target */}
      {rect && (
        <div style={{
          position: "fixed", zIndex: 9450, pointerEvents: "none",
          left: rect.left - pad - 2, top: rect.top - pad - 2,
          width: rect.width + pad * 2 + 4, height: rect.height + pad * 2 + 4,
          borderRadius: 12, border: "2px solid var(--gc-primary)",
          boxShadow: "0 0 20px 4px rgba(73,2,162,0.3)",
          animation: "jillaRing 1.5s ease infinite",
        }} />
      )}

      {/* Arrow */}
      {arrowSvg}

      {/* Teaching card */}
      <div style={cardStyle}>
        <TeachingCard
          type={step.type}
          title={step.title}
          body={step.body}
          code={step.code}
          diagram={step.diagram}
          step={total ? { current: currentStep + 1, total } : undefined}
          onNext={onNext}
          onDismiss={onDismiss}
          onDeepen={step.onDeepen}
          deepenLabel={step.deepenLabel}
        />
      </div>
    </>
  );
}
