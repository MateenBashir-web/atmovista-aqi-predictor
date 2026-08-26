import { useEffect, useRef, useState } from "react";

type Options = {
  duration?: number;
  decimals?: number;
  enabled?: boolean;
};

export function useAnimatedNumber(
  target: number | null | undefined,
  { duration = 700, decimals = 0, enabled = true }: Options = {},
) {
  const currentRef = useRef(0);
  const [display, setDisplay] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (frameRef.current != null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    if (target == null || Number.isNaN(target)) return;

    if (!enabled) {
      currentRef.current = target;
      setDisplay(target);
      return;
    }

    const from = currentRef.current;
    const startAt = performance.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - startAt) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = from + (target - from) * eased;
      currentRef.current = next;
      setDisplay(next);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        currentRef.current = target;
        setDisplay(target);
        frameRef.current = null;
      }
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration, enabled]);

  if (target == null || Number.isNaN(target)) return "—";
  return decimals > 0 ? display.toFixed(decimals) : Math.round(display).toLocaleString();
}
