import { useCallback, useEffect, useState } from "react";

export type ArStep = 1 | 2 | 3 | 4 | 5;
export type Theme = "system" | "light" | "dark";

const KEY = "tajrid.settings.v1";

export interface Settings {
  step: ArStep;
  harakat: boolean;
  theme: Theme;
}

const DEFAULTS: Settings = { step: 3, harakat: true, theme: "system" };

function read(): Settings {
  // Private-mode Safari throws on localStorage access rather than returning
  // null, and a reader should not get a blank page because of a storage
  // preference. Fall back to defaults and carry on.
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    const step = parsed.step;
    const theme = parsed.theme;
    return {
      step: step === 1 || step === 2 || step === 3 || step === 4 || step === 5 ? step : 3,
      harakat: parsed.harakat !== false,
      theme: theme === "light" || theme === "dark" ? theme : "system",
    };
  } catch {
    return DEFAULTS;
  }
}

/**
 * Reading preferences. The size step is written to `data-ar-step` on <html>, so
 * the type scale lives in CSS where the leading can scale with it, rather than
 * being recomputed in JavaScript on every render.
 */
export function useSettings() {
  const [settings, setSettings] = useState<Settings>(read);

  useEffect(() => {
    document.documentElement.dataset["arStep"] = String(settings.step);
    // "system" removes the attribute entirely so the prefers-color-scheme media
    // query decides. That also means no flash: the correct palette is applied
    // by CSS before any JavaScript runs, which would not be true if the theme
    // were always resolved in JS.
    if (settings.theme === "system") {
      delete document.documentElement.dataset["theme"];
    } else {
      document.documentElement.dataset["theme"] = settings.theme;
    }
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
    } catch {
      /* storage unavailable — the session still works, it just will not persist */
    }
  }, [settings]);

  const setStep = useCallback(
    (step: ArStep) => setSettings((s) => ({ ...s, step })),
    [],
  );
  const toggleHarakat = useCallback(
    () => setSettings((s) => ({ ...s, harakat: !s.harakat })),
    [],
  );
  // Cycles system -> light -> dark -> system. Three states rather than two so
  // a reader can always get back to following the device.
  const cycleTheme = useCallback(
    () =>
      setSettings((s) => ({
        ...s,
        theme: s.theme === "system" ? "light" : s.theme === "light" ? "dark" : "system",
      })),
    [],
  );

  return { ...settings, setStep, toggleHarakat, cycleTheme };
}

// Harakat, tanwin, shadda, sukun, superscript alef, tatweel — the same set the
// pipeline's normalise() strips, so hiding them here and normalising there
// cannot disagree about what a diacritic is.
const DIACRITICS =
  /[\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0670\u0640]/g;

/** Strip vowel marks for the self-testing mode. */
export function stripHarakat(text: string): string {
  return text.replace(DIACRITICS, "");
}
