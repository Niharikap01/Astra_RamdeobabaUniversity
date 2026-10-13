# NightWatch UI/UX Specification: "Nocturne Clinical Observatory"

**Status:** Binding Design Specification  
**Version:** 1.0.0  
**Design Persona:** Specialized Clinician Decision Support (Cardiology / Hypertension Specialist / Sleep Medicine)

---

## 1. Visual Identity & Aesthetic Principles

The "Nocturne Clinical Observatory" is engineered for high-cognition clinical environments. It replaces generic dashboard widgets with a specialized circadian monitoring station.

### Core Philosophy
1. **Calm, High-Contrast Circadian Theme**: Deep slate-indigo tones evoke nocturnal monitoring without blinding glare in dim hospital reading rooms or clinic workspaces.
2. **Strict Typography Hierarchy**:
   - **Inter**: Crisp, neutral grotesque for UI controls, metrics, badges, and tabular data (`font-feature-settings: 'tnum' 1`).
   - **Source Serif 4**: Editorial, authoritative serif for clinical narratives, diagnostic rationale, and summary headlines.
   - **JetBrains Mono**: Clean monospace for sensor timestamps, device telemetry IDs, and confidence intervals.
3. **No Decorative Noise**: Zero neon glows, zero continuous bouncing animations, zero speedometer gauges. Motion is reserved for state transitions and live incoming telemetry pulses.
4. **Trust & Safety Language**:
   - All risk projections are framed as *associations and probabilistic estimates* ("associated with", never "caused by").
   - Persistent disclaimer visible across all viewports:
     *"NightWatch is a research prototype for clinical decision support. It does not diagnose hypertension, replace validated BP measurement, prescribe medication, or provide autonomous treatment recommendations. All data is synthetic or simulated."*

---

## 2. Color Palette & Token Architecture

All design tokens are defined in `src/styles/tokens.ts` and mirrored in Tailwind theme extension:

| Token Name | Hex Code (Dark) | Hex Code (Light) | Semantic Role |
| :--- | :--- | :--- | :--- |
| `obs-bg-base` | `#0b0f19` | `#f8fafc` | Primary canvas background |
| `obs-bg-surface` | `#111827` | `#ffffff` | Panel and card surface |
| `obs-bg-surface-elevated` | `#1f293d` | `#f1f5f9` | Hover states, modals, elevated controls |
| `obs-border-subtle` | `#1e293b` | `#e2e8f0` | Dividers and card borders |
| `obs-border-active` | `#334155` | `#cbd5e1` | Selected tabs, focused borders |
| `obs-text-primary` | `#f8fafc` | `#0f172a` | High-contrast data values, headings |
| `obs-text-secondary` | `#94a3b8` | `#475569` | Clinical labels, supporting copy |
| `obs-text-muted` | `#64748b` | `#94a3b8` | Metadata timestamps, units |
| `risk-low` | `#10b981` | `#059669` | Low risk tier (< 35%) |
| `risk-moderate` | `#f59e0b` | `#d97706` | Moderate risk tier (35% - 64%) |
| `risk-high` | `#ef4444` | `#dc2626` | High risk tier (≥ 65%) |
| `circadian-sleep` | `#3b82f6` | `#2563eb` | Sleep architecture, REM/Deep blocks |
| `circadian-hrv` | `#06b6d4` | `#0891b2` | Parasympathetic autonomic tone (RMSSD) |
| `circadian-bp` | `#8b5cf6` | `#7c3aed` | Home BP cuff measurements |
| `circadian-med` | `#ec4899` | `#db2777` | Antihypertensive medication timing |

---

## 3. Structural Layout: Tri-Pane Clinical Workspace

The observatory uses a cohesive 3-column architecture on desktop ($W \ge 1280\text{px}$):
1. **Left Navigation Rail (72px / 260px expanded)**:
   - Cohort switcher & patient search
   - Active patient thumbnail and archetype chip
   - Digital Twin readiness indicator (Green live pulse / Amber re-sync)
   - Simulation engine controls (Start / Stop / Speed / Inject Scenario)
   - Theme toggle (Nocturne Dark / Clinical Light)
2. **Center Clinical Workspace (Fluid)**:
   - **Header Bar**: Patient identity, sex, age, BMI, archetype, 30-day baseline overview, twin status, and last reading sync.
   - **Signature Risk Horizon**: 24-hour synchronized trajectory (Observed 12h + Predicted 12h) with shaded confidence bands, sleep backdrop, cuff diamonds, and med capsules.
   - **Executive Risk Assessment**: Calibrated 0–100 probability dial, risk band badge, and plain-language pathophysiological rationale.
   - **Modular Workspace Tabs**:
     - *Overview & Twin*: Hemodynamic and autonomic delta from 30d baseline, blood pressure tracking.
     - *Circadian Waves*: Stacked, synchronized Sleep, HRV, and Resting HR time-series with crosshair scrub.
     - *Clinical Rationale*: "Why Risk Changed" signed factor waterfall (zero SHAP jargon).
     - *What-If Simulator*: Interactive counterfactual scenario testing with side-by-side delta.
     - *Sleep Fingerprint*: 6-axis autonomic radar deviation overlay.
     - *Data Logs & Actions*: Document clinical notes, request cuff recheck, and export tabular data.
3. **Right Alert & Triage Drawer (360px)**:
   - Categorized alert feed:
     - **Review Now** (High Risk $\ge 65\%$ requiring immediate attention)
     - **Review Today** (Moderate Risk with sleep debt or missed dose)
     - **Monitor** (Stable / Normotensive maintenance)
   - One-click clinician actions:
     - *Acknowledge with Clinical Note*
     - *Mark False Positive with Audit Reason*
     - *Dispatch Home BP Recheck Request*
