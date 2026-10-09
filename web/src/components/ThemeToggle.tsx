import { useEffect, useState } from "react";

type Theme = "system" | "dark" | "light";
const KEY = "game-garden-theme";
const NEXT: Record<Theme, Theme> = { system: "dark", dark: "light", light: "system" };
const LABEL: Record<Theme, string> = { system: "🖥️ 自動", dark: "🌙 ダーク", light: "☀️ ライト" };

function stored(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "dark" || value === "light" ? value : "system";
  } catch {
    return "system";
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(stored);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      if (theme === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, theme);
    } catch {
      // storage may be unavailable (private mode); the theme still applies for this visit
    }
  }, [theme]);

  return (
    <button className="theme-toggle small" onClick={() => setTheme(NEXT[theme])} title="配色を切り替え">
      {LABEL[theme]}
    </button>
  );
}
