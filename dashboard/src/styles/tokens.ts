/**
 * NightWatch Design Tokens: Nocturne Clinical Observatory
 * Central design tokens referenced by charts, components, and styling.
 */

export const TOKENS = {
  colors: {
    // Nocturne Dark Palette
    dark: {
      bgBase: "#0b0f19",
      bgSurface: "#111827",
      bgSurfaceElevated: "#1e293b",
      borderSubtle: "#1f293d",
      borderActive: "#334155",
      textPrimary: "#f8fafc",
      textSecondary: "#94a3b8",
      textMuted: "#64748b",
      
      // Clinical Risk Spectrum
      riskLow: "#10b981",       // Emergent Green < 35%
      riskModerate: "#f59e0b",  // Amber 35-64%
      riskHigh: "#ef4444",      // Clinical Crimson >= 65%

      // Physiological Layers
      circadianSleep: "#3b82f6",     // Sleep Architecture / Restorative
      circadianDeep: "#1d4ed8",      // Slow Wave Sleep
      circadianRem: "#60a5fa",       // REM Sleep
      circadianHrv: "#06b6d4",       // Autonomic RMSSD HRV / Cyan
      circadianBp: "#8b5cf6",        // Home BP Cuff Measurements / Purple
      circadianMed: "#ec4899",       // Medication Capsules / Pink
      circadianActivity: "#14b8a6",  // Physical Steps / Teal
      
      // Horizon Visuals
      observedBand: "#38bdf8",
      predictedBand: "#f59e0b",
      confidenceShade: "rgba(245, 158, 11, 0.14)",
      gridLines: "#1e293b",
    },

    // Clinical Companion Light Palette
    light: {
      bgBase: "#f8fafc",
      bgSurface: "#ffffff",
      bgSurfaceElevated: "#f1f5f9",
      borderSubtle: "#e2e8f0",
      borderActive: "#cbd5e1",
      textPrimary: "#0f172a",
      textSecondary: "#475569",
      textMuted: "#94a3b8",
      
      riskLow: "#059669",
      riskModerate: "#d97706",
      riskHigh: "#dc2626",

      circadianSleep: "#2563eb",
      circadianDeep: "#1e40af",
      circadianRem: "#3b82f6",
      circadianHrv: "#0891b2",
      circadianBp: "#7c3aed",
      circadianMed: "#db2777",
      circadianActivity: "#0d9488",
      
      observedBand: "#0284c7",
      predictedBand: "#d97706",
      confidenceShade: "rgba(217, 119, 6, 0.12)",
      gridLines: "#e2e8f0",
    },
  },

  typography: {
    fontSans: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSerif: "'Source Serif 4', Georgia, serif",
    fontMono: "'JetBrains Mono', monospace",
  },

  radii: {
    sm: "4px",
    md: "8px",
    lg: "12px",
    full: "9999px",
  },

  shadows: {
    panel: "0 4px 20px -2px rgba(0, 0, 0, 0.35)",
    glowLow: "0 0 12px rgba(16, 185, 129, 0.25)",
    glowModerate: "0 0 12px rgba(245, 158, 11, 0.25)",
    glowHigh: "0 0 16px rgba(239, 68, 68, 0.35)",
  },

  timing: {
    transitionFast: "150ms cubic-bezier(0.4, 0, 0.2, 1)",
    transitionNormal: "250ms cubic-bezier(0.4, 0, 0.2, 1)",
  },
} as const;

export type ThemeMode = "dark" | "light";

export function getThemeTokens(mode: ThemeMode) {
  return {
    ...TOKENS,
    current: TOKENS.colors[mode],
  };
}
