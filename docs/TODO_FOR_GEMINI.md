# NightWatch: Prioritized Remaining Implementation Tasks

This file contains remaining unfinished production-readiness tasks in strict priority order.
Each block is a self-contained, ready-to-paste prompt (<=10 lines) with explicit acceptance checks.

---

### Task 1: JWT Authentication & Role-Based Access Control (RBAC)

```text
Implement JWT authentication and RBAC for NightWatch.
1. Add User model in backend/app/models.py (id, username, hashed_password, role, full_name).
2. Add auth router /api/auth/login and /api/auth/me using bcrypt and PyJWT/python-jose.
3. Protect patient REST endpoints and WebSocket /ws/twin/{id} with Depends(get_current_user).
4. Auto-populate acknowledged_by and note author from JWT clinician identity.
5. Seed default clinician user (dr_clinician/nightwatch2026) in backend/scripts/seed.py.
6. Add auth context & login modal in dashboard/src/, injecting Bearer token into api.ts.
7. Write backend/tests/test_auth.py validating login, invalid token 401, role permission, and WS auth.
Acceptance: pytest backend/tests/test_auth.py passes; dashboard prompts login, stores token, and loads twin.
```

---

### Task 2: Production Containerization & GitHub Actions CI

```text
Containerize NightWatch and set up GitHub Actions CI workflow.
1. Create backend/Dockerfile (Python 3.11-slim, install deps, run uvicorn on :8000).
2. Create dashboard/Dockerfile (multi-stage Node 20 build -> nginx alpine serving dist/ on :80).
3. Create nginx.conf routing /api/ and /ws/ to backend:8000 and static assets to frontend.
4. Create docker-compose.yml orchestrating backend and dashboard containers with shared volume.
5. Create .github/workflows/ci.yml running pytest on backend and npm run build on dashboard on push/PR.
Acceptance: docker compose up -d builds and runs; curl http://localhost:80/health returns 200; CI passes.
```

---

### Task 3: Comprehensive Clinical Documentation & Architecture Diagrams

```text
Author comprehensive clinical documentation, architecture diagrams, and hackathon presentation artifacts.
1. Update README.md: problem statement, clinical rationale, stack, setup guide, AI-assisted development disclosure.
2. Create docs/architecture.mmd with Mermaid diagram (Sensors -> Ingestion -> Feature Store -> Twin Service -> WS -> Dashboard).
3. Create docs/clinical_safety.md: honest limitations, decision support boundaries, false alert mitigation, synthetic priors.
4. Create docs/demo_script.md: 3-minute hackathon judge walkthrough (Patient NW-0001 triage, What-If simulation, alert snooze).
Acceptance: All 4 files written without placeholders; Mermaid diagram renders valid syntax; links in README work.
```

---

### Task 4: Clinical Daylight (Light) Theme Implementation

```text
Implement Clinical Daylight (light theme) for NightWatch dashboard while preserving dark mode default.
1. Wire theme toggle in NavigationRail to switch theme state between 'dark' and 'light'.
2. Map TOKENS.colors.light into CSS variables / Tailwind utility classes across all components.
3. Update EChart.tsx to apply light palette (bgSurface: #ffffff, text: #0f172a, borders: #e2e8f0) when theme is light.
4. Verify contrast ratios >= 4.5:1 for all clinical metrics, badges, and chart axes in light mode.
Acceptance: npm run build succeeds; clicking theme toggle in NavigationRail cleanly flips UI and charts to light mode.
```

---

### Task 5: Clean-Clone Automated Smoke Test Script

```text
Create an automated end-to-end smoke test script for fresh repository clones.
1. Write scripts/smoke_test.py executable on both Windows and Linux.
2. Tests: (a) fresh SQLite DB creation, (b) seed_database(20 patients), (c) backend startup probe on :8000,
   (d) GET /health, /api/patients, /api/patients/NW-0001/twin, /api/patients/NW-0001/readings-series,
   (e) POST /api/patients/NW-0001/whatif, (f) WebSocket connection probe, (g) dashboard build verification.
3. Output a clean summary table of passed checks and exit with code 0 on success.
Acceptance: python scripts/smoke_test.py executes on a clean temporary directory and passes 100% of probes.
```
