// Theme preference (light | dark) - a single store shared by every screen.
//
// Components subscribe through useTheme() (useSyncExternalStore), so the
// landing page, the login screen and the console header can all render a
// toggle and stay in sync - no per-button DOM binding to leak or go stale
// when a screen unmounts and remounts (the old bindThemeButton() silently
// stopped working after a sign-out / sign-in cycle for exactly that reason).
//
// The <html data-theme> attribute is also set by the inline script in
// index.html before first paint, so there is no flash of the wrong theme.
import { useSyncExternalStore } from "react";

const THEME_KEY = "vajra-theme";

const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn());

function readStored() {
  try { return localStorage.getItem(THEME_KEY); } catch { return null; }
}
function writeStored(value) {
  try { localStorage.setItem(THEME_KEY, value); } catch { /* storage blocked - keep in memory */ }
}
function systemTheme() {
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  catch { return "light"; }
}

let theme = readStored() === "dark" ? "dark" : readStored() === "light" ? "light" : systemTheme();

function apply() {
  document.documentElement.setAttribute("data-theme", theme);
}
apply();

export function getTheme() { return theme; }
export function setTheme(next) {
  const t = next === "dark" ? "dark" : "light";
  if (t === theme) return;
  theme = t;
  writeStored(t);
  apply();
  emit();
}
export function toggleTheme() { setTheme(theme === "dark" ? "light" : "dark"); }

function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export const useTheme = () => useSyncExternalStore(subscribe, getTheme, () => "light");

// keep two open tabs in sync, and follow the OS setting until the user picks one
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === THEME_KEY && (e.newValue === "dark" || e.newValue === "light") && e.newValue !== theme) {
      theme = e.newValue; apply(); emit();
    }
  });
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
      if (readStored()) return; // an explicit choice always wins
      theme = e.matches ? "dark" : "light"; apply(); emit();
    });
  } catch { /* older browsers */ }
}
