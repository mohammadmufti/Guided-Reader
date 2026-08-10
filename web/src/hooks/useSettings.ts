import { useCallback, useEffect, useState } from "react";

export type ArStep = 1 | 2 | 3 | 4 | 5;
/** Size of the WORD PANEL's body text, independent of the matn's. */
export type PanelStep = 1 | 2 | 3 | 4 | 5;
export type Theme = "system" | "light" | "dark";
export type Face = "scheherazade" | "amiri" | "noto";

export const FACES: { id: Face; label: string; note: string }[] = [
  { id: "scheherazade", label: "شهرزاد", note: "Scheherazade New — the most open of the three" },
  { id: "amiri", label: "أميري", note: "Amiri — a Bulaq naskh, tighter set" },
  { id: "noto", label: "نوتو", note: "Noto Naskh — plainest, clearest on small screens" },
];

const KEY = "tajrid.settings.v1";

export interface Settings {
  step: ArStep;
  // Separate from `step`. The matn is set large to be read at a distance; the
  // panel is reference text, and a reader who needs a Lane entry bigger does
  // not necessarily want the hadith bigger too.
  panelStep: PanelStep;
  harakat: boolean;
  theme: Theme;
  face: Face;
}

const DEFAULTS: Settings = {
  step: 3,
  panelStep: 2,
  harakat: true,
  theme: "system",
  face: "scheherazade",
};

function read(): Settings {
  // Private-mode Safari throws on localStorage access rather than returning
  // null, and a reader should not get a blank page because of a storage
  // preference. Fall back to defaults and carry on.
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    const step = parsed.step;
    const ps = parsed.panelStep;
    const theme = parsed.theme;
    const face = parsed.face;
    return {
      face: face === "amiri" || face === "noto" || face === "scheherazade" ? face : "scheherazade",
      step: step === 1 || step === 2 || step === 3 || step === 4 || step === 5 ? step : 3,
      panelStep: ps === 1 || ps === 2 || ps === 3 || ps === 4 || ps === 5 ? ps : 2,
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
    document.documentElement.dataset["panelStep"] = String(settings.panelStep);
    document.documentElement.dataset["arFace"] = settings.face;
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
  // Clamped rather than wrapped: a reader pressing + repeatedly wants the
  // largest size, not a jump back to the smallest.
  const nudgePanel = useCallback(
    (by: 1 | -1) =>
      setSettings((s) => ({
        ...s,
        panelStep: Math.min(5, Math.max(1, s.panelStep + by)) as PanelStep,
      })),
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

  const cycleFace = useCallback(
    () =>
      setSettings((s) => {
        const at = FACES.findIndex((f) => f.id === s.face);
        return { ...s, face: FACES[(at + 1) % FACES.length]!.id };
      }),
    [],
  );

  return { ...settings, setStep, nudgePanel, toggleHarakat, cycleTheme, cycleFace };
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
