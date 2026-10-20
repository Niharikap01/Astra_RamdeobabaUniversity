# Verified handoff

- Workspace: NightWatch on Windows PowerShell; venv is .venv_checkScriptspython.exe.
- Full test command: .venv_checkScriptspython.exe -m pytest -q.
- Full suite result: 49 passed, 51 warnings in 44.33 s.
- Isolated modules passed: test_alerts.py (6), test_api.py (17), test_auth.py (14), test_fusion.py (2), test_honest_data_layer.py (7), test_prediction.py (1), test_twin.py (1), test_whatif.py (1).
- The reported >16 minute hang was not reproduced; no code-level culprit or fix was established.
- metrics.json reports pooled OOF ROC-AUC 0.7751 with patient-cluster 95% CI 0.7338-0.8155.
- The distinct 5-fold mean ROC-AUC is 0.8143 +/- 0.0283.
- Sparse daily: fold-mean dAUC +0.0035 +/- 0.0093; pooled dAUC +0.0040; pooled CI -0.0093 to +0.0166; not supported.
- Sparse 2-3/week: fold-mean dAUC +0.0186 +/- 0.0222; pooled dAUC +0.0360; pooled CI +0.0165 to +0.0579; suggestive, fold t-test p=0.168922.
- Sparse 1/week: fold-mean dAUC +0.0474 +/- 0.0386; pooled dAUC +0.0620; pooled CI +0.0292 to +0.0960; supported, fold t-test p=0.070174.
- README metrics block is generated from ml/artifacts/metrics.json and thresholds.json by scripts/update_readme_metrics.py.
- scripts/check_readme_links.py reports 1 relative link/image and 0 broken.
- data/README.md now lists the six data files observed by Get-ChildItem data -Recurse -File and states the circular-label limitation.
- README states CGM is not included and genetic markers are out of scope for this run.
- Docker validation, CI, dashboard build/screenshots, clean-clone smoke test, evaluation rerun and repository-wide credential audit were NOT RUN.
- No test-fix commit was made because the full suite and isolated files passed; the historical hang remains unexplained.
