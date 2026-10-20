# Compliance evidence

| Requirement | Evidence (file/command) | Status | Note |
|---|---|---|---|
| G1 | backend/app/simulation/; docs/data_dictionary.md | PARTIAL | EHR paths present; genetic markers not included in this run. |
| G2 | backend/app/simulation/wearable_simulator.py | PARTIAL | Simulator source present; live sensor behavior not rechecked. |
| G3 | ml/; ml/artifacts/metrics.json | PARTIAL | Model/evaluation assets present; only synthetic data evidence. |
| G4 | dashboard/src/ | PARTIAL | Dashboard source present; UI acceptance not rechecked. |
| G5 | README.md; data/ | PARTIAL | Synthetic-data disclosure present; repository privacy audit not run. |
| H1 | git remote -v; public repository | MISSING | Public visibility and required repository name not verified. |
| H2 | README.md | PARTIAL | README present; requested sections/team details incomplete or unverified. |
| H3 | docs/architecture.pdf | MISSING | Required PDF absent. |
| H4 | docs/NightWatch_presentation.pptx; docs/presentation_outline.md | MISSING | Presentation deliverable absent. |
| H5 | docs/demo_script.md; video link | MISSING | Demo script and video link absent. |
| H6 | LICENSE | PARTIAL | License file present; contents not reviewed. |
| H7 | README.md | PARTIAL | Synthetic-data statement present; full audit not run. |
| H8 | ml/; scripts/evaluate.ps1 | PARTIAL | Code paths present; evaluation not rerun in this pass. |
| H9 | backend/app/simulation/ | PARTIAL | Simulator source present; live run not verified. |
| H10 | backend/app/routers/; dashboard/src/ | PARTIAL | Twin-related source paths present; live update not verified. |
| H11 | dashboard/src/ | PARTIAL | Dashboard source present; feature acceptance not rechecked. |
| H12 | backend/app/routers/whatif.py; dashboard/src/ | PARTIAL | What-If source paths present; behavior not rechecked. |
| H13 | dashboard/src/; backend/app/routers/ | PARTIAL | Sleep Fingerprint source paths present; behavior not rechecked. |
| H14 | docker-compose.yml; Dockerfiles | PARTIAL | Compose file presence only; Docker validation NOT RUN. |
| H15 | repository credential/privacy audit | MISSING | Repository-wide scan NOT RUN. |
| H16 | .github/workflows/ci.yml | PARTIAL | Workflow present; CI NOT RUN. |
| A1 | .venv_check/Scripts/python.exe -m pytest -q | MET | Full suite: 49 passed in 33.11 s outside the sandbox. In-sandbox TestClient stalls at Windows socketpair accept. |
| A2 | auth, API, UI role controls | PARTIAL | Alert reasons required, actors use token identity, and missing coverage/risk deltas/authors remain null. Full role audit remains incomplete; see backend/app/routers/predictions.py, patients.py, and dashboard/src/App.tsx. |
| A3 | ml/artifacts/metrics.json; docs/evaluation_report.md; docs/model_card.md | PARTIAL | Metrics JSON has corrected sparse fields; report/model-card agreement not checked. |
| B1 | Risk Horizon API and dashboard | PARTIAL | Presence only; behavior not checked. |
| B2 | What-If API and docs/whatif_effects.md | PARTIAL | Presence only; behavior not checked. |
| B3 | backend/app/simulation/ | PARTIAL | Presence only; tick behavior not checked. |
| B4 | data/README.md; backend/app/routers/ | PARTIAL | Data file list and circular-label note refreshed; WebSocket ticket and final-day label not checked. |
| C1-C8 | dashboard/src/ | PARTIAL | Dashboard source present; requirements not verified. |
| D1 | synthetic genetic markers | MISSING | Intentionally skipped by budget gate; genetic markers out of scope. |
| D2 | README.md CGM statement | MET | README explicitly says CGM not included and explains why. |
| D3 | README.md; scripts/update_readme_metrics.py | PARTIAL | Metrics block generated; remaining requested sections/generators incomplete. |
| D4 | docker-compose.yml; Dockerfiles; .github/workflows/ci.yml | PARTIAL | Files present; Docker config and CI NOT RUN. |
| D5 | docs/data_dictionary.md; clinical_safety; presentation | PARTIAL | Data dictionary exists; safety/demo/presentation deliverables absent or unverified. |
| E0 | scripts/update_readme_metrics.py; scripts/check_readme_links.py | PARTIAL | README metrics generated; local link check reports 1 link/image and 0 broken; API/env/tree generators absent. |
| E1 | clean clone, install, health, login, dashboard build | MISSING | NOT RUN. |
| E2 | docs/COMPLIANCE.md; docs/HANDOFF.md; docs/TODO.md | PARTIAL | Evidence ledger/handoff/TODO present; bounded by this run. |
