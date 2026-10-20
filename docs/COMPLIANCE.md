# Compliance evidence

| Requirement | Evidence (file/command) | Status | Note |
|---|---|---|---|
| G1 Static/historical EHR, including genetic markers | backend/app/simulation/; docs/data_dictionary.md | PARTIAL | EHR source paths exist; genetic markers not verified/included in this run. |
| G2 Dynamic wearable/IoT streams | backend/app/simulation/wearable_simulator.py | PARTIAL | Simulator path exists; live correctness not revalidated here. |
| G3 Fusion model predicts next-24-hour BP event | ml/; ml/artifacts/metrics.json | PARTIAL | Model/evaluation paths exist; clinical validity is not established. |
| G4 Doctor-facing conceptual dashboard | dashboard/src/ | PARTIAL | Dashboard source exists; acceptance workflow not revalidated. |
| G5 Synthetic/open-source data only | README.md; data/ | PARTIAL | README states synthetic data; repository-wide privacy audit not run. |
| H1 Public repository and required name | git remote -v | MISSING | Public visibility/name not verified. |
| H2 README with project/team details | README.md | PARTIAL | README exists; team details and requested sections incomplete/unverified. |
| H3 Architecture diagram PDF | docs/architecture.pdf | MISSING | PDF absent. |
| H4 Presentation PDF/PPT | docs/NightWatch_presentation.pptx; docs/presentation_outline.md | MISSING | Both absent. |
| H5 20-25 minute demo video link | docs/demo_script.md | MISSING | Script/link absent. |
| H6 Open-source license | LICENSE | PARTIAL | License file exists; contents not reviewed. |
| H7 Synthetic-data statement | README.md | PARTIAL | Statement exists; no full content audit. |
| H8 Training and evaluation code | ml/; scripts/evaluate.ps1 | PARTIAL | Source paths exist; training/evaluation not rerun. |
| H9 Live sensor simulator | backend/app/simulation/ | PARTIAL | Source exists; live run not verified. |
| H10 Auto-updating twin | backend/app/routers/; dashboard/src/ | PARTIAL | Source paths exist; live update not verified. |
| H11 Risk dashboard, trends, alerts, explanations | dashboard/src/ | PARTIAL | Source exists; UI acceptance not checked. |
| H12 Working What-If | backend/app/routers/whatif.py; dashboard/src/ | PARTIAL | Source exists; behavior not revalidated. |
| H13 Sleep Fingerprint | dashboard/src/; backend/app/routers/ | PARTIAL | Source exists; behavior not revalidated. |
| H14 Clean docker compose up | docker-compose.yml | PARTIAL | Compose file exists; Docker command NOT RUN. |
| H15 No real data/credentials committed | data/; repository scan | MISSING | Full audit NOT RUN. |
| H16 CI workflow | .github/workflows/ci.yml | PARTIAL | Workflow exists; CI not run here. |
| A1 Pytest hang diagnosis | .venv_check/Scripts/python.exe -m pytest -q | PARTIAL | 49 passed in 44.33 s; hang not reproduced and root cause remains unknown. |
| A3 Sparse-BP statistics | ml/artifacts/metrics.json | PARTIAL | Corrected result fields present; report/model-card regeneration not revalidated. |
| E1 Clean-clone smoke test | git clone; backend health; dashboard build | MISSING | NOT RUN. |
