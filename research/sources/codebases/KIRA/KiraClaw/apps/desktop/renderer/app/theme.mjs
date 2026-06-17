const STORAGE_KEY = "kiraclaw-theme";

const THEMES = new Set(["red", "pubg"]);

const DEFAULT_LOGO = "../assets/krafton-horizontal-logo-black.svg";

const THEME_LOGOS = {
  red: DEFAULT_LOGO,
  pubg: "../assets/krafton-horizontal-logo-white.svg",
};

let currentTheme = "red";
let changeHandler = null;

function normalizeTheme(theme) {
  return THEMES.has(theme) ? theme : "red";
}

function applyLandingBrand(theme) {
  const logo = document.getElementById("landing-logo-image");
  if (logo) {
    logo.src = THEME_LOGOS[theme] || THEME_LOGOS.red;
  }
}

export function applyTheme(theme, { persist = true } = {}) {
  currentTheme = normalizeTheme(theme);
  document.documentElement.dataset.theme = currentTheme;

  const selector = document.getElementById("ui-theme");
  if (selector) {
    selector.value = currentTheme;
  }

  applyLandingBrand(currentTheme);

  if (persist) {
    window.localStorage.setItem(STORAGE_KEY, currentTheme);
  }

  changeHandler?.(currentTheme);
}

export function initTheme({ onChange } = {}) {
  changeHandler = onChange || null;
  const storedTheme = window.localStorage.getItem(STORAGE_KEY);
  currentTheme = normalizeTheme(storedTheme || "red");

  const selector = document.getElementById("ui-theme");
  if (selector) {
    selector.value = currentTheme;
    selector.addEventListener("change", () => {
      applyTheme(selector.value);
    });
  }

  applyTheme(currentTheme, { persist: false });
  return currentTheme;
}
