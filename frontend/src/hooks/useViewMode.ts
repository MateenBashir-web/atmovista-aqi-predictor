import { useEffect, useState } from "react";

export type ViewMode = "everyday" | "technical";

const STORAGE_KEY = "atmovista-view-mode";

function getInitialMode(): ViewMode {
  if (typeof window === "undefined") return "everyday";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "everyday" || stored === "technical") return stored;
  return "everyday";
}

export function useViewMode() {
  const [mode, setModeState] = useState<ViewMode>(getInitialMode);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const setMode = (next: ViewMode) => setModeState(next);

  return {
    mode,
    setMode,
    isEveryday: mode === "everyday",
    isTechnical: mode === "technical",
  };
}
